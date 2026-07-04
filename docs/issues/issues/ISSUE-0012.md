# ISSUE-0012: Adjust project creation defaults for AI generation and page images

- **Status:** closed
- **Priority:** P2
- **Created:** 2026-05-09T04:44:21Z
- **Updated:** 2026-05-25T05:03:13Z
- **Origin:** human-suggestion
- **Deadline:** None
- **Dependencies:** None
- **Canonical JSON:** [ISSUE-0012.json](ISSUE-0012.json)

## Notes

Suggestion #2 from admin export (submitted by mannyrayner on 2026-05-09). Change two
project-creation defaults to better match expected current usage: make the default new-project input
mode generate text from a description using AI rather than supplying source text manually, and set
the default page image placement to top rather than none. Verify that these defaults apply in the
project creation UI without changing existing projects or import flows, and update any form tests
that assume the old defaults.

Marked closed on 2026-05-25 from human update suggestion #19 (submitter: mannyrayner): issue can be
marked as closed.
