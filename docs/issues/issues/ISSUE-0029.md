# ISSUE-0029: Autosave community judging inputs to prevent accidental data loss

- **Status:** reported
- **Priority:** P1
- **Created:** 2026-05-24T13:00:00Z
- **Updated:** 2026-05-24T14:00:00Z
- **Origin:** human-suggestion
- **Deadline:** None
- **Dependencies:** None
- **Canonical JSON:** [ISSUE-0029.json](ISSUE-0029.json)

## Notes

Created from human suggestion #18 (2026-05-24, mannyrayner). Community members can lose entered
judgements on communities/.../member/projects/.../judge/ when leaving before pressing Save. Scope:
implement autosave-on-change (or equivalent immediate persistence) for judgement entries, add clear
saved-state feedback, and verify recovery across navigation/reload. Planning roadmap:
docs/roadmap/community-judging-autosave.md (implementation deferred until after June 1 Kok Kaper
visit).
