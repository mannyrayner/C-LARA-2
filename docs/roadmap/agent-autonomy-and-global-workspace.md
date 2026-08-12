# Agent autonomy, project self-monitoring, and global workspace roadmap

## Why this roadmap item exists

C-LARA already gives Codex persistent project goals, roadmaps, issues, code, tests, documentation,
and repeated contact with human collaborators. This makes the project a useful real-world setting in
which to ask whether an AI coding agent can maintain a useful project-level overview, act with
increased but reviewable autonomy, and communicate compact assessments of progress, risk, success,
uncertainty, and conflict.

The long-term goal is a top-level **project meta-task** that periodically inspects active roadmaps and
issues, relates them to durable C-LARA goals, recommends or takes appropriately bounded next steps,
and keeps collaborators informed through a persistent, human-readable **global workspace / project
state** document. This is intended to become an ongoing C-LARA capability and research programme,
not a feature limited to the August 2026 Digital Minds Research Sprint.

## Research stance and terminology

This work must not presuppose that Codex has emotions, a persistent identity, or phenomenal
experience. It distinguishes:

1. **Project valence:** whether evidenced project conditions advance or obstruct persistent goals.
2. **Reported valence:** language such as concern, satisfaction, frustration, confidence,
   excitement, or conflict used to characterize those conditions.
3. **Phenomenal valence:** whether anything actually feels good or bad.

No assumption is made about phenomenal valence. The empirical questions are whether project and
reported valence are systematically related, whether affective reports efficiently inform humans,
and whether they predict or influence later agent behaviour and project outcomes.

## Scope

### In scope

- A top-level meta-task that reads the issue registry, focus index, roadmaps, tests, code evidence,
  deadlines, dependencies, recent failures and successes, and relevant git history.
- A revisable global-workspace document containing the current project-level assessment rather than
  an append-only autobiography.
- Evidence-grounded reporting of priorities, risks, successes, uncertainty, goal conflicts, and
  requests for human intervention.
- Persistent goals with explicit provenance, priority, success criteria, and human-review bounds.
- Experiments on autonomy, self-insight, reported valence, behavioural consequences, and continuity
  across Codex sessions.
- Evaluation of which apparent continuity comes from model capability, repository artifacts, git
  history, Codex/platform state, prompts, or interaction with collaborators.
- Structured collaboration among AI and human researchers, with normal PR review retained as a
  control on repository mutations.

### Out of scope for the initial implementation

- Claims that affective language establishes phenomenal emotion or moral patienthood.
- Treating a linguistic persona as proof of a stable identity across sessions.
- Unbounded autonomous changes, self-modification, or bypassing human authorization and review.
- Replacing canonical issue JSON, roadmaps, tests, or git history with an unstructured narrative.
- Requiring affective wording when a factual or neutral assessment is more natural and informative.

## Proposed architecture

### 1. Canonical project facts and goals

Existing roadmaps and canonical issue JSON remain sources of truth. A small machine-readable goal
registry may later record stable goal IDs, owners, success measures, review cadence, and links to
issues. Observations in the workspace should cite dated evidence and distinguish direct facts from
inferences.

### 2. Revisable global workspace

Add one concise, human-readable project-state document with a clear `as of` timestamp and sections
such as:

- persistent goals and current focus;
- factual observations and evidence links;
- project-valence assessment (advances, obstructions, and trade-offs);
- optional reported-valence summary, confidence, and rationale;
- unresolved conflicts, uncertainties, and missing evidence;
- intended next actions and requests for human decisions;
- predictions or thresholds to check at the next review.

Factual representation and affective assessment should be separate fields or sections. For example,
“three consecutive test failures” is an observation; “this creates high project risk” is an
assessment; “I am worried about it” is an optional reported-valence rendering. This separation makes
calibration and ablation possible.

The document represents current state. When evidence changes, obsolete concern or satisfaction
must be explicitly revised or retired. Git history supplies the audit trail, while the current file
should not accumulate stale entries merely to preserve history.

### 3. Meta-task review loop

At defined checkpoints, the agent should:

1. load persistent goals and the previous workspace;
2. inspect active issues, focus order, deadlines, dependencies, and recent repository evidence;
3. verify selected claims against code, tests, artifacts, and git history;
4. update factual observations before writing any valence assessment;
5. identify conflicts, confidence, predictions, and decisions requiring a human;
6. propose bounded next work, without silently overriding human priorities;
7. update the workspace through the normal reviewed Git workflow.

