from __future__ import annotations

from .billing import credits_enabled, get_user_balance_usd


def credit_balance(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {"credits_enabled": credits_enabled(), "credit_balance_usd": None}
    return {
        "credits_enabled": credits_enabled(),
        "credit_balance_usd": get_user_balance_usd(user),
    }
