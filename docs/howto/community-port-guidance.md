# Workflow suggestions for existing language versions

AWS follow-up: Manny reports the update workflow producing the expected French
content, but also duplicate image-only cards and slow navigation. See the
[repair and measurements](community-guidance-repair.md) before further deployment.

After adding and accepting sentences in a source dictionary, the owner can now
see that an existing language version needs updating. Both dictionaries' cards
and Browse pages link to the work. For example, the Swedish card can say
“French version: 6 new sentences to translate”, while the French card says
“6 new sentences available from Swedish”. The estimate separates new sentences
from changed ones.

The owner approves the displayed cost, reviews the translated sentences, and
then approves word suggestions derived from the accepted destination sentences.
The existing review screens include editing and accept-all. This updates the
existing dictionary, retaining its membership and settings. It does not create
another copy or independently translate the source's generated word pages.

## Scope and protection

- This first cut follows an existing language-port relationship created by the
  current owner. The same person must still have the required owner access to
  both dictionaries. It does not infer relationships between unrelated copies.
- Only eligible accepted source sentences are considered. Pending, empty,
  archived and unchanged entries are skipped. Changing a source word page alone
  does not retranslate its sentences.
- Adding examples to a small category retains its established translation while
  the original evidence remains valid; it does not retranslate old sentences
  merely because the category now contains more examples.
- The existing incremental port planner detects source changes and protects
  destination entries edited since their last saved port. Corrections, added
  recordings and other destination edits are excluded rather than overwritten.
  Their count appears alongside the estimate when other work is available.
  If only protected entries remain, no paid update is suggested.
- Source snapshots, destination state, category context, languages, model, voice,
  prices and payer are bound to the approval. Changed work requires a fresh
  estimate. Existing save-time checks also catch edits made during generation.
- The usual credit reservation and retry receipt apply. Two tabs cannot start
  two simultaneous updates for the same relationship. Loading pages never
  starts an AI call or reserves credit.
- This is incremental addition/update, not deletion synchronization or merging.
  Existing withdrawal/dependency controls remain responsible for withdrawn
  content. This feature adds no new publication permission.

## Which suggestion appears?

Each dictionary still displays one primary suggestion. Its own membership
requests, reviews, running work, vocabulary and undescribed pictures take
priority. Existing language versions follow those local tasks. If several
versions need work, they are offered one at a time in relationship creation
order.

The source can link to a related version's progress, unfinished review or word
stage before offering another translation. Previous previews must be saved or
discarded on their review screen, including flagged results. There is no
automatic retry, approval or repeated spending.

**Settings → Workflow suggestions** still controls reminders. Turning them off
on the source hides its own notices; the destination can still offer updates.
Turning them off on the destination suppresses that version's update reminders
at both ends. Hidden dictionaries are excluded. The destination must have AI
photo processing enabled and, for a changed target language, supported TTS
enabled. Existing manual Settings workflows remain available.

## Implementation and evidence

The read-only incremental selection is shared with `porting.quote`; guided
updates select sentences only. The same background queue, reviewed sentence
save and destination-vocabulary pipeline are used. No migration, setting,
dependency or static-file change is needed.

See [installation instructions](community-port-guidance-install.md) and the
[verification record](../../experiments/community_dictionary/port-guidance-2026-10-12.md).
Local checks are not AWS acceptance of this extension.