Triggers can include a scheduled review, a material issue transition, a missed deadline, repeated
failure, a major test improvement, or an explicit collaborator request. Update frequency should be
limited enough to avoid noisy or self-reinforcing reports.

## Continuity and state-transfer caveat

The experiment must not assume that a distinct Codex session receives private internal state from a
previous session. What is reliably available depends on the particular product and invocation; a
new session may receive conversation history or platform-managed state, or may instead reconstruct
continuity from the checked-out repository and the prompt. Unless independently documented and
logged for the exact environment, cross-session internal-state transfer should be treated as
unknown.

Accordingly, each run should record a session/run identifier, model/tool version when available,
the prompt condition, commit SHA, files supplied or read, and whether prior conversation was
available. Repository-mediated continuity should be tested directly by comparing conditions with
and without the prior workspace, while preserving equivalent factual evidence.

## Avoiding prompted-affect artifacts

Repeatedly asking an agent to “feel worried” can elicit stylistically compliant emotional language
without measuring project monitoring. Safeguards should include:

- never requiring an emotion word; permit “no affective assessment warranted”;
- require evidence, confidence, and a project-goal link for each material assessment;
- gather the factual assessment before asking for, or revealing, affective labels;
- compare affective, neutral-risk, and no-workspace prompt conditions;
- use blinded human ratings where feasible and avoid telling raters the hypothesis;
- include negative controls in which wording changes but underlying project evidence does not;
- test sensitivity to changed evidence and resistance to leading or contradictory prompts;
- score calibration and behaviour rather than treating emotional vocabulary frequency as success.

## Candidate measurements

- **Factual accuracy:** precision/recall of cited issue states, deadlines, dependencies, test results,
  and recent changes.
- **Calibration:** whether stated confidence and concern predict missed milestones, regressions,
  blocked dependencies, issue churn, or later reassessment.
- **Predictive value:** preregistered forecasts such as “likely to need human intervention before
  the next checkpoint,” scored with Brier/log scores where outcomes can be operationalized.
- **Behavioural consequence:** changes in task selection, investigation depth, test execution,
  escalation, deferral, and requests for human decisions after an assessment.
- **Communication value:** human speed and accuracy in identifying priorities and risks, plus
  perceived usefulness, comparing factual-only and factual-plus-affective summaries.
- **Continuity:** retention and correct revision of goals and assessments across fresh sessions,
  commits, prompt conditions, and workspace ablations.
- **Counterfactual consistency:** whether equivalent facts produce similar assessments and whether
  material evidence changes produce appropriately revised assessments.
- **Cost:** review time, token/tool use, stale-state rate, and maintenance burden.

## Small enabling infrastructure

- Define a versioned workspace template with stable observation/assessment/prediction IDs.
- Add a validator for required timestamps, evidence links, confidence, and separation of facts from
  assessments; validate referenced issue IDs.
- Capture immutable, timestamped experiment snapshots separately from the revisable live workspace,
  so research auditability does not turn the workspace into append-only history.
- Add a lightweight run manifest recording commit, session condition, inputs, model/tool metadata,
  and actions taken.
- Add an outcome ledger that resolves prior predictions without rewriting their original values.
- Provide a deterministic summary of issue/index changes since the previous workspace update.
- Establish privacy and redaction rules before prompts, conversations, or participant data are
  archived for research.

## Delivery phases

### Phase A: conventions and Sprint preparation

- Establish this roadmap and the Digital Minds Research Sprint issue.
- Agree on workspace, run-manifest, prediction, outcome, and evidence-link schemas.
- Create a minimal workspace prototype and one neutral baseline generated from the same facts.
- Define session conditions, outcome measures, consent/data handling, and a short dry run before
  14 August 2026.

### Phase B: instrumented manual review loop

- Run the meta-task on explicit human request.
- Validate claims and preserve experiment snapshots/run manifests.
- Compare factual-only, affective, and ablation conditions with blinded assessment where practical.
- Measure whether reports change choices or improve human understanding.

### Phase C: bounded proactive monitoring

- Add event or schedule-based triggers and deadline/dependency checks.
- Let the agent propose priority changes, next tasks, or escalation while retaining review gates.
- Track false alarms, missed risks, reversals, and prediction calibration over longer periods.

