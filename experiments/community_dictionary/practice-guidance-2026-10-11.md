# Public practice and owner next steps — 11 October 2026

## Human evidence and request

Manny reports that the discovery, membership-request, Profile and About increment
works. The message does not identify laptop versus AWS; this is acceptance of the
workflow, not a new device matrix or explicit AWS migration report. Remote main
contains that increment at `7cb9a82fe3cf2e7aa54d383ffd80056fb452dc34`.

He requests anonymous practice without AI calls, proactive suggestions for AI
sentence/word generation with confirmation and a Settings opt-out, and prominent
top-level dictionary indicators for useful pending actions. This is a bounded UX
increment before the introductory paper and wider trials.

## Implemented

- Public Practice uses the accepted-only public projection and existing game
  algorithms, with six flashcard directions, choices/reveal, crosswords and word
  scrambles. Public-content policy, hiding and withdrawal remain authoritative.
- Owner cards link to one next step: membership requests, unflagged previews to
  review, running work, vocabulary from accepted sentences, or missing sentences.
  Ordinary contributors and visitors have no construction prompts.
- The generation panel discloses scope, estimate, payer, voice and credit
  reservation. Explicit POST approval is signed against the same read-only plan
  used by the existing batch/vocabulary quote functions. Changed input or pricing
  requires a new estimate; retries do not reserve or dispatch twice.
- Migration 0022 adds a default-on owner preference plus stale-submit revision.
  It does not enable AI/public access or change existing content.
- Existing batch/review/accept-all/cancel flows remain; words are a second stage
  after sentence review. Flagged sentence previews can wait while accepted
  sentences proceed to vocabulary. No new general retry/repair engine is added.

## Local verification

The environment is Linux, Python 3.12, Django 5.2.17, SQLite. New tests cover public
projection/privacy, all games, stale media, withdrawal and revocation; owner-only
suggestions, state progression, exact-cost confirmation, changed scope/payer/model,
insufficient credit, repeat/cancelled approval, CSRF and stale Settings forms.

The full app plus account-recovery/admin/profile suite passed: **591 tests in
126.123 seconds**. After a final flagged-review selection refinement, all **17
workflow-guidance tests** passed again (1.533 seconds). The language-port/public/
guidance focused suite also passed (42 tests).

`check` and `makemigrations --check --dry-run` pass. The pre-existing 93-test
batch/vocabulary/practice/public-browsing subset also passes. An initial full run
exposed one expected presentation assertion tied to the old review-button wording;
it was updated to check the new mixed-entry wording and the old fallback when
guidance is disabled. A new withdrawal test initially omitted its required revision
argument; the test was corrected. No application cleanup or migration error occurred.

The disposable Chromium rehearsal passes at 320, 390 and 1280px: owner card →
scope/cost → one-click approval → processing, preference off, anonymous six-mode
multiple-choice flashcards, crossword, scramble, and access revocation. There are
no JavaScript errors or horizontal page overflow. Representative phone screenshots
were inspected. Test pictures and audio are synthetic fixtures, not language-quality
evidence. The harness disables dispatch and provider creation; it sends no real
AI requests, mail or production changes. Its first run used an incorrect expected
URL in the test script; correcting the selector completed the rehearsal.

Reproduce the browser test with:

```bash
python experiments/community_dictionary/practice_guidance_browser_rehearsal.py /tmp/community-guidance-browser
```

Playwright/Chromium must be available; module/executable overrides match the other
repository browser rehearsals. The database and media are disposable.

## Limits and next step

The [runbook](../../docs/howto/community-practice-guidance-install.md) covers laptop
backup, apply/test/migrate and subsequent AWS deployment. This increment still
needs Manny's laptop and AWS/phone acceptance, including real provider/billing
behavior. Browser tests do not replace physical iPhone/Android testing. No
production PostgreSQL/load test or measured reduction in human effort is claimed.
The result is another supervised implementation, not autonomous operation.
