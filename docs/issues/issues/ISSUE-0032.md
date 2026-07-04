# ISSUE-0032: Fix community judging image visibility for non-owner community members

- **Status:** closed
- **Priority:** P0
- **Created:** 2026-05-28T07:32:17Z
- **Updated:** 2026-05-28T21:30:00Z
- **Origin:** human-suggestion
- **Deadline:** None
- **Dependencies:** [ISSUE-0029](ISSUE-0029.md), [ISSUE-0030](ISSUE-0030.md)
- **Canonical JSON:** [ISSUE-0032.json](ISSUE-0032.json)

## Notes

Suggestion #22 from admin export (submitted by mannyrayner on 2026-05-28), rewritten and prioritized
as critical. In community image judging (`communities/.../member/projects/.../judge`), project
owners can see images but other legitimate community members (including test accounts) see broken
image links. Likely scope includes object/file access policy, signed URL generation/expiry, and
route-level authorization differences between owner and member views. Deliverables: reproduce with
at least owner+member accounts, identify permission boundary causing broken links, ship fix so
authorized community members can load judging images reliably, and add regression tests/monitoring
for owner vs member access paths. Closed on 2026-05-28 after deployed fix to compiled-artifact
authorization for community members plus regression coverage. Duplicate closure confirmation
received in update suggestion #22 from dummyuser1 on 2026-05-28; no state change needed because the
issue was already closed.
