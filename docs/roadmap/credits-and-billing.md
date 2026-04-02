# Roadmap: credits, billing, and API-cost governance

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

## Future capability

- **Online top-up payments** (e.g., PayPal/Stripe) once accounting, reconciliation, and dispute handling are stable.

## Data and audit requirements

- Immutable ledger entries for all balance-affecting events.
- Idempotency protection for retries/webhooks.
- Exportable audit reports for finance/ops review.

## Delivery phases

### Phase A
- Ledger model, visible balances, per-call charging, low-balance gate.
- Admin manual recharge and adjustment tools.

### Phase B
- User-provided API keys and policy controls per project/user.
- Transfer workflow with limits and abuse monitoring.

### Phase C
- External payment integration and reconciliation tooling.

## Success criteria

- Users can always see available credits before running costly actions.
- Metered calls are consistently billed and auditable.
- System safely blocks operations that exceed configured spending limits.
