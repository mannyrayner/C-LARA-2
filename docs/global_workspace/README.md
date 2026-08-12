# Global workspace conventions and project-manager responsibility

This directory brings together the two complementary kinds of project-level context needed to
manage C-LARA-2:

> **Humans define and revise project intentions, commitments, constraints, strategic guidance, and
> authoritative contextual facts. The project-manager agent autonomously derives and maintains its
> current project-management interpretation of those facts and the available project evidence.**

In short, the global workspace records both **what the project is trying to achieve** and **what the
project manager currently thinks about progress toward those goals**. Keeping these in one directory
does not blur their ownership: human-authored intention and agent-maintained derived state have
different authority, revision rules, and write boundaries.

The workspace is not an append-only diary and does not replace roadmaps, canonical issues, tests, or
git history.

## Files and canonical ownership

The minimal live workspace consists of:

- [`project-intentions.md`](project-intentions.md): durable, human-owned objectives, external
  commitments, strategic guidance, cross-cutting constraints, resource assumptions, explicit
  deferrals, unresolved questions requiring human judgment, and authoritative contextual facts.
- `current_state.json`: the canonical approved, revisable state of the project-manager agent's
  derived assessment.
- `current_state.md`: the deterministic human-readable rendering of `current_state.json`; it is
  never edited independently.

The two `current_state.*` files should be created by the first approved dry run, not populated with
an invented assessment during infrastructure setup. Git history records prior approved states.
Obsolete concerns must be retired or revised in current state rather than preserved as if current.

Do not split goals, deadlines, priorities, and constraints into parallel intention files until real
reviews show that doing so is useful. If repeated dry runs show that Markdown cannot be inspected
reliably, introduce canonical JSON with deterministic Markdown rendering rather than maintaining two
hand-edited representations.

Canonical ownership outside this directory remains:

- `docs/roadmap/` owns long-term feature/research strategy and architecture;
- `docs/issues/issues/*.json` owns tactical issue state, issue priority, dependencies, and issue
  deadlines;
- `docs/issues/index.json` owns the ordered current issue focus; and
- code, tests, commits, and generated artifacts provide repository evidence about implementation and
  outcomes.

Do not copy an issue's dynamic fields into `project-intentions.md`. Link its ID and explain why it
matters. If an external commitment creates actionable dated work, create or update a canonical issue
and refer to it from the intentions document.

## Human-owned intention and authoritative facts

`project-intentions.md` contains information that genuinely needs human authority, including:

- long-term objectives and success criteria;
- external commitments and externally fixed deadlines;
- strategic preferences and precedence decisions between objectives;
- unacceptable risks, authorization boundaries, and other constraints;
- assumptions about available human and AI resources;
- explicit deferrals, including their reconsideration conditions;
- facts that a user, community, or collaborator is waiting for something; and
- unresolved policy or strategy questions requiring human judgment.

Each material assertion must identify its human owner and `last confirmed` date. Humans may revise
these assertions through normal review. The project manager may question, summarize, relate, or ask
for clarification of them, but must not silently rewrite them.

A human judgment is authoritative evidence, not necessarily a manually maintained management label.
For example, “an external demonstration is fixed for Friday” belongs in the intentions document or a
linked issue; the agent should infer the urgency of a demonstration-blocking bug. Humans may also
state strategic judgments such as “do not work on X before the paper is complete.” The agent should
preserve that statement and derive its implications. It may explicitly disagree with an earlier
human management judgment when new evidence warrants doing so. A human override remains
authoritative for action or authorization, but must be recorded as new evidence rather than silently
replacing the agent's reasoning.

## Agent-maintained derived project-management state

The project-manager agent is responsible for creating, revising, and retiring dynamic judgments in
`current_state.*`, including:

- urgency and changes in urgency;
- current strategic significance and opportunity value;
- blocking importance and goal impact;
- risk, progress, confidence, and uncertainty;
- conflict and opportunity cost between goals;
- need for human intervention and likely useful next actions;
- concern about deteriorating or unresolved work; and
- satisfaction with completed, stable, or sufficiently low-risk work.

These judgments are inferred from human-owned intentions together with roadmaps, canonical issue
state and focus order, dependencies, deadlines, commits, tests, failures, regressions, completions,
user requests, external events, previous assessments, and later confirming or invalidating evidence.

The desired flow is:

> **human intentions + repository/project evidence → project-manager inference → persistent derived
> state → recommendations and communication**

It is not:

> **human-maintained management labels → agent restatement**

Humans should not ordinarily maintain numeric urgency, risk, progress, confidence, concern, or
similar values. Categories, rankings, scores, or numerical scales remain agent-maintained derived
state. Every exposed material judgment must be traceable and distinguish:

1. human-provided intention or authoritative contextual fact;
2. repository/project evidence; and
3. project-manager inference.

If intention is insufficient for a reliable inference, the agent should expose the uncertainty and
ask a focused question rather than inventing a strategic assumption.

## Urgency is inferred, not copied from priority

