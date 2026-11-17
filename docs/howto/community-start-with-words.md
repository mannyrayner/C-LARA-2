# Start a guided picture with words

In **Picture, confirm and finish**, **Start with a picture** remains the first-use
default. **Start with words** opens the typed/spoken input, language and picture
style controls. Both routes use the existing private-preview, confirmation,
sentence, vocabulary and audio workflow.

## Words first

1. Choose **Start with words**, then **Type** or **Speak** and the language you
   are using. The choices are the dictionary's text and commenting languages.
2. Enter up to 255 characters, or record/upload a short spoken description.
   Choose **Photorealistic**, **Simple colour illustration**, **Cartoon** or
   **Watercolour**. **Describe another style…** asks for a short name and a
   description; the named style then appears in your menu. Reusing a custom name
   updates that personal style. Up to 20 custom styles can be saved.
3. Review the estimate and approve sending the words/recording/style to OpenAI
   and paying for the processing. Typed words go straight to image generation.
   For speech, check and correct the transcript, then **Generate picture**.
4. Check the private picture and the exact words. **Use these words and finish**
   shares them and generates the counterpart text, linked vocabulary and audio.
   **Change words or style** starts a fresh preview; it requires a new image
   request and permission. Existing previews remain private until approved.

The contributor's text is authoritative in whichever language they choose.
The image never supplies a replacement description. Enrichment and publication
both require an exact match with the supplied text, after trimming outer
whitespace. There is no automatic spelling/grammar correction of that text.
Generated-image provenance and automatic vocabulary/translation provenance are
recorded without claiming native-speaker or vocabulary review.

## Personal choices and recovery

Route, input method, language and styles are remembered for the signed-in user
in this dictionary, across logins/devices. The first words-first use shows a
style reminder, with Photorealistic selected. Other members' choices and the
dictionary's shared image style are unaffected. Each words-first attempt needs
fresh paid permission; remembering a UI choice never grants consent.

The existing `ContributionPreference.consent` JSON stores these UI choices under
`_guided_choices`; the preference accessor removes that metadata before returning
the actual consent snapshot. This release needs no migration or dependency change.

Requests and workers are claimed before provider calls. Repeated taps and GET
polling do not repeat purchases. Failed image generation leaves the words
available through **My recent pictures**; restart explicitly with those words.
If later enrichment fails, **Try again** retains the generated picture and words
and retries enrichment without buying another image. Existing missing-audio
recovery applies after publication. Previews/recordings use existing private
storage, participation checks and 30-day cleanup. Raw speech recordings are not
published. Policy/payment changes invalidate unfinished paid work.
Clearing a private preview also clears its private image prompt. A versioned
consent marker prevents older application code from processing words-first
previews after a rollback; previously shared entries remain ordinary content.

AI picture generation must be enabled by the owner. Image generation uses the
existing model, payer, daily limits and accounting; the displayed total includes
the configured image allowance, enrichment estimate and a small recording
allowance. Actual provider charges can vary.

## Laptop-first acceptance

Use the usual code-only laptop installation before accepting deployment to AWS.
No schema, environment or controller changes are included.

- Retest taking/uploading a picture in the existing route.
- Type a short sentence in each dictionary language. Check that the original
  text survives exactly and that the counterpart, word links and audio finish.
- Speak, correct a word in the transcript, and check that image generation uses
  the corrected version. Test the microphone on a physical phone.
- Try a preset and a named custom style. Log out/in and check the remembered
  choices; another member should retain their own settings.
- Check the controls and confirmation page at phone width. Verify that choosing
  a preset hides custom fields and that speech hides the typing field.

Provider tests are mocked: live image quality, recognition accuracy and physical
phone behaviour require acceptance testing. Automated text-preservation checks
cannot establish the quality of the translation, extracted vocabulary or image.
