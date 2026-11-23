# Shared lemma pictures

First version, 23 November 2026. Implementation and local tests are separate from
installation and a live-provider/learner trial.

## Behaviour

Each dictionary lemma **and sense** has one picture decision, shared by all its
forms in sentences. The existing Entry/SentenceWord/form-contribution structure
is retained: inflected occurrences do not get separate entries or generated
pictures. Multiword expressions use their existing dictionary form.

The decision is one of:

| Decision | Vocabulary pages | Picture games |
| --- | --- | --- |
| Picture clue | Show picture | Include lemma |
| Illustration only | Show picture | Exclude |
| No simple picture | Show shared thought symbol | Exclude |
| Hidden | Show no word picture | Exclude |

Queued, planning, generating, failed and outdated states are distinct from a
deliberate No simple picture decision. Existing pictures are kept. An editor can
choose an existing accepted picture, upload a replacement, regenerate, hide the
word picture or override its clue suitability under **Word page → Word picture**.
Hiding the word picture changes its learning presentation; it does not withdraw
the original contribution from its author's history or other existing uses.

Member and visitor flashcards, crosswords and word scrambles use the existing
lemma entries and dedicated clue pictures. A picture merely linked from a
sentence or another word remains context; it is no longer a vocabulary clue.
Existing dedicated accepted word pictures remain eligible until an editor makes
a different choice. Suitability is initially a model proposal, not a visual or
human review of the generated output. Human checking can improve it.

## Automatic generation and costs

For an AI-supported language, **Enable AI picture generation** and
**Automatically illustrate new word pages** enable background work after a new
accepted word is committed. The automatic preference defaults on; the existing
dictionary AI switch still applies, so dictionaries with image AI disabled do
not start paid work. Newly created dictionaries retain the existing
language-dependent AI defaults. Turning the automatic preference off preserves
completed pictures. Older dictionaries are not backfilled by a migration.

Automatic requests use the owner's configured account/key. A manually requested
regeneration or backfill uses its requester's account/key. Settings explain the
standing automatic permission and costs. Missing credentials/configuration
leave a failed marker without undoing the accepted vocabulary.

One bounded text request plans whether and how to illustrate the lemma, using
its accepted translation and up to three current accepted example sentences.
If useful, one image request follows, using the approved dictionary style text
or a simple default style when no shared style is set. No image request is made
for No simple picture. Prompts prohibit written answers and labels.

The existing configured photo/text model, image model, image allowance, daily
limits, personal-key and credit accounting are reused. Estimated allowance is
the image allowance plus a bounded text estimate. It is not a fixed charge or
provider spending cap. Returned usage is accounted even when later image
validation or publication fails; the provider invoice remains authoritative.

## Backfill and recovery

Open **Tools → Add missing word pictures**. Start with the default five-word
preview, or choose 1–50 missing words. The signed, expiring preview binds the
selected entries, their words/meanings and the displayed model/pricing settings.
Confirm processing/publication, then start. Images and deliberate picture
decisions are skipped. A subsequent batch continues with the remaining missing
lemmas. Progress lists the latest attempts and links to individual controls.

**Resume queued pictures** re-enqueues only unstarted work. A committed claim
precedes each paid request. Broker redelivery cannot repeat an in-flight or
completed call. Failed or uncertain paid attempts require an explicit new
attempt; after an uncertain in-flight interruption wait ten minutes. Daily
limits, missing credit or changed policy may leave failures needing a later
retry. Work is serialised per payer and uses the existing bounded task runner.

Source revisions, access, participation, policy and pricing are rechecked before
provider stages and publication. A changed word or meaning invalidates its
picture for learning until an editor updates the decision. An older worker
cannot overwrite a newer manual choice. Withdrawal dependencies include the
lemma, translation, example sentences actually used and any shared style.
Exports retain current terminal picture decisions and contributions, with private
job/quote/analysis state removed. Operational restoration still requires the
normal database/private-media backup.

## Installation and first trial

Migration **0030_lemma_images** adds one dictionary preference column and the
LemmaImage table. It rewrites no dictionary content and performs no provider
calls. Use the [bounded laptop preparation](community-lemma-images-deployment.md)
before the normal code-only release path. Do not widen the deployment
controller's migration restrictions. Collect static files/catalogues as usual.
Rolling code back does not require reversing this additive migration.

For the first live trial, use a small staging dictionary containing a concrete
noun, an action, an abstract/function word, two senses of one spelling, a
multiword expression and an inflected occurrence. Check automatic generation,
the five-word backfill, replacement/overrides, the sentence vocabulary view and
all three picture activities. Then have Manny/Cathy judge the generated clues.
Mocked tests establish mechanics, not actual provider quality or learning value.
