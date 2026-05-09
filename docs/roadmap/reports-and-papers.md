# Reports and academic papers roadmap

This roadmap tracks C-LARA-2 writing outputs: internal technical reports, conference/journal papers, and related literature-positioning work.

It is directly linked to [ISSUE-0008](../issues/issues/ISSUE-0008.json), which currently tracks the initial AI-authored C-LARA-2 technical report.

## 1) Starting point from the ChatGPT-5.5 discussion

The immediate trigger for this roadmap was a discussion with ChatGPT-5.5 about where C-LARA-2 fits among other AI-assisted software projects.

The most important points to preserve are:

1. **C-LARA-2 is now large enough to be a serious software-engineering case study.** The repository bundle includes code, tests, and documentation, is already tens of thousands of lines, and is growing quickly while remaining easy to extend and correct.
2. **The unusual claim is not just that AI writes code.** The stronger and more interesting claim is that Codex has written the code, tests, roadmap documents, issue records, and operational documentation together, with humans primarily advising, reviewing, and steering.
3. **Documentation and tests appear to be part of the mechanism, not just by-products.** The working hypothesis is that maintaining code, tests, and docs in the same AI-authored GitHub bundle helps the AI preserve a coherent overview of a complex architecture with many interacting features.
4. **The project should be compared with adjacent AI-assisted software efforts.** We need a literature and grey-literature search covering academic papers, preprints, blog posts, and developer-community discussions about AI coding agents, agentic software engineering, self-documenting repositories, and human-in-the-loop AI development.
5. **The C-LARA-2 angle should be precise.** We should avoid a vague “AI helped us code” story and instead foreground the repo-native, documentation-and-tests-first workflow: Codex acts as an implementation agent, documentation maintainer, test author, issue triager, and architectural memory, while humans provide direction and review.

The discussion trace available here records the user's side of the exchange rather than a complete transcript of ChatGPT-5.5's answers. The summary above therefore captures the planning implications we want to preserve for C-LARA-2 writing work.

## 2) Current writing targets

### Target A — long internal technical report

- **Status:** prioritised.
- **Target date:** mid-June 2026.
- **Tracked by:** [ISSUE-0008](../issues/issues/ISSUE-0008.json).
- **Purpose:** create a detailed, citable account of C-LARA-2's architecture, AI-assisted development workflow, current functionality, tests/docs/issue-tracking practices, and near-term roadmap.
- **Likely format:** LaTeX technical report.
- **Audience:** internal project team, collaborators, and future paper authors.

### Target B — EuroCALL 2026 paper

- **Status:** accepted; full paper preparation prioritised.
- **Deadline:** mid-August 2026.
- **Purpose:** turn the internal-report material into a focused academic paper for the EuroCALL 2026 audience.
- **Likely emphasis:** C-LARA-2 as a rapidly evolving AI-assisted CALL platform, including practical workflows for language-learning content creation and the AI-assisted software/documentation process behind the platform.

### Target C — possible ALTA 2026 paper

- **Status:** possible target.
- **Deadline:** to be confirmed.
- **Purpose:** consider a more computational-linguistics/NLP-oriented paper, potentially emphasising multilingual annotation, low-resource language workflows, evaluation, or the AI-assisted engineering methodology if it fits the call.

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

A first internal report could use this structure:

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

## 6) Workflow for producing the report and papers

1. **Inventory the repo state.** Summarise current code size, app structure, major features, tests, and roadmap/issue files.
2. **Draft the internal report in LaTeX.** Codex should produce the initial draft, using repository docs as primary evidence.
3. **Ask ChatGPT-5.x for high-level critique.** Use it as a reviewer/suggester, not as the sole author.
4. **Human review.** Humans correct framing, claims, terminology, and domain details.
5. **Extract paper versions.** Derive the EuroCALL and possible ALTA submissions from the internal report rather than starting from scratch.
6. **Keep repo documentation synchronized.** Any claims about process or functionality should be checked against current roadmap/issues/tests.

## 7) Near-term action items

- Update [ISSUE-0008](../issues/issues/ISSUE-0008.json) to link this roadmap and list the current writing targets.
- Gather current repository metrics and feature inventory.
- Create a report outline in LaTeX.
- Start a related-work bibliography, including both academic and grey-literature sources.
- Decide which parts of the internal report should feed the EuroCALL 2026 paper versus a possible ALTA 2026 paper.
