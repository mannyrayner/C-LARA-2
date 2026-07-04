# ISSUE-0009: Auto-regenerate and validate source project bundle stage artifacts before export/import

- **Status:** closed
- **Priority:** P1
- **Created:** 2026-05-06T12:02:30Z
- **Updated:** 2026-05-06T13:31:10Z
- **Origin:** human-suggestion
- **Deadline:** None
- **Dependencies:** None
- **Canonical JSON:** [ISSUE-0009.json](ISSUE-0009.json)

## Notes

Suggestion #1 from admin export (submitted by mannyrayner on 2026-05-06), updated by follow-up human
guidance on 2026-05-06. Source project bundle export can produce unusable zipfiles when the latest
run folder only contains compile_html stage artifacts, for example after rerunning linguistic
annotation with both start and end stage set to compile_html. Implemented on 2026-05-06: export now
detects missing required stage files and, when earlier annotation artifacts are available,
automatically regenerates a complete current-run stage set by rerunning the pipeline from audio
through compile_html before creating the source bundle. If upstream artifacts needed for this
automatic refresh have never been produced or cannot be read, export fails with an informative error
explaining which stages are missing and what the user should rerun. Import of source project
zipfiles also validates required stages and fails early with a clear diagnostic when stage files are
missing.
