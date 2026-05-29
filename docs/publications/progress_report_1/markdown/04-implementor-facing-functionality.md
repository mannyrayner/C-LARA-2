# 4. Implementor-Facing Functionality (Concise Draft Plan)

## 4.1 Engineering process as first-class platform capability

- C-LARA-2 uses repository-native planning and maintenance artifacts to support ongoing implementation.
- Roadmaps and issue records are not just reporting outputs; they are part of the operational control system for AI-assisted development.
- This implementor-facing process should be summarized because it is central to the project, but the report should avoid excessive technical detail.

## 4.2 Roadmap-as-memory pattern

- Roadmap documents provide stable architecture and functionality context.
- They reduce dependence on ad-hoc conversational memory and make reasoning auditable.
- This matters because the same AI-centered workflow is producing code, documentation, issue records, and publication text.

## 4.3 Issue suggestion ingestion loop

- Project members submit suggestions through platform UX and related communication channels.
- Suggestions are exported and incorporated into canonical issue JSON and overview materials.
- This creates a low-friction human-to-Codex steering path: humans advise and prioritize, while the AI updates the repository artifacts.

## 4.4 Migration of legacy projects

- Migration from C-LARA to C-LARA-2 has required explicit format conversion and staged operational workflows.
- Legacy import tooling and runbooks are now part of implementor-facing project infrastructure.
- The report should mention migration mainly as evidence of rapid AI-supported engineering, not as a long technical case study.

## 4.5 Sysadmin/deployment support as implementor workflow

- AI-guided sysadmin work is a notable part of the C-LARA-2 story.
- When migration to an AWS server became necessary, the AI organized and executed the required operational plan on a days-scale timeline.
- This broadens the AI-centered claim: the AI is not only writing application code, but also supporting deployment, migration, and operational documentation.

## 4.6 Quality-control infrastructure (current and planned)

- Existing tests and artifact checks provide partial safeguards.
- Planned work includes stronger end-to-end runners, AI/human review gates, and autonomous drift tracking for functionality regressions.
- The report should be frank that more autonomous checking is one of the highest-priority unfinished items.

## 4.7 Questions for refinement

- Which process details are essential for the main body versus appendix material?
- Should the report include a small process diagram showing the human suggestion → issue → Codex implementation → review loop?
- How much operational detail about AWS migration is appropriate for non-implementor readers?
