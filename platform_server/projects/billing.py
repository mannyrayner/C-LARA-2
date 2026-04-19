from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction

from django.db.models import F

from .models import AIUsageCharge, CreditAccount, CreditLedgerEntry, OpenAIModelPricing, Project


FOUR_DP = Decimal("0.0001")
SIX_DP = Decimal("0.000001")


def _quantize_4(value: Decimal) -> Decimal:
    return value.quantize(FOUR_DP, rounding=ROUND_HALF_UP)


def _quantize_6(value: Decimal) -> Decimal:
    return value.quantize(SIX_DP, rounding=ROUND_HALF_UP)


def credits_enabled() -> bool:
    return bool(getattr(settings, "CREDITS_ENABLED", True))


def minimum_compile_balance_usd() -> Decimal:
    raw = getattr(settings, "CREDITS_MIN_BALANCE_USD", "0.0000")
    return _quantize_4(Decimal(str(raw)))


def get_or_create_credit_account(user: Any) -> CreditAccount:
    account, _ = CreditAccount.objects.get_or_create(user=user)
    return account


def get_user_balance_usd(user: Any) -> Decimal:
    return get_or_create_credit_account(user).balance_usd


def has_minimum_balance_for_compile(user: Any) -> bool:
    if not credits_enabled():
        return True
    return get_user_balance_usd(user) >= minimum_compile_balance_usd()


@transaction.atomic
def apply_credit_delta(
    *,
    user: Any,
    amount_usd: Decimal,
    entry_type: str,
    description: str,
    metadata: dict[str, Any] | None = None,
) -> CreditLedgerEntry:
    account, _ = CreditAccount.objects.select_for_update().get_or_create(user=user)
    new_balance = _quantize_4(Decimal(account.balance_usd) + Decimal(amount_usd))
    account.balance_usd = new_balance
    account.save(update_fields=["balance_usd", "updated_at"])
    return CreditLedgerEntry.objects.create(
        user=user,
        entry_type=entry_type,
        amount_usd=_quantize_4(Decimal(amount_usd)),
        balance_after_usd=new_balance,
        description=description[:255],
        metadata=metadata or {},
    )


def _settings_openai_price_table() -> dict[str, dict[str, Decimal]]:
    raw = getattr(settings, "OPENAI_TOKEN_PRICING_USD_PER_1M", {})
    table: dict[str, dict[str, Decimal]] = {}
    for model_name, prices in raw.items():
        table[model_name] = {
            "input": Decimal(str((prices or {}).get("input", "0"))),
            "output": Decimal(str((prices or {}).get("output", "0"))),
        }
    return table


def _openai_price_table() -> dict[str, dict[str, Decimal]]:
    table = _settings_openai_price_table()
    db_rows = list(OpenAIModelPricing.objects.all())
    for row in db_rows:
        table[row.model_name] = {"input": Decimal(row.input_usd_per_1m), "output": Decimal(row.output_usd_per_1m)}
    return table


def estimate_openai_token_cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> Decimal:
    prices = _openai_price_table().get(model) or _openai_price_table().get("default")
    if not prices:
        return Decimal("0")
    total = (Decimal(prompt_tokens) * prices["input"] + Decimal(completion_tokens) * prices["output"]) / Decimal(
        1_000_000
    )
    return _quantize_6(total)


def openai_price_for_model(model: str) -> dict[str, Decimal]:
    prices = _openai_price_table().get(model) or _openai_price_table().get("default")
    if not prices:
        return {"input": Decimal("0"), "output": Decimal("0")}
    return {"input": Decimal(prices["input"]), "output": Decimal(prices["output"])}


def record_openai_usage_and_charge(
    *,
    user_id: int,
    project_id: int | None,
    model: str,
    operation: str,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    request_type: str = "",
) -> None:
    User = get_user_model()
    user = User.objects.filter(pk=user_id).first()
    if user is None:
        return
    project = Project.objects.filter(pk=project_id).first() if project_id else None

    cost = estimate_openai_token_cost_usd(model, prompt_tokens, completion_tokens)
    ledger_entry = None
    status = AIUsageCharge.STATUS_SKIPPED
    notes = "credits disabled"
    if credits_enabled():
        ledger_entry = apply_credit_delta(
            user=user,
            amount_usd=-cost,
            entry_type=CreditLedgerEntry.ENTRY_USAGE,
            description=f"OpenAI {operation} ({model})",
            metadata={
                "provider": "openai",
                "model": model,
                "operation": operation,
                "request_type": request_type,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "cost_usd": str(cost),
            },
        )
        status = AIUsageCharge.STATUS_CHARGED
        notes = ""

    AIUsageCharge.objects.create(
        user=user,
        project=project,
        provider=AIUsageCharge.PROVIDER_OPENAI,
        model=model,
        operation=operation,
        request_type=request_type or operation,
        prompt_tokens=max(0, int(prompt_tokens or 0)),
        completion_tokens=max(0, int(completion_tokens or 0)),
        total_tokens=max(0, int(total_tokens or 0)),
        cost_usd=cost,
        status=status,
        notes=notes,
        ledger_entry=ledger_entry,
    )
    if project is not None and status == AIUsageCharge.STATUS_CHARGED:
        Project.objects.filter(pk=project.pk).update(total_cost_usd=F("total_cost_usd") + cost)
