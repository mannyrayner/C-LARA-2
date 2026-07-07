# ISSUE-0041: Add named project snapshots with restore and gold-standard metadata

- **Status:** reported
- **Priority:** P1
- **Created:** 2026-07-06T18:33:22Z
- **Updated:** 2026-07-06T18:33:22Z
- **Origin:** human-suggestion
- **Deadline:** None
- **Dependencies:** [ISSUE-0013](ISSUE-0013.md), [ISSUE-0036](ISSUE-0036.md)
- **Canonical JSON:** [ISSUE-0041.json](ISSUE-0041.json)

## Notes

Created from human suggestion #32 (submitted by mannyrayner on 2026-07-06). Add a simple
project-level snapshot mechanism so users can save and restore named checkpoints of a project's
current state. A first version should capture the core project data needed to revert or branch work
safely, including source text, manual and AI-produced text annotations, stage artifacts, image
prompts, generated/selected images, and related metadata. Each snapshot should have a user-supplied
name, timestamp, creator metadata where available, and explicit gold-standard metadata indicating
whether the snapshot contains gold-standard data and, if so, for which components. Provide a restore
control with clear warning/confirmation semantics and enough audit information to understand what
will be overwritten. Design should also consider optional partial snapshots for selected components
to reduce time and storage cost, but the initial implementation can prioritize reliable full-project
snapshots if that is simpler and safer. This is well grounded because project editing,
prompt-learning experiments, gold-standard curation, and manual annotation all need reversible
checkpoints and systematic gold-data handling; coordinate with ISSUE-0036 for
prompt-learning/few-shot experiment gold-standard workflows and with persistence/export issues where
snapshot storage overlaps stage artifacts or bundles.
