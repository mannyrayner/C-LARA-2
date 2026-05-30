# Roadmap: restricted project-understanding assistant

Tracked by [ISSUE-0034](../issues/issues/ISSUE-0034.json).

## Goal

Create a lightweight admin/restricted-user feature that lets authorised users ask high-level questions about the C-LARA-2 project and receive answers grounded in publicly available project materials.

The target evidence base is broader than a small help-document subset. It should include the public C-LARA-2 GitHub repository wherever useful: `docs/roadmap/`, `docs/issues/`, `docs/howto/`, project reports, tests, prompts, and relevant source files. The assistant should support questions about architecture, goals, implementation status, issue structure, roadmap plans, prompt design, tests, and module relationships.

This is not intended as a general public chatbot. The initial product is a restricted project-maintenance and evidence-gathering tool that demonstrates how well C-LARA-2 can use its own repository-native documentation and code to explain itself.

## Why this matters

C-LARA-2 is intentionally developed with extensive repository-native documentation so AI tools can understand and help maintain the platform. A restricted self-knowledge assistant would make this capability inspectable from inside the platform and could:

- help project maintainers, trusted reviewers, and report authors find reliable answers faster;
- create a versioned evidence record of how well Codex/OpenAI models can answer project-level questions from the repository;
- support the initial C-LARA-2 report's argument about autonomy and AI-assisted authorship by letting sceptical readers inspect concrete question/answer records;
- reveal gaps, contradictions, or stale areas in the documentation when the model cannot answer reliably;
- provide a reusable baseline for later user-facing help or broader conversational UX, if the restricted version proves accurate and safe.

## Relationship to existing dialogue work

This roadmap is related to, but narrower and more evidence-oriented than, [the freeform dialogue-based top-level roadmap](dialogue-top-level.md).

- The dialogue top level is about helping users operate C-LARA-2 workflows through conversation.
- The restricted project-understanding assistant is about answering questions concerning the project itself, using repository materials as evidence.
- The first implementation should be read-only: it must not trigger project mutations, expensive pipeline runs, admin actions, or repository changes from user prompts.
- A later phase can decide whether project-understanding answers become one intent within a broader dialogue/orchestration layer.

## Initial requirements

1. Access is initially restricted to admins or a clearly defined trusted group.
2. The user enters a question through a simple platform form or management command.
3. The system wraps the question in a prompt instructing the model to answer from C-LARA-2 repository materials.
4. The model distinguishes implemented functionality from planned or speculative functionality.
5. The model cites supporting files wherever possible.
6. The model explicitly says when available project materials do not support an answer.
7. Each run stores the question, answer, timestamp, model name, prompt version, and cited/supporting files.
8. Records are stored in the C-LARA-2 file tree, preferably under `docs/project_understanding/` or a similar folder, so they are versionable and inspectable.
9. Each record includes fields for later human assessment: `accurate`, `partially accurate`, `inaccurate`, or `unclear`, plus reviewer notes.
10. Tests and user/developer documentation are added before broad use.
11. A development log explains design choices and why the feature is relevant to the broader C-LARA-2 authorship/autonomy evidence case.

## Evidence scope

The assistant should be able to use publicly available project materials, with a conservative default ordering that prefers high-signal documentation before raw code:

1. `docs/roadmap/` for goals, plans, status notes, and feature relationships.
2. `docs/issues/overview.md`, `docs/issues/index.json`, and `docs/issues/issues/*.json` for current issue state, priorities, dependencies, and human-suggestion provenance.
3. `docs/howto/` and other user/developer guidance when available.
4. Project reports and report drafts, especially material tied to autonomy, authorship, and project history.
5. Tests, prompts, and fixtures for evidence about expected behaviour and model-facing task design.
6. Relevant implementation files for architecture and status questions that documentation alone cannot answer.

The first prototype may use a bounded retrieval/indexing strategy rather than whole-repository context, but it should not be conceptually limited to a small curated FAQ. When answers depend on code, the assistant should identify uncertainty if the supporting implementation is hard to verify from the retrieved materials.

## Wrapper prompt baseline

