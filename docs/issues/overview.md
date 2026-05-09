# C-LARA-2 issues overview

_Last updated: 2026-05-09T00:37:55Z_

This document summarizes the current issue registry for quick human review. Canonical machine-readable records remain in `docs/issues/issues/*.json` and `docs/issues/index.json`.

## Recent progress

- **[ISSUE-0002](issues/ISSUE-0002.json)** is closed: supported legacy C-LARA JSON export ZIPs can now be imported directly into normal C-LARA-2 projects.
- **[ISSUE-0010](issues/ISSUE-0010.json)** has been added as a high-priority follow-up to exercise that importer on a representative legacy corpus and then add admin batch-import tooling.
- The focus index now reflects that broad migration support is delivered, while corpus import and batch tooling are the next legacy-migration risk-reduction step.

## Near-term priorities

1. **[ISSUE-0003](issues/ISSUE-0003.json) (P1)** — Add an efficient end-to-end pipeline test runner so quality regressions can be reproduced and measured systematically.
2. **[ISSUE-0010](issues/ISSUE-0010.json) (P1)** — Import a representative legacy C-LARA corpus, gather importer diagnostics from real archives, and add batch import tooling for a folder of legacy ZIPs.
3. **[ISSUE-0006](issues/ISSUE-0006.json) (P2)** — Investigate segmentation_phase_2 token-span failures and rerun-path correctness, preferably using ISSUE-0003 diagnostics where possible.
4. **[ISSUE-0008](issues/ISSUE-0008.json) (P2)** — Write an initial AI-authored C-LARA-2 technical report in LaTeX before the 2026-06-15 target date.
5. **[ISSUE-0005](issues/ISSUE-0005.json) (P2)** — Tune segmentation_phase_1 prompting so prose and poetry segment granularity better matches expected legacy behavior.
6. **[ISSUE-0004](issues/ISSUE-0004.json) (P2)** — Introduce AI-based review gates with a pluggable evaluator architecture after the test-runner foundation is available.
7. **[ISSUE-0007](issues/ISSUE-0007.json) (P2)** — Improve page-image generation by routing prompt construction through an LLM-backed indirection layer.
8. **[ISSUE-0001](issues/ISSUE-0001.json) (P2)** — Support registration of hosted compiled legacy content in C-LARA-2; ISSUE-0010 should provide useful imported legacy material for this work.

## Completed issues

1. **[ISSUE-0002](issues/ISSUE-0002.json) (completed 2026-05-09)** — Support migration of legacy C-LARA projects into C-LARA-2 through direct import of supported legacy JSON export ZIP bundles.
2. **[ISSUE-0009](issues/ISSUE-0009.json) (completed 2026-05-06)** — Auto-regenerate and validate source project bundle stage artifacts before export/import.

## Notes and risks

- **Legacy import coverage:** ISSUE-0010 is intentionally separate from the completed broad migration issue; it is about proving the importer against many real legacy archives and adding operational batch tooling.
- **Batch import safety:** the batch mechanism should reuse the existing single-archive validation/import path, protect against bad ZIPs, and report failures per archive so one malformed legacy project does not block the rest of the batch.
- **Dependency highlights:** ISSUE-0010 depends on completed ISSUE-0002; ISSUE-0004, ISSUE-0005, ISSUE-0006, ISSUE-0007, and ISSUE-0008 all depend directly or indirectly on ISSUE-0003.
