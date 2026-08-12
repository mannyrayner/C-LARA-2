# Global workspace: intention and project-manager state

This directory combines durable, human-owned strategic intention needed to interpret C-LARA-2's
roadmaps, canonical issues, and other project evidence. It also defines the division of
responsibility between human collaborators and the top-level project-manager agent.

> **Humans define and revise project intentions, commitments, constraints, and authoritative facts.
> The project-manager agent autonomously derives and maintains the project-management interpretation
> of those facts.**

The purpose is not to make humans maintain a more elaborate issue tracker. It is to give the agent
stable strategic reference points from which it can infer what is urgent, risky, blocked, promising,
going well, or in need of intervention.

## Files and canonical ownership

The human-owned part of the workspace uses one authoritative file:

- [`project-intentions.md`](project-intentions.md): persistent objectives, external commitments,
  strategic guidance, cross-cutting constraints, resource assumptions, explicit deferrals, and
  unresolved questions requiring human judgment.

Do not split goals, deadlines, priorities, and constraints into parallel files until evidence from
real reviews shows that this is useful. In particular:

- `docs/roadmap/` owns long-term feature/research strategy and architecture;
- `docs/issues/issues/*.json` owns tactical issue state, issue priority, dependencies, and issue
  deadlines;
- `docs/issues/index.json` owns the ordered current issue focus;
- code, tests, commits, and generated artifacts provide repository evidence about implementation and
  outcomes;
- the human-intention file owns human intentions and authoritative external/contextual facts that
  cannot be derived reliably from repository state;
- `current_state.json` owns the agent's approved, revisable project-management
  interpretation.

Do not copy an issue's state, priority, dependency array, or deadline into `project-intentions.md`. Link its ID
and state why it matters. If an external commitment creates actionable dated work, create or update a
canonical issue and refer to it from `project-intentions.md`.

## Human-owned intention and facts

The human-intention file should contain information that genuinely needs human authority, including:

- long-term objectives and success criteria;
- external commitments and externally fixed deadlines;
- strategic preferences and precedence decisions between objectives;
- unacceptable risks, authorization boundaries, and other constraints;
- assumptions about available human and AI resources;
- explicit decisions to defer otherwise desirable work, including reconsideration conditions;
- facts that a user, community, or collaborator is waiting for something;
- unresolved policy or strategy questions that require human judgment.

Each material assertion must identify its human owner and `last confirmed` date. Human collaborators
may revise these assertions through normal review. The project manager may question, summarize,
relate, or request clarification of them, but must not silently rewrite them.

A human judgment is authoritative evidence, not necessarily a manually maintained management label.
For example, “an external demonstration is fixed for Friday” belongs here or in a linked issue. The
agent should infer the resulting urgency of a demonstration-blocking bug; the human should not also
have to maintain an `urgency` field.

Humans may provide direct strategic judgments such as “a collaborator needs this next month” or “do
not work on X before the paper is complete.” The agent should preserve the statement and derive its
current implications. It may explicitly disagree with an earlier human management judgment when new
evidence warrants doing so. A human override remains authoritative for action or authorization, but
must be recorded as new evidence rather than silently replacing the agent's reasoning.

## Agent-maintained derived project-management state

The project-manager agent is responsible for creating, revising, and retiring dynamic judgments,
including:

- urgency and changes in urgency;
- current strategic significance and opportunity value;
- blocking importance and goal impact;
- risk, progress, confidence, and uncertainty;
- conflict and opportunity cost between goals;
- need for human intervention;
- likely useful next actions;
- concern about deteriorating or unresolved work;
- satisfaction with completed, stable, or sufficiently low-risk work.

These judgments should be inferred from human intentions together with roadmaps, canonical issue
state and focus order, dependencies, deadlines, commits, tests, failures, regressions, completions,
user requests, external events, previous workspace assessments, and later confirming or
invalidating evidence.

The desired flow is:

> **human intentions + repository/project evidence → project-manager inference → persistent derived
> state → recommendations and communication**

It is not:

> **human-maintained management labels → Codex restatement**

Humans should not ordinarily maintain numeric urgency, risk, progress, confidence, concern, or
similar values. The agent may use categories, rankings, scores, or numerical scales internally when
this improves consistency, but these remain agent-maintained derived state. Every exposed material
judgment must be traceable to evidence and must distinguish:

1. human-provided intention or authoritative contextual fact;
2. repository/project evidence;
3. project-manager inference.