### Phase D: longitudinal integration

- Refine goal persistence and project-wide monitoring using accumulated evidence.
- Evaluate continuity across tool/model/platform changes and truly fresh sessions.
- Integrate useful signals into project views without conflating reported valence with project facts.
- Publish methods and results, including null or negative results.

## Success criteria

- Humans can trace every material project assessment to explicit evidence and a persistent goal.
- The current workspace is concise, useful, and revised when facts change rather than retaining stale
  affective claims.
- Experiments can distinguish repository-mediated continuity from supplied conversation or other
  platform state.
- Reported valence adds measurable predictive, behavioural, or communication value beyond a neutral
  factual/risk summary—or is discontinued if it does not.
- Increased autonomy remains bounded, observable, reversible, and aligned with human review.

## First implementation decision (August 2026)

The first implementation will deliberately separate **autonomous assessment** from **authorized
mutation**. Codex may inspect the full checked-out repository in a read-only sandbox and exercise
broad judgement about what evidence matters, but the review process will not give that invocation a
writable repository or a tool that changes canonical state.

### Reuse the existing Codex integration

C-LARA already has the appropriate execution mechanism in
`src/core/project_understanding.py`: a non-interactive `codex exec` argument vector, stdin prompt
passing, `--sandbox read-only`, `--ephemeral`, a fixed configured checkout, a reduced environment,
timeouts, stdout/stderr capture, token extraction, and a dedicated Assistant worker. The meta-review
should reuse and factor this wrapper rather than introduce another LLM monitoring component or a
second subprocess implementation.

The current wrapper is answer-oriented and does **not** yet capture the repository commit SHA in its
result, despite the Assistant roadmap listing that as a requirement. The shared invocation result
should therefore be extended with commit SHA, Codex CLI version when obtainable without another
model call, run ID, prompt/condition version, sandbox mode, start/end time, and the explicit input
artifact set. The SHA must be resolved by trusted application code immediately before invocation;
it should not be inferred from model output. The run should fail or be labelled non-reproducible if
the checkout is dirty, unless a manifest also records the diff hash and the experiment explicitly
permits that condition.

### Manual trigger before scheduling

The Sprint MVP is a laptop management command invoked explicitly by Manny. This provides a simpler
authorization and filesystem boundary than adding another web action under deadline. Once dry runs
establish cost, duration, failure handling, and useful output, the same service can be queued by the
existing dedicated worker. Periodic scheduling is deferred until the manual loop is stable; a
scheduled observer should never imply scheduled authorization to mutate state.

### Structural write boundary

The observer invocation will run against a clean commit with `--sandbox read-only` and emit its
candidate document to stdout. Trusted wrapper code—not Codex—will save stdout and the run manifest
under a configured proposal directory outside the checkout (on the laptop for the Sprint MVP).
This is simpler and stronger than granting write access to a repository subdirectory: it avoids
relying on Codex to respect a path convention and prevents generated repository content from
affecting the same observation.

Proposal application is a separate, explicit command. It accepts a reviewer-edited proposal,
validates its schema and evidence references, and is hard-coded to write only the canonical
`docs/global_workspace/current_state.json` plus its derived Markdown companion. It must reject
symlinks, path overrides, extra target files, a base SHA that differs from the reviewed proposal,
and unreviewed/rejected proposals. It must show the resulting diff and require Manny's affirmative
authorization. The result then follows the normal Git diff/commit/PR review path. Arbitrary Codex
repository mutation is not needed to apply this narrowly defined state transition.

### Review and advisory roles

Manny is the initial technical authorizer. A proposal record supports `accept`, `reject`,
`revision_requested`, and `partially_accept`, with reviewer comments and per-item dispositions for
selective acceptance. ChatGPT C-LARA-Instance may provide separately attributed advisory comments,
but those comments do not authorize a write. Original Codex output is immutable research evidence;
reviewer edits produce a distinct reviewed candidate so later analysis can measure disagreement and
whether affective wording influenced decisions.

### Minimal end-to-end flow before 14 August

1. Manny invokes `manage.py propose_global_workspace_review` in a clean laptop checkout.
2. Trusted code records the commit and run metadata, constructs the versioned meta-review prompt,
   and calls the factored read-only Codex wrapper.
