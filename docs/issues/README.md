# C-LARA-2 internal issues format (Phase B baseline)

This folder contains the canonical, Codex-first issue registry used for project-internal issue tracking.

## Layout

- `index.json`: current focus list (issues currently prioritized).
- `index-archive/`: timestamped snapshots of previous `index.json` states.
- `issues/ISSUE-XXXX.json`: one JSON file per issue.

## Issue schema (baseline)

Required fields:

- `schema_version` (currently `1`)
- `issue_id` (must match filename stem, e.g. `ISSUE-0001`)
- `title`
- `state` (`reported|active|closed`)
- `priority` (`P0|P1|P2|P3`)
- `created_at` (ISO 8601 UTC)
- `updated_at` (ISO 8601 UTC)
- `origin`
- `notes`
- `deadline` (ISO 8601 UTC string or `null`)
- `dependencies` (array of issue IDs)

## Focus index schema (baseline)

`index.json` fields:

- `schema_version`
- `updated_at`
- `description`
- `focus_issue_ids` (ordered array of active/reported issue IDs currently in focus)

Closed issues should normally be removed from `focus_issue_ids`; keep them in their per-issue JSON files with `state: "closed"` and summarize them in `overview.md`.

## Human-readable overview conventions

`overview.md` is regenerated when issue priorities, states, or focus ordering change.

Recommended sections:

- Active focus order: mirrors `index.json` and excludes closed issues.
- Completed issues: closed issues ordered by completion date, most recent first. In the current schema, use the issue's `updated_at` timestamp as the completion date unless a future schema adds an explicit `closed_at` field.
- Priority distribution: active issues only.
- Dependency highlights: active dependencies and any important deadline notes.

## Archive naming convention

Use UTC timestamps:

- `index-YYYYMMDD-HHMMSSZ.json`

Example:

- `index-20260503-143000Z.json`

## Validation

Run:

```bash
python scripts/validate_issues_registry.py
```

This checks:

- required fields and allowed enum values
- issue-id/filename consistency
- dependency references to existing issues
- index references to existing issues
- archive filename pattern and basic index schema