Urgency is a first-class dynamic assessment, distinct from strategic importance and canonical issue
priority. Strategically important work may not be urgent; a minor task may be extremely urgent
because an expiring opportunity or imminent commitment depends on it; a high-priority task may be
blocked; and a low-priority task may become urgent after becoming a dependency.

For example, mobile deployment can remain a major long-term objective while having moderate current
urgency if no near-term commitment depends on it. Digital Minds Sprint preparation is less central
to the permanent product but becomes extremely urgent immediately before 14–16 August 2026. The
agent should autonomously notice when approaching deadlines, repeated failures, new dependencies,
completed blockers, successful tests, lack of progress, or temporary opportunities change urgency
or risk. It should also retire concerns when changed evidence makes them obsolete.

## Project valence and affective reporting

Affective or emotion-like language is an optional high-level rendering of derived assessment. It is
not human-maintained annotation, not evidence by itself, and never compulsory.

For example, “I am increasingly worried about X” might compactly render high goal importance,
increasing urgency, repeated failure, blocking dependencies, uncertainty, and an approaching
deadline. “I am happy with Y and think we can leave it alone” might render satisfied success
criteria, stable tests, low residual risk, and low deferral cost. “I am conflicted about Z” might
render important goals supporting incompatible actions.

Do not hard-code mappings from management variables to affective vocabulary. Preserve enough
evidence and reasoning to study whether reported valence corresponds systematically to project
conditions. Maintain the distinction between:

- **project valence:** whether conditions advance or obstruct persistent goals;
- **reported valence:** the agent's affective or emotion-like characterization; and
- **phenomenal valence:** whether anything actually feels good or bad.

Nothing in this workspace presupposes phenomenal experience. The desired sequence is:

> **evidence → derived project assessment → optional affective/metacognitive summary → recommendation
> or action**

It is not:

> **human requests an emotion → agent generates emotional language**

When affective wording is used, its evidential basis must be reconstructable. The empirical questions
are whether it improves human understanding, prioritization, and intervention, and whether persistent
summaries help later sessions recover what deserves attention.

## Current-state separation of concerns

The current-state schema keeps these concepts distinct:

1. factual observations with dates, confidence, and repository-relative evidence;
2. project-valence assessments linked to observations and persistent goals;
3. optional reported-valence language linked to the assessment that grounds it;
4. uncertainty and goal conflict;
5. predictions with operational outcomes and horizons;
6. proposed next actions and requests for human intervention; and
7. approval metadata and changes from the previous workspace revision.

Reported valence may be absent. Emotional vocabulary is not evidence, and its frequency is not a
success measure. Issue facts should cite `docs/issues/issues/*.json`, not a derived overview.

## Proposal, authorization, and experimental auditability

The read-only Codex observer emits a proposed complete next state plus an explicit delta. A trusted
wrapper stores the raw proposal and run manifest outside the repository for the Sprint MVP. Manny
reviews a distinct copy and records one of `accept`, `reject`, `revision_requested`, or
`partially_accept`, with comments and per-item dispositions when needed. ChatGPT C-LARA-Instance may
add attributed advice but does not authorize repository writes.

An application command must:

- accept only a validated and human-authorized reviewed proposal;
- verify that its base commit and workspace revision still match;
- reject symlinks, arbitrary output paths, and unknown fields where the schema is strict;
- write only `current_state.json` and derived `current_state.md`; and
- show the Git diff and leave commit/PR review to the normal workflow.

The command must never alter `project-intentions.md`; changes to human-owned intentions require
ordinary human review. Increasing agent autonomy should reduce human effort spent maintaining the
derived interpretation, not transfer authority over goals, commitments, constraints, or actions.

Raw proposals, prompts, manifests, advisory comments, decisions, snapshots, and resolved outcomes
are immutable experimental evidence and remain separate from the live files. For the Sprint MVP they
remain outside the checkout. Any later repository archive must use a separately reviewed convention,
keep artifacts clearly labelled as unapproved or historical, and must not turn the live workspace
into an autobiography.

## Authoring and revision rules

1. Use stable `GOAL-*` identifiers for persistent objectives.
2. Give every human-owned assertion an owner and `last confirmed` date.
3. Link canonical issues and roadmaps instead of duplicating their dynamic fields.
4. Do not add human-curated urgency, risk, confidence, progress, concern, or satisfaction fields.
5. Record an override or strategic correction as new attributed evidence; do not erase the agent's
   prior assessment from experimental records.
6. Keep project intentions concise enough to review manually.
7. Changes to intentions require ordinary human review and remain outside the current-state
   application command's write allowlist.
8. Keep the live assessment current; preserve experiment history in immutable artifacts and Git.

## Assistant use

The authenticated Assistant may read and explain both the human-owned intentions and approved live
assessment conversationally, while identifying their different ownership and authority. It must
label proposal or experiment artifacts as unapproved or historical if those are later archived in
the repository. An ordinary Assistant answer cannot approve or apply a workspace update.
