# Picture descriptions (7 October 2026)

This optional workflow is for AI-supported languages. The dictionary owner enables
**Settings → Enable Picture descriptions (OpenAI)**, with saved spoken audio also
on. Existing dictionaries start with the new option **off**. Human-only contribution
and the single-object Learn from a photo workflow remain available.

## Using it

1. Choose **Describe a picture** on the dictionary page. Take a photo or choose an
   image, then say/type what you mean. Select the target or explanation language.
   Picture source is remembered on this device; language, input mode and AI voice
   are remembered in this signed-in browser session. Each can be changed.
2. **Prepare suggestion** saves a private attempt, then interprets the picture and
   description together. Both language versions appear. Spoken input also gets
   spoken confirmation in the input language; the transcript can be inspected.
   Mobile browsers may require tapping Play. Written feedback remains available
   if speech generation fails.
3. Choose **Yes — save and share** to confirm the intended meaning and permission
   to share. This publishes a sentence and the vocabulary you keep (up to 12 words or expressions),
   without requiring an expert's prior approval. **Change or clarify my description**
   retains the picture for another suggestion. Each new suggestion is a new paid
   attempt. Nothing is published merely by preparing a preview.
   Before saving, open **Words and expressions — edit, add or remove** to change
   lemmas or meanings, remove suggestions, or add related vocabulary. The optional
   sentence-form field accepts exact spans separated by `…` for discontinuous
   expressions. Leave it blank for a related word that does not occur literally.
   Empty new rows are ignored. Edits take effect with **Yes — save and share**;
   changes on an unsaved preview do not modify existing dictionary entries.
4. Listen to the sentence/words, reveal translations, open a word page, or choose
   **Next picture**. Synthetic audio is prepared in the background using the
   existing Django-Q adapter. The normal laptop threaded adapter works without a
   separate worker; keep runserver running. AWS uses its existing Q service.
   If queuing fails, **Continue creating audio** claims one still-waiting item.
5. For a picture already saved in the dictionary, open its entry and choose
   **Describe this picture**. The original image must be accepted. After saving,
   Next picture offers the oldest accepted, not-yet-described image from an ordinary
   entry. When none remains, it opens capture for a new picture.

**Pictures**, **Words**, and **Sentences** provide complementary views. Sentence pages
link to dictionary-form words (e.g. *Katten → katt*, *ligger → ligga*). Word pages
link back to the sentences. An existing picture's page links to descriptions made
from it. Listen/Translation controls work inline. In the normal Pictures/Accepted
view, a described image-only source is represented by its sentence card. The original
remains accessible through Original picture and discussion or Pictures/All; sources
with independent content or undescribed images remain visible. Withdrawing the
description makes its otherwise hidden source visible again.

## Meaning confirmation, language checking, and errors

A contributor confirms the intended meaning, not expert-level linguistic correctness.
AI-assisted entries say **Meaning confirmed … language not yet checked**. Any member
can flag an entry under **Needs attention**, optionally describing the problem.
The top-level Needs attention tab contains shared reports and a list of recent
unchecked AI-assisted wording. This is separate from the owner's private language-port
review flags. Dictionary owners/editors act as language reviewers in this first cut;
assign editor access to a suitable speaker through People.

Editors use the normal Edit words controls and then **Mark wording checked and
resolve reports**. A check applies only to the exact word/sentence and translation
revisions inspected. Later edits invalidate it. Audio is still subject to listening
review; a waveform check cannot establish correct pronunciation. English homograph warnings and pronunciation coaching apply to word/MWE entries.
Sentences and spoken confirmations use sentence-reading instructions without the
word-definition/IPA request. Both paths retain one near-silence retry. Saved audio
progress updates in place, preserving playback and open translations. A failed
clip offers an explicit new audio request; no timeout is retried automatically.

## Content and privacy

- Existing vocabulary is reused conservatively by exact lemma + meaning. Existing
  text and human recordings are never overwritten by this workflow. Different
  senses receive separate entries. The model proposes the lemmas; these remain
  editable, fallible linguistic annotations.
- Captured sentences are at most 255 characters; descriptions at most 1,000.
  AI selects at most six useful vocabulary items; the contributor can keep up to 12 after editing. Up to 200 recent
  dictionary words/meanings (bounded to 24,000 characters) are sent as context.
  The UI discloses these outbound data, provider and approximate cost before consent.
- The image informs interpretation; it must not overrule a contributor's private
  knowledge, names, humour or metaphor. A materially unresolved ambiguity produces
  a clarification question, not a forced object label. Actual model behaviour
  needs human evaluation.
- New contributions retain the contributor and AI provenance. Reused pictures
  keep the original custodian/attribution and a source link. Derived text/audio
  dependencies participate in existing withdrawal/restore operations. Withdrawing
  a source picture withdraws its derived contributions; no copies are placed in
  public MEDIA_ROOT. Changing a sentence or linked word hides stale automatic links.
  Generated audio whose source wording/meaning changed is not promoted or played as
  current audio. Re-describe an edited sentence's picture to produce fresh links.
- Draft images, input recordings, transcripts and feedback are private to the
  requesting member, expire after 48 hours, and are purged by the existing daily
  `expire_photo_studies` command. Withdrawal/settings changes invalidate associated
  private previews. This app cannot retract data already sent to a provider.
  Published components have separate storage and follow ordinary retention rules.
- Private attempts are excluded from dictionary exports. Sentence/word links,
  public-in-the-dictionary attention notes and language checks are included.

