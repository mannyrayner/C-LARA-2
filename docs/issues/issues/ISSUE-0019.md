# ISSUE-0019: Ensure favicon reliably appears on AWS deployment

- **Status:** closed
- **Priority:** P3
- **Created:** 2026-05-21T00:51:14Z
- **Updated:** 2026-05-23T06:05:00Z
- **Origin:** human-suggestion
- **Deadline:** None
- **Dependencies:** [ISSUE-0014](ISSUE-0014.md)
- **Canonical JSON:** [ISSUE-0019.json](ISSUE-0019.json)

## Notes

Suggestion #10 from admin export (submitted by mannyrayner on 2026-05-20). Favicon appears in
local/laptop deployments but not on AWS-hosted deployment. Investigate deployment-specific static
asset delivery and cache behavior: verify favicon files are present in collected static output,
template/head references use stable URLs, MIME type is correct, CDN/proxy rules are not stripping or
rewriting icon requests, and browser cache invalidation/versioning works across updates. This is
minor UX polish but visible and should be fixed with a small, low-risk deployment/static-assets
patch.

Closed based on maintainer confirmation in issue update suggestion #10 (2026-05-23): favicon
behavior is now working well on AWS deployment.
