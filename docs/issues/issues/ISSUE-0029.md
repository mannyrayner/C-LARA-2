# ISSUE-0029: Autosave community judging inputs to prevent accidental data loss

- **Status:** active
- **Priority:** P0
- **Created:** 2026-05-24T13:00:00Z
- **Updated:** 2026-08-13T00:00:00Z
- **Origin:** human-suggestion
- **Deadline:** 2026-08-24T00:00:00Z
- **Dependencies:** None
- **Canonical JSON:** [ISSUE-0029.json](ISSUE-0029.json)

## Notes

Created from human suggestion #18 (2026-05-24, mannyrayner). Community members can lose entered
judgements on communities/.../member/projects/.../judge/ when leaving before pressing Save. Scope:
implement autosave-on-change (or equivalent immediate persistence) for judgement entries, add clear
saved-state feedback, and verify recovery across navigation/reload. Planning roadmap:
docs/roadmap/community-judging-autosave.md (implementation deferred until after June 1 Kok Kaper
visit).

Human issue-review update from Manny Rayner on 2026-08-13: This has similar Indigenous-community
timing to ISSUE-0026 but is probably much easier. Treat autosave as low-hanging fruit and aim to
land it before the 24 August visit if feasible.
