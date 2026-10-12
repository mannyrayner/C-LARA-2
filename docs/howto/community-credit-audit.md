# Community Dictionaries: credit reservation investigation

> **Follow-up:** [Port reliability](community-port-reliability.md) introduces smaller new
> allowances, incremental refunds and an extended audit. The investigation below
> describes the earlier implementation and its original evidence.

12 October 2026. Baseline: `9fd3d9d695467c13264e447908d96ff749be5625`.

Manny reports that the AWS guidance performance and duplicate-card repairs work,
but sees unexpectedly large reserved-credit messages. No production account or
ledger has yet been inspected. This investigation must not be described as a
confirmed lost-credit incident or a completed AWS financial reconciliation.

## Findings in the code

* A workflow suggestion said **Credit reserved** even before approval. It is a
  read-only offer; the amount is not deducted until approval. The label now says
  **Credit needed to start**, and explicitly says nothing has been reserved for
  the suggestion.
* The job page displayed the original allowance under **credit reservation**
  even after settlement. It now distinguishes an unapproved estimate, an active
  hold, and zero still held after settlement. The original amount and final
  charge remain visible for reference.
* Vocabulary allowances are very conservative. Each sentence reserves analysis
  plus up to twelve words, each allowing pronunciation guidance and two
  one-minute recordings with a 12,000-byte speech-input proxy. The rough estimate
  instead assumes six short recordings. Neither calculation discounts expected
  word/audio reuse before the analysis has happened.
* For a short example sentence, no vocabulary context, and the repository's
  configured input/output prices of US$2/US$10 per million tokens, the current
  calculation gives **US$0.0661 estimated / US$0.8690 allowance per sentence**:
  **US$9.9150 / US$130.3500 for 150 sentences**. Context can increase these amounts.
  These are application calculations, not a fresh provider tariff check or the
  actual AWS quote. Database pricing overrides can differ.
* Approval takes one ledger debit under a database lock. Settlement returns the
  unused amount once and marks the job settled. A vocabulary job deliberately
  waits for all word review and queued/running audio; unreviewed suggestions can
  therefore keep the large allowance held even while no API request is running.
  Cancellation waits for in-flight requests; it is not an audit operation.
* `AIUsageCharge` rows for a batch record usage; the credit settlement happens
  through the reservation, rather than debiting each such row again. Unknown
  provider usage remains flagged. Recorded cost is not a provider invoice.

This patch corrects the two display defects and adds diagnosis. It does **not**
change quoted amounts, approval limits, ledger records, balances, settlement
timing, job states or review results. Existing jobs remain compatible. No schema,
static asset, dependency or environment change is required.

## Read-only production check

After installing, use the existing protected-environment helper:

```bash
clara_manage community_credit_audit --username 'YOUR_LOGIN_NAME'
```

Use the actual account login name, not its email address. This is an operator
management command, not a public endpoint. It reads a consistent, read-only
PostgreSQL transaction. It sends no AI requests and makes no corrections.

The report lists:

* Unapproved quote allowances (possibly expired, never held).
* Outstanding holds, settled charges and net batch ledger deduction.
* Each reserved job's stage, status, date, recorded usage, uncertain-cost count,
  item/audio status counts, initial debit and returned amount.
* Mismatched or duplicate reservation/refund records and orphan references.
* Whether the latest account ledger balance agrees with available credit.

It prints no dictionary names, texts, images, email addresses or API credentials.
It reports only the selected account. Refund arithmetic is reconciled to job
records, not independently to provider invoices or every other billing path.
The command does not fail on reconciliation warnings: these are evidence to
inspect, not permission to modify credit. A missing account name fails cleanly.

Send the output and, if possible, the exact screen wording that prompted the
question. Large **unapproved quote allowances** alone are not a debit. Large
**outstanding holds** with vocabulary `ready`/`unclear` items can be explained by
unfinished review. A mismatch needs investigation before a targeted correction.
Do not cancel wanted previews merely to diagnose credit, manually reset balances,
or delete old job/ledger rows.

## Next design decision

The allowance is disproportionate for ordinary short dictionary words. A later
change should use a realistic bounded budget and release unused completed work
promptly, while preserving the approved maximum, concurrency safety, idempotent
refunds, manual review and interrupted-call accounting. Releasing all credit at
analysis completion would be unsafe without separately funding the word audio
that acceptance starts. First reconcile the existing AWS holds; this patch does
not silently rewrite their financial contract.

## Verification

The focused 82-test SQLite suite passes (17.659 seconds); system checks and
`makemigrations --check --dry-run` pass. Tests cover free quotes, once-only approval, insufficient funds,
settlement/refunds, cancellation, review/audio lifecycles, wording in all three
financial states, and the audit's account isolation and read-only behavior.
Audit fixtures exercise absent credit accounts, missing refunds, duplicate refunds
and orphan ledger references. Provider and queue calls are mocked. The AWS
PostgreSQL audit output is still needed; no live provider calls were made.
