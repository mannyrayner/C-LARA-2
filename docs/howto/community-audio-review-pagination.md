# Faster word-audio batches and lexical review downloads

This application-only update adds pagination to replacement-audio batches,
including Google word-audio conversion and homograph repair. It does not change
the synthesis method, voice selection, dictionary entries or recorded decisions.
Existing batches acquire the new presentation when reopened.

## Install and check

This release needs no new database migration, dependency or Google credential.
Use the prepared `current_release.json` in the private deployment-control
repository, with the existing **Install Community Dictionaries on laptop**
workflow on `main`. Keep the laptop runner open. The controller verifies the
expected installed commit and waits for active work to finish.

After a successful installation:

1. Open **Tools → Convert existing word audio to Google**, then an existing
   completed batch. Words/forms should appear alphabetically, 25 groups per page.
2. Try **Next**, **Previous** and the review filter. Overall recording counts
   should still describe the whole batch. Candidate playback, acceptance,
   rejection and restoration retain their existing checks.
3. Save an optional note. The page, filter and item anchor are retained after a
   decision or note. If a filtered list shrinks, the last available page is used.
4. Download **JSON** and **CSV**. Both cover the entire batch, irrespective of the
   displayed page/filter. Prefer JSON when sending data for lexical analysis.
5. An estimate initially shows counts and costs, with an optional **Inspect
   selected words** link. A running batch shows progress counts and controls,
   without a word list. Refresh reads the latest saved outcomes. Starting a new
   generation still requires the usual explicit billing approval.

Once the laptop check is satisfactory, use **Accept laptop and deploy AWS** on
`main`. Reopen the existing large batch on AWS and compare setup/refresh/review
responsiveness. No need to regenerate recordings to obtain a download.

## Download contents and interpretation

Owner-only JSON schema 1 contains:

- Dictionary and run identifiers, languages, selected voice, estimated/settled
  costs, generation totals and the count of omitted unavailable groups.
- One group per representative word/form recording, with every linked occurrence
  retained as a member. Stable contribution/entry IDs allow analysis without
  treating spelling alone as lexical identity.
- Member text and meaning; corresponding lemma, lemma meaning and entry ID;
  current sentence contexts, surface forms and sentence translations.
- Current audio identifiers, provider, voice and pronunciation-review flag.
- Candidate method, provider, model/voice, status, decision, estimated usage cost,
  failure category and accepted audio IDs; plus the owner's optional review note.

CSV is UTF-8 with a byte-order mark for spreadsheet compatibility. It has one row
per candidate × occurrence; `contexts_json` and `current_audio_json` retain nested
data in JSON cells. Formula-like text is escaped for spreadsheet use. JSON also
contains run metadata and omission totals even when no rows can be exported.

Acceptance/rejection records workflow decisions, not independent quality ratings.
Bulk acceptance is not pronunciation approval. Contexts and current audio are
read at export time, not necessarily as they were when the batch was created.
Changed or withdrawn material is omitted using the same checks as review; counts
for unavailable groups are retained without their text. Sources sharing one
job item are checked together, so a source change can hide other groups in that
item until a new estimate is made.

The files contain dictionary text and notes for the owner's analysis. They do
not include audio files, storage paths, credentials or raw provider responses.
Generating or downloading them does not call an AI service or change entries.

## Performance and limits

Progress refresh uses saved job JSON and does not revalidate every lexical source
or build hundreds of playback controls. Completed review sorts and paginates
before live validation, loading source data in batches for the displayed items.
Google quote preparation and approval also batch related-data reads; creation
uses bulk item/dependency inserts.

This first cut still reads the batch's saved JSON to calculate counts, filter and
sort. It is not constant-memory SQL pagination. Explicit whole-batch downloads
validate all exportable items and can take longer than a page. The acceptance and
restoration operations retain their existing per-item transaction checks.
Production latency should be checked on the large dictionaries after installation.
