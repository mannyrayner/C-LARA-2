# Personal writing practice — first version

An active member of an AI-enabled dictionary can open **Settings → My way of adding pictures → Writing practice**. The owner must first enable Picture
descriptions and saved audio. This is a personal preference for this dictionary
remembered across logins and devices, not a policy change for other members.
Saved attempts remain available through **My writing**.

## Phone workflow

1. Choose **+ Contribute**, take or upload a picture, and **Save picture and write**.
   This saves a private picture, not a shared, unannotated dictionary entry.
2. Write a short description in the dictionary's text language (up to 255
   characters). **Save draft** is free. Before **Save and check my writing**, read
   the AI cost estimate and confirm consent. Explanations default to the
   commenting language; the target language and an AI voice can be selected.
3. Read the original, highlighted suggested version and explanations. Necessary
   corrections and optional stylistic suggestions are separated. Optional changes
   are not applied automatically. **Edit my text** creates a new private draft,
   preserving the preceding attempt and its feedback. A clarification question
   must be resolved by editing before approval is offered.
4. **Use this version and finish** approves sharing and the remaining AI work.
   Translation, vocabulary, cross-links and audio continue in the background.
   The approved sentence must be preserved exactly: a provider rewrite is rejected.
5. Return through **My writing — start or continue**. The attempt page reports
   completion, or identifies missing audio. **Retry missing audio** makes an
   explicit new paid attempt only for failed recordings, retaining text and
   successful audio. No email or push notification is sent.

The normal contribution form remains available. With this mode enabled, a
permitted existing dictionary picture also offers **Write about this picture**.
Its original entry is preserved. Ordinary members can use accepted pictures;
editors can also use pending pictures, whose acceptance still follows the
existing permissions at publication.

## Data, costs and limits

- The original writing and correction feedback are private to their author
  (apart from operational server/database administrators). They are not copied
  into shared contribution provenance, public pages or dictionary exports.
- New private writing attempts use the existing PictureCapture storage and
  expire after 30 days. The existing `expire_photo_studies` command removes
  expired preview files; access expires even if cleanup has not yet run.
  **Clear private preview** can clear them sooner. Published entries remain.
  Withdrawal, membership and dictionary-policy checks apply throughout.
- The feedback call sends the picture, original writing and language labels to
  the configured OpenAI photo model. Only after approval does enrichment send
  the approved text, picture and up to 200 existing accepted words/meanings.
- Estimates combine one bounded feedback call with the existing capture estimate
  for translation, up to six words and audio. They are planning estimates, not
  spending caps. Usage is billed through existing C-LARA credit accounting or the
  member's personal key. Interrupted provider calls can still cost money.
- Merely saving a picture/draft does not use the daily AI allowance. Submitting
  for feedback counts as one attempt. Failed/discarded submitted attempts still
  count. Revising and requesting new feedback is a fresh attempt.
- AI-generated vocabulary/translation/audio is published after sentence approval,
  without pretending the member reviewed it. The existing language-attention
  controls remain available. Feedback quality and pedagogical benefit require
  learner testing; automated tests use mocked provider responses.

## Deployment and first acceptance check

The initial writing release was code-only. The subsequent durable-workflow
revision adds migration 0026; follow [the preparation runbook](community-learning-deployment.md)
once before the normal supervised laptop/AWS workflow. Keep the two manual acceptance
steps; this feature is not an expansion of deployment authority.

On a small French/English test dictionary, try a deliberate agreement error such
as `Le chat sont sur le canapé.` with a suitable image. Check the original,
correction and explanation; approve it; leave and reopen the attempt; check the
finished sentence, translation, word links and audio. Also try an already correct
sentence, **Edit my text**, and the ordinary contribution form. Verify that
another member cannot open the private feedback URL and retains their own mode.
Repeat the main sequence on a physical phone before inviting broader use.

Long paragraphs, adaptive proficiency profiles and email/push notification
remain outside this version. The workflow
is language-general but has not yet been evaluated for beginner Icelandic use.
