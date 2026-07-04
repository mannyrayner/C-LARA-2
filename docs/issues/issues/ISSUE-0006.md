# ISSUE-0006: Investigate segmentation_phase_2 token-span failures and rerun-path correctness

- **Status:** reported
- **Priority:** P2
- **Created:** 2026-05-03T23:11:10Z
- **Updated:** 2026-05-25T00:53:31Z
- **Origin:** human-suggestion
- **Deadline:** None
- **Dependencies:** [ISSUE-0003](ISSUE-0003.md)
- **Canonical JSON:** [ISSUE-0006.json](ISSUE-0006.json)

## Notes

Suggestion #5 from admin export (submitted by mannyrayner on 2026-05-03), reprioritized on
2026-05-07. Investigate frequent segmentation_phase_2 errors where lexical tokens are over-extended
(sometimes covering an entire segment). Triage two hypotheses in parallel: (1) prompt template
and/or few-shot examples are incorrect, potentially language-dependent; (2) rerun orchestration
across annotation phases can skip or trivialize segmentation_phase_2. Priority is currently P2
rather than P1 because the work should be easier and more systematic after ISSUE-0003 provides an
efficient end-to-end pipeline test runner and artifact review harness.

Update from human suggestion #15 (submitted 2026-05-25 by mannyrayner): evaluate a
surface-form-first segmentation_phase_2 redesign that (1) seeds boundary markers from
whitespace/punctuation, (2) asks the model to correct boundaries (e.g., clitics/compounds), (3)
enforces text-preservation modulo boundaries with retry on mismatch, and (4) converts validated
segmented text back to JSON tokens. Treat as a candidate implementation strategy/prototype under
this issue, not yet confirmed as an easy drop-in replacement.
