# Codex project orientation

For every substantive task, follow this operating principle:

> **orient globally → perform local task → reflect globally**

The authoritative conventions, ownership boundaries, and update rules are in
[`docs/global_workspace/README.md`](docs/global_workspace/README.md). Consult that file rather than
inferring policy from this summary.

## Orient globally

At the start of substantive work, inspect enough of `docs/global_workspace/` to understand how the
request relates to persistent goals, current project state, external commitments, concerns and
successes, urgency, risks, blockers, conflicts or uncertainties, and requests for human intervention.
Use judgment: this is project-level orientation, not a requirement to reread every management file
before a trivial operation. Remember that `project-intentions.md` is human-owned and authoritative,
whereas `current_state.*` is the project-manager agent's derived assessment.

## Perform the local task

Carry out the requested work normally while retaining its project-level context. If it appears to
conflict with an important goal, urgent commitment, known constraint, or serious unresolved risk,
make that tension visible and ask whether the human wants to reprioritize rather than silently
treating the request as context-free. The human remains authorized to decide.

## Reflect globally

At the end of substantive work, consider whether the result is material new evidence about how the
project is going—for example, a success or repeated failure, a blocker added or removed, changed test
evidence, progress, dependency, urgency, risk, confidence, goal conflict, obsolete concern, newly
available next step, or need for human input.

Do not update the global workspace mechanically because a task completed. Ask instead:

> **Does this evidence materially change the project manager's assessment?**

If not, no workspace change is needed. If it does, update the global workspace according to its
README. Before replacing the live `current_state`, ensure that its existing revision is preserved in
the global-workspace archive and preserve the human input that materially informed the new revision;
never rewrite archived historical states or inputs. Do not silently rewrite human intentions.
