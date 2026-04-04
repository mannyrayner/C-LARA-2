# Status report generation method

The first version of report generation is driven from the Django admin tools page.

## Inputs
- Prioritized source set:
  1. `docs/**/README*.md` (especially `docs/README.md`)
  2. most recent previous report from `reports/updates/`
  3. files in `docs/roadmap/`
  4. files likely relevant to new functionality since previous report (derived from git changes)

## Output
- Datestamped Markdown file: `reports/updates/status_report_YYYYMMDD_HHMMSSZ.md`.

## Prompting strategy
The generator asks the AI model for a concise 3-6 page stakeholder update in Markdown with sections for:
1. summary for users,
2. changes since previous report,
3. current user-visible functionality,
4. near-term work,
5. risks/notes.
When relevant, generated reports should include links to repo files using:
`https://github.com/mannyrayner/C-LARA-2/tree/main/<relative_path>`.
