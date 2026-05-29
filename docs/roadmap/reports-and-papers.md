# Reports and academic papers roadmap

This roadmap tracks C-LARA-2 writing outputs: interim progress reports, conference/journal papers, and related literature-positioning work.

It is directly linked to [ISSUE-0008](../issues/issues/ISSUE-0008.json), which currently tracks the initial AI-authored C-LARA-2 progress report and downstream academic papers.

## 1) Updated reporting strategy

The first C-LARA-2 report should be short and selective rather than comprehensive. Much of the platform continues LARA/C-LARA functionality, and repeating that material in detail would weaken the report.

The central theme should instead be the AI-centered nature of the project:

1. **The AI writes the committed repository artifacts.** In the current workflow, Codex writes the code, tests, documentation, roadmap documents, issue-tracking records, operational documentation, and publication drafts.
2. **Humans advise and decide.** Human project members supply goals, priorities, domain expertise, critique, ethical judgment, and acceptance decisions. At present this advice is substantial, but the repository artifacts remain AI-authored.
3. **Speed and flexibility are the key practical results.** Compared with C-LARA, C-LARA-2 can often change direction much faster: unsatisfactory code, plans, documentation, or draft text can frequently be rewritten in hours or minutes.
4. **The AI role extends beyond programming.** C-LARA-2 should foreground the AI acting as project manager, documentation maintainer, issue triager, publication drafter, and sysadmin/deployment assistant. The AWS server migration is a useful concrete example because the AI organized and executed the operational work on a days-scale timeline when migration became necessary.
5. **The report is explicitly interim.** It should say what has been done in the first few months and then clearly list important unfinished work.

## 2) Current writing targets

### Target A — first C-LARA-2 progress report

- **Status:** prioritised.
- **Target date:** 2026-06-15.
- **Tracked by:** [ISSUE-0008](../issues/issues/ISSUE-0008.json) and [first-progress-report.md](first-progress-report.md).
- **Purpose:** create a concise, citable interim account of C-LARA-2's early progress, focusing on the AI-centered workflow, selected new user-facing functionality, implementor-facing process, and future work.
- **Likely format:** Markdown-first report under `docs/publications/progress_report_1/markdown/`, later transposed to LaTeX if needed.
- **Audience:** internal project team, collaborators, and future paper authors.

### Target B — EuroCALL 2026 paper

- **Status:** accepted; full paper preparation prioritised.
- **Deadline:** mid-August 2026.
- **Purpose:** turn progress-report material into a focused academic paper for the EuroCALL 2026 audience.
- **Likely emphasis:** C-LARA-2 as a rapidly evolving AI-centered CALL platform, with practical examples such as picture dictionaries, low-resource-language support, multimodal content creation, and the human-advised AI development process behind the platform.

### Target C — ALTA 2026 paper

- **Status:** active target.
- **Deadline:** mid-September 2026.
- **Purpose:** prepare a computational-linguistics/NLP-oriented paper, primarily emphasising the implementor-facing half of the report: AI-authored repository workflow, evaluation strategy, architecture/process lessons, and comparisons with adjacent AI-engineering projects.

### Target D — possible AI authorship paper with David Gunkel

- **Status:** increasingly likely but not yet fully agreed.
- **Purpose:** use the initial report, and possibly the wider C-LARA-2 publication workflow, as a case study in academic AI authorship.
- **Working angle:** the report may be a piece of academic writing where the AI has a strong formal claim to be considered an author, because it performs the drafting and repository-maintenance work normally associated with authorship, while failing the usual criterion of being human.
- **Caution:** this should be framed as a research/ethics question and not as a settled authorship-policy claim.

## 3) Proposed split between reports and papers

Subject to agreement from the co-authors and other people concerned, the first progress report should act as the master source document, and later papers should draw selectively from it:

- **Progress report:** short interim account, emphasizing AI-centered process, selected functionality, and unfinished work.
- **EuroCALL 2026:** user-facing CALL story, with picture dictionaries and low-resource-language workflows as prominent examples.
- **ALTA 2026:** implementor-facing AI-authored repository story, with issue/roadmap workflow, testing/evaluation strategy, and related-work comparison.
- **Gunkel authorship paper:** AI authorship story, using the report and repository workflow as evidence.

