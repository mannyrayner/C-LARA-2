# Batch picture descriptions — 10 October 2026 (Adelaide)

## Human evidence and requested change

Manny reports that the simpler reading pages work and look much better. This
closes their pending human acceptance; the message did not specify a device or
separate deployment environment. He wants Cathy to be able to supply pictures
without authoring or reviewing sentences. Other contributors may still supply
optional words/translations. He requests an owner batch operation using the
existing sentence-then-vocabulary review workflow, plus dictionary renaming and
home-page sentence/word counts. This follows successful AWS conversion recovery;
it is not evidence of long-run queue stability.

## Prepared implementation

Same-dictionary description mode reuses port estimates, reservations, durable item
claims, bounded dispatch, recovery and both review stages. The first stage uses
image understanding with optional contributor hints; the second uses final
accepted sentences and the existing lemma/sense publisher and shared-word audio.
New sentences retain source dependencies; copied images retain original authors,
controllers and generation provenance. Pending images are included by default and
accepted only when their sentence is saved. Existing sentences and valid previews
are skipped; changed previews can be estimated again. Individual unexpired
picture descriptions take priority. The server's description pause is honoured.

A dedicated rename form changes only the name. Cards count accepted current
sentence/word text, not image placeholders, and reveal no counts to withdrawn or
inactive participants. Migration 0019 changes job metadata/uniqueness only.

Baseline: remote main `15772453d37457b3121c182567985fe9abae33a5`, verified by GitHub
fetch and a fresh clone. No production access or provider requests were used.

## Local verification

- Full Community Dictionaries plus admin-tools regression run: **475 tests pass**
  (includes the initial 20 new batch tests).
- Final focused suite: **26 tests pass**, adding checks for stale previews,
  individual-preview expiry, withdrawn-user count privacy, vocabulary review links,
  server pause and preservation of generated-image provenance.
- `manage.py check`, migration consistency and patch whitespace checks pass.
- Migration 0019 applied successfully in disposable SQLite test/browser databases;
  production PostgreSQL migration is not claimed tested here.
- Mocked-provider Chromium rehearsal passes at 320, 390 and 1280 pixels: rename,
  accepted/pending images, cost approval, sentence/audio preview, Save and next,
  second-stage word editing/bulk acceptance, shared word audio, gallery/counts,
  and no-op repeat estimates. Representative screenshots were visually checked.
  This is not a physical-phone or live model-quality trial.

Human laptop acceptance, live estimates/audio quality, AWS deployment and the
larger Cathy/Manny workflow trial remain next. The fallback queue still loses
waiting in-memory tasks on process restart; the change uses its existing bounded
execution and explicit recovery rather than claiming durable operation.

See [workflow](../../docs/howto/community-batch-descriptions.md) and
[laptop runbook](../../docs/howto/community-batch-descriptions-install.md).
