# ISSUE-0041: Add named project snapshots with restore and gold-standard metadata

- **Status:** active
- **Priority:** P1
- **Created:** 2026-07-06T18:33:22Z
- **Updated:** 2026-07-07T22:00:00Z
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

First implementation cut on 2026-07-07: added a file-backed full-project snapshot service callable
from code, a platform project-detail UI for owner save/restore, and a project_snapshot management
command for prompt-learning experiments and other programmatic workflows. The initial snapshot
captures core project fields, image style/element/page/variant rows including preferred variants,
and the project artifact tree while excluding prior snapshots to avoid recursive copies. Restore
replaces the captured project fields, image rows, and non-snapshot artifacts while preserving the
snapshot directory. Remaining follow-up work should consider richer partial snapshot semantics,
broader related-model coverage for specialised workflows, and restore previews/audit trails before
destructive restore operations.

UI follow-up on 2026-07-07: replaced the free-text gold-standard components field in the snapshot
save UI with checkbox choices for common project components, including group checkboxes for all
linguistic annotation data and all image data. The save view now treats selected components as
sufficient to mark the snapshot as containing gold-standard data, reducing the chance that a user
selects components but forgets the separate gold-standard checkbox.

Windows/Cygwin snapshot follow-up on 2026-07-07: replaced the artifact snapshot copy path with an
explicit recursive copy that creates target parents for every file, skips nested snapshots, uses
extended-length Windows paths when running on Windows, and removes a partially created snapshot
directory if copying fails. This addresses maintainer testing where deep manual_versions files under
MWE experiment runs failed during shutil.copytree with a destination ENOENT on Windows/Cygwin paths.
