# Roadmap: Codex PR update-branch inconsistencies

Tracked by [ISSUE-0035](../issues/issues/ISSUE-0035.json).

## Goal

Track and diagnose intermittent Codex behaviour where a maintainer asks Codex to update a pull-request branch and receives a refusal such as:

> Codex does not currently support updating PRs that are updated outside of Codex. For now, please create a new PR.

The initial reports started on 2026-05-30. The immediate goal is not to change C-LARA-2 product code, but to preserve enough evidence to decide whether this is a Codex product limitation, a GitHub branch-state edge case, or a project workflow/documentation problem that C-LARA-2 maintainers can work around more reliably.

## Why this matters

C-LARA-2 relies heavily on Codex-assisted repository maintenance. If the Codex PR update flow sometimes refuses to update branches unexpectedly, maintainers may lose time, produce unnecessary replacement PRs, or lose a clear review trail for issue-registry and documentation changes.

The issue is especially relevant for process-heavy work such as issue-suggestion incorporation, roadmap cleanup, and report preparation, where small follow-up updates to an existing PR are common.

## Current symptoms

- First known occurrence: 2026-05-30.
- Trigger surface: Codex requests to run the PR **Update branch** action.
- Observed response: Codex states that it does not currently support updating PRs that were updated outside Codex and asks the maintainer to create a new PR.
- Known workaround: create a new PR for the follow-up change.
- Open uncertainty: it is not yet clear whether the affected branches were in fact modified outside Codex, whether GitHub metadata made them appear externally modified, or whether Codex is applying a conservative safety rule inconsistently.

## Incident log

- **2026-05-30:** first known occurrence; Codex refused a PR update with the message that it cannot update PRs updated outside Codex and advised creating a new PR.
- **2026-06-03:** repeated occurrence during the few-shot curation / segmentation variants / stage-parameter PR sequence. The maintainer reported that the PR was evidently not updated outside Codex, but Codex still returned the same refusal. Workaround requested: create a replacement PR carrying the same branch content. This should be treated as evidence for a possible false-positive Codex/GitHub branch-state detection rather than as confirmed external branch modification.
- **2026-06-03, follow-up:** the first replacement-PR attempt did not clear the problem; the maintainer saw exactly the same refusal. Next workaround to try: create the replacement PR from a freshly named branch with a new tracking commit, so the branch identity/provenance differs from the affected PR branch.

## Evidence to collect

For each new occurrence, record:

1. Date and approximate time.
2. PR number or branch name, if safe to include.
3. Whether any human, GitHub web UI action, merge-base update, CI bot, or other automation touched the branch after Codex created it.
4. The exact Codex refusal text, summarized if necessary.
5. Whether retrying, rebasing locally, creating a replacement branch, or creating a new PR resolved the problem.
6. Any visible GitHub branch protection, stale-base, conflict, or permissions signals at the time.

## Investigation plan

### Phase A: incident log

- Add short notes to [ISSUE-0035](../issues/issues/ISSUE-0035.json) or this roadmap when new examples appear.
- Distinguish confirmed externally modified branches from cases where no external modification is known.
- Keep examples concise and avoid copying private logs or credentials.

### Phase B: workflow guidance

- If a reliable pattern emerges, document a recommended maintainer response in the issue notes or a future how-to page.
- Prefer a low-friction workaround that preserves review history when possible, such as confirming branch provenance before deciding to create a replacement PR.
- If creating a new PR remains the only dependable route, document when to close or supersede the old PR.

### Phase C: escalation or retirement

- If evidence suggests this is a Codex product limitation or regression, prepare a concise external support/report summary with dates and reproducible conditions.
- If the behaviour stops occurring and no repo-side action is useful, close ISSUE-0035 with a note that it was tracked as an external-tool anomaly.
- If C-LARA-2 process changes are needed, link those changes back to ISSUE-0035.

## Open questions

- Does Codex intentionally block updates to any PR branch with non-Codex commits, or only to branches with ambiguous provenance?
- Can a GitHub **Update branch** operation, branch protection rule, or CI bot make a Codex-created branch look externally updated?
- Is the refusal tied to specific PR age, merge conflicts, stale base branches, or force-push history?
- Can maintainers preserve the original PR review trail without violating Codex's branch-safety constraints?
