# ISSUE-0021: Add GPT-Image-2 as selectable model for element and page image generation

- **Status:** closed
- **Priority:** P1
- **Created:** 2026-05-21T12:23:39Z
- **Updated:** 2026-05-23T06:05:00Z
- **Origin:** human-suggestion
- **Deadline:** None
- **Dependencies:** [ISSUE-0017](ISSUE-0017.md), [ISSUE-0007](ISSUE-0007.md)
- **Canonical JSON:** [ISSUE-0021.json](ISSUE-0021.json)

## Notes

Suggestion #12 from admin export (submitted by mannyrayner on 2026-05-21), refined after follow-up
feedback. Treat this as a focused near-term delivery item rather than the full model-catalog
program. Immediate scope: add GPT-Image-2 as an additional selectable image model (alongside
GPT-Image-1) in the generation pipeline for both element images and page images. Implementation
should cover: (1) pipeline/config wiring so both models are supported and GPT-Image-1 remains
backward-compatible default unless explicitly changed; (2) organiser-facing model selection where
image generation/regeneration jobs are launched; (3) persistence of selected model in job/stage
metadata for traceability; (4) graceful fallback/error messaging when GPT-Image-2 is unavailable;
and (5) regression tests and docs updates for selection behavior in element/page image flows.
Broader cross-task model governance remains future work and can be tracked separately if needed.

Closed based on maintainer confirmation in issue update suggestion #12 (2026-05-23): GPT-Image-2
selectable model support is complete.
