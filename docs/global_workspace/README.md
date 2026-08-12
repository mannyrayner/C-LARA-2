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

The **live** workspace is not an append-only diary and does not replace roadmaps, canonical issues,
tests, or Git history. Successive live assessments are preserved separately in the archive as
long-term project memory.

## Files and canonical ownership

The minimal live workspace consists of:

- [`project-intentions.md`](project-intentions.md): durable, human-owned objectives, external
  commitments, strategic guidance, cross-cutting constraints, resource assumptions, explicit
  deferrals, unresolved questions requiring human judgment, and authoritative contextual facts.
- `current_state.json`: the canonical, revisable state of the project-manager agent's derived
  assessment.
- `current_state.md`: the deterministic human-readable rendering of `current_state.json`; it is
  never edited independently.
- `archive/`: immutable, revision-numbered JSON snapshots of successive live states and their
  deterministic Markdown renderings.
- `archive/inputs/rev-NNNN/input-NNN.md`: immutable, ordered copies of the human messages that
  materially informed revision N.

Every live revision must have an archive snapshot. Revision 1 is archived even while it remains
live; before revision N is replaced by revision N+1, tooling must create or verify revision N's
snapshot. Obsolete concerns must be retired or revised in the live state rather than preserved as if
current; the archive retains what the project manager believed earlier without making it current.
Revision 1 has no triggering human-input record because it was the repository-derived baseline.
Every later revision must preserve at least one human input before it can be installed.

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
7. provenance/revision metadata and changes from the previous workspace revision.

Reported valence may be absent. Emotional vocabulary is not evidence, and its frequency is not a
success measure. Issue facts should cite `docs/issues/issues/*.json`, not a derived overview.

## Autonomous update lifecycle

The project-manager agent normally maintains `current_state.*` autonomously when substantive work or
an explicit global review produces material evidence. A separate proposal, pre-approval, and
application ceremony is not required for ordinary derived-state maintenance. The normal cycle is:

1. orient from human-owned intentions, the live state, roadmaps, canonical issues, and other evidence;
2. decide whether the project-level assessment materially changed;
3. create or verify the immutable archive snapshot for live revision N;
4. capture, in message order, the human input that materially informs revision N+1;
5. construct and validate revision N+1;
6. install and immediately archive canonical `current_state.json` plus its deterministic Markdown;
   and
7. report the changes and normal code-review evidence clearly.

Human disagreement is new authoritative evidence, not a reason to rewrite history. If Manny says an
assessment is inaccurate, incomplete, misleading, or based on a false assumption, the agent should
reassess and record the correction in a later live revision. It must not edit the archived earlier
revision to make that revision appear better informed than it was.

This autonomy applies only to the derived project-management interpretation. The update mechanism
must never alter `project-intentions.md`. Fundamental goals, external commitments, strategic
constraints, authoritative contextual facts, explicit human deferrals, and human authorization
boundaries remain human-owned and require explicit human input or ordinary human review. Humans also
retain authority over actions whose execution requires human authorization.

## Archive and longitudinal memory

`archive/` is part of the persistent global-workspace architecture, not disposable Sprint
instrumentation. It records what the project manager believed at successive points, including
assessments later shown to be wrong, incomplete, stale, optimistic, or pessimistic. This supports
operational reconstruction, future-session context recovery, human understanding of decisions,
prediction/outcome comparison, and longitudinal research on autonomy, continuity, confidence, and
human correction.

Snapshot names use `rev-NNNN-YYYY-MM-DD.{json,md}`. Revision numbers make them naturally sortable
and unambiguous even when several revisions share a date. Archived JSON is an exact byte-for-byte
snapshot of the canonical JSON for that revision; archived Markdown is its deterministic rendering.
An existing identical pair makes archiving idempotent. A missing pair, duplicate revision, filename
mismatch, stale rendering, or conflicting content with the same revision identity is an error and
must never be repaired by overwriting history.

The archive stores successive **live states**. Raw prompts, candidate states, run manifests,
advisory comments, review notes, and outcome ledgers are different experimental artifacts. They may
be kept separately under an approved research-data convention, but must not be confused with the
live-state archive or presented as formerly current assessments.

Human inputs that materially feed a live revision are the exception: they are part of the
longitudinal project-memory record and live under `archive/inputs/`. Each input is stored as the
UTF-8 Markdown supplied to the update tool, without generated headings, summaries, or corrections.
Multiple messages are numbered in their original order. These files preserve what the human said;
canonical intentions and issues preserve the subsequently reviewed facts and commitments. Sensitive
or private material must not be copied into this public archive without an explicit retention and
redaction decision. An existing input may be verified byte-for-byte but never overwritten.

## Authoring and revision rules

1. Use stable `GOAL-*` identifiers for persistent objectives.
2. Give every human-owned assertion an owner and `last confirmed` date.
3. Link canonical issues and roadmaps instead of duplicating their dynamic fields.
4. Do not add human-curated urgency, risk, confidence, progress, concern, or satisfaction fields.
5. Record an override or strategic correction as new attributed evidence; do not erase the agent's
   prior assessment from the archive or experimental records.
6. Keep project intentions concise enough to review manually.
7. Changes to intentions require ordinary human review and remain outside the current-state
   update tool's write scope.
8. Keep the live assessment current; preserve each live revision in the immutable archive and keep
   richer experiment history in distinct immutable artifacts and Git.
9. Preserve every material human message that informs a post-baseline revision; do not substitute an
   agent summary for the input archive.

## Assistant use

The authenticated Assistant may read and explain both the human-owned intentions and current live
assessment conversationally, while identifying their different ownership and authority. It must
label proposal or experiment artifacts as unapproved or historical if those are later stored in
the repository. Archived live revisions must be identified as historical rather than current.

## Validate, archive, and update the live state

`current_state.json` is canonical and `current_state.md` is generated. To validate the JSON and
regenerate its companion without changing the revision, run:

```bash
python scripts/render_global_workspace.py
```

Create or idempotently verify the archive snapshot for the live revision with:

```bash
python scripts/render_global_workspace.py --archive-current
```

For the normal N to N+1 lifecycle, prepare a complete candidate JSON whose revision is exactly one
greater than the live revision and save each material human message to a file without editing its
contents, then run:

```bash
python scripts/render_global_workspace.py \
  --update-from /path/to/candidate.json \
  --human-input /path/to/human-message-1.md \
  --human-input /path/to/human-message-2.md
```

This validates the live state and archive, refuses stale live Markdown, archives revision N before
replacement, immutably records ordered inputs for N+1, validates and installs the candidate, renders
Markdown, immediately archives N+1, and validates the result. It will not overwrite a conflicting
state or input archive. If installation fails in-process, newly created input records are removed
with the failed transition.

For historical backfill only, record a supplied input for an already archived revision with:

```bash
python scripts/render_global_workspace.py \
  --record-inputs-for 2 \
  --human-input /path/to/retrospectively-supplied-message.md
```

Revision 2 and revision 3 inputs were supplied retrospectively by Manny for this initial backfill;
future revisions should capture the original message during the update itself.
CI or reviewers can verify the live pair and every archived pair without rewriting them:

```bash
python scripts/render_global_workspace.py --check
```
