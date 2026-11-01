# Review homograph audio

Dictionary owners can open **Tools → Review homograph audio** to listen to
accepted dictionary words and sentence forms whose spelling also occurs in
English. By default, it lists only single words. **Include expressions containing
homographs** also shows phrases containing an English spelling (including small
words such as `de` or `en`). The broader detector is still used for pronunciation
guidance; this filter changes the review list, not the synthesis strategy.
It is a review aid, not a
complete inventory of pronunciation problems or a guarantee that a flagged word
is wrong.

## Listening and repair

1. Listen to each current recording alongside its word/form and translation.
   Sentence forms show their sentence; dictionary words show an available sentence
   example when one exists.
   Equivalent sentence forms are grouped: the same surface form, dictionary
   lemma/sense and voice share one card, with their sentences and contextual
   translations available together. For example, `est` from the same entry for
   `être` is grouped across sentences; a dictionary entry for `est` meaning
   “east”, a different sense or a different voice is kept separate. Human
   recordings stay on separate protected cards.
   If one current variant is already good, **Use this recording for all these
   occurrences** copies it to the displayed group without API calls or cost.
2. Choose **Keep** or **Needs regeneration**. Each choice saves immediately.
   Progress survives leaving the page. Text, meaning, language or audio changes
   invalidate the corresponding decision. Human recordings cannot be selected for
   automatic replacement.
3. Choose one to five **Candidates per word or form** (default three), then
   **Estimate regeneration of marked items** (up to 100 items per batch).
   A group needs only one set of candidates, not a separate set for every
   occurrence. The estimate includes every requested recording and states the payment source, estimated
   API cost and refundable C-LARA allowance. Insufficient C-LARA credit blocks
   approval. A personal OpenAI key's balance cannot be checked by the app.
4. Approve to generate private previews with the current enriched pronunciation
   guidance. Existing supported voices are preserved. No carrier phrases are
   used, and current dictionary audio remains available throughout generation.
5. When processing finishes, each word shows its **Current dictionary audio** and
   numbered **New preview** candidates. **Use this recording** accepts one
   candidate for all occurrences listed in that quote and closes the other
   choices for that group. Contextual translations and sentence links are not
   changed. **Reject preview; keep
   current audio** rejects just that candidate; the others remain available.
   Failed candidates do not prevent successful ones being reviewed.
6. If none is suitable, choose a count and **Estimate more candidates** under that
   word. This prepares a separate estimate for that item only, requiring fresh
   approval before any further calls. Earlier previews are kept and linked until
   an accepted replacement or source edit makes them stale. You do not have to
   reject every candidate before requesting more. Each new batch uses fresh
   pronunciation guidance and synthesis attempts with the same supported voice;
   repeated generation may still repeat the same error.

Jobs and previews remain accessible from the checklist. **Refresh progress**
reads fresh state. **Resume interrupted work** resumes unstarted tasks and, after
15 minutes, accounts for abandoned requests without repeating them. Completed
near-silent audio can be regenerated once by the ordinary TTS adapter. Network
errors have no automatic retry. Estimates are neither invoices nor hard provider
spending caps.

New captures, vocabulary generation and sentence-form backfills can reuse an
existing equivalent form recording locally in the same voice. For homographs,
reuse requires a recording explicitly kept or accepted in review; unchecked
homograph audio is not propagated. Non-homograph forms may reuse accepted
synthetic audio. Human recordings are neither copied nor overwritten. Concurrent
first-time generation can still produce more than one attempt before any usable
recording exists. This is reuse of available results, not a new global queue.

The checklist, playback routes, quotes and replacement actions are owner-only.
The ordinary public browsing and entry-editing permissions are unchanged. French
and Slovak interface translations are included; generation uses the dictionary's
text and explanation languages independently of the interface language.

## Integrity and custody

The saved review compares exact text/meaning and recording fingerprints. An edit,
withdrawal, new recording or loss of owner access makes stale previews unusable.
Replacement rechecks these conditions under the same dictionary lock used by
withdrawal. It never overwrites a human recording, including one added while a
job is running. Each acceptance is idempotent. An old tab cannot accept or reject
another candidate after a replacement was accepted for the same word. New
candidate batches respect the checklist: items now marked Keep cannot be quoted
from an older results page. Repeated quote submissions reuse their original quote.

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
Each reused occurrence has its own file and contribution, with the source
recording's author/custodian and an explicit dependency on that recording. Source
withdrawal therefore also withdraws its copies. Sentence/form contributions keep
their original authors, glosses and dependencies. Selecting a different recording,
editing a source, or adding human audio while a quote is running blocks stale
replacement. Older quotes retain their original per-occurrence scope.

## Implementation and deployment

This is a code-only update: no database migration or controller replacement.
Existing batch tables store zero-cost listening checklists (`audio_review`) and
separate approved regeneration quotes (`audio_repair`). The latter reuse the
bounded private-clip worker and settlement/recovery machinery from the homograph
comparison experiment. They cannot be published through the generic port-review
route. Existing single-preview jobs and saved decisions remain compatible. The
experiment remains a separate Tools control.

Deploy through **Install Community Dictionaries on laptop** on `main`. Try a
synthetic homograph such as `queue`, mark it, approve three candidates and compare them.
Check that the existing entry keeps its audio until explicit acceptance, that
rejection preserves it, and that revisiting the checklist preserves decisions.
Try requesting more candidates for just one item and check the new estimate.
Then use **Accept laptop and deploy AWS** for the same release. This update also
includes the preceding comparison experiment, so only one AWS deployment is
needed after laptop acceptance. For grouped review, try two sentences using `est`
from the same `être` entry; choose one existing recording for both, then add a
third sentence and verify that its audio reuses the approved recording. Check the
optional expressions filter and that distinct senses remain separate.

Offline regression tests cover selection, durable decisions, stale tabs, CSRF,
owner access, cost approval/settlement, uncertain requests, cancellation,
withdrawal, source edits, human recordings, exact-word guidance, forms sharing a
sentence, private range playback, and explicit/idempotent replacement. Candidate
coverage includes count validation, full-batch estimates, per-recording progress,
mixed successful/failed candidates, fresh cost approval, legacy jobs, and stale
choices both within a batch and between batches.
Grouped coverage includes filtering, shared candidate costs, contextual gloss
preservation, free reuse, custody and withdrawal/restore, voice/sense separation,
human protection, old quotes, and capture/backfill reuse without synthesis.
