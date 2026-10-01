# Community dictionary app

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
the project compilation pipeline, task queue or existing dictionary commands.
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
adapter and create reviewable contributions with provenance. Image generation and a practice system remain deferred. The 28 September patch adds optional single-object
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
sofa/cat example; deployment and a fuller server/phone trial are next.
