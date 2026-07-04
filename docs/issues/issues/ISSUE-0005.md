# ISSUE-0005: Tune segmentation_phase_1 prompting to improve segment granularity by genre

- **Status:** reported
- **Priority:** P1
- **Created:** 2026-05-04T00:19:24Z
- **Updated:** 2026-06-15T09:32:00Z
- **Origin:** human-suggestion
- **Deadline:** None
- **Dependencies:** [ISSUE-0003](ISSUE-0003.md), [ISSUE-0004](ISSUE-0004.md)
- **Canonical JSON:** [ISSUE-0005.json](ISSUE-0005.json)

## Notes

Suggestion #6 from admin export (submitted by mannyrayner on 2026-05-04). Investigate
segmentation_phase_1 output quality, especially overly short segments. Review and revise prompt
template plus few-shot examples, with explicit default heuristics aligned with legacy C-LARA
behavior (prose: sentence-level segments by default; poetry: line-level segments by default). Add
evaluation examples and acceptance checks so changes can be measured against current behavior.
Update suggestion #24 from 2026-06-13 reports that segmentation_phase_1 still produced clearly
unsatisfactory prose output by splitting at line breaks rather than respecting sentence boundaries,
suggesting the current prompt/few-shot set may not distinguish prose from poetry robustly. Treat the
next change as a measurable prompt-and-few-shot experiment: add prose examples where line breaks
should be ignored in favor of sentence/semantic boundaries, add poetry examples where line breaks
can remain meaningful, and validate against the reported failure mode before promoting changes to
defaults.
