# C-LARA-2 issues overview

_Last updated: 2026-05-09T00:00:00Z_

This document summarizes the current issue registry for quick human review. Canonical machine-readable records remain in `docs/issues/issues/*.json` and `docs/issues/index.json`.

## Active focus order (from `index.json`)

1. **[ISSUE-0003](issues/ISSUE-0003.json) (P1)** — Add efficient end-to-end pipeline test runner for systematic quality checks.
2. **[ISSUE-0006](issues/ISSUE-0006.json) (P2)** — Investigate segmentation_phase_2 token-span failures and rerun-path correctness.
3. **[ISSUE-0008](issues/ISSUE-0008.json) (P2)** — Write an initial AI-authored C-LARA-2 technical report in LaTeX.
4. **[ISSUE-0005](issues/ISSUE-0005.json) (P2)** — Tune segmentation_phase_1 prompting to improve segment granularity by genre.
5. **[ISSUE-0004](issues/ISSUE-0004.json) (P2)** — Introduce AI-based review gates for phase outputs with extensible evaluator architecture.
6. **[ISSUE-0007](issues/ISSUE-0007.json) (P2)** — Use LLM prompt-construction indirection for page-image generation prompts.
7. **[ISSUE-0001](issues/ISSUE-0001.json) (P2)** — Support hosted compiled legacy content registration in C-LARA-2.

## Completed issues (most recent first)

1. **[ISSUE-0002](issues/ISSUE-0002.json) (completed 2026-05-09)** — Support migration of legacy C-LARA projects into C-LARA-2.
   - C-LARA-2 now imports supported legacy C-LARA JSON export ZIP bundles directly through the source-bundle import flow.
   - Supported legacy bundles can be flat or single-root archives containing `annotated_text.json` and `metadata.json`; optional audio/image assets and image metadata are preserved where present.
   - Imported projects are normal C-LARA-2 projects with converted stage artifacts and valid runtime processing settings, while original legacy files remain available under `legacy_clara/` for provenance.
2. **[ISSUE-0009](issues/ISSUE-0009.json) (completed 2026-05-06)** — Auto-regenerate and validate source project bundle stage artifacts before export/import.

## Priority distribution (active issues)

- **P1:** [ISSUE-0003](issues/ISSUE-0003.json)
- **P2:** [ISSUE-0001](issues/ISSUE-0001.json), [ISSUE-0004](issues/ISSUE-0004.json), [ISSUE-0005](issues/ISSUE-0005.json), [ISSUE-0006](issues/ISSUE-0006.json), [ISSUE-0007](issues/ISSUE-0007.json), [ISSUE-0008](issues/ISSUE-0008.json)
- **P3:** none
- **P0:** none

## Dependency highlights

- [ISSUE-0006](issues/ISSUE-0006.json) depends on [ISSUE-0003](issues/ISSUE-0003.json); it should be more efficient once the end-to-end test runner and artifact review harness are in place.
- [ISSUE-0008](issues/ISSUE-0008.json) depends on [ISSUE-0003](issues/ISSUE-0003.json) and has a target deadline of 2026-06-15 for a usable initial LaTeX report; the report should emphasize the end-to-end testing work and the emerging issue-tracking/human-suggestion loop as temporal-context mechanisms.
- [ISSUE-0004](issues/ISSUE-0004.json) depends on [ISSUE-0003](issues/ISSUE-0003.json).
- [ISSUE-0005](issues/ISSUE-0005.json) depends on [ISSUE-0003](issues/ISSUE-0003.json) and [ISSUE-0004](issues/ISSUE-0004.json).
- [ISSUE-0007](issues/ISSUE-0007.json) depends on [ISSUE-0003](issues/ISSUE-0003.json) and [ISSUE-0004](issues/ISSUE-0004.json).
