# Roadmap: restricted project-understanding assistant

Tracked by [ISSUE-0034](../issues/issues/ISSUE-0034.json).

## Goal

Create a lightweight admin/restricted-user feature that lets authorised users ask high-level questions about the C-LARA-2 project and receive answers grounded in the repository.

The revised architecture is deliberately simple: the platform should delegate the whole project-understanding task to Codex running against the checked-out C-LARA-2 repository, rather than trying to preselect evidence files or reconstruct Codex-style repository understanding in application code.

The target evidence base is the full repository available to Codex in read-only mode. Codex should decide which files to inspect, including `docs/roadmap/`, `docs/issues/`, `docs/howto/`, project reports, tests, prompts, and relevant source files. The assistant should support questions about architecture, goals, implementation status, issue structure, roadmap plans, prompt design, tests, and module relationships.

This is not intended as a general public chatbot. The initial product is a restricted project-maintenance and evidence-gathering tool that demonstrates how well C-LARA-2 can use Codex and its repository-native documentation/code to explain itself.

## Why this matters

C-LARA-2 is intentionally developed with extensive repository-native documentation so AI tools can understand and help maintain the platform. A restricted self-knowledge assistant would make this capability inspectable from inside the platform and could:

- help project maintainers, trusted reviewers, and report authors find reliable answers faster;
- create a versioned evidence record of how well Codex can answer project-level questions from the repository;
- support the initial C-LARA-2 report's argument about autonomy and AI-assisted authorship by letting sceptical readers inspect concrete question/answer records;
- reveal gaps, contradictions, or stale areas in the documentation when Codex cannot answer reliably;
- provide a reusable baseline for later user-facing help or broader conversational UX, if the restricted version proves accurate and safe.

The practical motivation for using Codex directly is that C-LARA-2 has already been maintained successfully for months through Codex sessions connected to the repository. That is the strongest evidence that Codex is the right component to choose and inspect supporting files, rather than a bespoke API wrapper trying to guess the relevant evidence before the model sees the question.

## Revised architecture: delegate repository understanding to `codex exec`

The earlier idea of wrapping a user request, preselecting likely evidence files, and sending that package to a model through a normal API call is now considered brittle. It asks the platform to solve the hardest part of the task — knowing what repo evidence matters — before the system has invoked the tool that is best at repository exploration.

Instead, the platform should:

1. Accept a restricted user's project-understanding question.
2. Build a concise, versioned instruction prompt that tells Codex to answer from the C-LARA-2 repository, cite files, distinguish implemented from planned work, and identify uncertainty.
3. Invoke `codex exec` in the deployed C-LARA-2 checkout with a read-only sandbox and no approval prompts.
4. Let Codex inspect the repository and choose evidence files itself.
5. Capture Codex's stdout/stderr, exit status, model name, prompt version, repository path, and timestamp.
6. Store the answer and metadata as a versionable project-understanding evidence record.

A representative command shape is:

```bash
codex exec \
  --cd /srv/C-LARA-2 \
  --sandbox read-only \
  --ask-for-approval never \
  --model gpt-5.3-codex \
  "$(cat prompt.txt)"
```

The exact command should be generated without shell-injection hazards; production code should prefer `subprocess.run([...], input=prompt_text, ...)` or an equivalently safe argument vector over interpolating untrusted text into a shell command. The example above is documentation of the intended Codex invocation semantics, not a prescription to use unsafe shell string construction.

### Why `codex exec` rather than a normal API call

- Codex is already designed to operate inside a repository and inspect files as needed.
- The platform does not need to build or maintain a retrieval/indexing layer for the first version.
- Evidence selection remains part of the model/tool task, where project-development experience shows it works well.
- The implementation can start as a restricted management command or staff-only action that shells out to Codex, avoiding premature productisation.
- Running with `--sandbox read-only` and `--ask-for-approval never` makes the intended first version answer-only: Codex can read repository files but cannot mutate the repo or request privileged follow-up actions.

## Installation and safe invocation details

### What must be installed to run `codex exec`

The first implementation should treat Codex CLI availability as an explicit deployment prerequisite, not as an implicit Python dependency. A local development machine or server that runs project-understanding requests needs:

1. A supported operating system for the Codex CLI. The expected primary targets are Linux for AWS/server deployment and macOS or Linux for maintainer machines; Windows should be treated as a separate/experimental path unless tested through WSL.
2. Node.js and `npm`, because the Codex CLI is distributed as the `@openai/codex` npm package.
3. The Codex CLI installed and upgraded through npm, for example:

   ```bash
   npm install -g @openai/codex
   codex --version
   ```

