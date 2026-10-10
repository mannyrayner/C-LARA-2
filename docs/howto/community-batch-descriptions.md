# Add missing sentences to dictionary pictures

Owners can use **Settings → Add missing sentences** to process pictures in the
current dictionary. This is optional AI-supported functionality. Enable Picture
descriptions, Learn from a photo, and supported spoken audio first.

1. Choose accepted pictures, pictures awaiting review, or both (the default), and
   a voice. Request an estimate; this makes no provider calls.
2. Review the cost and outbound-data permission, then approve. The bounded job
   queue generates a sentence, a commenting-language translation and sentence
   audio for each eligible picture.
3. Review/edit each suggestion with **Save and next**, flag it for later, discard
   it, or **Accept all remaining suggestions**. Bulk acceptance skips unclear,
   flagged, failed or changed inputs. Confirmation is not expert linguistic review.
4. Choose **Build vocabulary from accepted sentences**. Estimate and approve this
   separate stage; it uses the final accepted wording and picture. Review words
   beside their sentence/picture or accept the ready suggestions together. The
   existing vocabulary publisher shares pages by lemma and meaning and generates
   missing word audio. Sentence recordings remain in place.

A contributor can simply upload pictures and stop. Existing accepted words,
translations and categories, plus the latest pending proposal for each field,
are optional hints to the description model. They are not overwritten or silently
accepted as text. Saving a sentence also accepts its pending source picture;
the copied picture retains its contributor and withdrawal controller. New text
and audio record their AI origin and the owner who accepted them, with dependency
links to the actual picture and hints. Withdrawal invalidates private previews
and removes dependent shared material through the existing participation rules.

The job creates sentence entries **inside the existing dictionary**. It creates
no new dictionary, changes no language, and does not turn existing word entries
into sentences. Multiple distinct pictures on one entry can have separate jobs.
An accepted or pending sentence already linked by picture-copy provenance counts
as described. Single-word labels do not. Unlabelled original picture cards use
the existing described-picture hiding rule; original discussion stays available.

## Repeat runs and recovery

The start page lists recent jobs. Valid unsaved suggestions remain available;
a repeat estimate skips them and existing sentences, picking up new pictures.
Stale suggestions are discarded before estimating their changed inputs again.
In-progress, unexpired individual picture descriptions also take priority.
Finish or cancel a running batch before starting another. A running vocabulary
job may be waiting for review before it can settle, rather than waiting for AI.
Only sentences created by this batch workflow enter its vocabulary stage;
unchanged completed vocabulary is skipped. Language-port vocabulary continues to
work separately and can coexist on the same dictionary.

The shared port dispatcher retains bounded fan-out and committed per-item claims.
Duplicate delivery and repeated approval do not repeat paid calls. **Resume
waiting work** handles interrupted queues; attempts running for over 15 minutes
are abandoned with an unknown-cost warning, not blindly retried. The fallback
queue remains in-memory and per-process bounded; this does not install a durable
broker. Finish active work before restarting services.

Each stage has its own estimate/approval and credit reservation. Insufficient
C-LARA credit blocks approval. Personal provider balances cannot be checked.
The estimate uses configured prices, image/text allowances and sentence/word
speech estimates; it is not a provider quotation. Unused reserved credit is
returned at settlement. The individual-description daily count is separate from
this explicitly cost-approved batch. No original audio is sent to the provider.

Editing a sentence before accepting it prevents saving audio for the old wording;
use **Create audio** on the saved entry to obtain its revised recording. A failed
sentence recording does not prevent accepting the sentence. Word-audio failures
can likewise be retried from their word pages.

## Name and counts

**Settings → Rename dictionary → Save name** changes only its name. The owner can
still edit the name through the existing general settings form. Top-level cards
show counts of nonarchived sentences and word pages with accepted current target
text. Blank image holders and text awaiting review are not counted. Counts are
not shown to withdrawn or inactive participants who cannot browse the dictionary.

## Implementation and verification

Migration `0019_batch_descriptions` adds description-job identity, input options,
source-image and saved-entry references. It adjusts the port-item uniqueness
constraint so normal ports remain unique by run/source entry while description
items are unique by run/source image. It does not rewrite dictionary content or
move files. No dependency or static-asset changes are needed.

`batch_descriptions.py` supplies eligibility, snapshots, a sentence-only image
prompt and publication. `LanguagePort.target` selects the existing source
for this mode; the destination OneToOne relation for genuine language ports is
unchanged. The queue, usage accounting, recovery, review forms and vocabulary
stages are shared. `batch_views.py` supplies the owner controls.

See `tests/test_batch_descriptions.py` and the disposable browser rehearsal in
`experiments/community_dictionary/batch_descriptions_browser_rehearsal.py`.
Provider calls are mocked in automated tests. Live model quality, Windows and
physical-phone acceptance require the owner's trial.
