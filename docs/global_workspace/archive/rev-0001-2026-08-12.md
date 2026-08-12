# C-LARA-2 current project state

> This file is generated from `current_state.json`; do not edit it directly.

- **Workspace revision:** 1
- **As of:** 2026-08-12T00:00:00Z
- **Assessed commit:** `23246418e5cb4b3081894db8ecfb81fff1d94931`
- **Approved proposal:** `INITIAL-BASELINE-2026-08-12`
- **Approved run:** None (direct initial baseline)
- **Persistent goals:** `GOAL-1`, `GOAL-2`, `GOAL-3`, `GOAL-4`, `GOAL-5`

## Current focus

The immediate focus is the time-critical Digital Minds Sprint/global-workspace loop. The broader project has a substantial working platform and several delivered user-facing and infrastructure capabilities, but progress is uneven: quality/regression coverage, mobile access, publication work, and several real-user workflow follow-ups remain incomplete or lack fresh verification. Legacy migration and the picture-dictionary workspace show concrete progress, while their next operational and user-validation steps remain open.

## Factual observations

### OBS-0001

The core text and linguistic pipeline is implemented, the Django platform has a strong initial implementation, and initial image generation and cloze exercise implementations have been delivered.

- **Observed:** 2026-08-12
- **Confidence:** high
- **Evidence:** [`docs/roadmap/README.md`](../roadmap/README.md)

### OBS-0002

Systematic end-to-end pipeline testing and UI regression tracking are still reported work, and known segmentation quality/failure investigations depend on the broader testing and evaluator work.

- **Observed:** 2026-08-12
- **Confidence:** high
- **Evidence:** [`docs/issues/issues/ISSUE-0003.json`](../issues/issues/ISSUE-0003.json), [`docs/issues/issues/ISSUE-0005.json`](../issues/issues/ISSUE-0005.json), [`docs/issues/issues/ISSUE-0006.json`](../issues/issues/ISSUE-0006.json), [`docs/issues/issues/ISSUE-0025.json`](../issues/issues/ISSUE-0025.json)

### OBS-0003

The unified picture-dictionary organiser workspace has received several implementation cuts, and subset creation plus flashcard generation were exercised successfully; however, the P0 workspace and P1 subset issues remain active and their July classroom-readiness targets have passed without recorded Sophie sign-off.

- **Observed:** 2026-08-12
- **Confidence:** high
- **Evidence:** [`docs/issues/issues/ISSUE-0037.json`](../issues/issues/ISSUE-0037.json), [`docs/issues/issues/ISSUE-0039.json`](../issues/issues/ISSUE-0039.json)

### OBS-0004

The authenticated project-understanding Assistant is implemented and operational on AWS through a dedicated worker, including a resolved self-query false-positive sequence; export/review controls, budgets, recovery hardening, and curated evaluation evidence remain open.

- **Observed:** 2026-08-12
- **Confidence:** high
- **Evidence:** [`docs/issues/issues/ISSUE-0034.json`](../issues/issues/ISSUE-0034.json), [`docs/roadmap/platform-self-knowledge-assistant.md`](../roadmap/platform-self-knowledge-assistant.md)

### OBS-0005

The global-workspace programme has human-confirmed intentions and operating conventions, but the initial current-state baseline and the instrumented propose/review/apply loop were not yet present at the assessed commit; Sprint preparation is active P0 with a 14 August deadline.

- **Observed:** 2026-08-12
- **Confidence:** high
- **Evidence:** [`docs/global_workspace/README.md`](../global_workspace/README.md), [`docs/issues/issues/ISSUE-0042.json`](../issues/issues/ISSUE-0042.json), [`docs/roadmap/agent-autonomy-and-global-workspace.md`](../roadmap/agent-autonomy-and-global-workspace.md)

### OBS-0006

Legacy source migration has progressed from individual imports to a validated Adelaide v3 library of 485 ZIPs and an initial provenance-aware, idempotent bulk importer; the full batch run, catalogue integration, and hosted compiled-LARA registration remain active work.

- **Observed:** 2026-08-12
- **Confidence:** high
- **Evidence:** [`docs/issues/issues/ISSUE-0001.json`](../issues/issues/ISSUE-0001.json), [`docs/issues/issues/ISSUE-0010.json`](../issues/issues/ISSUE-0010.json), [`docs/roadmap/unified-content-catalogue-and-legacy-migration.md`](../roadmap/unified-content-catalogue-and-legacy-migration.md)

### OBS-0007

Publication work is still reported rather than active: the issue's 15 June progress-report deadline and the roadmap's 31 July EuroCALL full-paper deadline have passed, while the repository records no updated disposition for those deliverables.