4. A working Codex authentication setup for the account or service context that will run the command. For local development this may be an interactive Codex login or an `OPENAI_API_KEY` in the developer shell. For a server, prefer a purpose-specific API key or service account configuration with the minimum practical permissions and clear ownership/revocation procedures.
5. The target model available to that account. The roadmap examples use `gpt-5.3-codex`; deployment should keep the model name configurable so the team can change it without code changes.
6. A clean C-LARA-2 checkout at a configured path. The examples use `/srv/C-LARA-2` for production, while local development can use the developer's repo path.
7. Enough host resources and network access for Codex model calls, but no need for application code to expose additional repository read privileges beyond the configured checkout.

Before enabling platform calls, add a deployment check that runs a harmless command such as `codex --version` and, where credentials are configured, a short read-only smoke question against a test checkout. Record failures as configuration errors rather than user-facing assistant failures.

### Safe local-machine invocation

For local development and maintainer-run experiments, safety should favour transparency and reproducibility:

- Run from a disposable or clean Git checkout so accidental local state does not affect answers.
- Use `--sandbox read-only` and `--ask-for-approval never` for project-understanding questions.
- Prefer a prompt file or stdin over shell interpolation. If a shell example is used manually, treat it as a convenience only; implementation should not build a shell command with untrusted question text.
- Keep the Codex command visible in logs or terminal output, minus secrets.
- Capture stdout and stderr separately so maintainers can distinguish an answer from command warnings or failures.
- Record the Git commit used for the answer with `git rev-parse HEAD`.
- Set a timeout even locally, so hung requests do not look like silent platform failures.

A local Python prototype should use an argument list rather than `shell=True`, for example:

```python
subprocess.run(
    [
        "codex",
        "exec",
        "--cd",
        repo_path,
        "--sandbox",
        "read-only",
        "--ask-for-approval",
        "never",
        "--model",
        model,
        prompt_text,
    ],
    capture_output=True,
    text=True,
    timeout=timeout_s,
    check=False,
)
```

If the CLI supports prompt input on stdin in the deployed version, that may be preferable for long prompts; the same safety rule applies: pass arguments as a list and keep user text out of shell syntax.

### Safe web/server invocation

A staff-only web feature adds risks beyond local use because a remote user can indirectly start a local process. The first web implementation should therefore be more restrictive than the local management command:

- Restrict access to staff/admin users or a small trusted group; do not expose this to ordinary users until the risk model is better understood.
- Store configuration in settings: Codex executable path, repository path, model, sandbox mode, approval mode, timeout, maximum prompt length, output directory, and feature flag.
- Use a fixed allowlisted repository path such as `/srv/C-LARA-2`; never accept `--cd` or filesystem paths from request parameters.
- Build the subprocess call with an argument vector via `subprocess.run` or `asyncio.create_subprocess_exec`; never use `shell=True` with user-provided text.
- Run with `--sandbox read-only` and `--ask-for-approval never` unconditionally for this feature.
- Apply strict request-size limits, execution timeouts, and rate limits per user and globally.
- Queue longer runs through a background worker rather than blocking a web request thread, especially if answers may take minutes.
- Capture stdout, stderr, exit code, duration, prompt version, model, repository commit, and requesting user in an internal run record.
- Return stdout only when the exit code is successful; otherwise show a controlled error message and preserve diagnostics for admins.
- Scrub or avoid recording environment variables, API keys, absolute private paths outside the configured repo root, and raw server logs.
- Use a minimal environment for the child process. Pass only variables needed for Codex authentication and normal CLI operation.
- Consider running the web-triggered Codex process as a dedicated OS user with read-only access to the repository checkout and no write access to application data, uploaded media, credentials, or deployment scripts.
- Prevent concurrent-run overload with a small worker pool or lock, since each Codex call may be expensive and resource-intensive.
- Keep evidence records `unreviewed` by default until a human reviewer marks them otherwise.

This server pattern keeps Codex responsible for repository understanding while keeping the web application responsible for authentication, authorization, process containment, auditability, and failure handling.

## Relationship to existing dialogue work

This roadmap is related to, but narrower and more evidence-oriented than, [the freeform dialogue-based top-level roadmap](dialogue-top-level.md).

