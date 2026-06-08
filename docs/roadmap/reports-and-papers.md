# Reports and academic papers roadmap

This roadmap tracks C-LARA-2 writing outputs: the first progress report, conference/journal papers, and related literature-positioning work.

Linked issues and companion docs:

- [ISSUE-0008](../issues/issues/ISSUE-0008.json) — report/papers umbrella issue.
- [roadmap-cleanup.md](roadmap-cleanup.md) — tracks the cleanup pass that produced this clearer structure.
- `docs/publications/progress_report_1/markdown/` — Markdown-first draft report workspace.

## Current status snapshot

- **First progress report:** in progress, target date **2026-06-15**; self-understanding is now one of the central themes.
- **EuroCALL 2026 paper:** accepted; full-paper deadline now confirmed as **2026-07-31**.
- **ALTA 2026 paper:** active target, deadline currently treated as **mid-September 2026** until confirmed more precisely.
- **Possible David Gunkel AI-authorship paper:** increasingly likely but not yet fully agreed.

## Completed or settled framing decisions

- The first report should be **short, selective, and interim**, not a long catalogue of C-LARA-like functionality.
- The main contribution to foreground is the **AI-centered project organization**: Codex writes committed code, tests, documentation, roadmap documents, issue records, operational documentation, and publication drafts, while humans advise, review, prioritize, and accept/reject.
- A second central contribution is now **project self-understanding**: C-LARA-2 is beginning to expose, inside the platform, an authenticated Codex-backed assistant that can inspect the repository and answer questions about the project with file-grounded evidence.
- The report should emphasize practical consequences of this organization: faster iteration, greater flexibility, rapid rewriting, and AI-guided sysadmin/deployment work such as the AWS migration.
- The user-facing examples to foreground are **picture dictionaries** and **more coherent support for low-resource languages**. The first picture-clue word-scramble exercise is a good concrete example of rapid user-requested functionality delivered on top of picture dictionaries and should be considered for the First Progress Report. A draft report claim can say that the feature required roughly **twelve minutes of AI implementation time** and about **one hour of human AI-expert steering/review time**, while being careful not to imply that this covers the full community consultation, pedagogical discussion, or cultural-permission work.
- The report should clearly state that C-LARA-2 is unfinished, while also trying to include a first concrete AI self-checking result: AI-based evaluation of default versus candidate segmentation phase 1, segmentation phase 2, and MWE outputs using the existing pipeline runner. Remaining high-priority future work includes stronger AI self-checking/autonomy, export/review of self-understanding evidence records, mobile support, and platform audio recording.
- The possible AI-authorship paper should be framed as an open research/ethics question, not as a settled authorship-policy claim.

## Current work

### Target A — first C-LARA-2 progress report

- **Status:** in progress.
- **Target date:** 2026-06-15.
- **Source workspace:** `docs/publications/progress_report_1/markdown/`.
- **Purpose:** create a concise, citable interim account of C-LARA-2's early progress, focusing on the AI-centered workflow, selected user-facing functionality, implementor-facing process, and future work.
- **Likely format:** Markdown-first report, later transposed to LaTeX only if useful.
- **Audience:** internal project team, collaborators, and future paper authors.

The report workspace and this roadmap should stay synchronized. The current Markdown section map is:

| Report section | Roadmap role |
|---|---|
| `README.md` | Top-level narrative, length discipline, and review questions. |
| `01-introduction-and-history.md` | Short lineage from LARA/C-LARA to C-LARA-2, plus interim-report and authorship-paper framing. |
| `02-core-themes-and-ai-autonomy.md` | Main AI-centered thesis, self-understanding as an emerging core theme, AI role decomposition, human role, speed/flexibility, limits, and authorship implications. |
| `03-user-facing-functionality.md` | Selected user-facing examples: picture dictionaries, picture glossing/flashcards, low-resource-language support, and brief continuity notes. |
| `04-implementor-facing-functionality.md` | Roadmap-as-memory, issue ingestion, authenticated project-understanding assistant, legacy migration, AWS/sysadmin work, and quality-control infrastructure. |
| `05-medium-term-future-work.md` | Interim-status caveat and prioritized future work: AI self-checking, self-understanding evidence workflow, mobile support, platform audio recording, alignment, access, and migration/tooling refinements. |

