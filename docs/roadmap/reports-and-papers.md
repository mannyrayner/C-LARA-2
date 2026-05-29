# Reports and academic papers roadmap

This roadmap tracks C-LARA-2 writing outputs: the first progress report, conference/journal papers, and related literature-positioning work.

It is directly linked to [ISSUE-0008](../issues/issues/ISSUE-0008.json), which currently tracks the initial AI-authored C-LARA-2 progress report and downstream academic papers. This file now also carries the execution details formerly held in `first-progress-report.md`, which has been retired to avoid maintaining two overlapping publication roadmaps.

## 1) Starting point from the ChatGPT-5.5 discussion

The immediate trigger for this roadmap was a discussion with ChatGPT-5.5 about where C-LARA-2 fits among other AI-assisted software projects.

The most important points to preserve are:

1. **C-LARA-2 is now large enough to be a serious software-engineering case study.** The repository bundle includes code, tests, and documentation, is already tens of thousands of lines, and is growing quickly while remaining easy to extend and correct.
2. **The unusual claim is not just that AI writes code.** The stronger and more interesting claim is that Codex has written the code, tests, roadmap documents, issue records, and operational documentation together, with humans primarily advising, reviewing, and steering.
3. **Documentation and tests appear to be part of the mechanism, not just by-products.** The working hypothesis is that maintaining code, tests, and docs in the same AI-authored GitHub bundle helps the AI preserve a coherent overview of a complex architecture with many interacting features.
4. **The project should be compared with adjacent AI-assisted software efforts.** We need a literature and grey-literature search covering academic papers, preprints, blog posts, and developer-community discussions about AI coding agents, agentic software engineering, self-documenting repositories, and human-in-the-loop AI development.
5. **The C-LARA-2 angle should be precise.** We should avoid a vague “AI helped us code” story and instead foreground the repo-native, documentation-and-tests-first workflow: Codex acts as an implementation agent, documentation maintainer, test author, issue triager, and architectural memory, while humans provide direction and review.
6. **The strongest version of the C-LARA-2 claim is “AI-authored repository”, not “AI-assisted coding”.** In this project, Codex does not merely write most implementation patches; it writes all repository content that is committed, including source code, tests, docs, roadmap updates, issue JSON, and PR text. Humans supply goals, constraints, criticism, and acceptance decisions, but the committed artifact is AI-authored end to end. This is unusual and should be stated explicitly, while still being careful about human intellectual contribution and responsibility.

The discussion trace available here records the user's side of the exchange rather than a complete transcript of ChatGPT-5.5's answers. The summary above therefore captures the planning implications we want to preserve for C-LARA-2 writing work.

## 2) Current writing targets

### Target A — first C-LARA-2 progress report

- **Status:** prioritised.
- **Target date:** 2026-06-15.
- **Tracked by:** [ISSUE-0008](../issues/issues/ISSUE-0008.json).
- **Purpose:** create a concise, citable interim account of C-LARA-2's architecture, AI-assisted development workflow, current functionality, tests/docs/issue-tracking practices, and near-term roadmap.
- **Likely format:** Markdown-first report under `docs/publications/progress_report_1/markdown/`, with later migration to LaTeX if needed.
- **Audience:** internal project team, collaborators, and future paper authors.

#### Progress-report workspace details

These details were merged from the retired `docs/roadmap/first-progress-report.md` roadmap.

Scope for the first report workspace:

- Create and maintain a report workspace under `docs/publications/progress_report_1/`.
- Use a **Markdown-first** drafting process, with later migration to LaTeX if needed.
- Maintain a top-level Markdown document that links to section documents.
- Keep major claims traceable to roadmap and issue artifacts where possible.

Out of scope for now:

- Final paper-ready LaTeX styling and bibliography polishing.
- Venue-specific formatting for EuroCALL/ALTA.

Initial outline requirements:

1. **Project lineage and motivation** (LARA → C-LARA → C-LARA-2).
2. **Stable vs evolving themes**, especially multimodal pedagogical content and increasing AI autonomy.
3. **AI role decomposition in C-LARA-2**, including text/annotation generation, coherent image generation, code implementation, project-management/documentation support, publication drafting support, and sysadmin/deployment tasks.
4. **User-facing functionality**, including the cleaned-up authoring flow, structured editing for low-resource languages, exercise generation, and picture dictionaries.
5. **Implementor-facing functionality**, including roadmap-as-memory, issue suggestion ingestion, and legacy-project migration.
6. **Medium-term future work**, grounded in current issues and roadmaps.

