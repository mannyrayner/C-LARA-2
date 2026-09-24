# Iteration 1 — construction and discussion prototype

Date: 23 September 2026. Status: functional patch prepared; not deployed or
accepted on physical phones. This is one development session with multiple
implementation, test and repair passes, not a single model call.

## Input, baseline and authorship

Manny supplied successful bootstrap application, commit and push output and
had asked the assistant to continue with the agreed implementation. The source
brief is [version 0.4](../../docs/roadmap/community-dictionary.md).

- Repo: `mannyrayner/C-LARA-2`.
- Branch used by Manny: `feature/community-dictionary-prototype`.
- Exact patch base: `bc21188595bae9f2ee89c080243a76fdd4a960b1`.
- Delivered artifact: `community_dictionary_prototype_01.patch`. The resulting
  commit is to be supplied after Manny installs/checks in the patch. Its checksum
  is supplied at delivery; it cannot be embedded in the patch itself without a
  circular dependency.
- Preparation baseline: `82bb185181acf0fa01958a19a3187f6ee8492f4f`.
- Agent: assistant in this thread, using the Codex work environment. No delegated
  coding/review agent was used. Exact deployed model identifier, provider usage
  and cost are not independently exposed here; do not infer them from a model
  nickname. Preserve the conversation/tool trace for later accounting.
- Software and tests were assistant-written. Human work so far: scope discussion,
  bootstrap application/check-in/push, and the supplied trace. No human code repair
  or acceptance of this functional implementation has yet been reported.
- Total elapsed effort and cost were not measured. Preparation/specification and
  environment setup must be counted separately as well as this implementation.

## Implemented result and reuse

The app reuses accounts and Django hosting/static/database infrastructure. The
older picture dictionary is tied to compiled projects and required text, so it
is not reused as the contribution store. No old project models or views are changed.
The new app adds its own models/migration, routes, templates, JavaScript and tests.

Implemented: invitation-only dictionaries; owner/member/editor roles; camera/gallery
input; browser voice recording and file selection; optional written information;
spoken/written comments; named partnerships and request queues in both directions;
review and accepted-version restoration; separate media/author credits; protected
media with audio ranges; local drafts and idempotent submission receipts; removal;
owner export; setup/deployment/recovery instructions. Language and text-direction
metadata are stored. AI providers and practice activities are not invoked.

Twenty Django tests are explicitly added to CI, since root pytest discovers only
`tests/` and would miss this app. Pillow is the only new application dependency.
Browser rehearsal tooling is optional development tooling, outside runtime deps.

## Executed checks

Environment: Linux, Python 3.12, Django 5.2.17, Pillow 12.3.0, SQLite; Node 24.19.0
and Chromium 153.0.8010.0 for the browser rehearsal. CI remains configured for
Python 3.11; that separate environment was not run locally.

From `platform_server/`, using the isolated Python environment:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run community_dictionary
python manage.py test community_dictionary --verbosity 2
python manage.py test projects.tests.test_community_access projects.tests.test_picture_dictionary --verbosity 1
```

Results:

| Check | Result |
| --- | --- |
| New app workflows/access control | 20 passed |
| Schema/system checks | No issues; no missing migration |
| Existing community/picture-dictionary selection | 18 run; 16 passed, 2 failed |
| Same existing selection on clean pre-feature base | Same two failures |
| JavaScript syntax and Python compilation | Passed |
| Fresh local database migration | Passed |
| Two-account Chromium browser rehearsal | Passed |
| Global workspace validation and patch whitespace/application | Checked during packaging |

The existing failures are in
`projects.tests.test_picture_dictionary.PictureDictionaryCommandTests`:

1. `test_import_project_as_dictionary_copy_filters_untranslated_pages_and_supports_picture_glossing`:
   expected `Katze`/`Hund`, got `Frida`/`ist`.
2. `test_removing_word_keeps_page_variants_in_sync`: page-001/page-002 image-path
   mismatch after removing a word.

These reproduce before the new app, so they are reported as baseline defects.
Existing compile tests also log missing AI credentials; no credentials were added
to make this prototype work. The new app has no AI-client calls. This is a focused
regression selection, not a claim that the whole repository test suite passes.

The backend tests cover both contribution directions, spoken discussion/requests,
review progress, multiple replies, text-version conflicts, restoration, retry
receipts, rollback cleanup, membership revocation, third partners, owner-only
settings/export, cross-dictionary IDs, CSRF, escaping, invalid media, private root
configuration, range playback, file removal and fixture/media restoration.

## Browser evidence and repairs within this iteration

The normal Playwright browser download failed in this environment. A separately
installed `@sparticuz/chromium` development package supplied a working Chromium
binary; it is not an app dependency. Rehearsal used Playwright's iPhone 13 and
Pixel 7 viewport presets, both running **Chromium on Linux**, not Safari/Android
hardware, plus a desktop-width check. Microphone input was simulated.

The [browser probe](browser_workflow.cjs) and [isolated launcher](browser_rehearsal.py)
are retained for reproduction. With Playwright and its Chromium installed locally:

```bash
. .venv/bin/activate
python experiments/community_dictionary/browser_rehearsal.py
```

Set `COMMUNITY_PLAYWRIGHT_MODULE` to the absolute Playwright module path if Node
cannot resolve it. Set `COMMUNITY_CHROMIUM_PATH` to an alternate Chromium binary
if needed. The launcher creates a disposable database/private media tree and test
accounts; it refuses an occupied test-server port. Do not use those test accounts
on a deployed server. Output goes under `reports/community-browser/` by default.

Observed passes:

- choose a large synthetic photo, save a local draft, reload and restore the photo,
  consent and submission ID;
- allow the server to save a submission, deliberately discard its response, then
  retry successfully with the same receipt;
- ask a partnership for a recording; the second account records simulated audio,
  saves/reloads the audio draft and submits;
- add a Swedish comment; owner accepts the recording, completing the request;
- play the accepted audio; no uncaught JavaScript errors;
- no horizontal page overflow on the checked contribution, entry, queue and
  desktop browse pages; screenshots visually inspected.

Internal repairs included restoring form controls only after draft initialization,
guarding submission while the microphone starts, displaying partnership names in
the request selector, and clearing removed contribution content. Several browser
probe selectors were also corrected to the interface's actual button labels.
These are part of iteration 1, not hidden later iterations.

## Limits and next step

The working code is ready for installation and a small trial, not for a claim
that all acceptance criteria have passed. Still unverified: actual iPhone/Safari
and Android/Chrome camera/permission behavior; cross-device audio formats (no
transcoding); PostgreSQL and simultaneous-worker stress; production nginx/storage
configuration; full operator backup/restore; and usability/enjoyment without
coaching. Browser draft storage has documented limitations and is not full offline
support. Unicode/direction metadata is not evidence of broad script coverage.

Next: Manny installs and commits the patch, deploys using the [setup guide](../../docs/howto/community-dictionary.md),
and supplies one consolidated functional/phone report with commit and device
versions. A second implementation iteration should repair that evidence. AI media
generation and practice stay deferred. Swedish success would not establish
suitability for a particular Indigenous community or learning effectiveness.

The derived global workspace records this material progress and marks older August
urgency as historical. Human intentions and canonical issue state remain unchanged.
