# Describe a picture: private speaking and writing practice

Open a dictionary, choose **Practise → Describe a picture**, then speak or type
in its text language. A few words, a description, a story or imagined dialogue
are all welcome. **Show an example** keeps the existing caption out of the way.
Only current accepted pictures are offered; the current category is respected.
**Another picture** avoids the same image file when another one is available.

For speech, record or upload a short clip, then choose **Check what I said**.
The app transcribes it and waits. Correct the transcript or use **Try again** to
record another attempt. **Use these words and get feedback** checks exactly the
confirmed words with the image. Typed input goes straight to feedback.

Feedback briefly explains what the AI understood, shows a version preserving the
learner's intention, and explains necessary changes. Optional style suggestions
are separate and unapplied. A clarification question is possible. This is
feedback on text, including a confirmed transcript; it does not assess
pronunciation, accent or speaking fluency. AI judgments can be wrong.

**Try again** starts a separate attempt on the same picture; typed text is
prefilled for revision, while speech can be recorded again. **Listen to this
version** explicitly requests private synthetic audio, for supported OpenAI TTS
languages with saved audio enabled. Replaying the resulting clip is free.
Nothing is published or added to the dictionary. There is no automatic image,
translation, vocabulary, word-audio or entry-audio generation. Saving a practice
answer as a dictionary entry is outside this first version.

## Cost, access and recovery

- A signed estimate and explicit consent precede each feedback/transcription
  submission. Text uses one bounded image-and-text call; speech adds one
  transcription call. Optional listening has its own estimate and button.
- Practice uses the existing dictionary/account picture-description allowance,
  payment checks and usage accounting. Failed/discarded attempts still count.
  Ordinary feedback does not require a working word-audio provider or TTS setup.
- Input method, explanation language and synthetic voice persist per user and
  dictionary independently of contribution workflow preferences.
- Private attempts and audio use existing 30-day expiration and withdrawal
  cleanup. **Clear this practice attempt** erases its private content earlier.
  Device draft recovery follows the existing IndexedDB mechanism and may be
  cleared separately with **Discard local draft**.
- Attempts are available only to their author while they remain a member. Owners
  cannot inspect another member's attempts through these pages. Withdrawal,
  archival, participation changes and capture-policy changes invalidate access.
- A chosen image is pinned in the URL, so page reload/draft recovery cannot pair
  old words with a newly randomized image. Recovered permission and estimates
  are not reused; confirm the current estimate.
- Each paid stage commits a claim before contacting a provider, with no SDK
  retries. Reloads, repeated taps and background redelivery do not repeat a
  claimed call. A failed/uncertain stage needs an explicit new attempt.
  **Continue pending work** only starts unclaimed stages.
- This is a signed-in activity; public practice games remain free and read-only.

## Implementation and validation

Uses `PictureCapture(input_mode='practice')` and private `CaptureSpeech` clips;
no database migration or new dependency is needed. Entry publishers explicitly
reject this mode. Existing writing feedback supplies image serialization and
strict correction validation, with a separate bounded practice schema/prompt.

Tests cover transcription confirmation/editing, the actual rendered button's
DOM submission in both input modes and asynchronous draft recovery, idempotency,
payment/allowances, preference isolation, private access, source withdrawal during
provider processing, publication rejection and optional audio. Provider calls
are mocked; laptop testing is still needed for real Italian feedback quality,
microphone behavior and listening comfort.
