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

- ISSUE-0034 has produced a first admin-only project-understanding implementation. Staff users can submit high-level questions about C-LARA-2, and the platform queues a background `codex exec` run against the repository rather than trying to preselect evidence files itself.
- The core wrapper builds a versioned prompt, invokes Codex in read-only/non-interactive mode, passes credentials through a reduced environment, captures stdout/stderr/exit status/elapsed time/model/prompt version/token count where available, and parses the final answer.
- The Django surface at `/admin-tools/project-understanding/` shows live progress through Django Q task updates and persists request/result JSON under the media tree. Manual smoke tests have produced plausible cited answers for repository-summary and annotated-text-format questions.
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
- Planned work includes stronger end-to-end runners, AI/human review gates, autonomous drift tracking for functionality regressions, and reviewed self-understanding evidence records.
- The report should be frank that more autonomous checking and stronger evidence governance are among the highest-priority unfinished items.

## 4.8 Questions for refinement

- Which process details are essential for the main body versus appendix material?
- Should the report include a small process diagram showing the human suggestion → issue → Codex implementation → review loop?
- How much operational detail about AWS migration is appropriate for non-implementor readers?
- Which assistant outputs should become curated, human-reviewed evidence records for the report?
