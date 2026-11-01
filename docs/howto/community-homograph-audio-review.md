# Review homograph audio

Dictionary owners can open **Tools → Review homograph audio** to listen to
accepted dictionary words and sentence forms whose spelling also occurs in
English. The page uses the existing spelling detector; it is a review aid, not a
complete inventory of pronunciation problems or a guarantee that a flagged word
is wrong.

## Listening and repair

1. Listen to each current recording alongside its word/form and translation.
   Sentence forms show their sentence; dictionary words show an available sentence
   example when one exists.
2. Choose **Keep** or **Needs regeneration**. Each choice saves immediately.
   Progress survives leaving the page. Text, meaning, language or audio changes
   invalidate the corresponding decision. Human recordings cannot be selected for
   automatic replacement.
3. Choose **Estimate regeneration of marked items** (up to 100 per batch).
   The estimate lists the selected items and states the payment source, estimated
   API cost and refundable C-LARA allowance. Insufficient C-LARA credit blocks
   approval. A personal OpenAI key's balance cannot be checked by the app.
4. Approve to generate private previews with the current enriched pronunciation
   guidance. Existing supported voices are preserved. No carrier phrases are
   used, and current dictionary audio remains available throughout generation.
5. When processing finishes, compare **Current dictionary audio** with **New
   preview**. **Use this recording** explicitly replaces the captured synthetic
   recordings. **Reject preview; keep current audio** leaves the item marked for
   another attempt. Failed attempts also remain marked; request a fresh estimate
   to try again. Do not assume regeneration corrected the pronunciation.

Jobs and previews remain accessible from the checklist. **Refresh progress**
reads fresh state. **Resume interrupted work** resumes unstarted tasks and, after
15 minutes, accounts for abandoned requests without repeating them. Completed
near-silent audio can be regenerated once by the ordinary TTS adapter. Network
errors have no automatic retry. Estimates are neither invoices nor hard provider
spending caps.

The checklist, playback routes, quotes and replacement actions are owner-only.
The ordinary public browsing and entry-editing permissions are unchanged. French
and Slovak interface translations are included; generation uses the dictionary's
text and explanation languages independently of the interface language.

## Integrity and custody

The saved review compares exact text/meaning and recording fingerprints. An edit,
withdrawal, new recording or loss of owner access makes stale previews unusable.
Replacement rechecks these conditions under the same dictionary lock used by
withdrawal. It never overwrites a human recording, including one added while a
job is running. Each acceptance is idempotent.

Only selected wording and meanings are sent to OpenAI, using the existing
language-aware guidance adapter. Current audio, images, reviewer decisions and
example sentences displayed for lemmas are not sent. A successful generation is
not automatically published. Its generation cost settles before review; rejecting
an audible result cannot undo the API work already performed.

Accepted replacements are new attributed contributions. Previous synthetic audio
is marked superseded and its file retained. Source-word/meaning/form dependencies
are recorded so contribution withdrawal still applies. Preview and published
files are separate: invalidating a private preview cannot delete an accepted
contribution's file. Earlier evaluation snapshots remain independent.

## Implementation and deployment

This is a code-only update: no database migration or controller replacement.
Existing batch tables store zero-cost listening checklists (`audio_review`) and
separate approved regeneration quotes (`audio_repair`). The latter reuse the
bounded private-clip worker and settlement/recovery machinery from the homograph
comparison experiment. They cannot be published through the generic port-review
route. The experiment remains a separate Tools control.

Deploy through **Install Community Dictionaries on laptop** on `main`. Try a
synthetic homograph such as `queue`, mark it, approve one preview and compare it.
Check that the existing entry keeps its audio until explicit acceptance, that
rejection preserves it, and that revisiting the checklist preserves decisions.
Then use **Accept laptop and deploy AWS** for the same release. This update also
includes the preceding comparison experiment, so only one AWS deployment is
needed after laptop acceptance.

Offline regression tests cover selection, durable decisions, stale tabs, CSRF,
owner access, cost approval/settlement, uncertain requests, cancellation,
withdrawal, source edits, human recordings, exact-word guidance, forms sharing a
sentence, private range playback, and explicit/idempotent replacement.