- The dialogue top level is about helping users operate C-LARA-2 workflows through conversation.
- The restricted project-understanding assistant is about answering questions concerning the project itself, using Codex connected to the repository as the evidence-gathering and reasoning engine.
- The first implementation should be read-only: it must not trigger project mutations, expensive pipeline runs, admin actions, or repository changes from user prompts.
- A later phase can decide whether project-understanding answers become one intent within a broader dialogue/orchestration layer.

## Initial requirements

1. Access is initially restricted to admins or a clearly defined trusted group.
2. The user enters a question through a simple platform form or management command.
3. The system wraps the question in a prompt instructing Codex to answer from the C-LARA-2 repository.
4. The system invokes `codex exec` against the server checkout, initially `/srv/C-LARA-2`, with `--sandbox read-only`, `--ask-for-approval never`, and a pinned/default Codex model such as `gpt-5.3-codex`.
5. Codex, not the platform, is responsible for deciding which repository files to inspect.
6. The answer distinguishes implemented functionality from planned or speculative functionality.
7. The answer cites supporting files wherever possible.
8. The answer explicitly says when available project materials do not support a claim.
9. Each run stores the question, answer, timestamp, model name, prompt version, Codex command metadata, repository path/commit where available, and cited/supporting files where extractable.
10. Records are stored in the C-LARA-2 file tree, preferably under `docs/project_understanding/` or a similar folder, so they are versionable and inspectable.
11. Each record includes fields for later human assessment: `accurate`, `partially accurate`, `inaccurate`, or `unclear`, plus reviewer notes.
12. Tests and user/developer documentation are added before broad use.
13. A development log explains design choices and why the feature is relevant to the broader C-LARA-2 authorship/autonomy evidence case.

## Evidence scope

The evidence scope is the repository visible to Codex in the configured checkout. The platform should not attempt to collect evidence files before invoking Codex. It may include high-level guidance in the prompt about likely useful areas, but Codex should choose what to inspect.

Useful evidence areas to mention in the prompt include:

1. `docs/roadmap/` for goals, plans, status notes, and feature relationships.
2. `docs/issues/overview.md`, `docs/issues/index.json`, and `docs/issues/issues/*.json` for current issue state, priorities, dependencies, and human-suggestion provenance.
3. `docs/howto/` and other user/developer guidance when available.
4. Project reports and report drafts, especially material tied to autonomy, authorship, and project history.
5. Tests, prompts, and fixtures for evidence about expected behaviour and model-facing task design.
6. Relevant implementation files for architecture and status questions that documentation alone cannot answer.

This is guidance, not a precomputed retrieval corpus. If the question requires other files, Codex should inspect them. If it cannot find support, it should say so.

## Codex prompt baseline

A first prompt version can be based on the following template:

