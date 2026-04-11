# Credits and billing operations

This guide documents the currently implemented billing workflow (Phase A + pricing governance baseline).

## What is implemented

- Per-user credit account balances.
- Immutable ledger entries for all credit adjustments and usage charges.
- OpenAI usage charge rows with model + token counts + computed USD cost.
- Compile gate when balance is below configured minimum.
- Admin Tools actions for:
  - manual credit adjustments,
  - AI-assisted pricing sync from source URL,
  - manual pricing review/override with provenance/status.
- Project detail cost visibility:
  - total cost (USD),
  - request-type breakdown (e.g. segmentation/image stages).

## Key settings

Configured in `platform_server/platform_server/settings.py`:

- `CREDITS_ENABLED`
- `CREDITS_MIN_BALANCE_USD`
- `OPENAI_TOKEN_PRICING_USD_PER_1M` (fallback pricing map)
- `OPENAI_PRICING_TRACKED_MODELS`
- `OPENAI_PRICING_AI_MODEL`

## Admin workflows

## 1) Manually recharge or deduct user credits

1. Log in as admin/staff user.
2. Open **Admin Tools** (`/admin-tools/`).
3. Under **Adjust user credits**, choose user, amount, and reason.
4. Submit.

Result:
- User balance updates immediately.
- Immutable ledger row is created with admin metadata.

## 2) Sync OpenAI pricing provisionally with AI

1. In **Admin Tools**, under **OpenAI pricing source of truth**, keep (or change) source URL.
2. Click **AI sync pricing from source**.

Result:
- Pricing rows are upserted as `ai_parsed`.
- Source URL and sync timestamp are stored.
- Notes may include model-extracted evidence.

## 3) Human-review pricing values

1. In **Manual pricing override/review**, fill model + input/output price values.
2. Submit.

Result:
- Row status is set to `human_revised`.
- Human review timestamp is updated.

## Scheduled sync (recommended)

Set up a daily job (cron/systemd/etc):

```bash
python platform_server/manage.py sync_openai_pricing
```

Optional flags:

```bash
python platform_server/manage.py sync_openai_pricing --source-url "https://developers.openai.com/api/docs/pricing" --ai-model "gpt-5"
```

## Notes on reliability

- AI sync is intended as a **provisional extractor**, not a blind authority.
- Human review remains available at all times.
- Runtime charging uses DB pricing rows when present, otherwise settings fallback values.