## Processing and limits

Interpretation uses the configured Community Dictionary photo model with strict
structured output. Voice input uses `gpt-4o-mini-transcribe` with an explicit language
hint. Target/confirmation audio reuses the existing TTS/voice/guidance code.
API keys remain server-side. Network calls happen outside database transactions.
Only an explicit, authenticated POST claims a provider attempt; refreshing,
resubmitting or queue redelivery cannot repeat a claimed call. Unknown outcomes
are not automatically retried. A new explicit attempt may still be needed after
interruption. Progress polling does not authorize extra attempts.

The default limit is 10 capture attempts per member and dictionary per rolling day,
configurable as `COMMUNITY_DICTIONARY_CAPTURE_DAILY_LIMIT`. At most thirteen target
recordings are generated per confirmed capture, plus optional spoken feedback.
The cost shown is a rough estimate, not a guaranteed ceiling. Existing account
balance checks apply before each provider stage. Returned usage and estimated TTS
costs are recorded once; unknown provider charges are not fabricated as zero-token
usage. Personal-key provider balances cannot be checked by the app.

Current reference: [OpenAI transcription guide](https://developers.openai.com/api/docs/guides/speech-to-text),
[pricing](https://developers.openai.com/api/docs/pricing), and
[model card](https://developers.openai.com/api/docs/models/gpt-4o-mini-transcribe),
checked 7 October 2026. The transcription accounting uses the published input/output
token rates ($1.25/$5 per million); provider billing is authoritative.

Questions, learner-response grading and conversational exercises are deferred.
Existing practice games continue using word entries (including newly linked words),
not whole sentences. Language porting currently ports word entries only; sentence
entries and sentence links are explicitly excluded and the porting screen says so.

## Installation and verification

Migration **0015_picture_descriptions** adds fields/tables. It does not rewrite
existing content or enable the option on existing dictionaries. No new dependency,
API credential or public media configuration is needed.

After a database backup, apply the patch, run `manage.py check`,
`manage.py test community_dictionary`, then `manage.py migrate`. Restart the laptop
server with `--insecure` as usual for local static files under DEBUG=False.
See the accompanying laptop installation runbook for the Cygwin commands.

Before AWS: test typed and spoken descriptions in both languages; existing-picture
capture; Next picture; inline listening/translation; flagging and editor checking;
withdraw/restore. Only then check in, deploy/migrate/collectstatic and restart both
web and Q processes. Do not enable DEBUG on AWS.

Automated/provider-simulated evidence is in
[the experiment record](../../experiments/community_dictionary/picture-capture-2026-10-07.md).
Manny reports that nearly everything worked on the laptop and the workflow felt
much faster, but the first cut split *sträcka ut sig*. Manny subsequently reports that the follow-up works on the small Swedish laptop
dictionary. AWS redeployment and three initial examples are now reported; the trial
found redundant image-only source cards and one failed sentence-audio request.
See the [focused repair and evidence](../../experiments/community_dictionary/picture-capture-aws-fixes-2026-10-07.md).
Acceptance of that repair, broader trials and new physical-phone results remain
pending. Further MWE refinement stays deferred until after the functionality trial.

## Multi-word expressions and editable vocabulary

The original first cut selected lemmas in the joint picture/description call;
it did **not** run C-LARA's MWE stage. The follow-up adapts the existing
`prompts/mwe/<language>/template.txt` and bounded examples through
`pipeline.annotation_prompts`. It incorporates their linguistic guidance into the
same structured interpretation call, rather than launching the full segmented-text
pipeline or adding a separately charged MWE call.

The model is instructed to select lexical expressions before individual words,
keep fixed particles/reflexives together, and avoid selecting their component
words for the same occurrence. *sträcker ut sig → sträcka ut sig* and
*zieht … an → anziehen* illustrate contiguous/discontinuous expressions. This
is fallible model-based analysis, not a guarantee or a measured accuracy result.
The vocabulary editor lets the contributor correct mistakes before publication.

Original AI suggestions and the confirmed vocabulary are retained in contribution
provenance. Edited items reuse an existing word only when its lemma and sense match
in this dictionary; existing text/audio are not overwritten. Whole expressions get
normal sentence/image cross-links and audio. Voice-feedback completion updates its
own panel and does not reload away unsaved vocabulary edits.

## Image-only test dictionaries

The owner can choose **Settings → Create an image-only copy**. This creates a new
private-by-membership dictionary with shared, accepted images from non-archived
entries; repeated derivatives of the same original image are copied once. No word,
translation, category, audio, discussion, member list or generated-style setting is
copied. The target/commenting languages and picture-description setting are kept;
AI image generation starts off. Image provenance is retained, including any original
image-generation prompt. The original dictionary is unchanged.

Only the owner initially has browsing access. They affirm permission before making
the copy. Original author/custodian and source relationships are preserved; source
withdrawal also withdraws copied images and dependent descriptions, and restoration
restores them. Image bytes remain in the existing private store; no AI calls or API
charges are made by copying. Copy submission retries are idempotent. This is a
transition/testing utility, not a dictionary-merging feature.

The follow-up requires no new migration beyond **0015_picture_descriptions**.
See [follow-up installation](community-picture-vocabulary-install.md).

After laptop acceptance, use the [combined check-in/AWS runbook](community-picture-descriptions-aws.md).

For the first AWS trial fixes, use [the incremental runbook](community-picture-capture-aws-fixes.md). No further migration is needed.
