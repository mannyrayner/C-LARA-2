# Issue tracking and human-suggestion loop roadmap

## Why this roadmap item exists

As C-LARA-2 grows, we need a lightweight but structured way to track platform issues inside the repository in a format Codex can read and update reliably.

The design goal is to keep AI-driven repo maintenance in place while giving humans a clear, low-friction path to review and influence issue priorities through platform UX and suggestions.

## Scope and non-goals

### In scope

- A small, Codex-first issue registry kept in the `C-LARA-2` GitHub repository.
- A simple issue lifecycle with three states: `reported`, `active`, `closed`.
- Priority labels for issues (initially a short fixed set).
- A platform mechanism that lets humans submit issue suggestions.
- An admin command that exports **unreported suggestions** into a single summary document.
- A C-LARA-2 issue browser/view that parses issue files from `docs/issues/` and supports search/filtering for humans.
- A documented AI workflow where Codex updates issue-tracking files from suggestion exports.

### Out of scope (for now)

- Full GitHub Issues API integration.
- Complex workflow engines (assignees, sprints, dependencies, automations).
- End-user-facing public issue boards.

## Proposed data model (minimal)

### Issue states

- `reported`: issue is known and recorded, but not currently being worked on.
- `active`: issue is being investigated or implemented.
- `closed`: issue has been resolved or intentionally retired.

### Priorities

Initial priority vocabulary:

- `P0` (critical)
- `P1` (high)
- `P2` (normal)
- `P3` (low)

### Canonical issue record fields

Each issue JSON entry should include:

- Stable issue ID (e.g. `ISSUE-0001`).
- Short title.
- State (`reported|active|closed`).
- Priority (`P0|P1|P2|P3`).
- Created date.
- Last updated date.
- Origin (`human-suggestion`, `ai-discovered`, `migration`, etc.).
- Optional notes/history links.
- Optional deadline (empty/null by default).
- Optional dependency list of other issue IDs (empty by default).

## Repository representation (agreed direction)

Codex readability is the primary requirement for canonical data. Human readability is mainly provided through a C-LARA-2 UI view built on top of this data.

### File layout

- `docs/issues/issues/ISSUE-XXXX.json`: **one JSON file per issue**.
- `docs/issues/index.json`: JSON index of issues currently in focus (most important/currently prioritized).
- `docs/issues/index-archive/`: timestamped snapshots of past `index.json` versions.
- `docs/issues/README.md`: short conventions/spec note.

### Why this format

- Per-issue JSON makes updates localized and conflict-resistant in Git.
- Codex can quickly parse/validate deterministic JSON.
- The focus index gives Codex a fast entry point for the issues that matter most right now.
- Timestamped archived index snapshots make priority evolution auditable over time.
- The platform issue browser can render the same JSON data for humans with sorting/filter/search, including historical focus snapshots.

### Ownership rule

- Direct edits to canonical issue JSON are performed by Codex in PRs.
- Humans influence index composition, index-archive continuity, and issue changes through the suggestion pipeline.

## Human suggestion mechanism

### Submission path

Add a platform entry point where human users/admins can submit a short suggestion:

- summary/title
- description
- optional severity hint
- optional related project/content link
- optional proposal to add/remove/re-rank items in the focus index
- optional proposal to adjust deadline/dependency metadata

Suggestions are stored in the platform database with timestamps and an internal status:

- `new`
- `exported`
- `incorporated`

### Administrative export command

Provide an admin command that generates a timestamped Markdown report of suggestions not yet incorporated into repo issues.

Properties:

- Includes all `new` suggestions (and optionally already `exported` but not `incorporated`, depending on flag).
- Marks exported rows to avoid duplication noise.
- Produces deterministic ordering (e.g. oldest first).
- Saves output to a known location and/or returns it for download.

## AI-in-the-loop operating model

1. Human submits suggestions in platform UI.
2. Admin runs export command and obtains summary document.
3. Document is given to Codex in a development session.
4. Codex updates `docs/issues/issues/*.json` and, when relevant, `docs/issues/index.json`:
   - creates new issues,
   - updates states/priorities,
   - updates deadline/dependency metadata,
   - updates focus-index membership/order,
   - writes an index snapshot to `docs/issues/index-archive/` when focus priorities change,
   - merges duplicates,
   - records rationale in notes/changelog.
5. Changes are reviewed via normal PR workflow and merged.
6. Suggestions included in accepted update are marked `incorporated`.

This preserves AI control of repository mutations while keeping humans in the loop through structured inputs and PR review.

## Proposed implementation phases

### Phase A: Documentation + conventions (current step)

- Add and refine this roadmap document.
- Confirm JSON conventions for per-issue files, deadline/dependency fields, focus index, and index-archive snapshots.

### Phase B: Repo issue registry baseline

- Create `docs/issues/README.md`.
- Create starter `docs/issues/index.json` template.
- Create `docs/issues/index-archive/` with timestamp naming convention (e.g. `index-YYYYMMDD-HHMMSSZ.json`).
- Create `docs/issues/issues/` with starter issue JSON template (including empty deadline/dependency defaults).
- Add simple validation script/tests for schema and allowed state/priority values.

### Phase C: Platform suggestion capture + issue browser

- Add DB model for issue suggestions.
- Add admin/UI form for submitting suggestions.
- Add list view for admins.
- Add issue browser view that reads/parses `docs/issues/` JSON and supports search/filter.
- Add priority-evolution views over `index-archive/` (timeline + diffs + query interface).

### Phase D: Export + incorporation loop

- Add admin command to export unreported/unincorporated suggestions as Markdown.
- Add post-export state transitions and audit trail.
- Document Codex incorporation protocol in `docs/howto/`.

## Open design questions

- Exact JSON schema versioning approach (`schema_version` field or external schema file)?
- Should `index.json` be strictly ordered or grouped by bands (e.g. now/next/later)?
- Exact rule for automatic importance escalation as deadlines approach (or keep fully manual)?
- Should dependency links be soft references or schema-validated against existing issue IDs?
- How frequently should index snapshots be persisted (every change vs debounced checkpoints)?
- How strict should duplicate detection be during incorporation?
- Should priorities be mandatory at creation time?
- Should `closed` require a closure reason taxonomy?

## Success criteria

- Humans can submit suggestions without touching Git.
- Admin can export pending suggestions in one command.
- Codex can reliably turn export docs into reviewed issue JSON updates (including deadlines and dependencies).
- C-LARA-2 issue browser gives humans readable/searchable access to canonical issue data and historical focus snapshots.
- Priority evolution is inspectable via timestamped `index-archive` history.
