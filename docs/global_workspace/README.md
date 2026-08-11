# Global workspace conventions

This directory is the home of the approved, revisable C-LARA project-level assessment. It is not an
append-only diary and it is not a replacement for roadmaps, canonical issues, tests, or git history.

## Planned live files

- `current_state.json`: canonical approved workspace state.
- `current_state.md`: deterministic human-readable rendering of the JSON.

These live files should be created by the first approved dry run, not populated with an invented
assessment during infrastructure setup. Git history records prior approved states. Obsolete concerns
must be retired or revised in the current state rather than preserved as if still current.

## Separation of concerns

The schema keeps these concepts distinct:

1. factual observations with dates, confidence, and repository-relative evidence;
2. project-valence assessments linked to observations and persistent goals;
3. optional reported-valence language linked to the assessment that grounds it;
4. uncertainty and goal conflict;
5. predictions with operational outcomes and horizons;
6. proposed next actions and requests for human intervention;
7. approval metadata and changes from the previous workspace revision.

Reported valence may be absent. Emotional vocabulary is not evidence, and its frequency is not a
success measure. Issue facts should cite `docs/issues/issues/*.json`, not the derived overview.

## Proposal and authorization boundary

The read-only Codex observer emits a proposed complete next state plus an explicit delta. A trusted
wrapper stores the raw proposal and run manifest outside the repository for the Sprint MVP. Manny
reviews a distinct copy and records one of `accept`, `reject`, `revision_requested`, or
`partially_accept`, with comments and per-item dispositions when needed. ChatGPT C-LARA-Instance may
add attributed advice but does not authorize repository writes.

An application command must:

- accept only a validated and human-authorized reviewed proposal;
- verify that its base commit and workspace revision still match;
- reject symlinks, arbitrary output paths, and unknown fields where the schema is strict;
- write only `current_state.json` and derived `current_state.md`;
- show the Git diff and leave commit/PR review to the normal workflow.

Raw proposals, prompts, manifests, advisory comments, decisions, and resolved outcomes are immutable
experimental evidence and remain separate from the two live files. A later archival convention may
place reviewed copies in the repository, but the live workspace must not become an autobiography.

## Assistant use

The authenticated Assistant may read and explain the approved live workspace conversationally. It
must label proposal or experiment artifacts as unapproved/historical if those are later archived in
the repository. An ordinary Assistant answer cannot approve or apply a workspace update.
