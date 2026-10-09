# Porting dictionaries with picture descriptions

> **9 October update:** Sentence vocabulary now follows a separate review stage
> based on accepted destination sentences. See [current workflow](community-two-stage-porting.md)
> and [installation/recovery](community-two-stage-porting-install.md). Guidance below
> about independently porting sentence words is retained as historical context.

8 October 2026. This follow-up extends language versions to accepted **sentences
and words**. Earlier word-only ports remain usable. No new migration is required.

Manny reports a Swedish dictionary with over 150 image-associated sentence entries,
and says he accepted the AI suggestion in about 90% of cases. This is encouraging
human feedback, not a measured accuracy score. His French/English conversion
reported progress but appeared empty. Inspection confirms the old selector excluded
sentences; generated word results also remain private until reviewed and saved.
Without inspecting that production job, we cannot identify which combination of
these issues caused the empty view.

## Normal use

As owner, use **Settings → Create a version in another language**. Choose the new
languages and voice, request an estimate and explicitly approve its cost and data
permission. The quote now includes a sentence count. Both words and sentences run
through the existing bounded concurrent queue. The original dictionary is unchanged.

The progress page distinguishes **ready to review** from **saved in this run**.
Choose **Continue reviewing and saving**, check the sentence and audio, then
**Save and next**. An empty or partly populated destination also links its owner
back to unsaved results. This link is private to the authorised port owner.
Generation finishing does not itself publish the results.

Saved sentences appear in Pictures and Sentences; vocabulary appears in Words.
The sentence has its picture, target sentence, commenting-language text, audio and
word links. Links become available once both endpoints are saved, in either order.
Vocabulary that originally borrowed a sentence's picture continues to borrow it,
rather than producing a separate picture card for each word. Independent word
entries with their own pictures retain the old behaviour.

Changing only the commenting language preserves the original target sentence,
word forms, contributor attribution and recordings. Changing the target language
uses sentence-specific speech instructions for sentences and the existing
pronunciation guidance for individual words. A speech failure still permits saving
the text, followed by Create spoken audio or a human recording on the saved entry.

## Word links and review

The translation call receives the source sentence, explanation, category, one
representative image and the linked source vocabulary/meanings. It proposes exact
spans in the translated sentence for those source concepts. Multi-word expressions
stay together; discontinuous spans can use an ellipsis. No source recordings are
sent. The estimate includes the additional context/output; this adds no separate
alignment call. Existing configured prices, reservation, consent and retention
notices still apply.

Unknown or duplicate vocabulary IDs are rejected. A proposed span absent from the
sentence is cleared, while its word remains available as related vocabulary.
Editing the translated sentence during review discards mismatching generated audio
and clears precise spans; it retains the related word links. This first cut carries
across the existing vocabulary, rather than selecting a fresh target-language
vocabulary list. Translation choices and lexical correspondences still need review.

Source revisions and withdrawal dependencies include the linked word texts and
meanings. Changes before saving require a fresh estimate. Saved derivatives remain
connected to their source contributors' withdrawal controls. Automatic link updates
advance only previously unedited destination baselines; unrelated human edits stay
protected. Estimates freeze the sentence speech version as well as existing prices
and word-speech rules.

## Recovering a previous attempt

Do not delete the destination or repeat the entire conversion just because it
appears empty. Open the source dictionary's **Settings → Create a version in
another language**, select its existing language version and **Latest job** or
**Previous results**.

1. If word results are ready, review and save the ones you want. Existing word
   snapshots and prompt versions are preserved by this patch.
2. Finish reviewing, or explicitly discard unwanted results, before estimating an
   update. Discarding removes previews; it does not refund completed provider work.
3. Choose **Estimate an update** for that same version. It includes missing
   sentences and other new/changed eligible entries. Check the sentence count,
   skipped/protected counts and price before approving. Unchanged accepted word
   ports remain eligible to skip; changed category context/source material can
   legitimately require new work.
4. Review and save the sentences and remaining words. Check Pictures, Sentences,
   Words and cross-links. The destination can be shared using its usual invitations.

If the old job is still running, let it finish first. Use Resume waiting work for
stalled unclaimed tasks; uncertain paid attempts are not silently repeated. Failed
or stale results require a fresh estimate. Old already-saved picture copies are not
rewritten automatically. No bulk acceptance or destructive conversion is introduced.

See [installation](community-sentence-porting-install.md), the
[language-porting guide](community-language-porting.md), and
[verification record](../../experiments/community_dictionary/sentence-porting-2026-10-08.md).