### Target B — EuroCALL 2026 paper

- **Status:** accepted; full paper preparation prioritised.
- **Deadline:** **2026-07-31**.
- **Purpose:** extract a focused CALL paper from the first progress report.
- **Likely emphasis:** C-LARA-2 as a rapidly evolving AI-centered CALL platform, with picture dictionaries, low-resource-language support, multimodal content creation, and human-advised AI development as the central examples.
- **Constraint:** the July 31 deadline makes it important that the June progress report remain concise and reusable rather than overgrown.

### Target C — ALTA 2026 paper

- **Status:** active target.
- **Deadline:** mid-September 2026, pending confirmation.
- **Purpose:** prepare a computational-linguistics/NLP-oriented paper from the implementor-facing half of the material.
- **Likely emphasis:** AI-authored repository workflow, project self-understanding, evaluation strategy, architecture/process lessons, issue/roadmap memory, testing/evaluation, and comparison with adjacent AI-engineering projects.

### Target D — possible AI-authorship paper with David Gunkel

- **Status:** increasingly likely but not yet fully agreed.
- **Purpose:** use the first report, and possibly the wider C-LARA-2 publication workflow, as a case study in academic AI authorship.
- **Working angle:** the report may be a piece of academic writing where the AI has a strong formal claim to be considered an author because it performs the drafting and repository-maintenance work normally associated with authorship, while failing the usual criterion of being human.
- **Caution:** keep this as a research/ethics question and avoid making it the dominant claim of the first progress report.

## Planned paper split

Subject to co-author agreement, the first progress report should act as the master source document, and later papers should draw selectively from it:

- **Progress report:** short interim account emphasizing AI-centered process, project self-understanding, selected functionality, and unfinished work.
- **EuroCALL 2026:** user-facing CALL story, with picture dictionaries and low-resource-language workflows as prominent examples.
- **ALTA 2026:** implementor-facing AI-authored repository story, with issue/roadmap workflow, project self-understanding, testing/evaluation strategy, and related-work comparison.
- **Gunkel authorship paper:** AI authorship story, using the report and repository workflow as evidence.

There will naturally be overlap: EuroCALL needs enough implementation detail to make the platform credible, ALTA needs enough user-facing motivation to explain why the engineering choices matter, and the authorship paper needs enough project detail to make the case concrete.

## Core theses to develop

Two connected central theses now need to be developed:

> C-LARA-2 is not only an AI-assisted language-learning platform; it is an AI-centered project in which code, tests, documentation, roadmap planning, issue tracking, sysadmin/deployment work, and academic drafts are co-produced inside one repository by an AI agent under human direction and review.

> C-LARA-2 is also beginning to become self-understanding: because code, tests, issues, roadmaps, runbooks, and report drafts live in the repository, an authenticated Codex-backed assistant can inspect that evidence base and answer project-level questions from inside the platform.

These theses should be tested and made concrete by showing:

- how project members provide suggestions, corrections, and priorities;
- how the AI updates issue records, roadmap files, documentation, code, and publication drafts;
- how rapid rewriting changes the practical economics of research-software development;
- how AI-maintained documentation and tests may help preserve system-level coherence;
- how the authenticated project-understanding assistant delegates repository exploration to `codex exec`, captures answer metadata, and creates a path toward versioned human-reviewed evidence records;
- how a first ISSUE-0004 phase-output evaluator can use the existing pipeline runner to judge default versus candidate segmentation phase 1, segmentation phase 2, and MWE outputs, making autonomy/self-checking operational and potentially improvement-guiding rather than purely aspirational;
- where the workflow still fails and needs stronger autonomous checking, export/review controls, cost controls, and safety boundaries.

## Related-work and comparison work

The literature review should look beyond traditional CALL publications. Relevant comparison material may include:

- academic papers on AI coding assistants and autonomous/agentic software engineering;
- empirical studies of LLMs for code generation, debugging, test generation, documentation, and maintenance;
- papers or preprints on repository-level AI agents;
- practitioner blog posts and technical reports about AI-generated codebases;
- developer-community discussions where teams report experiences with AI agents maintaining nontrivial systems;
- CALL and educational-technology literature on AI-supported authoring platforms;
- AI-authorship and publication-ethics literature, especially if the David Gunkel paper proceeds.

