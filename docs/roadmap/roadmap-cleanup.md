# Roadmap cleanup roadmap

This roadmap tracks systematic cleanup of `docs/roadmap/*.md` files after several rounds of issue, deployment, publication, and feature-planning updates.

Linked issue: [ISSUE-0033](../issues/issues/ISSUE-0033.json).

## Why this roadmap exists

Roadmap files are a core part of the C-LARA-2 AI-centered workflow: they preserve planning context, help Codex recover architectural memory across sessions, and give humans a readable account of current direction. As new material is integrated, some roadmap files can become hard to scan because completed work, current work, future plans, historical notes, and cross-links are mixed together.

The cleanup should make each roadmap easier for both humans and AI agents to use without discarding useful history.

## General cleanup pattern

Each roadmap file can keep its topic-specific structure, but a cleanup pass should normally check whether it clearly separates:

1. **Completed work** — what has already been implemented, resolved, or superseded.
2. **Current work** — what is active or near-term, including linked issues and current blockers.
3. **Planned future work** — later ideas, dependencies, and open design questions.
4. **Relevant links** — issue files, related roadmap files, platform views/routes, code modules, docs, tests, or runbooks where useful.
5. **Status metadata** — last-updated dates or phase notes when they help readers understand freshness.

## Phase tracking

### Phase 1 — publication/report roadmaps

**Goal:** Clean up roadmap files that directly affect the first progress report and near-term papers.

Candidate files:

- [reports-and-papers.md](reports-and-papers.md)
- [first-progress-report.md](first-progress-report.md)
- `docs/publications/progress_report_1/markdown/README.md` and section outlines, where roadmap cleanup reveals inconsistencies

Suggested checks:

- Ensure the first progress report remains short, interim, and AI-centered.
- Keep future-work items distinct from completed first-report scaffolding.
- Preserve the possible David Gunkel authorship-paper angle without making it the main progress-report claim.
- Keep links to [ISSUE-0008](../issues/issues/ISSUE-0008.json) and [ISSUE-0033](../issues/issues/ISSUE-0033.json) current.

### Phase 2 — user-facing feature roadmaps

**Goal:** Clean up roadmaps for active or recently completed user-facing work.

Candidate topics:

- Picture dictionaries and picture-dictionary image generation.
- Community judging and community-recorded audio.
- Compiled-content presentation and access controls.
- Mobile access and low-resource-language workflows.

Suggested checks:

- Separate shipped functionality from planned refinements.
- Link to the current issues that still matter.
- Remove or demote obsolete implementation notes that no longer guide future work.

### Phase 3 — implementor-facing and infrastructure roadmaps

**Goal:** Clean up roadmaps that Codex uses as architectural/process memory.

Candidate topics:

- Issue tracking and human suggestions.
- End-to-end pipeline tests and AI review gates.
- Legacy project import/migration.
- AWS/deployment runbooks and service-limit notes.

Suggested checks:

- Keep process phases explicit.
- Link to scripts, tests, or runbooks when relevant.
- Preserve operational lessons learned, but move stale troubleshooting details out of the main path when they are no longer useful.

### Phase 4 — repeat cleanup cycle

**Goal:** Repeat the audit after the first progress report and near-term conference-paper work have produced more changes.

Suggested checks:

- Identify roadmaps that accumulated new ad hoc sections during urgent work.
- Fold useful decisions into stable headings.
- Archive or compress historical notes that are no longer needed for current planning.

## Working checklist for each file

- [ ] Does the file clearly say what problem it tracks?
- [ ] Does it distinguish completed, current, and future work where that distinction matters?
- [ ] Are linked issues current and correctly titled?
- [ ] Are related roadmap/doc/code/test links present where useful?
- [ ] Are stale claims, obsolete priorities, and duplicated historical notes removed or marked as historical?
- [ ] Is the file short enough to be useful as AI context?

## Current status

- **2026-05-29:** Roadmap cleanup tracking opened from human suggestion #23. Phase 1 should start with the publication/report roadmaps because they feed the first C-LARA-2 progress report.
- **2026-05-29:** Phase 1 started with [reports-and-papers.md](reports-and-papers.md): reorganized it around settled framing, current targets, planned paper split, related-work comparison, workflow rules, and near-term actions; also corrected the EuroCALL 2026 deadline to 2026-07-31 and synchronized it with the progress-report Markdown workspace.
