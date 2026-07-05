# ISSUE-0002: Support migration of legacy C-LARA projects into C-LARA-2

- **Status:** closed
- **Priority:** P1
- **Created:** 2026-05-03T21:32:31Z
- **Updated:** 2026-05-09T00:00:00Z
- **Origin:** human-suggestion
- **Deadline:** None
- **Dependencies:** None
- **Canonical JSON:** [ISSUE-0002.json](ISSUE-0002.json)

## Notes

Suggestion #2 from admin export (submitted by mannyrayner on 2026-05-03). Implemented on 2026-05-09:
C-LARA-2 can now import legacy C-LARA JSON export ZIP bundles directly through the existing
source-bundle import flow. The importer accepts both flat and single-root ZIP layouts containing
annotated_text.json and metadata.json, copies the original legacy files under the new project
artifact root for provenance, converts pages/segments/content elements into C-LARA-2 stage
artifacts, restores audio references and image metadata where present, records diagnostics for
unsupported legacy content, and normalizes legacy-only processing options to valid C-LARA-2 runtime
choices so imported projects can be inspected and rerun with current tooling. The earlier two-step
plan of first converting legacy data into a separate C-LARA-2-oriented bundle is therefore no longer
required for the supported JSON export format; remaining future work, if needed, should be tracked
as narrower follow-up issues for unsupported legacy fields or non-JSON legacy formats.