Relevant cross-links for future-work discussion include [ISSUE-0008](../issues/issues/ISSUE-0008.json), [ISSUE-0025](../issues/issues/ISSUE-0025.json), [ISSUE-0026](../issues/issues/ISSUE-0026.json), [mobile-access.md](mobile-access.md), and [alignment.md](alignment.md).

Completion criteria for the workspace:

- Publication workspace directories exist under `docs/publications/progress_report_1/`.
- Markdown top-level outline exists and links to section placeholders.
- LaTeX folder exists with a conversion-plan placeholder.
- ISSUE-0008 notes reference this roadmap and the new workspace workflow.

### Target B — EuroCALL 2026 paper

- **Status:** accepted; full paper preparation prioritised.
- **Deadline:** 2026-07-31.
- **Purpose:** turn the progress-report material into a focused academic paper for the EuroCALL 2026 audience.
- **Likely emphasis:** C-LARA-2 as a rapidly evolving AI-assisted CALL platform, including practical workflows for language-learning content creation and the AI-assisted software/documentation process behind the platform.

### Target C — ALTA 2026 paper

- **Status:** active target.
- **Deadline:** mid-September 2026.
- **Purpose:** prepare a more computational-linguistics/NLP-oriented paper, primarily emphasising the implementor-facing half of the progress report (AI-authored repo workflow, evaluation strategy, and architecture/process lessons), while retaining enough user-facing context to motivate the work.

### Proposed split between EuroCALL and ALTA

Subject to agreement from the co-authors and other people concerned, the first progress report should act as the master document, and the conference papers should split its material roughly as follows:

- **EuroCALL 2026:** focus on the user-facing half of the story: C-LARA-2 as a CALL platform for creating, reviewing, publishing, importing, and reusing multimodal language-learning materials. Likely examples include the core authoring pipeline, image generation, legacy C-LARA import, picture dictionaries, Kok Kaper language-game planning, and community workflows.
- **ALTA 2026:** focus on the implementor-facing half of the story: C-LARA-2 as an AI-authored, repo-native software engineering experiment with multilingual NLP/CALL functionality. Likely examples include the annotation pipeline, evaluation/test strategy, issue-suggestion loop, roadmap-as-memory, and comparison with projects such as CodePrism.

There will naturally be overlap: EuroCALL needs enough implementation detail to make the platform credible, and ALTA needs enough user-facing motivation to explain why the engineering choices matter.

## 3) Core thesis to develop

A likely central thesis is:

> C-LARA-2 is not only an AI-assisted language-learning platform; it is also an example of AI-assisted software engineering where code, tests, documentation, roadmap planning, and issue tracking are co-produced inside one repository, enabling the AI coding agent to maintain architectural context over a rapidly growing system.

This thesis should be tested and made concrete by showing:

- how functionality is decomposed into roadmaps, issues, tests, and implementation patches;
- how documentation is updated as part of the same workflow as code;
- how tests and issue records help preserve context across sessions;
- where humans intervene: problem selection, domain knowledge, review, priorities, and acceptance criteria;
- where the process is fragile or still unproven.

## 4) Candidate report/paper structure

The first progress report could use this structure:

1. **Introduction**
   - C-LARA background and motivation for C-LARA-2.
   - Why AI-assisted reimplementation is interesting.
2. **Platform functionality**
   - Text generation, annotation, glossing, audio, image generation, HTML compilation, publication, exercises, picture dictionaries, and legacy import.
3. **Repository-native AI development workflow**
   - Codex-authored code, tests, docs, roadmap files, issues, and PR summaries.
   - Human role as steering/review layer.
4. **Documentation and tests as architectural memory**
   - Why keeping docs/tests current may help the AI retain system-level coherence.
   - Examples from roadmap and issue-tracking files.
5. **Evaluation and quality control**
   - Unit tests, integration-style tests, planned end-to-end test runner, AI judges, and human review.
6. **Case studies**
   - Legacy C-LARA import.
   - Picture dictionaries and Kok Kaper language-game planning.
   - Issue-suggestion loop and temporal context.
7. **Related work**
   - AI coding agents and agentic software engineering.
   - Human-in-the-loop software generation.
   - AI-assisted documentation/testing.
   - CALL and AI-supported language-learning authoring tools.
