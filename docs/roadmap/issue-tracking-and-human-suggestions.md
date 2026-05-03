# Issue tracking and human-suggestion loop roadmap

## Why this roadmap item exists

As C-LARA-2 grows, we need a lightweight but structured way to track platform issues inside the repository so both humans and Codex can read and update them without relying on external tooling.

The design goal is to keep AI-driven repo maintenance in place while giving humans a clear, low-friction path to review and influence issue priorities.

## Scope and non-goals

### In scope

- A small, human-readable issue registry kept in the `C-LARA-2` GitHub repository.
- A simple issue lifecycle with three states: `reported`, `active`, `closed`.
- Priority labels for issues (initially a short fixed set).
- A platform mechanism that lets humans submit issue suggestions.
- An admin command that exports **unreported suggestions** into a single summary document.
- A documented AI workflow where Codex updates issue-tracking files from that summary.

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

Each issue entry should include:

- Stable issue ID (e.g. `ISSUE-0001`).
- Short title.
- State (`reported|active|closed`).
- Priority (`P0|P1|P2|P3`).
- Created date.
- Last updated date.
- Origin (`human-suggestion`, `ai-discovered`, `migration`, etc.).
- Optional notes/history links.

## Repository representation

To keep information both AI-friendly and human-readable:

- Store canonical issue data in version-controlled text files under `docs/issues/`.
- Use one machine-friendly summary file (e.g. JSON or YAML) plus optional per-issue Markdown notes.
- Maintain a small `README.md` in `docs/issues/` explaining conventions.

This keeps issue status reviewable in PRs and makes change history explicit through Git.

## Human suggestion mechanism

### Submission path

Add a platform entry point where human users/admins can submit a short suggestion:

- summary/title
- description
- optional severity hint
- optional related project/content link

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
4. Codex updates `docs/issues/` issue registry:
   - creates new issues,
   - updates states/priorities,
   - merges duplicates,
   - records rationale in notes/changelog.
5. Changes are reviewed via normal PR workflow and merged.
6. Suggestions included in accepted update are marked `incorporated`.

This preserves AI control of repository mutations while keeping humans in the loop through structured inputs and PR review.

## Proposed implementation phases

### Phase A: Documentation + conventions (first step)

- Add this roadmap document.
- Agree file formats and naming conventions for `docs/issues/`.

### Phase B: Repo issue registry baseline

- Create `docs/issues/README.md`.
- Add initial canonical issue index file (possibly empty template).
- Add simple validation script/tests for schema and allowed state/priority values.

### Phase C: Platform suggestion capture

- Add DB model for issue suggestions.
- Add admin/UI form for submitting suggestions.
- Add list view for admins.

### Phase D: Export + incorporation loop

- Add admin command to export unreported/unincorporated suggestions as Markdown.
- Add post-export state transitions and audit trail.
- Document Codex incorporation protocol in `docs/howto/`.

## Open design questions

- JSON vs YAML for canonical registry?
- Single file vs sharded files by area?
- How strict should duplicate detection be during incorporation?
- Should priorities be mandatory at creation time?
- Should `closed` require a closure reason taxonomy?

## Success criteria

- Humans can submit suggestions without touching Git.
- Admin can export pending suggestions in one command.
- Codex can reliably turn export docs into reviewed issue-registry updates.
- The repository always contains an up-to-date, readable issue snapshot.
