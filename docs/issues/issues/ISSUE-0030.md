# ISSUE-0030: Fix image-generation workflow UX around element expansion auto-refresh and selection confirmation

- **Status:** reported
- **Priority:** P1
- **Created:** 2026-05-24T14:21:50Z
- **Updated:** 2026-05-24T14:21:50Z
- **Origin:** human-suggestion
- **Deadline:** None
- **Dependencies:** [ISSUE-0017](ISSUE-0017.md), [ISSUE-0025](ISSUE-0025.md)
- **Canonical JSON:** [ISSUE-0030.json](ISSUE-0030.json)

## Notes

Suggestion #19 from admin export (submitted by mannyrayner on 2026-05-24). Reported two user-facing
failures in the image-generation flow: (1) UI text during element expansion claims the browser will
auto-update, but users observe no automatic refresh; either implement actual auto-refresh/push
update behavior or revise messaging to accurately describe required manual refresh. (2) After
selecting expanded elements via checkboxes, attempting image generation without an explicit confirm
step can fail silently; enforce a clear precondition with actionable warning, or treat selection as
implicitly confirmed and proceed with explicit user feedback. Include regression coverage to prevent
silent failures in this sequence.