8. **Limitations and risks**
   - Hallucination, hidden regressions, dependency on human steering, evaluation gaps, maintainability questions.
9. **Conclusions and next steps**
   - What the C-LARA-2 experience suggests for future AI-assisted research software projects.

## 5) Literature and comparison work

The literature review should look beyond traditional CALL publications. Relevant comparison material may include:

- academic papers on AI coding assistants and autonomous/agentic software engineering;
- empirical studies of LLMs for code generation, debugging, test generation, documentation, and maintenance;
- papers or preprints on repository-level AI agents;
- practitioner blog posts and technical reports about AI-generated codebases;
- developer-community discussions, including Reddit/Hacker News/GitHub discussions, where teams report experiences with AI agents maintaining nontrivial systems;
- CALL and educational-technology literature on AI-supported authoring platforms.

The comparison question should be narrow:

> Which projects, if any, are organised like C-LARA-2, where the AI agent writes and maintains code, tests, documentation, roadmap/issue records, and architectural explanations as an integrated repository bundle?

## 6) Closest known comparator: CodePrism

Of the currently known comparison points, **CodePrism** looks like the closest match and deserves focused investigation.

Current public materials describe CodePrism as an experimental, 100% AI-generated code-intelligence MCP server. Its GitHub README says that every line of code, documentation, tests, and configuration is AI-written, and that human-written code contributions are not accepted. The project site describes it as a graph-powered code-intelligence tool that turns multi-language repositories into a navigable knowledge graph for AI assistants, with an MCP-native interface.

Why CodePrism matters for C-LARA-2 comparison:

- It appears to share the rare **AI-authored repository** property: not just code generation, but AI generation of code, tests, documentation, and configuration.
- It is itself a tool for AI code understanding, whereas C-LARA-2 is an end-user CALL platform built through an AI-authored repository process. This makes the comparison especially interesting: CodePrism is AI-generated infrastructure for code intelligence; C-LARA-2 is AI-generated research/application software with extensive domain functionality.
- Its README foregrounds AI-only development as a deliberate experiment, including claims about consistency, speed, quality, documentation, and testing. These claims are close to the C-LARA-2 hypothesis and should be compared carefully rather than treated as background.
- It may provide a useful foil for the role of humans: CodePrism public materials appear to emphasise no human code contributions, while C-LARA-2 emphasises humans as domain experts, reviewers, planners, and acceptance authorities even though the committed repo content is AI-authored.

Near-term CodePrism questions:

1. What is the actual development process behind CodePrism, and how are prompts, issues, and human decisions managed?
2. Are its tests and documentation generated before, during, or after implementation?
3. How does it prevent drift or incoherence as the repository grows?
4. How much human review occurs, and at what level?
5. Are there published writeups, blog posts, talks, or discussions about its development methodology?
6. Can C-LARA-2 use CodePrism itself, or learn from its graph-based repository-understanding approach, for future AI context management?

## 7) Workflow for producing the report and papers

1. **Inventory the repo state.** Summarise current code size, app structure, major features, tests, and roadmap/issue files.
2. **Draft the first progress report in Markdown first.** Codex should produce the initial draft, using repository docs as primary evidence.
3. **Ask ChatGPT-5.x for high-level critique.** Use it as a reviewer/suggester, not as the sole author.
4. **Human review.** Humans correct framing, claims, terminology, and domain details.
5. **Extract paper versions.** Derive the EuroCALL and ALTA submissions from the first progress report rather than starting from scratch.
6. **Keep the methodology explicit in each publication.** State clearly that drafts are produced through the C-LARA-2 issues workflow (Codex authorship with human steering/review), and keep suggestion/issue traces auditable in-repo.
7. **Keep repo documentation synchronized.** Any claims about process or functionality should be checked against current roadmap/issues/tests.

## 8) Near-term action items

- Update [ISSUE-0008](../issues/issues/ISSUE-0008.json) to link this roadmap and list the current writing targets.
- Gather current repository metrics and feature inventory.
- Keep the Markdown-first progress report workspace coherent and ready for later LaTeX conversion if needed.
- Start a related-work bibliography, including both academic and grey-literature sources.
- Investigate CodePrism in detail as the closest currently known comparator.
- Confirm with co-authors that the split remains: EuroCALL 2026 focused on user-facing functionality, ALTA 2026 focused on implementor-facing methodology/engineering, with limited overlap as needed.
- Ensure each publication includes a concise methods statement explaining the issues-driven Codex authoring workflow and human review role.
