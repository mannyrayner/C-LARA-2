# Community dictionary app

## Reading-page cleanup — 9 October 2026

Manny reports successful completion of the resumed AWS French conversion and
consistent sentence/word links. The [reading-page revision](../../docs/howto/community-entry-options.md)
merges sentence words and picture tags, keeps completion actions visible, and
puts editing/history/pronunciation checks under Show more options on sentence
and word pages. No migration or static asset change. Human layout acceptance
remains pending. The earlier pending AWS recovery outcome below is superseded
by this report, without claiming long-run operational stability.

## Deployment incident — 9 October 2026

Manny reports initial laptop/AWS use of the two-stage release, followed by
site-wide HTTP 500s. Diagnostics confirm RDS connection exhaustion, migration
0018 applied, and the local thread-based queue selected on AWS. A subsequent
census confirms connection availability recovered. The
[queue recovery patch](../../docs/howto/community-queue-recovery.md) adds explicit
task connection cleanup, a per-process concurrency bound, private error logging
and a read-only deployment probe. Production verification remains pending;
pause new large AI jobs until the recovery checks pass. Earlier pending laptop
acceptance below is superseded by this report, not by a claim of AWS stability.

## Current follow-up — sentence-first vocabulary, 9 October 2026

Manny reports successful AWS conversion of the 150-entry Swedish dictionary, but
independently translated words can disagree with the translated sentence. The
[new two-stage workflow](../../docs/howto/community-two-stage-porting.md) reviews sentences first, then derives shared
word pages from their final wording with the normal capture/MWE logic. Both stages
support bulk acceptance; vocabulary review shows sentence and picture, and edits
are tracked. Destination Settings can repair an existing version without repeating
sentence translation. Additive migration 0018 and 410 mocked-provider app tests;
local browser checks at phone/desktop widths. Live acceptance of this follow-up is
pending. The 8 October installation and recovery guidance below is historical and
superseded by the new runbook.

## Latest follow-up — sentence language ports, 8 October 2026

Manny reports the image-copy workflow works and a Swedish dictionary with over
150 image-associated sentence entries, roughly 90% accepted without edits. His
French version appeared empty. The old port selected words only; results also
require explicit review/save before appearing in the destination. The
[prepared sentence extension](../../docs/howto/community-sentence-porting.md) preserves sentence
identity, images, sentence speech and vocabulary links, keeps prior word results
usable, and makes preview-versus-saved status prominent. No new migration.
391 app tests and a mocked Chromium rehearsal support the next trial; live
translation/phone/production acceptance of this follow-up remains pending.
Earlier pending image-copy acceptance below is superseded by Manny's new report.

## Latest follow-up — image-only copy review, 8 October 2026

Manny reports the three description modes work. The next
[prepared repair](../../docs/howto/community-image-copy-review.md) offers Accepted/Awaiting review/Both copying (default Both),
creates pending copies and lets owners/editors accept a picture by confirming its
description. Next picture includes pending work; original states and custody remain.
376 tests and a mocked browser rehearsal pass; no new migration. Human acceptance
of this follow-up remains pending. Earlier pending AI-mode acceptance is superseded.

## Latest update — three description modes, 8 October 2026

Manny confirms visibility works and requests Cathy's preferred AI-description route.
The prepared [unified workflow](../../docs/howto/community-ai-descriptions.md) offers Type, Speak and Suggest a description
on equal terms, remembers the choice and reuses the existing review/save/audio flow.
365 app tests and a mocked Chromium desktop/mobile-viewport rehearsal pass. No new
migration; human testing of this increment is next. WordPress/email recovery is
explicitly on hold. Earlier pending visibility acceptance is superseded; its test
environment was not specified.

## Current update — 5 October 2026

The faster port-review release is now reported accepted on the laptop and deployed
on AWS. Manny reports a positive 61-entry Swedish/English to German/English trial,
with “curry” the one pronunciation issue he noticed, subject to his limited German
listening confidence. See the [trial record](../../experiments/community_dictionary/german-port-review-2026-10-05.md)
and [French stakeholder draft](../../docs/publications/community_dictionaries_update_fr/README.md).
Earlier pending-acceptance/deployment statements below are historical.

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

## Optional picture descriptions (7 October 2026)

Migration 0015 adds an off-by-default picture + spoken/typed sentence workflow,
bilingual meaning confirmation, immediately shared sentence/word entries, background
TTS, revision-aware cross-links, and a shared Needs attention/editor-check queue.
Source custody and withdrawal dependencies are retained. See
[`community-picture-descriptions.md`](../../docs/howto/community-picture-descriptions.md)
and the [implementation evidence](../../experiments/community_dictionary/picture-capture-2026-10-07.md).
Live API/laptop/phone acceptance of this increment is still pending.


7 October follow-up: [picture-description expressions, editable vocabulary and image-only test copies](../../docs/howto/community-picture-descriptions.md). Manny reports a faster laptop workflow; the correction patch has 324 passing tests and now has reported small-Swedish-dictionary laptop acceptance. AWS deployment is now reported, with the first three examples exposing a redundant source card and a failed sentence TTS request; further MWE refinement remains deferred.

7 October AWS follow-up: [browsing and sentence-audio fixes](../../experiments/community_dictionary/picture-capture-aws-fixes-2026-10-07.md), with 334 passing app tests and simulated Chromium progress/playback checks. New live acceptance and the original provider failure diagnosis remain pending.

7 October later follow-up: [audio recovery](../../docs/howto/community-audio-recovery.md) refreshes shared recordings when returning to an example and suppresses obsolete timeout notices. 338 tests pass; Manny reports very positive AWS laptop/Chrome use in both languages/modalities. On 8 October he confirms missing audio is now correctly generated; Cathy’s trial remains unreported.

8 October follow-up: [owner-adjustable picture-description allowance](../../docs/howto/community-picture-description-limits.md), with local daily-cost preview and explicit confirmation under Settings. Default ten shared attempts per rolling 24 hours; usage survives changes. Additive migration 0016; 349 app tests and mocked Chromium checks pass. Manny subsequently reports it appeared to work; the environment is unspecified.

8 October next prepared change: [Visible/Hidden dictionaries](../../docs/howto/community-dictionary-visibility.md), an owner-only Settings control to move historical versions out of the main list. Hidden dictionaries stay accessible to their existing audience through a collapsed section, preserving contribution rights and linked images. Migration 0017; 356 tests and an owner/member browser rehearsal pass. New visibility acceptance remains pending.
