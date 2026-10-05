# Community dictionary app

Manny's first Swedish/English → French/English laptop port mostly works. The
[follow-up](../../docs/howto/community-language-porting.md) adds contextual category translation,
stronger TTS language instructions and editable uncertain results, including old
blocked previews. Updates can repair earlier generated outputs while protecting
human corrections. 257 app tests, six shared audio unit tests and a real-queue
browser rehearsal pass. Human retesting and AWS porting deployment remain pending.


Manny reports the practice/multiple-choice release deployed and working on AWS on
4 October. This supersedes its earlier pending-deployment status. Exact deployed
SHA/device matrix and broader learner/community feedback remain unrecorded.

Previous UX follow-up: [Settings and text-first photos](../../docs/howto/community-settings-and-photos.md).
Manny reports the image-generation increment works on his laptop; configuration
now has its own tab and entries explicitly offer camera/upload. 189 app tests
and the updated browser rehearsal passed; Manny subsequently accepted and deployed this release.

Preceding increment: [optional AI pictures](../../docs/howto/community-image-generation.md),
3 October. Off by default; editors approve a shared style, preview a generated
picture, then save it as an ordinary contribution. Private media, provenance and
withdrawal dependencies are preserved. A broad human laptop success report is recorded; AWS deployment is reported successful; systematic quality trials remain pending.

Current withdrawal UX: [dictionary-wide participation](../../docs/howto/community-participation.md).
A member can view, withdraw all content with confirmation, or restore all content
and rejoin. Retained material is read-only; shared browsing and contribution are
blocked while withdrawn. Owner handover is atomic with withdrawal. This supersedes
the individual contribution/private-dictionary interfaces described in older notes
below. Migrations 0008/0009 establish the model and restore the authorised laptop
experiments. 156 tests and a browser rehearsal pass. Manny reports successful
laptop acceptance; [AWS deployment](../../docs/howto/community-participation-aws.md)
and a withdrawal/restoration trial are now reported successful. See the
[server record](../../experiments/community_dictionary/participation-aws-2026-10-02.md)
for operational incidents, recovery and evidence limits.


First functional prototype: invited dictionaries built from photographs, human
recordings, discussion and review, with partnership request queues.

- [Specification](../../docs/roadmap/community-dictionary.md)
- [Setup, deployment, recovery and phone checks](../../docs/howto/community-dictionary.md)
- [Experiment evidence and current status](../../experiments/community_dictionary/README.md)
- [AWS and first phone trial](../../experiments/community_dictionary/aws-phone-trial-2026-09-25.md)
- [Proposed AI media and maintenance increment](../../docs/roadmap/community-dictionary-ai-and-maintenance.md)

The prototype is on `main` and deployed on the shared AWS server. On 25 September
2026 Manny reported successful laptop use and a physical-phone contribution
trial with Cathy. This is initial human acceptance on one unrecorded phone/browser,
not comprehensive mobile validation. Remaining production settings and the
invited Icelandic trial are recorded in the current evidence above.

The app owns its models, migrations, permissions, media views, templates and small
JavaScript/CSS interface. Its route is `/community-dictionaries/`. It reuses
C-LARA authentication/accounts and database/static infrastructure. It does not call
the project compilation pipeline or existing dictionary commands. Language porting
now uses the shared Django-Q adapter for background work.
The optional Learn from a photo flow calls OpenAI through a scoped adapter and
reuses C-LARA account/key and token-accounting components. Existing `projects.PictureDictionary` records are tied to compiled
projects and require written entries, so this contribution workflow uses separate
models. There is no automatic synchronization with the older dictionary representation.

Uploads live under `COMMUNITY_DICTIONARY_MEDIA_ROOT`, outside public media/static
roots, and are read only through membership-checked views. Photos are re-encoded
with Pillow. Audio containers are checked and stored without transcoding. JavaScript
uses browser MediaRecorder and IndexedDB; there is no frontend build step or CDN.

Text revisions are immutable contribution snapshots. The entry stores its accepted
presentation and version number. Acceptance checks that version under an entry
lock. Media candidates keep separate contributor credits. Submission receipts make
normal upload retries idempotent; the receipt and database writes commit together.
A failed transaction removes newly written files, although a process crash can
leave an unreferenced file requiring later operator cleanup. SQLite serializes
writes; PostgreSQL provides row locks. High-contention/load testing remains future work.