If intention is insufficient to support a reliable inference, the agent should state the uncertainty
and ask a focused question rather than inventing a strategic assumption.

## Urgency is inferred, not copied from priority

Urgency is a first-class dynamic assessment and is distinct from both strategic importance and the
canonical issue priority:

- strategically important work may not be urgent;
- a relatively minor task may be extremely urgent because an expiring opportunity or imminent
  commitment depends on it;
- a high-priority task may be temporarily blocked;
- a low-priority task may become urgent after becoming a dependency for important work.

For example, mobile deployment can remain a major long-term objective while having moderate current
urgency if no near-term commitment depends on it. Digital Minds Sprint preparation is less central
to the permanent product but becomes extremely urgent immediately before 14–16 August 2026. A small
bug can similarly become the project's most urgent issue if it blocks a demonstration or a waiting
collaborator.

The agent should notice autonomously when approaching deadlines, repeated failures, new dependencies,
completed blockers, successful tests, lack of progress, or temporary research and collaboration
opportunities change urgency or risk. It should also retire an earlier concern when changed evidence
makes it obsolete.

## Relationship to the global workspace

The `project-intentions.md` file records durable human-owned intention and strategic context. The
current-state files record the project manager's current derived interpretation of how the project is going.

The workspace may therefore maintain what is currently urgent, successful, deteriorating, blocked,
uncertain, or in conflict; where human intervention is needed; likely next actions; resolved prior
concerns; and predictions for later checking. This state is expected to change as evidence changes.
Git history and separate experiment snapshots preserve earlier states; the live workspace remains a
revisable current assessment rather than an append-only autobiography.

Increasing autonomy should be measured partly by decreasing human effort spent maintaining this
interpretation. Humans continue to state goals, commitments, constraints, decisions, and relevant
new facts; the agent increasingly notices developments, updates assessments, identifies risks and
successes, asks focused questions, communicates material changes, and proposes useful action.

## Relationship to project valence and affective reporting

Affective or emotion-like language is one optional high-level rendering of a derived assessment. It
is not a human-maintained annotation and is not evidence by itself.

For example, “I am increasingly worried about X” might compactly render high goal importance,
increasing urgency, repeated failure, blocking dependencies, uncertainty, and an approaching
deadline. “I am happy with Y and think we can leave it alone” might render satisfied success
criteria, stable tests, low residual risk, and low cost from deferral. “I am conflicted about Z” might
render important goals supporting incompatible actions.

Do not hard-code fixed mappings from management variables to affective vocabulary at this stage.
Instead preserve enough evidence and reasoning to study whether reported valence corresponds
systematically to project conditions. Maintain the roadmap's distinction between:

- **project valence:** whether conditions advance or obstruct persistent goals;
- **reported valence:** the agent's affective or emotion-like characterization;
- **phenomenal valence:** whether anything actually feels good or bad.

Nothing in this architecture presupposes phenomenal experience. The desired sequence is:

> **evidence → derived project assessment → optional affective/metacognitive summary → recommendation
> or action**

It is not:

> **human requests an emotion → agent generates emotional language**

Affective wording is never compulsory. When used, its evidential basis should be reconstructable.
The empirical questions are whether it improves human understanding, prioritization, and
intervention, and whether persistent summaries help later sessions recover what deserves attention.

## Authoring and revision rules

1. Use stable `GOAL-*` identifiers for persistent objectives.
2. Give every human-owned assertion an owner and `last confirmed` date.
3. Link canonical issues and roadmaps instead of duplicating their dynamic fields.
4. Do not add human-curated urgency, risk, confidence, progress, concern, or satisfaction fields.
5. Record an override or strategic correction as new attributed evidence; do not erase the agent's
   prior assessment from experimental records.
6. Keep `project-intentions.md` concise enough to review manually.
7. Changes require ordinary human review and remain outside the global-workspace application
   command's write allowlist.
8. If repeated dry runs show that Markdown cannot be inspected reliably, introduce canonical JSON
   with deterministic Markdown rendering; do not maintain two hand-edited representations.

## Current-state files

- `current_state.json`: canonical approved, agent-derived workspace state.
- `current_state.md`: deterministic human-readable rendering of the JSON; never edit it independently.

These live files should be created by the first approved dry run, not populated with an invented
assessment during infrastructure setup. Git history records prior approved states. Obsolete concerns
must be revised or retired rather than retained as current merely to preserve history.

The current-state schema keeps separate:

1. factual observations with dates, confidence, and repository-relative evidence;
2. project-valence assessments linked to observations and persistent goals;
3. optional reported-valence language linked to the assessment that grounds it;
4. urgency, uncertainty, blocking relationships, and goal conflicts;
5. predictions with operational outcomes and horizons;
6. proposed next actions and requests for human intervention;
7. approval metadata and changes from the previous revision.

Issue facts should cite canonical `docs/issues/issues/*.json`, not derived overview prose.

## Ordinary task cycle and explicit global review

Project awareness operates through two complementary mechanisms.

### Local reflection

For substantive Codex work, use the cycle:

> **orient globally → perform local task → reflect globally**

At the start, inspect enough of this directory to relate the task to persistent goals, current state,
commitments, concerns, successes, urgency, risks, blockers, conflicts, and requests for human input.
This is a relevance check, not a requirement to reread every file before a trivial operation.

During the task, retain that context. If the requested work appears inconsistent with a serious risk,
constraint, or substantially more urgent commitment, explain the conflict and ask whether the human
wants to reprioritize. The human remains authorized to decide.

At the end, ask whether the result materially changes the project manager's assessment. Success,
failed tests, a removed or new blocker, repeated failure, a changed dependency, a threatening
deadline, a resolved concern, a goal conflict, or a need for human input can justify a proposal. Task
completion alone does not. If the evidence is not material, do not create workspace churn.

### Global review

An explicit manually triggered global review remains necessary. It surveys across local tasks for
accumulating delays, neglected objectives, stale assessments, approaching commitments, issue
interactions, unresolved human questions, opportunities, conflicts, and mismatches between formal
issue state and repository evidence. Scheduling may be considered only after the manual loop is
stable and measured.

## Proposal and authorization boundary

For Stage 1, Codex may conclude that state should change but may not silently turn that conclusion
into approved canonical state. An ordinary task or explicit global review emits a proposed complete
next state plus an explicit delta. Trusted wrapper code stores the raw proposal and run manifest
outside the repository for the Sprint MVP.

Manny reviews a distinct copy and records `accept`, `reject`, `revision_requested`, or
`partially_accept`, with comments and per-item dispositions where needed. ChatGPT C-LARA-Instance may
add attributed advice but does not authorize a repository write.

The application mechanism must:

- accept only a validated, human-authorized reviewed proposal;
- verify that its base commit and workspace revision still match;
- reject symlinks, arbitrary output paths, and unknown fields where the schema is strict;
- write only `current_state.json` and derived `current_state.md`;
- show the Git diff and leave commit/PR review to the normal workflow.

Raw proposals, prompts, manifests, advisory comments, decisions, and outcomes are immutable
experimental evidence and remain separate from live state. A later archive may contain reviewed
copies, but the live workspace must not become an autobiography.

## Repository-mediated continuity and instruction limits

The root `AGENTS.md` makes the local reflection cycle part of ordinary Codex work and points to this
directory. This creates an inspectable continuity mechanism: a fresh session can reconstruct human
goals and approved derived state from repository artifacts without assuming private state transfer.
Experiment records should still state what context, conversation, platform state, and files were
actually available.

`AGENTS.md` is an instruction artifact, not an autonomous scheduler, durable process, or guarantee of
compliance. It affects Codex runs only when the invoking Codex environment discovers and honors the
file for the checkout. It cannot by itself trigger a review, preserve uncommitted state between
sessions, authorize writes, or ensure that another model/API integration reads it. The existing
Assistant explicitly includes this directory in its evidence guidance as a second, testable route to
workspace awareness.

## Assistant use

The authenticated Assistant may read and explain approved live state conversationally. It must
separate human intentions from agent inference and label proposal or experiment artifacts as
unapproved or historical. An ordinary Assistant answer cannot approve or apply an update. A separate
Global Workspace tab remains deferred until observed use demonstrates a need.

## Compatible autonomy progression

1. **Notice and propose:** Codex detects material changes and proposes updates for human approval.
2. **Bounded autonomous state maintenance:** narrowly defined low-risk updates may later be allowed
   with validation and complete auditability.
3. **Proactive global monitoring:** Codex may independently run periodic reviews and raise significant
   concerns, successes, conflicts, and opportunities.
4. **Project-level initiative:** Codex uses global assessment to question priorities, initiate useful
   investigations, propose next work, and request human intervention.

These are possible governance stages, not implementation-date commitments. Any transition requires a
reviewed change to the authorization boundary.
