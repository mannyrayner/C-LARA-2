# Picture-description allowance — 8 October 2026

## Human report and scope

Manny reports that missing audio is now correctly generated, accepting the
preceding recovery follow-up. Before systematic testing he requests a configurable
daily image-understanding limit under Settings, with a cost estimate and explicit
confirmation. The ten-request limit is in Picture descriptions; the older
single-object Learn from a photo tool has a different quota.

The prepared implementation adds an owner-controlled, shared dictionary allowance,
default ten per preceding 24 hours, with Preview daily cost → Confirm. Existing
usage, including failed/discarded attempts, survives changes. The estimate uses
configured model prices and an explicit associated-audio allowance, not a spending
guarantee. Existing per-request payer/billing rules remain in place. Migration 0016
adds only the allowance field. No paid requests or production changes were made.

GitHub main was observed at `3b7bcedd76b2e7fe7cf928e3b0be8a08264aa8a1`
(“Refresh repaired dictionary audio when returning to examples”). This is a remote
repository observation, not independent verification of the deployed server SHA.

## Verification

- Python 3.12, Django 5.2.17, SQLite: **349 app tests pass**, 72.840 seconds.
- The focused allowance/capture run: **35 tests pass**, 3.735 seconds. Eleven new
  allowance tests cover owner/access/CSRF checks, tampering and expiry, changed
  pricing/policy/ceiling, cancel/confirmation/replay, ordinary-settings bypass,
  rolling shared usage, per-account ceiling, request eleven after an increase,
  existing-preview publication after a reduction, local-only cost and balance
  warning, and new copies retaining the conservative default.
- `manage.py check` passes; `makemigrations --check --dry-run` reports no changes.
- Isolated Chromium rehearsal, synthetic records, mocked provider: start with ten
  used attempts; preview fifty; cancel without mutation; confirm fifty; show ten
  used and forty remaining; a member submits request eleven and reaches its preview.
  Cost-preview layouts checked at 390 and 1280 CSS pixels; owner Settings also
  checked at 390. No horizontal overflow or JavaScript errors; mobile screenshot
  visually inspected.

No live provider cost/pronunciation measurement, physical-phone test, AWS/PostgreSQL
concurrency rehearsal or human acceptance of this new allowance is claimed.
Pricing derives from local configuration and planning assumptions, not a newly
verified provider tariff. The server ceiling is operator-controlled; default 1000
is separate from the dictionary default ten.

## Next human check

Apply the additive migration on the laptop, preview and approve a higher allowance,
and check that existing usage is retained. A preview alone costs nothing. Then
deploy the same commit with a database backup and brief service interruption.
Systematic use with Cathy and further phone use remain the next useful UX evidence;
broader MWE work remains deferred.