The comparison question should be narrow:

> Which projects, if any, are organised like C-LARA-2, where the AI agent writes and maintains code, tests, documentation, roadmap/issue records, operational notes, and academic drafts as an integrated repository bundle?

### Closest known comparator: CodePrism

Of the currently known comparison points, **CodePrism** looks like the closest match and deserves focused investigation.

Current public materials describe CodePrism as an experimental, 100% AI-generated code-intelligence MCP server. Its GitHub README says that every line of code, documentation, tests, and configuration is AI-written, and that human-written code contributions are not accepted. The project site describes it as a graph-powered code-intelligence tool that turns multi-language repositories into a navigable knowledge graph for AI assistants, with an MCP-native interface.

Why CodePrism matters for C-LARA-2 comparison:

- It appears to share the rare **AI-authored repository** property: not just code generation, but AI generation of code, tests, documentation, and configuration.
- It is itself a tool for AI code understanding, whereas C-LARA-2 is an end-user CALL platform built through an AI-authored repository process.
- Its README foregrounds AI-only development as a deliberate experiment, including claims about consistency, speed, quality, documentation, and testing.
- It may provide a useful foil for the role of humans: CodePrism public materials appear to emphasise no human code contributions, while C-LARA-2 emphasises humans as domain experts, reviewers, planners, and acceptance authorities even though committed repo content is AI-authored.

Near-term CodePrism questions:

1. What is the actual development process behind CodePrism, and how are prompts, issues, and human decisions managed?
2. Are its tests and documentation generated before, during, or after implementation?
3. How does it prevent drift or incoherence as the repository grows?
4. How much human review occurs, and at what level?
5. Are there published writeups, blog posts, talks, or discussions about its development methodology?
6. Can C-LARA-2 use CodePrism itself, or learn from its graph-based repository-understanding approach, for future AI context management?

## Workflow rules

1. **Keep the progress report concise.** Draft from the Markdown workspace and remove repeated C-LARA background unless needed.
2. **Keep roadmap and report synchronized.** If the progress-report section map or main thesis changes, update this file and the Markdown report workspace.
3. **Use repository evidence.** Claims should be checked against current roadmap/issues/docs/tests where possible.
4. **State the method explicitly.** Each publication should explain the issues-driven Codex authoring workflow and the human review role.
5. **Ask ChatGPT-5.x for high-level critique if useful.** Use it as a reviewer/suggester, not as the sole author.
6. **Human review.** Humans correct framing, claims, terminology, domain details, and ethical/authorship language.
7. **Extract paper versions.** Derive EuroCALL, ALTA, and any Gunkel authorship material from the progress report rather than starting from scratch.
8. **Keep repo documentation synchronized.** If paper claims or deadlines change, update the roadmap and issue records as well.

## Near-term action items

- Keep [ISSUE-0008](../issues/issues/ISSUE-0008.json), this roadmap, and the Markdown report workspace synchronized.
- Finish the concise progress-report draft around the AI-centered thesis and the new self-understanding theme.
- Add concrete examples for picture dictionaries, picture-clue word scrambles as rapid user-requested functionality, low-resource-language support, AWS migration, the authenticated project-understanding assistant, and first-version AI evaluation of default versus candidate linguistic phase outputs. For the word-scramble example, explicitly separate the rapid AI/human-expert platform implementation estimate from Sophie’s end-user/community consultation work, and ask Sophie what, if anything, can be said publicly given the sensitivity of Australian Aboriginal language work.
- Gather current repository metrics and feature inventory only where they support the concise narrative.
- Start a related-work bibliography, including AI-authored repositories and AI authorship/publication ethics.
- Investigate CodePrism in detail as the closest currently known comparator.
- Confirm the ALTA deadline and the split among EuroCALL 2026, ALTA 2026, and the possible David Gunkel authorship paper.
- Plan backwards from the **2026-07-31** EuroCALL deadline.
- Ensure each publication includes a concise methods statement explaining Codex authorship, human steering/review, and the status of any self-understanding evidence records used as support.
