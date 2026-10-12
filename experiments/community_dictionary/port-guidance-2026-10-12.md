# Linked language-version guidance — 12 October 2026

## Human evidence and request

Manny reports successful AWS installation of the public-practice/owner-guidance
increment, followed by useful initial workflow testing. He completed six extra
Swedish pictures after the previous 144-image/sentence set but saw no suggestion
to update its existing French version. He explicitly requested this extension.
The deployed baseline is main `577343213cb603ee846057313bae0c1b4ba92721`.

The preceding collectstatic failure concerned write permission on generated
`staticfiles/community_dictionary/practice.js`. The supplied listing showed
`ssm-user:ssm-user` ownership, whereas `clara_manage` runs as `ubuntu:www-data`.
After the scoped static-root ownership/mode repair, Manny reported successful
installation. The prior runbook now records that repair. This is human-reported
AWS acceptance; the current agent did not inspect or operate that server.

## Prepared implementation

- Read-only incremental planning is shared with language-port quotes. Existing
  related dictionary cards/Browse pages offer new/changed accepted sentences,
  preserving locally edited destination entries and recordings.
- Explicit signed cost approval reuses the bounded queue and reservation/receipt
  mechanism. Reviewing the translated sentences precedes generating vocabulary
  from their accepted destination wording. No independent source-word translation
  occurs in a guided update.
- Existing owner and participation checks apply at both ends. Hidden versions,
  disabled destination guidance/AI and unsuitable TTS are excluded. Existing
  local tasks take priority; related progress/review/vocabulary gets a direct link.
- Browser rehearsal exposed an existing category-planning edge case: growing a
  category with fewer than five examples made old sentences appear changed.
  Established decisions now retain their original still-valid evidence when new
  examples are appended. Editing/removing that evidence still invalidates it.
- No schema, environment, dependency or static asset changes.

## Verification

Local Python 3.12 / Django 5.2.17 / SQLite, disposable fixtures and mocked providers:

- `check` and `makemigrations --check --dry-run`: passed; no model changes.
- Initial relevant regression selection: 93 tests passed in 30.844 seconds.
- Initial new guidance tests: 17 passed in 8.143 seconds.
- Full initial suite: 608 tests passed in 135.018 seconds.
- After the category refinement: 60 port/guidance tests passed in 15.928 seconds,
  including the added category-growth and stale-evidence regression.
- Final full suite: 609 tests passed in 131.816 seconds.

The combined suite covers `community_dictionary`, email recovery, admin tools
and profile tests. Failure-simulation log messages are expected. New cases include
six new sentences, new/changed counts and matched costs, no work on GET, protected
French edits/audio, review then destination vocabulary, stale approval/save,
duplicate tabs and billing, insufficient credit, permissions/withdrawal, CSRF,
expiry, opt-out, commenting-language-only updates and cancelled receipts.

The disposable Chromium rehearsal passed at 320/390/1280px: linked source and
destination cards, six-sentence scope/cost panel, approval from the source,
shared progress links and destination opt-out. No horizontal overflow or page
JavaScript errors; representative mobile screenshots were inspected. Browser
dispatch is deliberately disabled and any provider client construction fails.
The first attempts encountered a local Chromium extraction issue and then
exposed the category-growth issue above; the final rehearsal passed after both
were resolved.

Reproduce the browser check with Playwright/Chromium installed using
`port_guidance_browser_rehearsal.py OUTPUT_DIRECTORY`; optional
`COMMUNITY_PLAYWRIGHT_MODULE` and `COMMUNITY_CHROMIUM_MODULE` select those local
packages. All fixtures, media and server state are disposable.

No live provider requests, email, AWS changes, production PostgreSQL/load test
or physical-phone acceptance were performed for this extension. Manny's existing
positive AWS guidance report does not establish acceptance of this new code.
Follow the [runbook](../../docs/howto/community-port-guidance-install.md), then
record the real Swedish-to-French outcome before making deployment claims.
