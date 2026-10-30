# Picture, confirm and finish

This opt-in personal mode is intended for learners who want the AI to describe
what they photograph. The dictionary owner first enables Picture descriptions
and saved spoken audio for supported target and explanation languages.

## Choose a workflow

Open **Settings → My way of adding pictures**. Select **Picture, confirm and
finish**, read the per-picture cost estimate, tick the standing permission for
contributing pictures and paid AI processing, and **Save my workflow**. This
choice belongs to the signed-in member in this dictionary, persists across
logins/devices, and does not change anyone else's workflow. The alternatives are
**Writing practice** and **Usual contribution form**. The usual form remains the
default until this simpler mode has been tried with learners.

The permission covers new pictures submitted in this mode; there is no checkbox
on every upload. Turning it off affects future pictures. Previously approved
work can finish. A change to dictionary AI policy, languages, payer, model or
recorded rates requires a fresh consent/attempt before further paid work.

## Phone workflow

1. Choose **+ Add something** / **+ Contribute**, take or select a picture, and
   **Save picture and suggest a description**. The upload is saved privately
   first. One bounded AI call proposes a short description in the explanation
   language. It does not translate, extract vocabulary or generate audio yet.
2. View the picture and proposed description. **Change description** lets you
   name the intended subject or change focus in the explanation language. If
   identification is uncertain, the AI asks one question and opens that field.
3. **Use this description and finish** approves sharing and the remaining paid
   processing. The existing capture pipeline creates the target-language sentence,
   linked word pages and audio in the background. The approved explanation text
   is preserved exactly; a provider rewrite of that field fails safely. No
   claim of expert target-language or vocabulary review is recorded.
4. **My pictures — start or continue** shows recent attempts and progress. The
   final sentence page can be opened, heard, edited or flagged using the existing
   controls. Completion is shown in the app; there is no email/push notification.

A saved picture survives insufficient credit, exhausted quota and initial setup
failure. **Try the description now** retries admission when the issue is fixed.
Provider failure is not retried automatically. **Try again** is an explicit
new paid attempt; if meaning was already approved, it is retained for renewed
approval rather than redescribed. **Retry missing audio** regenerates only
failed, still-missing recordings, preserving the text and successful recordings.
Receipts and persisted job claims prevent duplicate work from repeated taps.

Private previews expire after 30 days, as in writing practice; the existing
cleanup command removes expired media. Shared entries are retained. Previews
remain readable through My pictures even after switching modes. Source-image
custody, withdrawal, membership and policy checks apply throughout. Other
members, including the owner, cannot browse a member's private previews through
the application. Server/database administrators remain an operational access
boundary, as before.

## Language level

Dictionary creation and owner Settings offer **Level of AI-generated language**:

- **Beginner** (default): one short clause and simple surrounding grammar.
- **Low intermediate**: everyday sentences and simple connections.
- **Higher intermediate**: varied grammar and more precise descriptions.
- **Advanced**: natural language without unnecessary restriction or artificial complexity.

The central subject/action must not be simplified away. A supported puffin
identification stays a puffin; unfamiliar but necessary concrete words are
welcome. Unsupported species/model guesses are discouraged and can prompt a
clarification. CEFR is approximate internal prompt guidance, not a certificate.

The level guides new image descriptions in both individual and batch workflows.
New attempts/batch quotes retain their selected level if Settings subsequently
changes. Existing entries are not rewritten. Language ports and image-only
copies inherit the setting for future generation, but translation preserves the
source meaning and does not become a silent simplification operation. Writing
practice retains the learner-approved text exactly, irrespective of level.
Descriptions remain bounded short entries (up to 255 characters).

## First acceptance exercise

Use a small Icelandic/English test dictionary with Beginner selected. Photograph
an identifiable object; check that only an English description appears before
approval. Change its focus on one attempt. Approve, leave and reopen My pictures,
and check the sentence, audio and word links. Try a less-common object whose
specific name matters. Log out/in to confirm the preference persists; use another
member to confirm that their workflow is unchanged. Also retest writing practice.
Try the main sequence on a physical phone before inviting a wider trial.

Automated tests use mocked AI responses. They establish workflow and permission
behaviour, not real image identification, Icelandic quality or learner benefit.

This revision introduces the additive `0026_learning_preferences` migration.
Follow [the one-time preparation runbook](community-learning-deployment.md)
before the normal code-only deployment workflow. No existing content migration,
provider/dependency change or extension of automatic deployment authority is included.
