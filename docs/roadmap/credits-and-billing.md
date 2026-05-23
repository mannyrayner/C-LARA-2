# Roadmap: credits, billing, and API-cost governance

Related issue: **ISSUE-0027** (`docs/issues/issues/ISSUE-0027.json`).

This roadmap defines a credit-based usage model for C-LARA-2 so AI/API spend is visible, controllable, and auditable.

## Goals

- Make per-user available balance always visible.
- Charge AI/API calls against that balance using consistent cost accounting.
- Block calls when balance is below a configured minimum threshold.
- Support both platform-managed credits and user-provided API keys.

## Core capabilities (first implementation target)

1. **Visible balance**
   - Show current balance in user-facing account/project contexts.
   - Show estimated cost before expensive operations where possible.

2. **Per-call accounting**
   - Record each metered call with model/provider, token usage, computed charge, and timestamp.
   - Deduct charge from user balance atomically with call completion record.

3. **Low-balance gate**
   - Enforce a policy threshold: if balance is too low, do not execute metered calls.
   - Return a clear message describing required top-up/admin action.

4. **User-provided API keys**
   - Allow users to register their own provider keys and opt to spend via personal accounts.
   - Keep key material encrypted and masked in UI/logs.

5. **Admin recharge controls**
   - Admin tools to add/subtract credits with reason codes and audit trail.

6. **User-to-user transfer (optional in phase 1/2)**
   - Controlled transfer workflow with confirmation and anti-abuse limits.

## First elaboration linked to ISSUE-0027

This roadmap now explicitly tracks two concrete capabilities requested from prior C-LARA usage:

1. **Credit transfer between users**
   - Sender must have positive available credit.
   - Transfer amount must be strictly positive (no zero/negative transfers).
   - Enforce atomic debit/credit ledger writes.
   - Require confirmation step and recipient identity check.
   - Add anti-abuse controls (rate limits, per-day caps, anomaly flagging).

2. **User-provided OpenAI API key billing (BYOK charging path)**
   - User registers API key securely (encrypted at rest, masked in UI/logs).
   - User can opt specific AI operations/projects into BYOK billing mode.
   - In BYOK mode, C-LARA-2 should charge provider usage to the user key rather than platform credits where supported.
   - Fail gracefully with clear fallback/error messaging when key is invalid, missing scope, or provider is unavailable.

Cross-reference: this section and ISSUE-0027 should stay synchronized as implementation details evolve.

## Future capability

- **Online top-up payments** (e.g., PayPal/Stripe) once accounting, reconciliation, and dispute handling are stable.

## Data and audit requirements

- Immutable ledger entries for all balance-affecting events.
- Idempotency protection for retries/webhooks.
- Exportable audit reports for finance/ops review.


## Why Phase C (PayPal/Stripe) is non-trivial

Online payments add work beyond a simple API integration:
- provider onboarding, compliance checks, and country/institution policy constraints;
- webhook reliability and idempotency (avoid double-crediting on retries);
- dispute/refund handling and reconciliation against the internal credit ledger;
- tax/VAT/GST and accounting reporting requirements;
- fraud controls (rate limits, suspicious transfer patterns, abuse lockouts).

Because of this, Phase C should be treated as a product + operations project, not just an engineering task.

## Teacher adoption strategy without forcing personal API keys

To address the concern that many teachers will not create their own API keys, use a hybrid model:

1. **Default: platform-managed credits**
   - Teachers can start immediately with institution- or admin-funded credits.
   - No provider account setup required for first use.

2. **Optional: bring-your-own-key (BYOK)**
   - Advanced users can connect personal keys for direct billing/control.
   - Keep this optional, not mandatory.

3. **Guided onboarding for users who do want BYOK**
   - In-product step-by-step setup checklist (where to click, what permissions to choose, test call button).
   - Key validation + clear error messages before saving.

4. **Institution-first rollout path**
   - Start with admin recharge workflows and internal budget controls.
   - Add external PayPal/Stripe top-up only after ledger/reconciliation/audit tooling is stable.

## Delivery phases

### Phase A
- Ledger model, visible balances, per-call charging, low-balance gate.
- Admin manual recharge and adjustment tools.

**Status (April 2026): initial implementation delivered.**

Implemented now:
- `CreditAccount` + immutable `CreditLedgerEntry` records.
- `AIUsageCharge` rows linked to user/project with token usage and computed USD charge.
- Compile gate when balance is below configured minimum.
- Admin Tools support manual credit adjustments.
- Project-level accumulated cost and request-type cost breakdown on project detail pages.
- Configurable model pricing table with DB-backed overrides.

### Phase A.1 (new): pricing source-of-truth governance

To reduce operational risk from stale or incorrect model prices:
- Keep a **managed pricing table** in the platform DB (`OpenAIModelPricing`) as runtime source-of-truth.
- Allow **AI-assisted provisional extraction** from official pricing page(s).
- Require/support **human review and manual correction** in Admin Tools.
- Track status + provenance for each model row:
  - `ai_parsed` vs `human_revised`,
  - source URL,
  - last synced timestamp,
  - last human review timestamp,
  - notes/evidence.
- Support scheduled refresh via management command (e.g. daily cron):
  - `python platform_server/manage.py sync_openai_pricing`

Operational expectation:
- AI-parsed updates are provisional.
- Admin can inspect source links and revise values before production use.
- If DB pricing rows are absent, system falls back to settings defaults.

### Phase B
- User-provided API keys and policy controls per project/user.
- Transfer workflow with limits and abuse monitoring.

### Phase C
- External payment integration and reconciliation tooling.

## Success criteria

- Users can always see available credits before running costly actions.
- Metered calls are consistently billed and auditable.
- System safely blocks operations that exceed configured spending limits.
