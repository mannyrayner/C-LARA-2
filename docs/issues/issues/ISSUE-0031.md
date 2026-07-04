# ISSUE-0031: Improve compiled-content presentation context and configurable public access controls

- **Status:** reported
- **Priority:** P1
- **Created:** 2026-05-25T01:11:48Z
- **Updated:** 2026-05-25T01:11:48Z
- **Origin:** human-suggestion
- **Deadline:** None
- **Dependencies:** [ISSUE-0024](ISSUE-0024.md), [ISSUE-0010](ISSUE-0010.md)
- **Canonical JSON:** [ISSUE-0031.json](ISSUE-0031.json)

## Notes

Suggestion #20 from admin export (submitted by mannyrayner on 2026-05-25). Two related improvements
requested for compiled content delivery: (1) context-aware navigation in compiled HTML so the 'Back
to project' affordance is shown only when launched from project-internal workflow (or replaced with
an appropriate 'Back to content' / neutral navigation when opened from published content views); (2)
publisher-managed access policy for compiled/published content, including support for
anonymous/public access where appropriate and a reset/change mechanism for access level after
publication. Scope should include UI controls, permission checks, stable serving paths, and
regression coverage for logged-in vs anonymous readers.
