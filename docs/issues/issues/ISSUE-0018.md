# ISSUE-0018: Use main-branch issue registry data when processing human issue suggestions

- **Status:** closed
- **Priority:** P2
- **Created:** 2026-05-20T00:17:41Z
- **Updated:** 2026-05-20T00:51:14Z
- **Origin:** human-suggestion
- **Deadline:** None
- **Dependencies:** None
- **Canonical JSON:** [ISSUE-0018.json](ISSUE-0018.json)

## Notes

Suggestion #9 from admin export (submitted by mannyrayner on 2026-05-20). During suggestion
processing, the admin UI currently appears to resolve existing issues/roadmap context from the
repository state checked out on the server, which can be stale when recent Codex PRs have not yet
been deployed. This creates avoidable confusion about which issues already exist and whether a
suggestion is new versus an update. Update the suggestion-processing pipeline so that issue/roadmap
context is read from the canonical checked-in `main` branch state (or equivalent deterministic
remote reference) rather than the local working checkout, and clearly surface which snapshot/ref was
used. Include fallback behaviour for offline/error states and tests that cover stale-local-vs-main
divergence. Resolved on 2026-05-20 by implementing main-branch-first issue registry lookup with
local fallback and source visibility in admin suggestion prompt.
