# Workplan conventions and project-manager responsibility

This directory records durable, human-owned strategic intention needed to interpret C-LARA-2's
roadmaps, canonical issues, and other project evidence. It also defines the division of
responsibility between human collaborators and the top-level project-manager agent.

> **Humans define and revise project intentions, commitments, constraints, and authoritative facts.
> The project-manager agent autonomously derives and maintains the project-management interpretation
> of those facts.**

The purpose is not to make humans maintain a more elaborate issue tracker. It is to give the agent
stable strategic reference points from which it can infer what is urgent, risky, blocked, promising,
going well, or in need of intervention.

## Files and canonical ownership

The Sprint-minimal workplan uses one human-authored file:

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
- the workplan owns human intentions and authoritative external/contextual facts that cannot be
  derived reliably from repository state;
- `docs/global_workspace/current_state.json` owns the agent's approved, revisable project-management
  interpretation.

Do not copy an issue's state, priority, dependency array, or deadline into the workplan. Link its ID
and state why it matters. If an external commitment creates actionable dated work, create or update a
canonical issue and refer to it from the workplan.

## Human-owned intention and facts

The workplan should contain information that genuinely needs human authority, including:

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

These judgments should be inferred from workplan intentions together with roadmaps, canonical issue
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

The workplan records durable human-owned intention and strategic context. The global workspace
records the project manager's current derived interpretation of how the project is going.

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

Nothing in the workplan presupposes phenomenal experience. The desired sequence is:

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
6. Keep project intentions concise enough to review manually.
7. Changes require ordinary human review and remain outside the global-workspace application
   command's write allowlist.
8. If repeated dry runs show that Markdown cannot be inspected reliably, introduce canonical JSON
   with deterministic Markdown rendering; do not maintain two hand-edited representations.
