# Stakeholder reports workflow

Status reports are no longer generated automatically inside the Django platform.

## Current approach
- Reports are created directly in Codex sessions.
- Output format is HTML (no LaTeX/Markdown conversion step in the platform).
- Completed report files are checked into `reports/updates/`.

## Recommended information sources for report authoring
1. `docs/README.md` and other README files under `docs/`.
2. The most recent previous report in `reports/updates/`.
3. `docs/roadmap/*.md`.
4. Newly created files/features since the previous report.

## Linking guidance
Where useful, include links to repository files using:
`https://github.com/mannyrayner/C-LARA-2/tree/main/<relative_path>`.
