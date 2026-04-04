# Status report generation method

The first version of report generation is driven from the Django admin tools page.

## Inputs
- Markdown files in `docs/`.
- Most recent prior report in `reports/updates/` (if available).

## Output
- Datestamped LaTeX file: `reports/updates/status_report_YYYYMMDD_HHMMSSZ.tex`.

## Prompting strategy
The generator asks the AI model for a concise 3-6 page stakeholder update with sections for:
1. summary for users,
2. changes since previous report,
3. current user-visible functionality,
4. near-term work,
5. risks/notes.
