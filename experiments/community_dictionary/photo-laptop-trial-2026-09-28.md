# First live photo-learning trial: 28 September 2026

Evidence: Manny's reports in the development conversation, following the original
photo patch and SDK import repair. This is a human-reported laptop trial, not an
instrumented benchmark or a physical-phone test of the new feature.

## Reported result

- Installation, local server startup, login and dictionary opt-in succeeded.
- The learner initially uploaded through the ordinary entry workflow and could
  not find interpretation. Guidance to Browse → Learn from a photo resolved this.
- An uploaded image described by Manny as copyright-free and depicting a horse
  was recognised quickly; the suggested Swedish wording was **en häst**.
- Manny reported good-quality spoken output and saved the wording after editing
  it to **häst**. He could not find a way to save the audio.

Source inspection explains the audio limitation: `photo.js` uses browser/device
speech synthesis for a preview. It creates no audio file, and the save action
stores the photo and wording only. This result therefore establishes neither
OpenAI TTS quality nor persistent generated-audio support. The selected browser
voice, exact model setting, measured latency and cost were not reported.

The successful live result supersedes the earlier absence of any live-provider
evidence. AWS deployment and physical-phone acceptance of this photo-learning
increment remain unreported; the earlier human-photo/recording phone trial is
separate. One familiar object is not a recognition-accuracy estimate.

## Feedback and proposed bounded follow-up

These are proposals, not features installed by this documentation update.

1. Put **Learn from this photo** beside an existing entry's image. Reuse that
   authorised image and offer wording as a contribution to the same entry,
   preserving existing material and review. Retain a capture-first shortcut if
   useful, but do not require a second upload or create a duplicate entry.
2. Add explicit generation, preview and saving of synthetic audio from confirmed,
   edited text through the existing real TTS adapter. Label its origin, keep
   source text/version, and use private storage and ordinary contribution review.
   A provider voice may differ from the browser voice praised in this trial.
3. Keep article/headword wording editable. For the initial Swedish trial,
   **en häst** is useful gender information; do not impose article removal across
   languages or add mandatory new grammatical fields merely for this example.
4. Explore a dictionary-lookup mode for target languages unsupported by AI:
   identify the object in the explanation/commenting language, ask for confirmation,
   then search accepted entries locally using their meanings. Return community
   wording and recordings, never an invented target-language translation.
   Show alternatives or no match explicitly; dictionary meanings may differ in
   specificity or use synonyms. An optional partner request can fill a gap.

The proposed lookup can send only the permitted photo and commenting-language
name outward; the dictionary and community recordings need not leave the server.
The photo still undergoes external processing, so existing community opt-in and
data-handling requirements continue to apply. Sophie/community interest is unknown.
Manny expects to discuss this direction with Sophie on Thursday 1 October.

Sustained low-intervention operation remains the strategic priority. These changes
respond to observed trial friction; they do not commit to a larger practice system.
