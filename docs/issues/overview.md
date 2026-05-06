# C-LARA-2 issues overview

_Last updated: 2026-05-06T13:31:10Z_

This document summarizes the current issue registry for quick human review. Canonical machine-readable records remain in `docs/issues/issues/*.json` and `docs/issues/index.json`.

## Active focus order (from `index.json`)

1. **[ISSUE-0003](issues/ISSUE-0003.json) (P1)** — Add efficient end-to-end pipeline test runner for systematic quality checks.
2. **[ISSUE-0002](issues/ISSUE-0002.json) (P1)** — Support migration of legacy C-LARA projects into importable C-LARA-2 bundles.
3. **[ISSUE-0006](issues/ISSUE-0006.json) (P1)** — Investigate segmentation_phase_2 token-span failures and rerun-path correctness.
4. **[ISSUE-0008](issues/ISSUE-0008.json) (P1)** — Write an initial AI-authored C-LARA-2 technical report in LaTeX.
5. **[ISSUE-0005](issues/ISSUE-0005.json) (P2)** — Tune segmentation_phase_1 prompting to improve segment granularity by genre.
6. **[ISSUE-0004](issues/ISSUE-0004.json) (P2)** — Introduce AI-based review gates for phase outputs with extensible evaluator architecture.
7. **[ISSUE-0007](issues/ISSUE-0007.json) (P2)** — Use LLM prompt-construction indirection for page-image generation prompts.
8. **[ISSUE-0001](issues/ISSUE-0001.json) (P2)** — Support hosted compiled legacy content registration in C-LARA-2.

## Completed issues (most recent first)

1. **[ISSUE-0009](issues/ISSUE-0009.json) (completed 2026-05-06)** — Auto-regenerate and validate source project bundle stage artifacts before export/import.

## Priority distribution (active issues)

- **P1:** [ISSUE-0002](issues/ISSUE-0002.json), [ISSUE-0003](issues/ISSUE-0003.json), [ISSUE-0006](issues/ISSUE-0006.json), [ISSUE-0008](issues/ISSUE-0008.json)
- **P2:** [ISSUE-0001](issues/ISSUE-0001.json), [ISSUE-0004](issues/ISSUE-0004.json), [ISSUE-0005](issues/ISSUE-0005.json), [ISSUE-0007](issues/ISSUE-0007.json)
- **P3:** none
- **P0:** none

## Dependency highlights

- [ISSUE-0008](issues/ISSUE-0008.json) has no tracked issue dependencies, but has a target deadline of 2026-06-15 for a usable initial LaTeX report.
- [ISSUE-0004](issues/ISSUE-0004.json) depends on [ISSUE-0003](issues/ISSUE-0003.json).
- [ISSUE-0005](issues/ISSUE-0005.json) depends on [ISSUE-0003](issues/ISSUE-0003.json) and [ISSUE-0004](issues/ISSUE-0004.json).
- [ISSUE-0006](issues/ISSUE-0006.json) depends on [ISSUE-0003](issues/ISSUE-0003.json).
- [ISSUE-0007](issues/ISSUE-0007.json) depends on [ISSUE-0003](issues/ISSUE-0003.json) and [ISSUE-0004](issues/ISSUE-0004.json).
