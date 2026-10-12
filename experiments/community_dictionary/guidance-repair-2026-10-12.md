# AWS follow-up: slow guidance and duplicate picture cards

Manny reports installation of main `dbeb9173d696a0f8574e95047dab61d3ef9a111e`
on AWS. The French update notice appeared and produced expected sentences,
recordings and vocabulary, but there were also image-only duplicate cards and
tens-of-seconds navigation delays, particularly on the top-level page. This
supersedes revision 67's pending deployment statement; it is mixed acceptance,
not evidence of a trouble-free release.

## Reproduction and repair

The code repeatedly performed source/destination snapshot and vocabulary checks
per entry while constructing guidance. A disposable fixture with 150 Swedish
sentences, their original image records, corresponding French sentences and
linked vocabulary reproduced **6,370 queries** on the home route with bulk reads
disabled. This comparison exercises the same selection rules and render; it is
not a production trace. Request-local bulk reads and reuse reduce the count to
**53**, with no cross-request or timed cache. The first five-sentence fixture
required 56 queries; the larger result has no query growth with sentence count.

During the full suite, local SQLite timings were 7.008 seconds for the original
read path, 0.130 seconds repaired and 0.131 seconds on another fresh request.
An earlier isolated run measured 6.287 versus 0.201 seconds. These show the
query problem and local improvement; network latency, PostgreSQL execution,
concurrent jobs and production volume still require Manny's AWS check.

The image-card rule previously recognised direct parent copies only. A fixture
with a blank image copy and a sentence copy sharing a grandparent reproduced the
duplicate. Presentation now follows recorded copy ancestry in batches. Different generated pictures sharing a style image
remain distinct. This correction applies to existing rows without deleting or
archiving them. All entries/direct pages retain originals; independent text,
notes, audio, manual links, requests, pending images and other pictures preserve
their own cards. The exact AWS duplicate rows were not inspected, so a remaining
case should be identified by the two entry URLs before considering further repair.

## Verification

- `check`, `makemigrations --check --dry-run`: passed; no schema changes.
- Initial guidance regressions: 35 passed in 8.741 seconds.
- Guidance/capture/public-browsing selection: 67 passed in 12.190 seconds.
- Full suite: **613 tests passed in 150.333 seconds**, including a 150-sentence
  query budget, matching bulk/fresh snapshots, fresh-request edits and a
  50-ready-sentence review check requiring **20 queries**.
- A subsequent extra regression checks distinct generated pictures that share
  a style. The final relevant suite reruns guidance, scaling, capture and public
  browsing after that guard: **72 tests passed in 21.795 seconds**. The complete
  installed suite now contains 614 tests. A trial requiring identical file paths
  broke two historical-capture tests: capture can save a resized JPEG under a
  new filename. The final guard instead distinguishes copy links from AI-style
  provenance and passes those existing regressions.
- Chromium at 320/390/1280px passed the existing linked-card/estimate/approval/
  progress/opt-out rehearsal. The fixture now uses `prepared_photo` correctly;
  the earlier `prepared_image` test argument had not actually attached the six
  new images. Providers and browser job dispatch remain disabled.

The tests use Python 3.12, Django 5.2.17 and SQLite. Simulated provider/mail errors
are expected. A review test first failed because its fixture omitted the frozen
source languages; correcting the fixture restored the intended current-preview
test. Existing authorization, signed approval, duplicate-charge and stale-save
tests continue to pass. No production operations, live API calls or email were
performed by the agent.

## Project implication

The previous small-fixture checks were insufficient for the actual dictionary
size and image-copy history. Keep a scaled cold-request query budget and realistic
media/provenance fixtures in the regression suite. Fast AI implementation has
not removed the need for deployment and real-use feedback; this incident adds
human testing/maintenance burden and is not evidence of unattended autonomy.

Apply the [code-only repair runbook](../../docs/howto/community-guidance-repair-install.md)
and record real AWS latency and the two-card outcome. No migration, collectstatic
or regeneration of paid language content is needed.