The export excludes submission receipts and private learning drafts, and includes
contributor-ID/username mapping. Operational backups need the shared user database
and private files too. Future TTS/image services should enter through an explicit
adapter and create reviewable contributions with provenance. The optional image-generation implementation is described above; the first practice games are now implemented as described above. The 28 September patch adds optional single-object
photo analysis, confirmation, a device-voice preview and saving as reviewable contributions.
See [photo learning](../../docs/howto/community-photo-learning.md) for setup and trial
boundaries. Manny reports a successful live laptop horse-identification trial on
28 September; Manny reports a successful AWS update on 29 September; detailed physical-phone
acceptance of the AI flow remains unrecorded.
Device speech remains an unsaved preview. The later
[entry-photo/audio patch](../../docs/howto/community-entry-photo-audio.md) adds
interpretation of an existing saved image and separately enabled persistent TTS
with private previews and contribution review. Manny reports this is working.
The [defaults and named-voice follow-up](../../docs/howto/community-voices-and-defaults.md)
adds visible, checked AI options to new-dictionary forms and remembers each user's
voice choice per dictionary. Existing settings and recordings are preserved. Its
64 mocked-provider app tests and Chromium phone-viewport rehearsals pass; live
listening and physical-phone acceptance remain separate work. Commenting-language
lookup remains deferred until discussion with Sophie.

The latest [current-audio repair](../../docs/howto/community-current-audio.md)
responds to Manny's successful voice-menu trial and report of outdated TTS.
Normal playback and partnership previews exclude synthetic recordings whose
source wording or language no longer matches; history retains them with a label.
Human recordings remain available. That increment had 67 passing tests.
Manny confirms the repair on his laptop and subsequently reports successful
AWS update on 29 September.

The [30 September saving/invitation patch](../../docs/howto/community-saving-and-invitations.md)
responds to Cathy’s use: top/bottom Save with explicit permission, clearer local
draft versus server-save status, navigation protection, and owner-only account
selection. It has 70 passing app tests and controlled Chromium browser checks;
Manny subsequently accepted the related password recovery and pronunciation-saving/
logout changes on his laptop. These combined changes are on main at `b945623`.

The [1 October manual picture/word links](../../docs/howto/community-picture-word-links.md)
add `ImageWordLink` in migration 0005, picture/word browse modes, inline audio and
translation disclosure, and word galleries. Original associations stay implicit;
extra links point to specific accepted pictures and existing word entries in the
same dictionary. Export version 2 includes them. All 95 app tests and a controlled
browser rehearsal pass. Manny now confirms first-time laptop success with the
sofa/cat example and subsequently reports successful AWS installation and exploration.
A new physical-phone matrix is not claimed.

The [contribution-control revision](../../docs/howto/community-contribution-control.md)
adds separate text-field provenance, retained private collections, withdrawal and
explicit sharing, inactive memberships and optional two-coordinator decisions.
Migrations 0006/0007 and a database backup are required. 118 tests and a Chromium
phone/desktop rehearsal pass. Manny subsequently reports successful installation,
restart and new-entry creation, with a My contributions display issue. The
[entry-context follow-up](../../docs/howto/community-contributions-by-entry.md)
addresses it using complete entry cards, own-material selection and grey reference
components. It has 128 passing app tests and a Chromium phone/desktop rehearsal;
Manny now confirms laptop testing of My contributions works as intended and
requests check-in. AWS/physical-phone validation of this increment remains pending;
his report does not specify separate governance/withdrawal acceptance cases.

The [2 October immediate-restoration follow-up](../../docs/howto/community-immediate-restore.md)
removes the confirmation step from Share back to the original dictionary. Unchanged,
previously accepted material voluntarily withdrawn by its custodian is visible
immediately; new/unreviewed, rejected or moderator-returned material needs review.
Newer shared text, custody, private copies and access checks remain protected.
148 app tests and a Chromium rehearsal pass, with no migration. Manny requested
this simplification after testing the first shortcut; human acceptance and new
AWS/physical-phone validation of this follow-up remain pending.

## Pronunciation follow-up (5 October 2026)

The prepared [homograph guidance and bounded silence retry](../../docs/howto/community-tts-guidance.md) increment
includes review warnings, explicit cost accounting and additive migration 0013.
275 app tests pass. Manny now reports successful chat/lit generation and a successful
small-dictionary laptop test. The local startup notes now retain `--insecure` for
static files with `DEBUG=False`. Manny subsequently reports AWS conversion/review
of 61 French entries, with four initially unsatisfactory recordings; two remain
unresolved after his local remedies. A review-UX follow-up adds next-item navigation,
saved-word labels and private attention flags (migration 0014; 286 passing tests),
still awaiting human acceptance.

See [review workflow and installation notes](../../docs/howto/community-port-review.md).
