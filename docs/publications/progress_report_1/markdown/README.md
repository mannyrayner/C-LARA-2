# C-LARA-2 Progress Report 1 (Concise Working Draft)

**Target date:** 2026-06-15  
**Draft status:** Concise internal draft plan for project-member review

This directory is the Markdown-first workspace for the first C-LARA-2 progress report. The report should be short, selective, and interim: it records what has been achieved during the first few months of work, not a claim that the project is finished.

## How to use this outline

- Read this file first to understand the intended narrative and length discipline.
- Then read each linked section draft.
- Treat all claims as *discussion-ready drafts* to be corrected, shortened, or expanded by Branislav, Cathy, and other project members.
- Avoid re-describing standard C-LARA functionality unless the point is necessary for understanding what is new in C-LARA-2.

## Section map

1. [01-introduction-and-history.md](01-introduction-and-history.md)
2. [02-core-themes-and-ai-autonomy.md](02-core-themes-and-ai-autonomy.md)
3. [03-user-facing-functionality.md](03-user-facing-functionality.md)
4. [04-implementor-facing-functionality.md](04-implementor-facing-functionality.md)
5. [05-medium-term-future-work.md](05-medium-term-future-work.md)

## Relationship to downstream papers

This Markdown workspace is the source outline for the writing targets tracked in [../../../roadmap/reports-and-papers.md](../../../roadmap/reports-and-papers.md):

- first C-LARA-2 progress report target date: **2026-06-15**;
- EuroCALL 2026 full-paper deadline: **2026-07-31**;
- ALTA 2026 remains an active target, currently treated as mid-September 2026 pending confirmation;
- the possible David Gunkel AI-authorship paper should draw on the report-production method without taking over the progress report's main narrative.

Keep this outline and `reports-and-papers.md` synchronized whenever the main thesis, section map, or publication deadlines change.

## Proposed high-level narrative

1. **Why this report is short**: much C-LARA-2 functionality continues C-LARA functionality, so the report should only summarize that background.
2. **What changed most**: C-LARA-2 is AI-centered in a stronger sense than C-LARA. The AI writes the committed code, roadmap material, issue records, operational documentation, and publication drafts, with humans advising, reviewing, and deciding.
3. **New central theme: self-understanding**: recent work has made project self-understanding concrete through an authenticated Assistant that delegates repository exploration to `codex exec` and answers questions from the checked-out C-LARA-2 repository. The Assistant is now working on the AWS deployment after resolving Codex/bubblewrap/AppArmor runtime issues, so it should be treated as one of the report's central examples, not a side note.
4. **Why that matters**: this workflow has produced unusually fast implementation and revision cycles. It has also given the project flexibility: when a feature, design, or deployment plan is wrong, the AI can often rewrite it in hours or minutes. The self-understanding assistant adds a new dimension: the same repository-native artifacts that guide development can be queried, tested, and eventually reviewed as evidence for how well the project can explain itself.
5. **What works now**: selected examples of user-facing functionality, especially picture dictionaries and stronger support for low-resource languages, plus an implementor-facing example of platform self-understanding.
6. **What remains unfinished**: this is an interim report. Major next steps include more autonomous checking by the AI, export/review of self-understanding evidence records, mobile deployment support, and audio recording through the platform.
7. **Possible later use**: the report may become evidence for a publication on AI authorship, including the planned discussion with David Gunkel, because the report itself is an example of academic writing whose production process gives the AI a strong formal claim to authorship apart from the human-status criterion. The self-understanding assistant can strengthen this case only if its answers are preserved with metadata and human assessment rather than treated as automatically reliable.

## Length and emphasis guidance

- Prefer a short report over a comprehensive catalogue.
- Foreground the AI-centered development process and the emerging self-understanding capability, not a full feature manual.
- Mention continuity with C-LARA only where it clarifies the C-LARA-2 contribution.
- Include concrete examples: AWS migration, picture dictionaries, low-resource-language workflows, roadmap/issue/documentation authorship, publication drafting, and the authenticated project-understanding Assistant now running on AWS.

## Open questions for the human review pass

- Are the claims about “100% AI-authored committed repository content” phrased accurately and defensibly?
- How explicitly should the report discuss possible AI authorship of the report and later papers?
- Which user-facing capabilities should be foregrounded for external audiences?
- Which future-work items are mandatory for the next reporting cycle?
- Which project-understanding questions and reviewed answer records are strong enough to cite in the First Progress Report?
