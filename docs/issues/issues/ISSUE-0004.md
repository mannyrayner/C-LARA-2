# ISSUE-0004: Introduce AI-based review gates for phase outputs with extensible evaluator architecture

- **Status:** reported
- **Priority:** P2
- **Created:** 2026-05-03T21:58:21Z
- **Updated:** 2026-05-03T21:58:21Z
- **Origin:** human-suggestion
- **Deadline:** None
- **Dependencies:** [ISSUE-0003](ISSUE-0003.md)
- **Canonical JSON:** [ISSUE-0004.json](ISSUE-0004.json)

## Notes

Suggestion #4 from admin export (submitted by mannyrayner on 2026-05-03). Add AI-assisted quality
review for phase outputs (generation, linguistic annotation, image generation, rendering), starting
with high-value checks: missing/empty outputs and obvious structural anomalies (e.g.,
segmentation_phase_2 token spans that cover entire segments). Extend to more complex checks,
especially MWE identification quality, potentially with language-specific prompts and
multi-model/panel evaluators. Architecture should be evaluator-pluggable and versionable so stronger
models/prompts can be adopted without redesigning the pipeline.
