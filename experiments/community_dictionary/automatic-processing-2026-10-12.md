# Automatic processing increment — 12 October 2026

## Human evidence and scope

Manny reports successful AWS deployment of the reliability repair and conversion
of the 150-entry Swedish dictionary to Japanese, with publicly available versions
in six languages. He also supplies a successful production queue probe: local
fallback, cleanup version 1, 20/20 SELECT probes, peak two active bodies, zero task
connections left open. The prior installation document's requirement for real
Django Q was incorrect and is now replaced by that behaviour-based probe.

Manny requests an optional fully automatic route for both batch picture
description and language conversion. He expects some users to accept a useful
first result and rely on later correction. Broader cleanup UX is explicitly
deferred until somebody can play the reviewer role and provide feedback.

## Prepared implementation

The owner selects automatic processing, approves a combined estimate, and can
leave while sentences, vocabulary links, shared word pages and recordings are
published. The existing review-by-stage route remains available. Workflow
suggestion estimates can be upgraded to the combined automatic estimate without
starting either job. An automatic vocabulary-only option covers already accepted
sentences.

Publication authorisation is recorded separately from linguistic review. Member
and public entry pages identify automatically published text; existing human
language checks take precedence for the exact current text/translation. Contributor
authorship, dependency withdrawal and human edit protections are reused.

One approved allowance includes the continuation. Root settlement and child
reservation are atomic and bounded by the original vocabulary pot. Individual
budget pauses still require an explicit top-up; no larger debit is silently
approved. Cancellation stops the child and preserves saved content. Partial
failure retry retains successful wording/vocabulary/audio. An unchanged flagged
sentence is not treated as reviewed by retrying it. Configuration/permission
changes can prevent continuation without discarding first-stage results/refunds.

## Verification

Baseline: `7eebb12` (origin/main when implementation started).
Linux, Python 3.12, Django, SQLite; all external generation calls mocked.

```text
manage.py check: no issues
manage.py makemigrations --check --dry-run: no changes detected
manage.py test community_dictionary projects.tests.test_admin_tools
  projects.tests.test_email_reset projects.tests.test_profile:
  654 tests, 245.121s, OK
manage.py test community_dictionary.tests.test_automatic:
  20 tests, 7.647s, OK (rerun after final recovery/label changes)
```

Focused cases include two images sharing vocabulary, sentence-first conversion,
once-only combined credit approval and zero audit warnings, insufficient balance,
manual-route compatibility, failed audio/vocabulary recovery, cancellation before
and after continuation, withdrawal during a request, intervening human edits,
already-reviewed sentences, public labels, owner-only approval, changed recipes
and budget exhaustion. The full suite also retains the existing scaling, public
access, participation and password-reset regressions.

No live paid calls were made for this increment. Tests do not establish model
accuracy, intelligibility of audio, actual provider cost or concurrent PostgreSQL
behaviour. No code was deployed or pushed from the implementation environment.
Small laptop and AWS acceptance, including a fresh credit audit, remain pending.
No new schema, static-file, environment, dependency or queue-mode changes.

## Next evidence

Try two or three pictures and a small automatic conversion; inspect sentence/word
consistency, recordings, attribution and automatic-publication labels. Then deploy
and repeat before a large run, recording original allowance and combined charges.
Keep remaining uncertain results visible and gather feedback before adding a
separate cleanup interface. This is automated content processing within a
human-operated project, not unattended software maintenance.
