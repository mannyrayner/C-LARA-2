# C-LARA-2 issues overview

_Last updated: 2026-05-06T08:08:30Z_

This document summarizes the current issue registry for quick human review. Canonical machine-readable records remain in `docs/issues/issues/*.json` and `docs/issues/index.json`.

## Recent progress

- **ISSUE-0002** was clarified after human review: legacy migration bundles must preserve media assets, with special attention to human-recorded audio in legacy projects such as the New Caledonia materials.
- No focus-order or priority-band changes were made in this refresh; the audio requirement reinforces the existing **P1** priority of ISSUE-0002 rather than creating a separate issue.

## Near-term priorities

1. **[ISSUE-0003](issues/ISSUE-0003.json) (P1)** — Add an efficient end-to-end pipeline test runner so quality regressions can be reproduced and measured systematically.
2. **[ISSUE-0002](issues/ISSUE-0002.json) (P1)** — Build the legacy C-LARA migration path into importable C-LARA-2 bundles, including preservation and validation of human-recorded audio assets.
3. **[ISSUE-0006](issues/ISSUE-0006.json) (P1)** — Investigate segmentation_phase_2 token-span failures and rerun-path correctness, using ISSUE-0003 diagnostics where possible.
4. **[ISSUE-0005](issues/ISSUE-0005.json) (P2)** — Tune segmentation_phase_1 prompting so prose and poetry segment granularity better matches expected legacy behavior.
5. **[ISSUE-0004](issues/ISSUE-0004.json) (P2)** — Introduce AI-based review gates with a pluggable evaluator architecture after the test-runner foundation is available.
6. **[ISSUE-0007](issues/ISSUE-0007.json) (P2)** — Improve page-image generation by routing prompt construction through an LLM-backed indirection layer.
7. **[ISSUE-0001](issues/ISSUE-0001.json) (P2)** — Support registration of hosted compiled legacy content in C-LARA-2.

## Notes and risks

- **Legacy audio migration risk:** ISSUE-0002 should cover both file inclusion and metadata/reference integrity checks; otherwise imported New Caledonia-style projects could appear structurally migrated while silently losing human-recorded audio.
- **Dependency highlights:** ISSUE-0004 depends on ISSUE-0003; ISSUE-0005 depends on ISSUE-0003 and ISSUE-0004; ISSUE-0006 depends on ISSUE-0003; ISSUE-0007 depends on ISSUE-0003 and ISSUE-0004.
