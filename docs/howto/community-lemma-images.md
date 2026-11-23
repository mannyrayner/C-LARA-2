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

Open **Tools → Manage word pictures**. The overview shows word/translation
cards with the current private 256-pixel thumbnail or a state: Not yet attempted, No simple
picture, Resource limit reached, Failed, Queued, Planning, Generating or Hidden.
Illustration-only pictures carry their exercise-clue warning. Existing uploaded
pictures and deliberate choices are shown as well as missing pictures.

Select cards, use **Select all shown** or **Clear selection**, then choose
**Generate/regenerate selected**. Review the selected cost and approve one batch
of 1–50 words. Existing pictures remain visible during regeneration and survive
a failed replacement. **Show more words** expands the first page from 20 to 100
cards; Previous/Next and search cover larger dictionaries. Browser-session
selection and scroll restoration support loading and refreshing. Changing the
selection requires a new cost preview. The server checks signed word/image
states, accepted sources, permissions and prices again before starting.

**Remove selected pictures** hides their word-picture decisions without deleting
word pages, contributions or billing history. **Undo picture removal** restores
unchanged, still-visible choices. A newer manual choice, changed meaning or
withdrawn picture is never overwritten. An unstarted queued attempt can be
cancelled without a provider call; undo never silently restarts a paid attempt.

### Three cost displays

- **Estimated selected cost** updates with selection; the signed preview records
  the batch estimate before consent.
- **Batch cost so far / Actual batch cost** reports recorded planning and image
  usage for that exact batch, including charged failures. The original estimate,
  completion counts and resource skips remain available. The latest batch and
  five recent batches persist across visits for their requester.
- **Cumulative word-picture cost** covers all word-image attempts in this
  dictionary, including previous regenerations and pictures later hidden.

New attempts retain cost parts in the existing private ImageStudy usage receipt,
including personal-key planning costs. Unknown provider usage is labelled as a
partial total and never treated as free. Legacy records are reconstructed from
image usage and matching planning charges; incomplete older records are flagged.
Cost parts are summed before display rounding. Recorded usage/prices are not a
promise that a provider invoice, allowances or tax will match exactly.

### Allowance and recovery

Failed words can be selected directly in the grid. Review and approve their next
attempt; paid requests are never retried automatically. **Resume queued
pictures** re-enqueues only unstarted work. A committed claim precedes each paid
stage and redelivery cannot repeat an in-flight or completed call.

The page shows normal rolling-24-hour account/dictionary usage. A batch exceeding
remaining capacity requires a smaller selection, a renewed normal allowance, or
an owner/co-owner’s explicit temporary approval. This signed permission applies
only to the selected attempts, expires after 24 hours and changes no normal
limit. Batches remain at most 50; the credit check and server pause at zero apply.
Queued receipts do not consume the allowance or block ordinary/guided images
until provider work is actually claimed. The per-payer serialisation remains.

This overview needs no additional schema migration beyond 0030. Operational
cost/batch receipts remain private and are excluded from dictionary exports.

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
