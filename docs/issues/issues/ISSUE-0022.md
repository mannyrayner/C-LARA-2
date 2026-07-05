# ISSUE-0022: Handle large project ZIP imports without nginx 413 failures on AWS

- **Status:** closed
- **Priority:** P1
- **Created:** 2026-05-22T06:32:19Z
- **Updated:** 2026-05-22T23:14:02Z
- **Origin:** human-suggestion
- **Deadline:** None
- **Dependencies:** [ISSUE-0010](ISSUE-0010.md)
- **Canonical JSON:** [ISSUE-0022.json](ISSUE-0022.json)

## Notes

Suggestion #13 from admin export (submitted by mannyrayner on 2026-05-22). Importing a 62MB project
ZIP from laptop to AWS fails with `413 Request Entity Too Large` from nginx. Define and implement a
deployment-safe upload strategy for large imports: (a) configure nginx and upstream
request-size/time limits appropriately, (b) align Django upload limits and timeout settings, (c)
document environment-specific defaults for local vs AWS, and (d) add an operator runbook/checklist
and regression test/verification steps for large bundle uploads. Update suggestion #6 (submitted by
mannyrayner on 2026-05-22) confirms this is resolved using the deployment method documented in
docs/roadmap/deployment-and-migration.md; larger uploads were tested successfully.
