# 4. Implementor-Facing Functionality (Concise Draft Plan)

## 4.1 Engineering process as first-class platform capability

- C-LARA-2 uses repository-native planning and maintenance artifacts to support ongoing implementation.
- Roadmaps and issue records are not just reporting outputs; they are part of the operational control system for AI-assisted development.
- This implementor-facing process should be summarized because it is central to the project, but the report should avoid excessive technical detail.
- Recent self-understanding work should be presented here as an implementor-facing capability: the same repository artifacts that support Codex development sessions are now available to a restricted in-platform question-answering workflow.

## 4.2 Roadmap-as-memory pattern

- Roadmap documents provide stable architecture and functionality context.
- They reduce dependence on ad-hoc conversational memory and make reasoning auditable.
- This matters because the same AI-centered workflow is producing code, documentation, issue records, and publication text.

## 4.3 Issue suggestion ingestion loop

- Project members submit suggestions through platform UX and related communication channels.
- Suggestions are exported and incorporated into canonical issue JSON and overview materials.
- This creates a low-friction human-to-Codex steering path: humans advise and prioritize, while the AI updates the repository artifacts.

## 4.4 Restricted project-understanding assistant

- ISSUE-0034 has produced an authenticated project-understanding implementation, now surfaced as the top-level **Assistant** rather than as an admin-only page. Authenticated users can submit high-level questions about C-LARA-2, and the platform queues a background `codex exec` run against the repository rather than trying to preselect evidence files itself.
- The core wrapper builds a versioned prompt, invokes Codex in read-only/non-interactive mode, passes credentials through a reduced environment, captures stdout/stderr/exit status/elapsed time/model/prompt version/token count where available, detects sandbox/credential failures, and parses the final answer.
- The Django surface at `/assistant/project-understanding/` shows live progress through task updates and persists request/result JSON under the media tree. It has now been made to work on the AWS server after a detailed deployment/debugging cycle around Codex CLI installation, `CODEX_HOME`, service-user identity, bubblewrap visibility, and Ubuntu AppArmor user-namespace policy.
- A concrete AWS answer has already been produced from inside the platform: Codex answered whether Italian text creation is supported, citing implemented language choices and text-generation fallback behavior while noting the lack of dedicated Italian text-generation templates. This is a good report example of repository-grounded self-understanding, but not yet a claim of automatic correctness.
- The June 2026 debugging cycle around Assistant self-queries is also a useful human-AI cooperation example for the report: a human noticed that English self-understanding questions failed while a related French question succeeded; the AI iteratively revised the worker setup, sandbox diagnostics, false-positive detection, and finally added a model-based reviewer to distinguish genuine Codex sandbox failures from answers that merely quote repository text about old failures. The episode shows both the value and fragility of repository-grounded self-understanding: the system could help debug itself, but only through human observation, deployment checks, and repeated correction.
- The report should frame this as recent progress toward self-understanding, not as a finished public chatbot. Remaining work includes export into version-controlled evidence records, reviewer assessment controls, citation/path sanitization, exact-cost reconciliation, budget/rate limits, and curated report-evidence runs.

## 4.5 Migration of legacy projects

- Migration from C-LARA to C-LARA-2 has required explicit format conversion and staged operational workflows.
- Legacy import tooling and runbooks are now part of implementor-facing project infrastructure.
- The report should mention migration mainly as evidence of rapid AI-supported engineering, not as a long technical case study.

## 4.6 Sysadmin/deployment support as implementor workflow

- AI-guided sysadmin work is a notable part of the C-LARA-2 story.
- When migration to an AWS server became necessary, the AI organized and executed the required operational plan on a days-scale timeline.
- This broadens the AI-centered claim: the AI is not only writing application code, but also supporting deployment, migration, and operational documentation.

## 4.7 Quality-control infrastructure (current and planned)

- Existing tests and artifact checks provide partial safeguards.
- A new few-shot curation/review loop provides an early concrete example of AI-assisted quality control: for French `segmentation_phase_2` boundary examples, the system generated candidate pools, applied deterministic preservation checks, created an AI-reviewed language-specific evaluation template, and retained high-confidence examples. The first smoke test retained eight examples that were all judged correct in maintainer review; the later 80-candidate run accepted 72 AI `none` judgements after human audit.
- The imported French evaluation corpus is now large enough for a meaningful first comparison: a 2026-06-19 corpus summary for `mannyrayner`/`fr` found 53 projects, 1600 segments, and 17344 current segmentation tokens. The AI then defined and implemented deterministic development/test manifests and began deriving prompt/evaluator assets for a default-vs-candidate comparison with held-out test data.
- The first development-set comparison loop has now run through default processing, the small few-shot candidate, and human judgements for both outputs. The next AI-proposed step is a development-only `FEWSHOT_COUNT` sweep (`medium`, `all`, and possibly one numeric tranche) before freezing the held-out test procedure; the Makefile now includes deterministic `evaluate`/`compare` targets to aggregate those human judgement files into summaries and flagged examples.
- A parallel multilingual chunk-decomposition workbench now records prompt-improvement cycles for English, French, and German. Development runs can revise prompts from gold/prediction divergences, while a new validation gate evaluates a frozen development-cycle prompt on validation data and writes a report without generating further prompt edits; this makes the dev → validation → test boundary explicit for report evidence.
- This thread is itself a useful AI-autonomy example for the report: the assistant has taken increasing initiative in experimental design, leakage-control policy, hypothesis formulation, audit-gate specification, Makefile orchestration, implementation, tests, and documentation, while the human role has been supervisory review and acceptance.
- The example is promising but deliberately modest: the review step appears overstrict, and broader promotion still needs evaluator comparisons, repair/arbiter steps, and more languages/phenomena.
- Planned work includes stronger end-to-end runners, AI/human review gates, autonomous drift tracking for functionality regressions, and reviewed self-understanding evidence records.
- The report should be frank that more autonomous checking and stronger evidence governance are among the highest-priority unfinished items.

## 4.8 Questions for refinement

- Which process details are essential for the main body versus appendix material?
- Should the report include a small process diagram showing the human suggestion → issue → Codex implementation → review loop?
- How much operational detail about AWS migration is appropriate for non-implementor readers?
- Which assistant outputs should become curated, human-reviewed evidence records for the report?
