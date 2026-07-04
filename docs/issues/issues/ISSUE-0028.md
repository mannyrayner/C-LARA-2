# ISSUE-0028: Ensure picture-dictionary image generation produces text-free images

- **Status:** closed
- **Priority:** P1
- **Created:** 2026-05-24T09:00:00Z
- **Updated:** 2026-05-24T12:00:00Z
- **Origin:** human-suggestion
- **Deadline:** None
- **Dependencies:** [ISSUE-0011](ISSUE-0011.md)
- **Canonical JSON:** [ISSUE-0028.json](ISSUE-0028.json)

## Notes

Opened on 2026-05-24 after validation of form→image flashcards. Problem: many picture-dictionary
images contain visible written words (often the illustrated word), which undermines pedagogical
value and invalidates image-based flashcards. Scope: enforce text-free image outputs for
picture-dictionary generation/regeneration; add prompt constraints and/or post-generation checks;
add organiser-facing rejection reason for detected text; add regression checks so dictionary images
used in flashcards are text-free by default. Closed on 2026-05-24 after UI/settings and prompt-path
changes distinguished discourage vs disallow controls and removed duplicate conflicting option,
enabling strict text-free picture-dictionary generation mode.
