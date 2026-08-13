# Implement a Project Manager mode in the existing Assistant

We would like to extend the existing authenticated **Assistant** feature so that it has two related modes:

1. the existing **Assistant** mode, which answers questions about C-LARA-2 from repository evidence;
2. a new **Project Manager** mode, which lets authorised project collaborators communicate directly with the C-LARA-2 project-manager agent.

The key design principle is to **reuse the existing Assistant/Codex infrastructure wherever possible** rather than creating a second independent AI interface.

The new Project Manager mode should primarily differ in the prompt/instructions sent to Codex, the way the authenticated user's identity and project role are supplied, the treatment of the user's message as potential project evidence, archival/audit behaviour, and detection of whether the message warrants a global-workspace review.

Please first inspect the existing Assistant implementation and use the smallest coherent extension consistent with its architecture.

A Project Manager invocation should read and follow `AGENTS.md`, inspect `docs/global_workspace/README.md`, project intentions and current state, inspect other repository evidence when useful, interpret the user's message in context, respond conversationally, and identify whether the message contains material new evidence that may change the project-manager assessment.

Do not create a separate project-manager model. The persistent project-manager identity/state should remain primarily repository-mediated.

The Project Manager should know which authenticated collaborator is speaking. Supply a concise identity/role description derived from authoritative C-LARA-2 information. Do not hard-code Sophie. It is reasonable initially to allow only a small explicitly authorised set of users.

Treat collaborator messages as potential project evidence and preserve authenticated identity, timestamp, mode, exact user message, Codex response, run metadata, and repository commit/state. Reuse existing Assistant request/result persistence.

Distinguish human evidence, project-manager inference, and authorization. A collaborator's statement must not silently become an approved judgment, and the Project Manager must distinguish direct observation, second-hand information, uncertainty, and interpretation.

A normal Project Manager conversation must not directly rewrite project intentions, current state, or other canonical management state. Codex should assess whether the message contains material evidence and whether review is warranted. The smallest implementation may persist boolean flags and a short explanation.

Do not build substantial chat-history infrastructure initially. Fresh ephemeral Codex processes should reconstruct context from the repository, global workspace, identity, and current message.

Responses should be conversational and useful rather than structured-state dumps or generic help. Do not require affective language; preserve it naturally if it arises.

Sophie and the 24 August Indigenous-language work are the first real use case, but do not add Sophie-specific logic. Preserve enough metadata for operational audit and later longitudinal research without turning the feature into an experiment-management system.

Optimize for the smallest useful implementation: a mode selector, unchanged Assistant path, Project Manager prompt builder, authenticated identity/role, the same read-only worker, persisted message/response/run metadata, material-evidence classification, conversational display, review boundary, and focused tests. Avoid a separate service, second worker, elaborate dashboards, forms, affect controls, complex memory, or automatic canonical mutation.

Please inspect the existing Assistant UI/views, `src/core/project_understanding.py`, worker, persistence, authentication/project roles, `AGENTS.md`, global workspace, roadmap, and issues. Then implement the smallest coherent version and update relevant roadmap/issue documentation.
