# Type, speak or ask AI to describe a picture

8 October 2026. This incremental update follows dictionary visibility (migration
0017). It needs no new migration, dependency, account setting or API credential.

## Using it

On an accepted image's entry, **Describe this picture** now offers three equal
choices: **Type**, **Speak**, and **Suggest a description**. Choose one and Continue.
The same choices appear when starting **Describe a picture** with a new image.
They replace the competing single-object **Learn from this photo** control where
Picture descriptions is enabled. The older route is retained when that feature
is off, or the picture is awaiting review.

**Suggest a description** needs only the picture. Select the language for feedback,
review the existing cost/data notice, and choose **Prepare suggestion**. AI proposes
one short visually grounded sentence, its translation and up to six useful words or
expressions. If the image cannot be described clearly, it can ask for clarification.
There is no second description-generation API call: this uses the same structured
image-understanding request as typed/spoken input, with adapted instructions.

All three modes use the usual preview, editable vocabulary, meaning confirmation,
sentence/word cross-links and TTS. **Change this description** retains the picture
and opens the proposed sentence in the selected feedback language for correction.
The correction follows the ordinary typed route, respecting the user's intended
meaning. Only **Yes — save and share** publishes. Preparing a preview is not a save
or expert language check. Language/audio errors can still be flagged afterwards.
AI mode provides written feedback; Speak retains spoken confirmation as before.

The last explicitly selected mode is remembered on this device separately for each
signed-in user and dictionary, with a session preference after successful submission.
Opening a correction does not itself change the next picture's preferred mode.
Choosing a mode, opening an entry, or remembering AI mode never starts a paid request.
Language and voice retain their existing session preferences; camera/upload retains
its existing device preference. A recovered unsent draft retains its own mode.

Typed drafts and recordings can remain available when switching modes, but unused
inputs are omitted from submission and ignored by server validation. AI mode sends
no stale typed description or input recording. As before, the picture and bounded
dictionary vocabulary are sent to OpenAI with consent. Existing balance checks,
shared daily allowance, permissions, idempotency and provider-failure handling apply.
Generated wording records input mode `ai` and the generation recipe in provenance;
the absent human description is not invented. Existing source-image ownership and
withdrawal dependencies remain in force.

## Evidence and trial

365 app tests pass, including nine focused tests for the new route. A mocked-provider
Chromium rehearsal covers 390/1280px layouts, AI preview/correction/save, next-picture
preferences, text-draft recovery, voice-to-AI input exclusion and user separation.
These establish software behaviour, not real AI quality or physical-phone acceptance.

Try several of Cathy's pictures without supplying a description. Check that the
suggested focus is useful, change one deliberately, and verify the next picture
still starts in AI mode. Try Type and Speak too. Further MWE quality work stays
separate; this route uses the same existing guidance and editable vocabulary.

WordPress access, email password reset and any incoming AI mailbox remain on hold.
See [installation](community-ai-descriptions-install.md) and
[experiment evidence](../../experiments/community_dictionary/ai-descriptions-2026-10-08.md).
