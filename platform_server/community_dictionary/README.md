# Community dictionary app

First functional prototype: invited dictionaries built from photographs, human
recordings, discussion and review, with partnership request queues.

- [Specification](../../docs/roadmap/community-dictionary.md)
- [Setup, deployment, recovery and phone checks](../../docs/howto/community-dictionary.md)
- [Experiment evidence](../../experiments/community_dictionary/iteration-001.md)

The app owns its models, migrations, permissions, media views, templates and small
JavaScript/CSS interface. Its route is `/community-dictionaries/`. It reuses
C-LARA authentication/accounts and database/static infrastructure. It does not call
the project compilation pipeline, AI clients, task queue or existing dictionary
commands. Existing `projects.PictureDictionary` records are tied to compiled
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

The export contains all app records except submission receipts and includes
contributor-ID/username mapping. Operational backups need the shared user database
and private files too. Future TTS/image services should enter through an explicit
adapter and create reviewable contributions with provenance. No AI generation or
practice functionality is included here.
