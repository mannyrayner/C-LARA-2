# C-LARA-2 issues overview

_Last updated: 2026-05-09T06:00:00Z_

This document summarizes the current issue registry for quick human review. Canonical machine-readable records remain in `docs/issues/issues/*.json` and `docs/issues/index.json`.

## Recent progress

- **[ISSUE-0008](issues/ISSUE-0008.json)** has been expanded and reprioritized to P1, with a new [reports and academic papers roadmap](../roadmap/reports-and-papers.md) covering the internal report, EuroCALL 2026 paper, and possible ALTA 2026 paper.
- **[ISSUE-0011](issues/ISSUE-0011.json)** remains a high-priority, time-sensitive image-game task centred on picture dictionaries and Kok Kaper community use before early June 2026.
- The focus index now places the writing/reporting work immediately after the three most urgent implementation/process items because the internal-report target is mid-June and the EuroCALL paper is already accepted.

## Near-term priorities

1. **[ISSUE-0003](issues/ISSUE-0003.json) (P1)** — Add an efficient end-to-end pipeline test runner so quality regressions can be reproduced and measured systematically.
2. **[ISSUE-0011](issues/ISSUE-0011.json) (P1, deadline 2026-06-01)** — Agree and implement a picture-dictionary-centred image-game workflow, starting with image-to-word and word-to-image flashcards for Kok Kaper community review sessions.
3. **[ISSUE-0010](issues/ISSUE-0010.json) (P1)** — Import a representative legacy C-LARA corpus, gather importer diagnostics from real archives, and add batch import tooling for a folder of legacy ZIPs.
4. **[ISSUE-0008](issues/ISSUE-0008.json) (P1, deadline 2026-06-15)** — Draft the long C-LARA-2 internal technical report and use it as the source for the accepted EuroCALL 2026 paper and possible ALTA 2026 submission.
5. **[ISSUE-0006](issues/ISSUE-0006.json) (P2)** — Investigate segmentation_phase_2 token-span failures and rerun-path correctness, preferably using ISSUE-0003 diagnostics where possible.
6. **[ISSUE-0005](issues/ISSUE-0005.json) (P2)** — Tune segmentation_phase_1 prompting so prose and poetry segment granularity better matches expected legacy behavior.
7. **[ISSUE-0004](issues/ISSUE-0004.json) (P2)** — Introduce AI-based review gates with a pluggable evaluator architecture after the test-runner foundation is available.
8. **[ISSUE-0007](issues/ISSUE-0007.json) (P2)** — Improve page-image generation by routing prompt construction through an LLM-backed indirection layer.
9. **[ISSUE-0001](issues/ISSUE-0001.json) (P2)** — Support registration of hosted compiled legacy content in C-LARA-2; ISSUE-0010 should provide useful imported legacy material for this work.
10. **[ISSUE-0012](issues/ISSUE-0012.json) (P2)** — Adjust project creation defaults for AI text generation and top page-image placement.

## Completed issues

1. **[ISSUE-0002](issues/ISSUE-0002.json) (completed 2026-05-09)** — Support migration of legacy C-LARA projects into C-LARA-2 through direct import of supported legacy JSON export ZIP bundles.
2. **[ISSUE-0009](issues/ISSUE-0009.json) (completed 2026-05-06)** — Auto-regenerate and validate source project bundle stage artifacts before export/import.

## Notes and risks

- **Writing scope:** ISSUE-0008 should use the internal report as the master source, then derive the EuroCALL 2026 paper and possible ALTA 2026 paper from it to avoid duplicated effort.
- **C-LARA-2 software-engineering claim:** the reports roadmap foregrounds the hypothesis that Codex-authored docs and tests, not only code, help maintain architectural coherence across the growing repository.
- **Kok Kaper timing:** ISSUE-0011 should be scoped tightly for the first delivery: picture-dictionary maintenance improvements plus image/word multiple-choice flashcards from approved entries, with broader game mechanics left for later issues if needed.
- **Dependency highlights:** ISSUE-0010 depends on completed ISSUE-0002; ISSUE-0004, ISSUE-0005, ISSUE-0006, ISSUE-0007, and ISSUE-0008 all depend directly or indirectly on ISSUE-0003.
