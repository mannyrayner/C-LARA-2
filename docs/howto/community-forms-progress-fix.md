# Sentence-form progress and audio diagnostics

This code-only follow-up to `f11730424ec12fa848b99d0586e6eb9ed5d1e40e` fixes the
sentence-form batch progress display. It needs no migration, dependency change,
schema preparation or new consent. It makes no changes to saved recordings or
the TTS generation strategy.

The previous headline showed the selected sentence total, which did not change
when Refresh was clicked. The page now separately counts forms saved, sentences
finished including their recordings, and ready/pending/failed/stopped recordings.
The recording denominator means jobs created so far; it grows as more sentences
are processed. Progress data uses two queries rather than revalidating every
word and form on a read-only page. Full revision and permission checks remain on
processing and retry approval.

On a sentence page, an editor can open **More options** below an inflected form
and read **Audio method** and any **English homographs detected**. These come
from that recording's saved synthesis report. Missing provenance is labelled
unknown; a guidance label is not a judgement that the pronunciation is correct.
Public browsing does not expose these diagnostic controls.

Carrier extraction remains the optional expression-audio regeneration pilot.
Ordinary sentence-form recordings use direct lexical speech, with enriched
guidance for detected English homographs. The preceding sentence-form note
incorrectly implied that carrier extraction was already the default for MWEs;
that statement is corrected. This follow-up does not silently change the
generation strategy, incur new API charges or regenerate existing audio.

## Supervised deployment

Both hosts have accepted `f11730424ec12fa848b99d0586e6eb9ed5d1e40e`.
Run a **new** Install Community Dictionaries on laptop workflow on **main**.
Do not rerun either schema-preparation helper. Open an existing forms run and
check the counters, then inspect the saved audio method for an affected form.
After laptop acceptance, run a **new** Accept laptop and deploy AWS workflow
using that successful laptop run.

For diagnosing pronunciation, collect the exact form, target language, intended
meaning, audio-method label and detected homographs for a few audible errors.
Detection failure and ineffective supplied guidance require different remedies.
No claim is made that carrier extraction would improve these isolated words.

## Verification

The focused form and pronunciation-guidance suites pass (39 tests). Coverage
includes refresh across text/audio states, failed and paused audio, bounded
progress-query count, private/changed-source hiding, audio provenance labels,
and the actual capture/backfill TTS adapter for the French inflection `pose`.
Only the provider is mocked in the adapter checks; they assert exact form,
language, contextual meaning and pronunciation-hint delivery, not audio quality.
