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

