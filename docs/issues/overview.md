# C-LARA-2 issues overview

_Last updated: 2026-05-04T01:13:22Z_

This document summarizes the current issue registry for quick human review. Canonical machine-readable records remain in `docs/issues/issues/*.json` and `docs/issues/index.json`.

## Focus order (from `index.json`)

1. **ISSUE-0003 (P1)** — Add efficient end-to-end pipeline test runner for systematic quality checks.
2. **ISSUE-0002 (P1)** — Support migration of legacy C-LARA projects into importable C-LARA-2 bundles.
3. **ISSUE-0006 (P1)** — Investigate segmentation_phase_2 token-span failures and rerun-path correctness.
4. **ISSUE-0005 (P2)** — Tune segmentation_phase_1 prompting to improve segment granularity by genre.
5. **ISSUE-0004 (P2)** — Introduce AI-based review gates for phase outputs with extensible evaluator architecture.
6. **ISSUE-0007 (P2)** — Use LLM prompt-construction indirection for page-image generation prompts.
7. **ISSUE-0001 (P2)** — Support hosted compiled legacy content registration in C-LARA-2.

## Priority distribution

- **P1:** ISSUE-0002, ISSUE-0003, ISSUE-0006
- **P2:** ISSUE-0001, ISSUE-0004, ISSUE-0005, ISSUE-0007
- **P3:** none
- **P0:** none

## Dependency highlights

- ISSUE-0004 depends on ISSUE-0003.
- ISSUE-0005 depends on ISSUE-0003 and ISSUE-0004.
- ISSUE-0006 depends on ISSUE-0003.
- ISSUE-0007 depends on ISSUE-0003 and ISSUE-0004.
