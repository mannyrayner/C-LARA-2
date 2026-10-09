# AWS conversion acceptance and simpler reading pages — 9 October 2026

Manny reports the AWS conversion now completes and creates the French/English
dictionary. Clicking through it, content appears correct and word links agree
with the sentences. This is human-reported acceptance of a substantial resumed
job and supersedes the previous pending conversion-recovery status. It is not a
controlled linguistic evaluation or a sustained operational reliability study;
no new connection census was supplied with this report.

He requests a single vocabulary list, hiding completed-content controls and
pronunciation warnings behind Show more options, and explicitly agrees to the
same principle for word pages.

The prepared revision combines sentence/picture vocabulary by entry identity,
preserves distinct senses and existing media checks, and uses native collapsed
details for additional options. Missing-content actions, playable vocabulary and
problem reporting remain accessible. Permission checks and POST endpoints are
reused. Discussion has a separate expandable heading. Review/generation warnings
are unchanged; the content and connection-management code are not redesigned.

All 422 Community Dictionaries tests pass locally (Python 3.12, Django 5.2.17,
SQLite; approximately 86 seconds). Four new tests cover deduplication without merging senses, missing wording, completed
entry/word views, and stale TTS still exposing recording actions. The local browser
rehearsal uses a disposable database and generated fixture media; no community
content or paid provider calls are involved. Chromium checks at 320/390/1280px
verify combined word rows, audio playback and translations, native disclosure by
keyboard and pointer, hidden/revealed pronunciation warnings, missing/stale-content
actions, no horizontal overflow and no JavaScript errors. Sentence and word page
screenshots were inspected. No physical-phone or AWS test of this presentation
increment has yet been performed. Human acceptance remains pending.

See [installation and acceptance checks](../../docs/howto/community-entry-options.md).
