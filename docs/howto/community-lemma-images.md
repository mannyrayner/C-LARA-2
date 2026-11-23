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
only its accepted lemma, translation and language names. Example sentences are
not sent to the planner or image generator. The prompt distinguishes nouns,
actions, colours, numbers and patterns using independent concepts, rather than
reconstructing a sentence scene.
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
selected entries, their words/meanings, attempt revisions and the displayed
model/pricing settings.
Confirm processing/publication, then start. Images and deliberate picture
decisions are skipped. A subsequent batch continues with the remaining missing
lemmas, including failed attempts without a usable accepted picture. Retry
items are labelled in the preview. A failed regeneration with a usable existing
picture keeps that picture and is not included in backfill. Progress lists the
latest attempts and links to individual controls.

**Resume queued pictures** re-enqueues only unstarted work. A committed claim
precedes each paid request. Broker redelivery cannot repeat an in-flight or
completed call. Failed or uncertain paid attempts require an explicit new
attempt; after an uncertain in-flight interruption wait ten minutes. Daily
limits, missing credit or changed policy may leave failures needing a later
retry. The page shows the normal rolling-24-hour limit and usage on both the
requester’s account and dictionary. A batch exceeding the remaining allowance
stays at the preview until the editor reduces its size, waits, or obtains an
owner’s explicit temporary approval.

An owner or co-owner can tick **Allow these selected word pictures above the
normal daily image limit, for this batch only** beside the cost approval. This
creates a signed allowance for each of the selected attempts (at most 50), tied
to its requester, dictionary, attempt and revision. It expires after 24 hours;
redelivery cannot reuse it for another attempt. It does not change any normal
daily setting or grant extra capacity to other requests. The owner approves
charges on their own requesting account, with the usual credit check still in
force. A server limit of zero continues to pause all image work. The same option
is available for an individual **Generate or regenerate** attempt.

Existing images are preserved when this prompt update is installed. Open a word’s
**Word picture → Generate or regenerate** control to replace an earlier image
with the independent-lemma recipe. Work is serialised per payer and uses the
existing bounded task runner.

Source revisions, access, participation, policy and pricing are rechecked before
provider stages and publication. A changed word or meaning invalidates its
picture for learning until an editor updates the decision. An older worker
cannot overwrite a newer manual choice. Withdrawal dependencies include the
lemma, translation and any shared style for new independent-lemma images.
Older images retain the source dependencies from the recipe that created them.
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