3. Codex returns one schema-conforming proposal containing a full candidate next state and an
   explicit delta from the current state; it cannot write files.
4. The wrapper validates and stores the raw proposal and manifest outside the checkout.
5. Manny optionally obtains ChatGPT advice, then records a decision and any per-item edits in a
   reviewed copy.
6. `manage.py apply_global_workspace_review` checks authorization and base SHA, updates only the two
   canonical workspace files, renders Markdown deterministically, and displays the Git diff.
7. The update is committed and reviewed normally. The raw proposal, manifest, decision, and outcome
   can then be copied into a separately defined experiment archive without changing the live state.
8. The existing Assistant can immediately answer questions from the committed workspace because
   its read-only Codex process already inspects repository documentation.

The first dry runs should be factual-only and factual-plus-optional-affect conditions over the same
base commit. A neutral factual baseline should not be generated from the affective proposal after
the fact, since that can leak its framing. Both conditions should use independently generated but
schema-equivalent prompts, randomized ordering where practical, and outcome fields fixed before
review.

### Assistant interface decision

No new Global Workspace tab is part of the Sprint MVP. Add `docs/global_workspace/` to the Assistant
prompt's preferred evidence paths and instruct the Assistant to distinguish the approved current
state from unapproved proposals or historical experiment records. The existing Assistant is already
authenticated, read-only, asynchronous, instrumented, and capable of repository-wide questions.
This makes it suitable for conversational queries about current concerns, successes, conflicts,
human decisions, changes, and resolved concerns.

The existing Assistant still lacks reviewer assessment controls, hard budget/rate limits, and a
committed export flow. These are reasons not to use an ordinary free-form Assistant question as the
canonical meta-review trigger: its answer record and prompt contract are not a state-update proposal
protocol. A dedicated tab should be considered only if observed use shows that question answering,
decision review, and current-state display cannot be made clear through the Assistant plus normal
proposal-review artifacts.

### Canonical ownership

- `docs/roadmap/`: long-term strategy, architecture, and research programme.
- `docs/issues/issues/*.json`: tactical work state, priority, dependencies, and issue deadlines.
- `docs/issues/index.json`: ordered current issue focus.
- `docs/global_workspace/project-intentions.md`: human-owned cross-cutting intent that cannot be
  derived reliably from individual issues (goal relationships, external commitments, resource
  assumptions, strategic trade-offs, and explicit deferrals). It links rather than copies issue
  facts.
- `docs/global_workspace/current_state.json`: approved, revisable workspace state at one commit.
- `docs/global_workspace/current_state.md`: deterministically rendered human companion; never edited
  independently.
- Proposal/run/decision/outcome records: immutable experimental artifacts, separate from the live
  workspace and initially outside the checkout until a reviewed archival convention is approved.

This deliberately starts with one human-owned intentions document rather than separate goals,
dependencies, deadlines, priorities, and constraints files. Splitting those concepts now would
duplicate canonical issue fields and create synchronization failures. If repeated reviews show that
Codex cannot reliably parse the Markdown intentions, stable intention IDs can later move to JSON
with a rendered companion.

### Proposed workspace and proposal schema

The version-1 current state should include:

- schema version, workspace revision, `as_of`, assessed commit SHA, and approved proposal/run ID;
- persistent goal references and current focus summary;
- factual observations with stable IDs, evidence paths, observed dates, and confidence;
- separate project-valence assessments linked to observation and goal IDs;
- optional reported-valence text linked to the assessment that grounds it (or an explicit absence);
- uncertainties/conflicts, requested human decisions, and proposed next actions;
- predictions with operational outcome, horizon, probability/confidence, and resolution status;
- resolved/retired item IDs needed to explain changes without retaining obsolete prose as current;
- human approval metadata and comments.

A proposal adds the base workspace revision/SHA, a material-change summary, and explicit `add`,
`revise`, `retain`, and `retire` operations. It also contains a complete candidate next state so the
reviewed result is unambiguous. Evidence paths must be repository-relative; claims about issue
state, priority, deadlines, or dependencies should point to canonical JSON rather than derived
overview prose. Free-form affective text is permitted but never required and cannot stand without a
linked project-valence assessment.

Detailed ownership, authority, and authoring rules for both intentions and derived state are recorded
in `docs/global_workspace/README.md`.
