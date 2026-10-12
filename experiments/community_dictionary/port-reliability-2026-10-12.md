# Port reliability: local verification, 12 October 2026

Baseline `3ed343a3b70565c686b836eadb5d0330c5df7f14`. Prepared patch; no AWS deployment
or new human acceptance is claimed. User evidence and implementation behavior are
summarized in [the guide](../../docs/howto/community-port-reliability.md).

## Reproduction and changes

The old `aligned_surface` implementation rejected `猫`, `ソファ` and `寝ています`
inside `猫がソファで寝ています。`, and `沙发` inside an unspaced Chinese sentence.
The revised validator accepts exact Han/kana spans and retains alphabetic boundaries.
An integration test translates a sentence into Japanese, creates its vocabulary,
edits/saves through the review form, and generates mocked audio for the shared words.

Regression tests also exercise wrong/unavailable language checks, review and bulk
acceptance exclusion, text-preserving audio pauses, separate missing-audio quotes,
current accepted wording, one-call recovery of only failed word audio, unchanged
original-job charges, stale/unauthorised requests, interrupted-call recovery, lower
quote bounds, insufficient funds, tampered and repeated top-up approval, cancellation,
per-item release while another sentence awaits review, final ledger reconciliation,
and legacy allowance compatibility. No linguistic accuracy score is inferred.

## Checks

Environment: Python 3.12, Django 5.2.17, SQLite on Linux. Provider and queue calls
are mocked; no paid calls or live credentials are used. PostgreSQL/RDS concurrency
and Windows audio-file behavior were not exercised in this run.

- Full suite: `python manage.py test community_dictionary projects.tests.test_admin_tools projects.tests.test_email_reset projects.tests.test_profile --noinput`: **634 tests, OK**, 170.979 seconds.
- Final focused reliability/audit suite: **20 tests, OK**.
- Final enqueue-contract test passes after allowing 240 seconds for translation, the added language check and up to two sentence recordings (previous limit: 180 seconds).
- `manage.py check`: no issues.
- `manage.py makemigrations --check --dry-run`: no changes detected.
- Migration 0023 is applied by the test database setup. It adds fields only.
- Global-workspace rendering/archive checks and Git patch whitespace/application checks pass.

The existing realistic-size guidance test still passes: 150 sentences require 53
queries at the top level (approximately 0.247 seconds in that fixture), versus 6370
in its simulated old path. These are local fixture measurements, not AWS timings.

No source content, existing account balances, historical charges or production
services were changed by this work. Existing approved jobs deliberately retain
old accounting. New-policy jobs must not be processed by pre-patch workers after
incremental refunds; stop all workers for deployment and follow the runbook's
rollback restriction. Review an actual new quote and rerun the AWS credit audit
before declaring the financial change accepted in production.