A first prompt version can be based on the following template:

```text
You are answering questions about the C-LARA-2 project.

Use the project documentation and codebase as evidence, especially roadmap/, issues/, howto/, project reports, tests, prompts, and implementation files.

Answer at the level of a project collaborator who understands the current architecture, goals, status, and development plans.

When relevant:
- distinguish implemented functionality from planned functionality;
- mention which files support your answer;
- explain relationships between modules or documents;
- identify uncertainty rather than guessing;
- say when the available project materials do not support an answer.

The question is:
...
```

The production prompt should be versioned and stored with the generated question/answer records so later reviewers can interpret changes in behaviour over time.

## Record format and storage

Use a repository-visible evidence log, for example under `docs/project_understanding/`. The exact schema can evolve, but each run should include at least:

- stable record ID or filename;
- timestamp;
- submitter or restricted-user identifier, subject to privacy policy;
- question;
- answer;
- model name and model/API route;
- prompt version;
- retrieval/index version or repository commit where possible;
- cited/supporting files;
- whether the answer says evidence is missing or uncertain;
- human assessment field: `unreviewed`, `accurate`, `partially accurate`, `inaccurate`, or `unclear`;
- human reviewer notes.

Records should be plain Markdown or JSON/Markdown pairs so they can be committed, diffed, cited in reports, and inspected by human reviewers.

## User interface and operating modes

Possible MVP surfaces:

- staff-only Django view linked from the admin/support area;
- management command for batch or report-oriented question runs;
- optional export command that writes selected records into `docs/project_understanding/` for version control.

The UI can be minimal: a question box, answer pane, supporting-file list, and reviewer assessment controls. A management-command path may be especially useful for generating repeatable evidence for the initial report.

## Safety and governance

The assistant should reason over publicly available repository content, but the production platform still needs strict boundaries:

- restrict initial access to admins/trusted users;
- do not expose private user/project data, credentials, server paths, raw logs, or environment variables;
- do not allow user prompts to execute code, mutate repository/platform state, or trigger costly workflows;
- treat retrieved repository text and user questions as prompt-injection surfaces;
- rate-limit usage and record costs through the credits/billing framework where appropriate;
- make stale documentation and unsupported answers visible rather than hiding uncertainty;
- preserve human review fields so the evidence log does not imply all model answers are correct.

## Phased plan

### Phase A: planning and evidence design

- Decide the first evidence corpus and retrieval/indexing method.
- Define the record schema and create `docs/project_understanding/` conventions.
- Version the wrapper prompt and decide how prompt versions are stored.
- Confirm the suitable OpenAI/Codex API route for repo-grounded answers from a production Django app or management command.
- Choose the first set of report-relevant evaluation questions.

### Phase B: restricted prototype

- Build a minimal admin/trusted-user question form or management command.
- Ground answers in repository materials, starting with roadmap, issues, reports, tests, prompts, and selected implementation files.
- Return cited/supporting files with each answer.
- Store each run as a versionable record with human assessment placeholders.
- Add tests for access control, prompt construction, record serialization, and missing-evidence behaviour.

### Phase C: report/evidence workflow

- Run a curated question set relevant to the initial C-LARA-2 report's autonomy/authorship argument.
- Human-review the answers and fill in assessment fields.
- Add a development log summarizing design choices, limitations, representative successes/failures, and implications for the report.
- Use reviewed records as inspectable evidence rather than unverified promotional claims.

### Phase D: possible productization

- Evaluate whether the restricted assistant should become a general staff help tool.
- Consider a carefully narrowed user-facing help assistant only after accuracy, privacy, safety, and cost controls are demonstrated.
- Consider convergence with the broader dialogue top level, while preserving the evidence-log workflow.

## Open questions

- Which API and retrieval architecture best supports repo-grounded answers while staying safe in production?
- Should records be written directly by the platform, exported for later commit, or both?
- What is the minimum curated question set needed for the first report?
- How should human assessments be summarized without overstating model reliability?
- Which parts of the public repository should be indexed first, and which should be excluded as too noisy or potentially misleading?