There will naturally be overlap: EuroCALL needs enough implementation detail to make the platform credible, ALTA needs enough user-facing motivation to explain why the engineering choices matter, and the authorship paper needs enough project detail to make the case concrete.

## 4) Core thesis to develop

A likely central thesis is:

> C-LARA-2 is not only an AI-assisted language-learning platform; it is an AI-centered project in which code, tests, documentation, roadmap planning, issue tracking, sysadmin/deployment work, and academic drafts are co-produced inside one repository by an AI agent under human direction and review.

This thesis should be tested and made concrete by showing:

- how project members provide suggestions, corrections, and priorities;
- how the AI updates issue records, roadmap files, documentation, code, and publication drafts;
- how rapid rewriting changes the practical economics of research-software development;
- how AI-maintained documentation and tests may help preserve system-level coherence;
- where the workflow still fails and needs stronger autonomous checking.

## 5) First progress report content priorities

The first report should foreground only the most important items.

### 5.1 AI-centered process

- Codex authorship of committed code, tests, docs, roadmap documents, issue JSON, runbooks, and publication drafts.
- Humans as advisors, reviewers, domain experts, and acceptance authorities.
- Fast iteration and rewriting as a major practical benefit.
- Sysadmin/deployment support, especially AWS migration.

### 5.2 Selected user-facing functionality

- **Picture dictionaries**, including picture glossing, picture flashcards, and reuse in learner activities.
- **Low-resource-language support**, including structured/manual editing and the need for future mobile/audio workflows.
- Brief continuity note on multimodal text authoring, annotation, images, compile/publish workflows, and exercises.

### 5.3 Implementor-facing workflow

- Roadmap-as-memory pattern.
- Issue suggestion ingestion loop.
- Legacy C-LARA project migration and operational runbooks.
- Tests, artifact checks, and planned regression/drift monitoring.

### 5.4 Future work

The report should explicitly say that C-LARA-2 is not finished. Highest-priority future work:

1. **More autonomy and self-checking** so the AI can detect regressions and verify its work more carefully.
2. **Mobile deployment/support**, particularly for community and low-resource-language use.
3. **Audio recording through the platform**, especially where TTS is weak or unavailable.

Other future-work items include audio/text alignment, improved compiled-content access, picture-dictionary extensions, batch migration tooling, and publication workflow hardening.

## 6) Literature and comparison work

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

## 7) Closest known comparator: CodePrism

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

## 8) Workflow for producing the report and papers

1. **Keep the progress report concise.** Draft from the Markdown workspace and remove repeated C-LARA background unless needed.
2. **Use repository evidence.** Claims should be checked against current roadmap/issues/docs/tests where possible.
3. **State the method explicitly.** Each publication should explain the issues-driven Codex authoring workflow and the human review role.
4. **Ask ChatGPT-5.x for high-level critique if useful.** Use it as a reviewer/suggester, not as the sole author.
5. **Human review.** Humans correct framing, claims, terminology, domain details, and ethical/authorship language.
6. **Extract paper versions.** Derive EuroCALL, ALTA, and any Gunkel authorship material from the progress report rather than starting from scratch.
7. **Keep repo documentation synchronized.** If paper claims change, update the roadmap and issue records as well.

## 9) Near-term action items

- Keep [ISSUE-0008](../issues/issues/ISSUE-0008.json), [first-progress-report.md](first-progress-report.md), and the Markdown report workspace synchronized.
- Shorten the progress report around the AI-centered thesis.
- Add concrete examples for picture dictionaries, low-resource-language support, and AWS migration.
- Gather current repository metrics and feature inventory only where they support the concise narrative.
- Start a related-work bibliography, including AI-authored repositories and AI authorship/publication ethics.
- Investigate CodePrism in detail as the closest currently known comparator.
- Confirm with co-authors the split among EuroCALL 2026, ALTA 2026, and the possible David Gunkel authorship paper.
- Ensure each publication includes a concise methods statement explaining Codex authorship and human steering/review.
