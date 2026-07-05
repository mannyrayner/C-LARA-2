# ISSUE-0003: Add efficient end-to-end pipeline test runner for systematic quality checks

- **Status:** reported
- **Priority:** P1
- **Created:** 2026-05-03T21:46:10Z
- **Updated:** 2026-05-10T01:02:50Z
- **Origin:** human-suggestion
- **Deadline:** None
- **Dependencies:** [ISSUE-0010](ISSUE-0010.md)
- **Canonical JSON:** [ISSUE-0003.json](ISSUE-0003.json)

## Notes

Suggestion #3 from admin export (submitted by mannyrayner on 2026-05-03), updated by follow-up
suggestion #3 on 2026-05-10. Provide an admin-oriented command or workflow that runs full pipeline
processing (text generation, linguistic annotation, image generation, rendering) on test texts
without stepping through the UI. Include reproducible run configuration, persisted per-phase
artifacts/logs, and summary reporting so annotation regressions are easier to detect than with unit
tests alone. Once ISSUE-0010 has imported a substantial representative corpus of legacy C-LARA
projects, use those imported projects as a first practical evaluation corpus: rerun selected stages
through the C-LARA-2 pipeline and compare outputs with the legacy C-LARA versions preserved by the
import. The first comparison layer should flag gross differences rather than require exact equality,
since large differences in translation or glossing may be benign. Use AI API calls as optional
reviewers to decide whether a difference is gross and whether it plausibly indicates a C-LARA-2
error. At minimum, support investigation of ISSUE-0006, because gross segmentation_phase_2
token-span errors, such as lexical tokens covering an entire segment, should usually be clear in
legacy-vs-C-LARA-2 comparisons. Design the runner so future AI-based phase reviewers can be plugged
in and can optionally stop downstream stages when quality gates fail.
