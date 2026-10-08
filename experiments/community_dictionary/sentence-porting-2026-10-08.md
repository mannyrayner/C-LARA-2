# Sentence dictionary language-port follow-up — 8 October 2026

## Human report

Manny reports that the image-copy follow-up worked extremely well and that his
Swedish dictionary now contains over 150 entries associating images with sentences.
He estimates accepting the AI suggestion unchanged in about 90% of cases. This is
self-reported acceptance, not an independently measured translation/recognition
accuracy rate. The environment and exact deployed SHA were not specified in this
message. A French/English port gave plausible progress feedback but appeared to
contain no entries.

## Diagnosis and bounded change

The inspected baseline selected only `entry_type='word'`; its screen explicitly
excluded sentence descriptions and sentence links. This is a confirmed compatibility
gap. The baseline also creates private previews before human review/save creates
entries, which can account for an empty destination. We did not inspect Manny's
production database or job, so do not claim to know how much each cause contributed.

The follow-up includes accepted sentences in quotes and processing, sends bounded
vocabulary context with the existing translation call, preserves entry type and
images, requests sentence speech and rebuilds sentence/word/image links as their
endpoints are reviewed. Speech version and expanded context/output are included
in the frozen estimate. Existing word snapshots/recipes are unchanged. Old ready
word results can be saved before an incremental estimate adds missing sentences.
No schema migration or paid repair script is needed.

The progress page and destination now distinguish private previews from saved
entries. Existing explicit approval, cost reservation, review, provenance,
withdrawal and human-edit protection remain in place. Source dictionaries are not
modified. Missing TTS permits saving text for later audio recovery.

## Verification

- 391 Community Dictionary Django tests pass on Linux/Python 3.12/Django 5.2.17.
  The previous baseline had 376. Fifteen new tests cover sentence-only sources,
  both review orders, incremental skipping and changed vocabulary, commenting-only
  ports preserving human recording/attribution, old word-only result recovery,
  edited sentence audio/alignment, source edits/withdrawal, private progress links,
  strict provider IDs/schema, sentence speech version and timeout handling.
- `manage.py check` passes; `makemigrations --check --dry-run` finds no changes;
  `git diff --check` passes. No migration or dependency is added.
- A disposable Chromium browser rehearsal creates a French version from synthetic
  Swedish sentence data, quotes/approves, follows the empty destination's review
  link, plays preview audio, saves all five results, checks sentence/vocabulary
  views and an unchanged incremental estimate. Layout checked at 320, 390 and
  1280 pixels with no horizontal overflow or JavaScript errors; screenshots
  inspected. Translation and TTS are mocked, using a synchronous test dispatcher.
  This is not a new concurrent-worker, physical-phone or live-provider trial.
- The initial new tests exposed an obsolete sentence revision on image links during
  incremental updates; reconciliation now advances those controlled links. Two
  withdrawal-test fixture mistakes (revision argument and dictionary ID) were
  corrected. Browser automation initially used an exact label without Django's
  trailing colon; the selector was corrected. These were local development findings,
  not production incident diagnoses.

The browser rehearsal is reproducible with the application's Python dependencies,
Playwright and Chromium:

```bash
python experiments/community_dictionary/sentence_port_browser_rehearsal.py /path/to/output
```

Set `COMMUNITY_PLAYWRIGHT_MODULE` and `COMMUNITY_CHROMIUM_PATH` if needed, following
`browser_rehearsal.py`. The script uses disposable data and never the production DB.

## Remaining acceptance

Test live French sentences, word choices and audio on a small dictionary before
recovering/updating the existing larger French version. Check counts and cost before
approval. Translation spans are fallible; editing the sentence keeps related word
links but clears exact alignment. This version ports the existing vocabulary rather
than extracting an independent destination vocabulary list. Saved historical word
picture copies are not rewritten. Large-dictionary timing, Windows, physical-phone
behaviour and deployment of this follow-up remain unverified.
