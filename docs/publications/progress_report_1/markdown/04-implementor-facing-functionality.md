# 4. Implementor-Facing Functionality (Outline)

## 4.1 Engineering process as first-class platform capability

- C-LARA-2 uses repository-native planning/maintenance artifacts to support ongoing implementation.
- Roadmaps and issue records are used not just for reporting, but for operational control of AI-assisted development.

## 4.2 Roadmap-as-memory pattern

- Roadmap documents provide stable architecture/functionality context.
- They reduce dependence on ad-hoc conversational memory and make reasoning auditable.

## 4.3 Issue suggestion ingestion loop

- Project members submit suggestions through platform UX.
- Suggestions are exported and incorporated into canonical issue JSON and overview materials.
- This creates a low-friction human-to-Codex steering path.

## 4.4 Migration of legacy projects

- Migration from C-LARA to C-LARA-2 has required explicit format conversion and staged operational workflows.
- Legacy import tooling and runbooks are now part of implementor-facing project infrastructure.
- Large-project import progress suggests migration at broader scale is increasingly practical.

## 4.5 Sysadmin/deployment support as implementor workflow

- AWS deployment and operational setup have been guided through AI-assisted runbooks and task execution.
- Deployment/migration operations should be described as part of the broader implementor toolchain.

## 4.6 Quality-control infrastructure (current + planned)

- Existing tests and artifact checks.
- Planned stronger end-to-end runners and AI/human review gates.
- Planned autonomous drift tracking for functionality regressions.

## 4.7 Questions for refinement

- Which process details are essential for the main body versus appendix material?
- How much operational detail is appropriate for non-implementor readers?
