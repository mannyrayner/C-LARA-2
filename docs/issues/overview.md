# C-LARA-2 issues overview

_Last updated: 2026-05-15T00:41:45Z_

This document summarizes the current issue registry for quick human review. Canonical machine-readable records remain in `docs/issues/issues/*.json` and `docs/issues/index.json`.

## Recent progress

- **[ISSUE-0011](issues/ISSUE-0011.json)** has been updated from a new human suggestion with a concrete Kok Kaper fast path: seed a community picture dictionary from the migrated **50 words in Kok Kaper** project, then generate image→word and word→image flashcards from approved dictionary entries.
- **[ISSUE-0013](issues/ISSUE-0013.json)** now has a dedicated [efficiency and stage-artifact persistence roadmap](../roadmap/efficiency-and-stage-artifacts.md), covering generic stage read/write operations, JSON backward compatibility, faster internal formats, timing instrumentation, project/run format selection, and a trusted admin-only binary migration experiment.
- **[ISSUE-0010](issues/ISSUE-0010.json)** records that C-LARA projects from the Adelaide server can now be imported as C-LARA-2 projects on AWS, but representative corpus triage is still needed.
- **[ISSUE-0003](issues/ISSUE-0003.json)** remains the planned systematic comparison runner; the imported Adelaide corpus and the known `The Dragon and the Cube` first-page corruption should become concrete fixtures for it.

## Near-term priorities

1. **[ISSUE-0003](issues/ISSUE-0003.json) (P1)** — Add an efficient end-to-end pipeline test runner; first target legacy-vs-C-LARA-2 comparisons over the imported corpus from ISSUE-0010, with AI-assisted gross-difference review where exact matching is inappropriate.
2. **[ISSUE-0011](issues/ISSUE-0011.json) (P1, active, deadline 2026-06-01)** — Implement the Kok Kaper image-game fast path: register/import **50 words in Kok Kaper** as a community picture dictionary, then adapt flashcards for image→word and word→image play using approved same-dictionary distractors.
3. **[ISSUE-0010](issues/ISSUE-0010.json) (P1)** — Import and triage a representative legacy C-LARA corpus from the Adelaide material now reaching C-LARA-2 on AWS; include known divergence checks such as `The Dragon and the Cube` first-page corruption before growing into multi-bundle batch import with heartbeat progress.
4. **[ISSUE-0013](issues/ISSUE-0013.json) (P1)** — Implement the efficiency roadmap: centralize stage-artifact read/write operations, benchmark JSON against faster formats, record read/write timings, and include a trusted admin-only binary/pickle-like migration-format experiment if it speeds the one-off Adelaide migration.
5. **[ISSUE-0008](issues/ISSUE-0008.json) (P1, deadline 2026-06-15)** — Draft the long C-LARA-2 internal technical report and use it as the source for the accepted EuroCALL 2026 paper and possible ALTA 2026 submission.
6. **[ISSUE-0006](issues/ISSUE-0006.json) (P2)** — Investigate segmentation_phase_2 token-span failures and rerun-path correctness, preferably using ISSUE-0003 diagnostics where possible.
7. **[ISSUE-0005](issues/ISSUE-0005.json) (P2)** — Tune segmentation_phase_1 prompting so prose and poetry segment granularity better matches expected legacy behavior.
8. **[ISSUE-0004](issues/ISSUE-0004.json) (P2)** — Introduce AI-based review gates with a pluggable evaluator architecture after the test-runner foundation is available.
9. **[ISSUE-0007](issues/ISSUE-0007.json) (P2)** — Improve page-image generation by routing prompt construction through an LLM-backed indirection layer.
10. **[ISSUE-0001](issues/ISSUE-0001.json) (P2)** — Support registration of hosted compiled legacy content in C-LARA-2; use the same AWS staging/rsync runbook and the imported C-LARA corpus as complementary test material.
11. **[ISSUE-0012](issues/ISSUE-0012.json) (P2)** — Adjust project creation defaults for AI text generation and top page-image placement.

## Completed issues

1. **[ISSUE-0002](issues/ISSUE-0002.json) (completed 2026-05-09)** — Support migration of legacy C-LARA projects into C-LARA-2 through direct import of supported legacy JSON export ZIP bundles.
2. **[ISSUE-0009](issues/ISSUE-0009.json) (completed 2026-05-06)** — Auto-regenerate and validate source project bundle stage artifacts before export/import.

## Notes and risks

- **Kok Kaper fast path:** ISSUE-0011 should avoid over-generalizing first. The first valuable implementation is a narrow project-to-picture-dictionary seed import for **50 words in Kok Kaper**, preserving approved word/image pages and adding only the metadata needed for dictionary ownership, readiness, game eligibility, and provenance.
- **Image-game distractors:** for ISSUE-0011, distractors should come from the same approved picture dictionary where possible; AI should rank/filter curated candidates rather than inventing unreviewed answer options for the first community-facing version.
- **Legacy corpus dependency:** ISSUE-0003 now depends on ISSUE-0010 for its first high-value evaluation corpus; the runner can be designed earlier, but legacy-vs-C-LARA-2 comparisons need enough imported material to be useful.
- **Known import divergence:** `The Dragon and the Cube`, a long English story with Chinese glosses, currently has a corrupted first page after import/compilation. Capture this as a concrete fixture for ISSUE-0010 triage and ISSUE-0003 comparison tooling.
- **Stage-artifact abstraction:** ISSUE-0013 should first centralize read/write operations behind a format-independent API so pipeline logic is not tied to `Path.read_text`/`json.loads` or `Path.write_text`/`json.dumps`.
- **Trusted one-off migration format:** ISSUE-0013 may use pickle or a similar binary representation for the Adelaide migration handoff because the source is trusted and the operation is admin-only/one-off. Keep this separate from ordinary user uploads and from long-term source-bundle interchange.
- **Measurement before defaults:** the efficiency roadmap calls for read/write timing and artifact-size measurements before changing defaults globally. JSON must remain readable for backward compatibility and available for human inspection, source-bundle compatibility, debugging, reproducibility, and untrusted/user-supplied bundles.
- **Gross-difference review:** exact comparison is inappropriate for stages like translation and glossing, so ISSUE-0003 should support AI-assisted judgement of whether differences are problematic, while still using deterministic structural checks where possible.
- **Segmentation triage:** ISSUE-0003 should at least support ISSUE-0006 by detecting clear segmentation_phase_2 token-span failures in legacy-vs-C-LARA-2 comparisons.
- **Compiled LARA corpus staging:** ISSUE-0001 should reuse the same large-folder transfer runbook, but target `/srv/c-lara/legacy-compiled/lara/` rather than the C-LARA source-bundle library so compiled hosted content is not mixed with importable C-LARA source bundles.
- **Service-environment visibility:** ISSUE-0010 records that `export C_LARA_LEGACY_BUNDLE_LIBRARY_ROOT=...` in an SSH shell is not enough for the website; configure the Gunicorn/Django service environment, restart services, and use the admin-only diagnostics panel on `projects/import-zip/` to confirm the running web process sees the setting.
- **Writing scope:** ISSUE-0008 should use the internal report as the master source, then, subject to co-author approval, split it into a user-facing EuroCALL 2026 paper and an implementor-facing ALTA 2026 paper to avoid duplicated effort.
