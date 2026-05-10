# C-LARA-2 issues overview

_Last updated: 2026-05-10T00:43:34Z_

This document summarizes the current issue registry for quick human review. Canonical machine-readable records remain in `docs/issues/issues/*.json` and `docs/issues/index.json`.

## Recent progress

- **[ISSUE-0010](issues/ISSUE-0010.json)** has been refined with a concrete Adelaide legacy-corpus import plan: first generate a global metadata file from per-bundle `metadata.json` files, then add an admin-only searchable import mode for that corpus.
- **[ISSUE-0008](issues/ISSUE-0008.json)** remains a P1 writing/reporting task, with CodePrism as the closest known comparator and a proposed EuroCALL/ALTA split.
- **[ISSUE-0011](issues/ISSUE-0011.json)** remains a high-priority, time-sensitive image-game task centred on picture dictionaries and Kok Kaper community use before early June 2026.

## Near-term priorities

1. **[ISSUE-0003](issues/ISSUE-0003.json) (P1)** — Add an efficient end-to-end pipeline test runner so quality regressions can be reproduced and measured systematically.
2. **[ISSUE-0011](issues/ISSUE-0011.json) (P1, deadline 2026-06-01)** — Agree and implement a picture-dictionary-centred image-game workflow, starting with image-to-word and word-to-image flashcards for Kok Kaper community review sessions.
3. **[ISSUE-0010](issues/ISSUE-0010.json) (P1)** — Import a representative legacy C-LARA corpus, starting with metadata aggregation for the Adelaide bundle folder and an admin-only searchable ZIP-import mode that can later grow into multi-bundle batch import with heartbeat progress.
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

- **Adelaide corpus usability:** ISSUE-0010 should include the metadata aggregation script early, since project-number directory names make manual bundle selection impractical without title/language/owner metadata.
- **Batch-import path:** the searchable admin-only import view should reuse the single-ZIP importer and be structured so later multi-select imports can add heartbeat-style progress and per-bundle diagnostics without a redesign.
- **Writing scope:** ISSUE-0008 should use the internal report as the master source, then, subject to co-author approval, split it into a user-facing EuroCALL 2026 paper and an implementor-facing ALTA 2026 paper to avoid duplicated effort.
- **Kok Kaper timing:** ISSUE-0011 should be scoped tightly for the first delivery: picture-dictionary maintenance improvements plus image/word multiple-choice flashcards from approved entries, with broader game mechanics left for later issues if needed.
- **Dependency highlights:** ISSUE-0010 depends on completed ISSUE-0002; ISSUE-0004, ISSUE-0005, ISSUE-0006, ISSUE-0007, and ISSUE-0008 all depend directly or indirectly on ISSUE-0003.