- **Observed:** 2026-08-12
- **Confidence:** high
- **Evidence:** [`docs/issues/issues/ISSUE-0008.json`](../issues/issues/ISSUE-0008.json), [`docs/roadmap/reports-and-papers.md`](../roadmap/reports-and-papers.md)

### OBS-0008

Mobile access is a documented major direction with a roadmap, but it has no issue in the current focus index and the roadmap primarily defines intended work rather than recorded delivery.

- **Observed:** 2026-08-12
- **Confidence:** medium
- **Evidence:** [`docs/issues/index.json`](../issues/index.json), [`docs/roadmap/mobile-access.md`](../roadmap/mobile-access.md)

### OBS-0009

Several concrete user-facing workflow gaps remain reported, including community-judging autosave, image-generation selection feedback, compiled-content navigation/access control, and community-recorded audio design.

- **Observed:** 2026-08-12
- **Confidence:** high
- **Evidence:** [`docs/issues/issues/ISSUE-0026.json`](../issues/issues/ISSUE-0026.json), [`docs/issues/issues/ISSUE-0029.json`](../issues/issues/ISSUE-0029.json), [`docs/issues/issues/ISSUE-0030.json`](../issues/issues/ISSUE-0030.json), [`docs/issues/issues/ISSUE-0031.json`](../issues/issues/ISSUE-0031.json)

### OBS-0010

Few-shot/MWE evaluation and named snapshots have substantial implementation notes but remain active; both still depend on broader quality or persistence work and need current acceptance evidence.

- **Observed:** 2026-08-12
- **Confidence:** high
- **Evidence:** [`docs/issues/issues/ISSUE-0036.json`](../issues/issues/ISSUE-0036.json), [`docs/issues/issues/ISSUE-0041.json`](../issues/issues/ISSUE-0041.json)

## Project-valence assessments

### ASM-0001

Platform maturity is meaningful but uneven: broad functionality exists, while weak systematic regression evidence and unresolved user-facing failures limit confidence in stability and ease of use.

- **Goals:** `GOAL-1`, `GOAL-5`
- **Grounding observations:** `OBS-0001`, `OBS-0002`, `OBS-0009`
- **Urgency / risk / progress:** high / high / mixed
- **Confidence:** high

### ASM-0002

The picture-dictionary work is a strong example of real-user-driven product progress, but overdue external validation makes its present classroom readiness uncertain.

- **Goals:** `GOAL-1`, `GOAL-5`
- **Grounding observations:** `OBS-0003`
- **Urgency / risk / progress:** high / medium / substantial_unverified
- **Confidence:** high

### ASM-0003

Useful autonomy has a credible deployed foundation in the Assistant, but the project-manager loop is not yet operational end to end and its near-term external deadline leaves very little contingency.

- **Goals:** `GOAL-2`, `GOAL-3`
- **Grounding observations:** `OBS-0004`, `OBS-0005`
- **Urgency / risk / progress:** critical / high / partial
- **Confidence:** high

### ASM-0004

The research programme has rich implementation evidence and a timely Sprint opportunity, but stale publication records create a serious uncertainty about missed, completed, or superseded commitments.

- **Goals:** `GOAL-3`
- **Grounding observations:** `OBS-0005`, `OBS-0007`, `OBS-0010`
- **Urgency / risk / progress:** critical / high / mixed_unknown
- **Confidence:** high

### ASM-0005

Legacy preservation has advanced materially and the main technical path is clearer, but value to users still depends on completing bulk operations and unified discovery/registration.

- **Goals:** `GOAL-1`, `GOAL-4`
- **Grounding observations:** `OBS-0006`
- **Urgency / risk / progress:** medium / medium / substantial_partial
- **Confidence:** high

### ASM-0006

Mobile use remains strategically important but appears displaced from active execution; without an explicit tactical issue or fresh status, near-term progress is unlikely.

- **Goals:** `GOAL-1`, `GOAL-5`
- **Grounding observations:** `OBS-0008`
- **Urgency / risk / progress:** medium / medium / limited_or_unrecorded
- **Confidence:** medium

### ASM-0007

The active portfolio is wider than the likely near-term capacity. The Sprint deadline should temporarily dominate, but quality infrastructure and overdue user validation should remain visible rather than silently losing priority.

- **Goals:** `GOAL-1`, `GOAL-2`, `GOAL-3`, `GOAL-5`
- **Grounding observations:** `OBS-0002`, `OBS-0003`, `OBS-0005`, `OBS-0007`, `OBS-0009`
- **Urgency / risk / progress:** critical / high / capacity_constrained
- **Confidence:** high

## Reported valence

None. This initial baseline deliberately uses neutral factual and assessment language.

## Uncertainties and conflicts

- **UNC-0001:** Repository evidence does not say whether the progress report and EuroCALL paper were completed elsewhere, missed, or superseded.
  - **Assessments:** `ASM-0004`
