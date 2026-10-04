# Language porting: first cut, 4 October 2026

## Human evidence and request

Manny reports the practice/multiple-choice update deployed and working on AWS.
No device/OS/browser or exact deployed SHA accompanies that report. He now asks for
the agreed language-porting workflow, with concurrent per-entry work and a rough
cost estimate, explicit approval and insufficient-credit feedback.

The agreed first experiment is Swedish/English → Italian/English, potentially
Icelandic/English for Kate/Axel. Either language may change independently. Existing
words, commenting-language text and visual context must jointly guide translation.
Merging and community discovery are later possibilities, not this implementation.

## Delivered scope

See [runbook](../../docs/howto/community-language-porting.md). Owner-only version
creation; source text plus representative picture; private reviewed results; named
TTS voice; language-independent copying; incremental source/destination fingerprints;
protection for review corrections and later edits; reusable matching audio.

Jobs use durable per-entry rows and the existing Django-Q adapter, a bounded fan-out
window and fan-in credit settlement. Estimates are free; approval atomically
reserves C-LARA funds where applicable. Personal API balance is explicitly unknown.
Failures have no automatic paid retry. Source provenance, multi-input withdrawal
holds and restoration extend the existing contribution model.

## Verification and corrections during development

- 243 app tests pass (28 new porting tests), including withdrawal while a request
  is in flight, multi-custodian restoration, credit caps/refunds, replay handling,
  changed source/destination, unchanged fields, preserved human corrections,
  shared-image word links and export reference metadata.
- Chromium 153, Linux, 390/320px: free estimate, explicit approval, background
  completion after leaving the page, image/audio preview, review/save and update
  skip. Eight fixture entries; two simulated provider calls overlap in two real
  Django-Q2 1.11.1 processes. The default threaded laptop adapter also passes with
  two overlapping fixture calls in one process. No browser script errors.
- Browser rehearsal caught task options incorrectly passed to the local Q shim;
  they now use the shared `q_options` argument. The real queue package was installed
  only in the verification environment, not added as an app requirement.
- The first image assertion ran before decoding; it now explicitly awaits image
  decoding. A damaged/partial cached Chromium binary was replaced by a fresh local
  extraction for the rehearsal. These were fixture/environment failures, not user
  acceptance results.
- PostgreSQL row locks explicitly target the primary row when nullable related
  dictionaries are joined. SQLite acquires its write lock before reading job state
  to avoid concurrent reader-to-writer upgrade failures. Actual PostgreSQL execution
  remains part of the subsequent AWS acceptance.

No paid provider call was made. Translation quality, real prices versus these
rough estimates, live Icelandic/Italian TTS and physical-phone ergonomics remain
human tests. This is an implementation result, not evidence of autonomous operation
or successful community uptake. The assembled baseline remains local, not a verified
remote/deployed commit.