```text
You are answering questions about the C-LARA-2 project.

You are running as Codex inside a read-only checkout of the C-LARA-2 repository. Use repository files as evidence. You may inspect whatever files are needed, especially docs/roadmap/, docs/issues/, docs/howto/, project reports, tests, prompts, and implementation files.

Answer at the level of a project collaborator who understands the current architecture, goals, status, and development plans.

When relevant:
- distinguish implemented functionality from planned functionality;
- cite supporting repository files and, where practical, line ranges;
- explain relationships between modules or documents;
- identify uncertainty rather than guessing;
- say when the available project materials do not support an answer;
- do not propose or perform repository/platform mutations;
- do not expose secrets, private user/project data, credentials, raw logs, or environment variables.

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
- model name and Codex invocation route;
- prompt version;
- repository path and repository commit where available;
- command metadata, including sandbox mode, approval mode, exit status, timeout, and whether stderr was non-empty;
- cited/supporting files as reported by Codex or extracted from the answer;
- whether the answer says evidence is missing or uncertain;
- human assessment field: `unreviewed`, `accurate`, `partially accurate`, `inaccurate`, or `unclear`;
- human reviewer notes.

Records should be plain Markdown or JSON/Markdown pairs so they can be committed, diffed, cited in reports, and inspected by human reviewers. If platform code writes records on the server, there should also be an explicit export/review step before committing them to the repository.

## User interface and operating modes

Possible MVP surfaces:

- staff-only Django view linked from the admin/support area;
- management command for batch or report-oriented question runs;
- optional export command that writes selected records into `docs/project_understanding/` for version control.

The management-command path is the safest first implementation because it keeps the initial feature close to administrator workflows and makes command invocation, timeouts, stdout/stderr capture, and record writing easy to inspect. A staff-only UI can be added after the command path has demonstrated reliable behaviour.

The UI can be minimal: a question box, answer pane, supporting-file list or extracted citations, command/run metadata, and reviewer assessment controls. A management-command path may be especially useful for generating repeatable evidence for the initial report.

## Safety and governance

The assistant should reason over publicly available repository content, but the production platform still needs strict boundaries:

- restrict initial access to admins/trusted users;
- run Codex with `--sandbox read-only` and `--ask-for-approval never`;
- use a fixed repository checkout path controlled by configuration, not arbitrary user-supplied paths;
- pass user questions to Codex without unsafe shell interpolation;
- apply request length limits and execution timeouts;
- capture and review stderr/exit status rather than silently returning partial answers;
- do not expose private user/project data, credentials, server paths beyond the configured repository root, raw logs, or environment variables;
- do not allow user prompts to execute code, mutate repository/platform state, or trigger costly workflows;
- treat repository text and user questions as prompt-injection surfaces;
- rate-limit usage and record costs through the credits/billing framework where appropriate;
- make stale documentation and unsupported answers visible rather than hiding uncertainty;
- preserve human review fields so the evidence log does not imply all model answers are correct.

## Implementation considerations

- Add settings for the Codex executable path, repository checkout path, model, timeout, prompt version, and output directory.
- Prefer a management command such as `answer_project_understanding_question` before a web UI.
- Use `subprocess.run` or `asyncio.create_subprocess_exec` with an argument list and bounded timeout.
- Capture stdout as the candidate answer; capture stderr and non-zero exit status in the record and user-visible error path.
- Record the current repository commit with `git rev-parse HEAD` when available.
- Ensure the process environment does not leak unnecessary secrets. If Codex needs credentials configured on the server, keep them outside the evidence record.
- Add tests around prompt construction, argument-vector construction, timeout/error handling, record serialization, and access control for any UI surface.
- Consider whether a second offline parser should extract file citations from Codex's answer into structured metadata, while still preserving the raw answer.

## Phased plan

### Phase A: revised planning and command design

- Treat the normal API/retrieval-wrapper approach as superseded for the main architecture.
- Define the first `codex exec` command contract: executable, repository path, sandbox mode, approval mode, model, timeout, prompt passing, and output capture.
- Version the Codex prompt and decide how prompt versions are stored.
- Define the record schema and create `docs/project_understanding/` conventions.
- Choose the first set of report-relevant evaluation questions.

### Phase B: restricted management-command prototype

- Build a management command that accepts a question, constructs the versioned Codex prompt, invokes `codex exec` in read-only/no-approval mode, and prints the answer.
- Store each run as a versionable record with command metadata and human assessment placeholders.
- Add tests for prompt construction, safe subprocess argument construction, timeout/error paths, record serialization, and missing-evidence behaviour.
- Run a small curated question set manually and inspect whether Codex cites useful files and distinguishes implemented/planned work.

### Phase C: staff-only UI and review workflow

- Add a minimal staff-only Django view after the command path is stable.
- Display answer text, extracted citations/supporting-file list, command metadata, and stderr/exit status warnings.
- Add reviewer assessment controls and export/review paths for committing selected records.
- Add access-control, rate-limit, and audit tests.

### Phase D: report/evidence workflow

- Run a curated question set relevant to the initial C-LARA-2 report's autonomy/authorship argument.
- Human-review the answers and fill in assessment fields.
- Add a development log summarizing design choices, limitations, representative successes/failures, and implications for the report.
- Use reviewed records as inspectable evidence rather than unverified promotional claims.

### Phase E: possible productization

- Evaluate whether the restricted assistant should become a general staff help tool.
- Consider a carefully narrowed user-facing help assistant only after accuracy, privacy, safety, and cost controls are demonstrated.
- Consider convergence with the broader dialogue top level, while preserving the evidence-log workflow.

## Open questions

- What is the most reliable production path to the Codex CLI and the intended repository checkout, especially across local development and AWS deployment?
- How should the platform pass prompts to `codex exec` so long questions are safe and robust without relying on shell interpolation?
- What timeout should be used for project-understanding questions, and how should partial/no-output cases be presented to users?
- Should records be written directly by the platform, exported for later commit, or both?
- What is the minimum curated question set needed for the first report?
- How should human assessments be summarized without overstating model reliability?
- How should answers cite files consistently enough for downstream parsing while still letting Codex decide what to inspect?
