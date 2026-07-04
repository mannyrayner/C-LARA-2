# ISSUE-0024: Stabilize and verify natural-language search controls on Published Content view

- **Status:** closed
- **Priority:** P3
- **Created:** 2026-05-23T00:00:00Z
- **Updated:** 2026-05-23T05:00:00Z
- **Origin:** human-suggestion
- **Deadline:** None
- **Dependencies:** None
- **Canonical JSON:** [ISSUE-0024.json](ISSUE-0024.json)

## Notes

Human suggestion #15 reports that the natural-language search control on /content/ disappeared.
Current template still includes the NL request textarea and dialogue-language selector, so likely
causes are conditional rendering drift, route/template mismatch, or a regression in deployed
branch/assets. Track this as a low-priority but user-visible regression investigation: (1) confirm
which deployed environment/URL reproduces, (2) verify authenticated vs anonymous rendering paths,
(3) add a focused view/template test asserting nl_query + dialogue_language controls render on
content_list, and (4) if deployment-only, add release checklist item to sanity-check /content/
search controls. Closed on 2026-05-23 after user confirmation that the /content/ natural-language
controls and invocation flow are working well in practice.
