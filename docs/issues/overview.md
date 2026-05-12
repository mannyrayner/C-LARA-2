# C-LARA-2 issues overview

_Last updated: 2026-05-11T23:13:22Z_

This document summarizes the current issue registry for quick human review. Canonical machine-readable records remain in `docs/issues/issues/*.json` and `docs/issues/index.json`.

## Recent progress

- **[ISSUE-0003](issues/ISSUE-0003.json)** has been refined: the first useful pipeline test runner should use the representative legacy corpus from **[ISSUE-0010](issues/ISSUE-0010.json)** as an evaluation set, comparing C-LARA-2 reruns against imported legacy outputs.
- **[ISSUE-0010](issues/ISSUE-0010.json)** is now active: a first cut of the metadata aggregation command and admin-only searchable Import from ZIP view has been implemented, and the Adelaide legacy folder has been uploaded to AWS after resolving the SSH security-rule and EC2 `.pem` key requirements; multi-bundle batch import remains future work.
- **[ISSUE-0008](issues/ISSUE-0008.json)** remains a P1 writing/reporting task, with CodePrism as the closest known comparator and a proposed EuroCALL/ALTA split.
- **[ISSUE-0001](issues/ISSUE-0001.json)** now has a concrete AWS staging plan for the compiled legacy LARA corpus: copy `/home/LARALegacyFromServer/` to a sister server directory such as `/srv/c-lara/legacy-compiled/lara/` using the same `.pem`-based `rsync` pattern as the Adelaide upload.

## Near-term priorities

1. **[ISSUE-0003](issues/ISSUE-0003.json) (P1)** — Add an efficient end-to-end pipeline test runner; first target legacy-vs-C-LARA-2 comparisons over the imported corpus from ISSUE-0010, with AI-assisted gross-difference review where exact matching is inappropriate.
2. **[ISSUE-0011](issues/ISSUE-0011.json) (P1, deadline 2026-06-01)** — Agree and implement a picture-dictionary-centred image-game workflow, starting with image-to-word and word-to-image flashcards for Kok Kaper community review sessions.
3. **[ISSUE-0010](issues/ISSUE-0010.json) (P1)** — Import a representative legacy C-LARA corpus from the now-uploaded AWS Adelaide folder, starting by building server-side metadata, configuring the import view, and importing representative projects before growing into multi-bundle batch import with heartbeat progress.
4. **[ISSUE-0008](issues/ISSUE-0008.json) (P1, deadline 2026-06-15)** — Draft the long C-LARA-2 internal technical report and use it as the source for the accepted EuroCALL 2026 paper and possible ALTA 2026 submission.
5. **[ISSUE-0006](issues/ISSUE-0006.json) (P2)** — Investigate segmentation_phase_2 token-span failures and rerun-path correctness, preferably using ISSUE-0003 diagnostics where possible.
6. **[ISSUE-0005](issues/ISSUE-0005.json) (P2)** — Tune segmentation_phase_1 prompting so prose and poetry segment granularity better matches expected legacy behavior.
7. **[ISSUE-0004](issues/ISSUE-0004.json) (P2)** — Introduce AI-based review gates with a pluggable evaluator architecture after the test-runner foundation is available.
8. **[ISSUE-0007](issues/ISSUE-0007.json) (P2)** — Improve page-image generation by routing prompt construction through an LLM-backed indirection layer.
9. **[ISSUE-0001](issues/ISSUE-0001.json) (P2)** — Support registration of hosted compiled legacy content in C-LARA-2; start by staging `/home/LARALegacyFromServer/` on AWS under a sister directory to the C-LARA bundle library, then use ISSUE-0010 imported material as complementary test content.
10. **[ISSUE-0012](issues/ISSUE-0012.json) (P2)** — Adjust project creation defaults for AI text generation and top page-image placement.

## Completed issues

1. **[ISSUE-0002](issues/ISSUE-0002.json) (completed 2026-05-09)** — Support migration of legacy C-LARA projects into C-LARA-2 through direct import of supported legacy JSON export ZIP bundles.
2. **[ISSUE-0009](issues/ISSUE-0009.json) (completed 2026-05-06)** — Auto-regenerate and validate source project bundle stage artifacts before export/import.

## Notes and risks

- **Legacy corpus dependency:** ISSUE-0003 now depends on ISSUE-0010 for its first high-value evaluation corpus; the runner can be designed earlier, but legacy-vs-C-LARA-2 comparisons need enough imported material to be useful.
- **Gross-difference review:** exact comparison is inappropriate for stages like translation and glossing, so ISSUE-0003 should support AI-assisted judgement of whether differences are problematic, while still using deterministic structural checks where possible.
- **Segmentation triage:** ISSUE-0003 should at least support ISSUE-0006 by detecting clear segmentation_phase_2 token-span failures in legacy-vs-C-LARA-2 comparisons.
- **Adelaide corpus usability:** ISSUE-0010 now has a first-cut metadata aggregation command, searchable admin import view, and verified AWS upload of the legacy folder. Preserve the operational lesson that large corpus transfer may require both EC2 inbound SSH-rule changes and explicit `.pem` key usage. The next step is to build metadata on AWS and import representative projects.
- **Compiled LARA corpus staging:** ISSUE-0001 should reuse the same large-folder transfer runbook, but target `/srv/c-lara/legacy-compiled/lara/` rather than `/srv/c-lara/legacy-bundles/adelaide/` so compiled hosted content is not mixed with importable C-LARA source bundles.
- **Metadata-build permissions:** ISSUE-0010 also records that Step 3 must be run by a user that can write the metadata file, normally `ubuntu` on AWS; if permissions were repaired for `ubuntu:www-data` but the active shell is another user, use `sudo -u ubuntu /srv/C-LARA-2/.venv/bin/python manage.py build_legacy_bundle_metadata ...` and inspect path ownership with `namei -l`.
- **Service-environment visibility:** ISSUE-0010 now also records that `export C_LARA_LEGACY_BUNDLE_LIBRARY_ROOT=...` in an SSH shell is not enough for the website; configure the Gunicorn/Django service environment, restart services, and use the admin-only diagnostics panel on `projects/import-zip/` to confirm the running web process sees the setting.
- **Adelaide source.zip shape:** ISSUE-0010 now records that real Adelaide directories use sibling `metadata.json` plus `source.zip`; server-side import combines those in memory when `source.zip` has flat or single-root `annotated_text.json` but no internal metadata, instead of treating the inner ZIP as a native C-LARA-2 source bundle.
- **Import trace for remaining failures:** ISSUE-0010 now surfaces an `Import trace` on the missing-project-metadata error path, including selected path, source ZIP path, sidecar metadata status, injected metadata entries, annotated/metadata ZIP entries, detected legacy root, and first ZIP entries.
- **Legacy project_dir source.zip support:** ISSUE-0010 now also handles the traced Adelaide layout with root `metadata.json`, `project_dir/metadata.json`, and text/media artifacts under `project_dir/*`, preserving the original tree and creating C-LARA-2 stage artifacts from the best available plain text.
- **Writing scope:** ISSUE-0008 should use the internal report as the master source, then, subject to co-author approval, split it into a user-facing EuroCALL 2026 paper and an implementor-facing ALTA 2026 paper to avoid duplicated effort.
