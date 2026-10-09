# Sentence-first language versions

9 October 2026. This supersedes the sentence/vocabulary alignment workflow in
`community-sentence-porting.md`. Installation: `community-two-stage-porting-install.md`.

Manny reports successful AWS conversion of the 150-entry Swedish/English dictionary
to French/English, but vocabulary translated independently from Swedish can disagree
with the French sentence. His example uses **repose**, while its word page offered
**être couché ; se trouver**. The sentence should instead lead to **reposer**.

## Workflow

1. **Translate and review sentences.** Estimate and approve the conversion as before.
   This stage includes sentences and independent word entries. It does not translate
   sentence-derived vocabulary separately. Review/edit the sentences, or explicitly
   accept all remaining ready suggestions. Flagged, unclear, failed and changed
   results are excluded from bulk acceptance.
2. **Build vocabulary from accepted sentences.** Open the link on the result page,
   or **Settings → Build or update vocabulary from accepted sentences** in the
   destination. Preview its separate cost estimate, then approve. The accepted
   destination sentence, translation and representative picture are authoritative;
   Swedish word pages are not translated as a substitute for analysing the French.
3. **Review words beside their sentence and picture.** Edit, add or remove words and
   multi-word expressions, or accept all remaining ready suggestions. Saving connects
   shared word pages and queues missing word recordings. Existing sentence text,
   pictures and matching sentence audio are kept.

Stage 2 uses the same lexical/MWE guidance, span validator, editable vocabulary
form and word-publication helper as ordinary picture descriptions. It uses bounded
fan-out/fan-in for sentence analyses and word speech, through the existing Django Q
workers and porting concurrency setting. GET requests make no provider calls.

Words share a page when their **lemma and sense gloss both match**, after Unicode,
case and whitespace normalization. Existing vocabulary is supplied to the model
with instructions to reuse a matching sense's exact wording. Different meanings
remain separate. This first cut conservatively treats differently worded glosses
as separate senses; it does not claim reliable automatic synonym resolution. Use
the same gloss in review when the intended sense is the same. New vocabulary
created by parallel analyses can therefore occasionally need this correction.
Existing pages are reused without overwriting their wording, attribution or audio.
One job creates at most one recording per shared word/text revision.

## Repair an existing French version

Keep the existing dictionary. Open its **Settings → Build or update vocabulary
from accepted sentences**. Accepted sentences go directly to stage 2; there is no
need to repeat sentence translation. Finish or flag any unreviewed sentence
translations before starting. Another running vocabulary job must be completed or
cancelled before a fresh estimate is prepared.

Approval discards unused legacy previews of sentence-derived words; it retains
independent word previews. Saving each sentence's vocabulary replaces its derived
word/image links, preserving manual image tags. After the job finishes, unchanged,
unused legacy word pages replaced by this repair are archived, not deleted. Pages
with human edits, notes, independent images or manual tags, and words still used by
another sentence, are preserved. Historical contributions and withdrawal links
remain. A cancelled job keeps accepted work but does not archive old word pages.

## Edits and repeated runs

The app records which sentence, explanation, representative picture, language
pair and word revisions produced accepted vocabulary. Changed inputs show
**Vocabulary needs updating** on the sentence page. The next stage-2 estimate
includes these sentences and skips current ones. It never silently calls AI after
an edit. Existing word corrections remain intact; review can reuse or select a
new sense. A sentence edited after quotation invalidates its old suggestions.

Sentence audio is preserved when it still matches the wording. If the sentence was
edited during review, use its existing **Create audio** control for the final text.
Stage 2 generates word audio, not replacement sentence audio. Failed word audio can
also be regenerated from the word page and is then available to its linked sentences.

## Costs, permissions and provenance

Each stage has a separate estimate and explicit permission/cost approval. Stage 2
quotes analysis plus roughly six word recordings per sentence; the larger credit
reservation allows up to twelve edited words, pronunciation guidance and the existing
single silent-audio retry. Reuse can reduce actual spending substantially. The
provider's bill remains authoritative; a configured C-LARA credit reservation is
not a cap on a personal provider account.

For stage 2, credit remains reserved while suggestions await review and while their
speech jobs run. Accept, discard or cancel the remaining suggestions to finish and
return unused reserved credit. “Running” can mean awaiting review; the page shows
analysis and audio progress separately. Interrupted calls are not blindly retried.

Only the initiating port owner, still authorised in both dictionaries, can run or
review the conversion. Preview media is private. Source and context dependencies
are retained, and withdrawal invalidates previews and moves derived contributions
to the appropriate private collections. Reusing an existing word does not transfer
its custody. Shared words have the same conservative withdrawal dependencies as
ordinary captured vocabulary; an affected word may disappear from several sentences.

Accepting a result is not an expert linguistic check. No changes are made to human
recording, community participation or the existing expert-check control.

## Evidence and limits

The release includes additive migration **0018_port_vocabulary_stages**; existing
jobs remain tagged as legacy jobs. Automated provider responses and TTS are mocked.
The regression suite and browser rehearsal cover workflow, access, withdrawal,
credit settlement, legacy repair, shared senses, edits and mobile-width layouts.
See `experiments/community_dictionary/two-stage-porting-2026-10-09.md` for results.
Live French analysis, MWE quality, pronunciation, AWS queue timing and physical-phone
acceptance still require user testing. No provider call or production write was made
while preparing this revision.