- **UNC-0002:** Repository evidence records successful picture-dictionary implementation tests but not the expected Sophie review or current classroom outcome.
  - **Assessments:** `ASM-0002`
- **UNC-0003:** Time spent making the Sprint loop operational competes with overdue user-facing and publication work, although the Sprint commitment is temporarily more urgent.
  - **Assessments:** `ASM-0003`, `ASM-0004`, `ASM-0007`
- **UNC-0004:** The current issue registry contains many old reported items without explicit recent disposition, so absence of closure may mean unfinished work, stale tracking, or both.
  - **Assessments:** `ASM-0001`, `ASM-0006`, `ASM-0007`

## Questions for human refinement

- **REQ-0001:** What are the actual outcomes and present relevance of the first progress report, EuroCALL paper, and ALTA target, and should ISSUE-0008 be updated or split accordingly?
  - **Why this matters:** Past deadlines with stale issue state prevent a reliable research-progress assessment.
  - **Assessments:** `ASM-0004`
- **REQ-0002:** Did Sophie review the unified picture-dictionary/subset workflow, and what happened in the planned classroom use?
  - **Why this matters:** This determines whether the main real-user workflow is a success, an unresolved blocker, or needs revision.
  - **Assessments:** `ASM-0002`
- **REQ-0003:** After the Sprint preparation deadline, which two or three outcomes should dominate: regression/quality infrastructure, picture-dictionary follow-up, publications, legacy catalogue completion, mobile access, or another user commitment?
  - **Why this matters:** The active portfolio exceeds plausible near-term capacity, and the repository does not contain a current precedence decision after the Sprint.
  - **Assessments:** `ASM-0007`
- **REQ-0004:** What concrete mobile outcome should be tackled first, for which users and target date?
  - **Why this matters:** Mobile access is strategically important but lacks a focused current issue and operational success criterion.
  - **Assessments:** `ASM-0006`
- **REQ-0005:** Which initial Sprint outcomes, human-rating measures, artifact-retention rules, and any additional participants should be fixed before the first instrumented dry run?
  - **Why this matters:** These human-owned choices are explicitly unresolved and affect whether the Sprint produces interpretable evidence.
  - **Assessments:** `ASM-0003`, `ASM-0004`
- **REQ-0006:** Which long-standing reported issues are genuinely still open, and should a short registry-triage pass retire or rewrite stale items?
  - **Why this matters:** Stale issue state weakens both human overview and autonomous assessment.
  - **Assessments:** `ASM-0001`, `ASM-0007`

## Proposed next actions

- **ACT-0001:** Complete the minimal validated propose/review/apply loop and run one end-to-end pilot before Sprint work begins.
  - **Assessments:** `ASM-0003`, `ASM-0004`
- **ACT-0002:** Obtain and record the missing publication and picture-dictionary outcomes, then update canonical issues rather than encoding those facts only in the workspace.
  - **Assessments:** `ASM-0002`, `ASM-0004`
- **ACT-0003:** After the Sprint, perform a bounded issue-triage pass and select a small execution set with explicit user or quality outcomes.
  - **Assessments:** `ASM-0001`, `ASM-0007`
- **ACT-0004:** Preserve momentum on legacy migration by running/reviewing the batch importer and defining the smallest catalogue slice that exposes migrated and hosted content safely.
  - **Assessments:** `ASM-0005`

## Open predictions

- **PRED-0001:** Without a focused pre-Sprint implementation pass, the complete instrumented manual review loop will not be operational by 2026-08-14.
  - **Horizon:** 2026-08-14
  - **Probability / confidence / status:** 70% / medium / open
  - **Assessments:** `ASM-0003`
- **PRED-0002:** Until explicit human outcome evidence is added, the next workspace review will still be unable to classify the publication and picture-dictionary commitments reliably.
  - **Horizon:** next_workspace_review
  - **Probability / confidence / status:** 85% / high / open
  - **Assessments:** `ASM-0002`, `ASM-0004`
- **PRED-0003:** If no mobile issue with a concrete outcome enters the focus index, mobile delivery will remain limited or unrecorded through the next workspace review.
  - **Horizon:** next_workspace_review
  - **Probability / confidence / status:** 80% / medium / open
  - **Assessments:** `ASM-0006`

## Approval and revision

- **Status:** human_requested_initial_baseline
- **Authorized by / at:** Manny Rayner / 2026-08-12
- **Basis:** Direct request to create a first version for review and refinement.
- **Comments:** Initial baseline assembled from repository evidence. Human answers to REQ-0001 through REQ-0006 should drive the next reviewed revision.
- **Change summary:** Initial workspace baseline; there is no previous revision.
- **Retired live items:** None
