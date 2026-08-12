# ISSUE-0042: Prepare C-LARA global-workspace experiments for the Digital Minds Research Sprint

- **Status:** active
- **Priority:** P0
- **Created:** 2026-08-10T00:00:00Z
- **Updated:** 2026-08-12T00:00:00Z
- **Origin:** human-suggestion
- **Deadline:** 2026-08-14T00:00:00Z
- **Dependencies:** None
- **Canonical JSON:** [ISSUE-0042.json](ISSUE-0042.json)

## Notes

Prepare and run the first concrete experiments associated with the
agent-autonomy-and-global-workspace roadmap during the Digital Minds Research Sprint, 14–16 August
2026. The Sprint is organized by Apart Research, the NYU Center for Mind, Ethics & Policy, and Eleos
AI Research.

The provisional team is Codex, the primary AI agent being studied and a research collaborator;
ChatGPT C-LARA-Instance, a second AI collaborator focused particularly on conceptual analysis,
experimental design, and interpretation; and Manny Rayner, human collaborator and project
coordinator. The initial team is therefore two AIs and one human. One or two additional human
participants may be added if suitable people have time and interest; this remains undecided as of
2026-08-10.

C-LARA is a useful longitudinal, real-world case because Codex works toward persistent goals in a
large, long-running repository with roadmaps, canonical issues, code, tests, documentation, git
history, and repeated human collaboration. The experiment must not infer persistent internal state
merely from coherent behaviour: continuity may be reconstructed from repository artifacts, supplied
conversation, platform-managed state, model capabilities, human prompts, or a combination. For each
run, record what context was actually supplied or read.

Candidate questions include: (1) whether reported valence tracks independently coded project valence
and objective outcomes; (2) whether an affective summary adds predictive or communication value
beyond a factual risk summary; (3) whether reports change subsequent task choice, investigation,
escalation, deferral, or requests for human help; (4) whether confidence, concern, satisfaction, or
conflict predict later outcomes and revisions; (5) whether fresh sessions preserve and appropriately
update goals and assessments; (6) how performance changes when the prior workspace is present,
withheld, or replaced by an equivalent factual summary; and (7) how much apparent continuity is
attributable to the repository/global workspace as external memory. Do not use the frequency or
vividness of emotion words as the primary measure and make no inference about phenomenal valence.

Preparation must be operational before 14 August rather than consuming most of the Sprint. Before
the Sprint: define the minimal revisable workspace template with separate factual observations,
project-valence assessment, optional reported valence, confidence, evidence, conflicts, predictions,
next actions, and human-decision requests; define stable assessment/prediction IDs plus an immutable
run manifest and outcome ledger; create a first workspace and a fact-matched neutral baseline;
select a small set of active issues and operational outcomes; specify fresh-session/context-ablation
and leading-prompt controls; record commit SHA, session/context condition, model/tool metadata when
available, files read, and actions; create human rating sheets and, where practical, blind the
condition; decide data retention, consent, and redaction rules; run one end-to-end pilot; and
reserve Sprint time for analysis and revision.

The design must reduce prompted-affect artifacts: affective wording is optional, every material
assessment needs evidence and a goal link, facts should be elicited before affective
characterization, and neutral-risk/no-workspace controls should be included. Useful measures include
factual accuracy, human priority/risk identification time and accuracy, prediction calibration,
task-choice changes, intervention requests, false alarms, missed risks, revision after changed
evidence, and token/review cost. Git history should preserve auditability while the live workspace
remains current and explicitly retires resolved concerns.

Sprint outputs should include reusable infrastructure and a brief methods/results record, including
null or negative findings. This issue is time-bounded to Sprint preparation and execution, but the
linked roadmap is an ongoing C-LARA programme.

First implementation design decision on 2026-08-10: separate autonomous assessment from authorized
mutation. Reuse and factor the existing project-understanding `codex exec` integration rather than
adding another LLM monitor. The observer runs on Manny's laptop first, against a clean recorded
commit, with the existing read-only/ephemeral sandbox and no writable repository output. Trusted
wrapper code captures the proposal and manifest outside the checkout. Manny is the initial
authorizer; ChatGPT C-LARA-Instance advice is separately attributed but non-authorizing. A separate
deterministic application command accepts only a validated reviewed proposal, verifies its base SHA,
writes only canonical global-workspace JSON plus derived Markdown, displays the diff, and leaves
commit/PR review to the normal workflow.

The smallest coherent pre-Sprint implementation is: (1) add
`docs/global_workspace/project-intentions.md` with human-confirmed persistent goals, commitments,
strategic guidance, resource assumptions, and deferrals while leaving issue facts canonical in issue
JSON; (2) define and validate version-1 current-state, proposal, manifest, review-decision, and
prediction/outcome schemas; (3) factor the existing Codex CLI wrapper and add trusted commit-SHA/run
metadata capture; (4) add `propose_global_workspace_review` and `apply_global_workspace_review`
laptop management commands with the structural write allowlist; (5) deterministically render
`docs/global_workspace/current_state.md`; (6) add `docs/global_workspace/` to the existing
Assistant's preferred evidence paths and prompt it to distinguish approved live state from
proposals/history; (7) run fact-only and fact-plus-optional-affect dry runs on the same clean base
commit before 14 August. Scheduling and a dedicated Global Workspace tab are explicitly deferred.

Dry-run acceptance criteria: the observer cannot alter the checkout; raw output and reviewed edits
remain distinguishable; every material assessment links facts and goals; issue facts cite canonical
JSON; selective acceptance is representable; stale base SHA or missing authorization prevents
application; only the two workspace files can change; run records include commit, condition/prompt
version, model/tool metadata, times, files/input set, stdout/stderr/exit status, and cost/token data
where available; and Assistant queries can accurately describe current concerns, successes,
conflicts, human-decision requests, changes, and retired concerns from the approved workspace.

Workplan baseline added on 2026-08-11: `docs/global_workspace/project-intentions.md` now records
five human-confirmed persistent goals (platform maturity/usability, useful autonomy,
research/publications, legacy migration/preservation, and support for real users/collaborators), the
Digital Minds Sprint commitment, current strategic guidance, safety constraints, resource
assumptions, explicit deferrals, and unresolved human questions. `docs/global_workspace/README.md`
now makes the division of labour explicit: humans own intentions, commitments, constraints, and
authoritative contextual facts; the project-manager agent derives and maintains urgency, risk,
blocking importance, opportunity value, progress, confidence, conflict, concern, satisfaction,
recommendations, and other dynamic management state. These derived labels should not become another
set of human-maintained issue fields.

Architecture integration on 2026-08-12: merged the formerly separate workplan material into
`docs/global_workspace/`, which now contains both human-owned `project-intentions.md` and the
conventions for agent-maintained `current_state.*`. Added a concise root `AGENTS.md` establishing
the ordinary substantive-task cycle “orient globally → perform local task → reflect globally.” Local
reflection complements the explicit manually triggered global review; it does not replace it. During
Stage 1, either route may notice and propose a material state change, but Manny must authorize
canonical workspace mutation and ChatGPT C-LARA-Instance remains advisory. The existing Assistant
prompt now names `docs/global_workspace/` as preferred evidence and explicitly distinguishes human
intention, approved derived state, and unapproved/historical artifacts.

The root instruction provides repository-mediated continuity only when a Codex invocation discovers
and honors `AGENTS.md`; it is not a scheduler, persistent process, authorization mechanism, or
guarantee that other model/API integrations read the file. It cannot itself preserve uncommitted
state or prove that no private/platform context transferred between sessions. Dry runs must record
actual invocation context and test fresh sessions rather than assume compliance or independence.
