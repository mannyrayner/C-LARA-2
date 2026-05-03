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
- `focus_issue_ids` (ordered array of issue IDs)

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
