# 2. Core Themes and AI Autonomy (Concise Draft Plan)

## 2.1 Stable core theme: multimodal pedagogical content

- The primary educational objective remains creation and delivery of multimodal texts for language learners.
- Core modalities include text, translation/glossing support, audio, images, and learner activities.
- Because this continuity has already been described in earlier LARA/C-LARA material, this report should summarize it briefly rather than repeat it at length.

## 2.2 Central new theme: the AI-centered project

- The central claim for this report is that C-LARA-2 is AI-centered throughout the project lifecycle.
- The AI writes the committed implementation, tests, project-management documents, roadmap documents, issue-tracking records, operational documentation, and publication drafts.
- Humans currently advise quite heavily, but the project can still move faster and change direction more easily than C-LARA because the AI can rapidly rewrite code, documentation, and planning artifacts.

## 2.3 New central theme: project self-understanding

- Recent work on the restricted project-understanding assistant should be treated as one of the central themes of the First Progress Report.
- The assistant exposes C-LARA-2's repository-native self-understanding inside the platform: an authorised user asks a high-level project question, the platform builds a versioned prompt, and `codex exec` inspects the checked-out repository in read-only mode to answer with supporting file evidence.
- This matters because it converts the project's documentation strategy into an inspectable capability. Roadmaps, issue records, tests, source files, runbooks, and publication drafts are not only internal memory for future Codex sessions; they can also be queried by the platform itself.
- The current implementation is deliberately restricted and evidential rather than public or action-taking. It is an admin/trusted-user tool for project maintenance, report preparation, and later human-reviewed evidence records.

## 2.4 AI role decomposition in C-LARA-2

- **Content and annotation generation**: AI-assisted writing, glossing, translation, segmentation, and linguistic annotation.
- **Image and picture-dictionary workflows**: AI-supported illustration generation and vocabulary-image association for glossing, flashcards, and other learner activities.
- **Code implementation**: Codex-driven implementation of repository code.
- **Project management and documentation**: AI-maintained roadmap, issue, runbook, and explanatory documents.
- **Project self-understanding**: Codex-backed repository exploration from inside the platform, with versioned prompts, read-only execution, captured metadata, and a path to reviewed evidence records.
- **Publication drafting**: AI-authored report and paper drafts under human steering and review.
- **Sysadmin and deployment**: AI-guided operational work, including organizing the AWS migration when it became necessary and completing the migration work on a days-scale timeline.

## 2.5 Human role

- Humans provide goals, project priorities, domain expertise, ethical judgment, critique, and acceptance decisions.
- Humans remain accountable for correctness, safety, framing, external claims, and assessment of any self-understanding answers used as evidence.
- The current system is therefore not “autonomous” in the sense of requiring no human intervention; it is autonomous in the narrower operational sense that the AI performs the writing and implementation work once humans have supplied direction and review.

## 2.6 Speed, flexibility, self-understanding, and limits

- The positive result to emphasize is development velocity and flexibility: unsatisfactory features, texts, or deployment plans can often be rewritten very quickly. A recent user-facing example is the rapid iteration on picture-dictionary image regeneration and diagnostics: a “no visible text” constraint was wired through to organiser-requested page-image generation, and an AI-based advisory checker was added to flag likely low-resource word/gloss language-confusion errors.
- The self-understanding result to emphasize is that the platform can now ask Codex to inspect the repository and produce project-level answers with citations, run metadata, token counts where extractable, and persisted request/result records.
- The Assistant self-query debugging episode should be considered as a concrete methods vignette: human questioning exposed a non-obvious failure mode, repeated AI-authored patches made the failure more diagnosable, and the final fix used an additional model call to judge whether a Codex transcript was a real execution failure or a plausible answer quoting failure-looking repository evidence.
- The issue-suggestion workflow also gives a compact AI/human collaboration vignette: a human reported a concrete page-oriented manual annotation save failure, the AI converted it into a P1 issue with a data-loss framing, linked it unprompted to the existing community-judging autosave issue, and the human then steered the mitigation choice toward autosave or per-segment save controls. This illustrates how repository-native issue memory lets a small human observation trigger broader design synthesis rather than only a literal bug note.
- The English MWE pilot gives a second compact autonomy vignette: human manual annotation exposed poor baseline MWE quality and supplied a small gold development sample, while the AI identified stale corpus metadata, implemented a refresh path from latest saved artifacts, and proposed a leakage-controlled prompt-improvement experiment before validation/test use.
- A useful external phrasing from a July 2026 r/codex discussion captures the working style: “I stopped writing 500 word prompts. Asked it like a co-worker. It just works.” Although the comment was about another model rollout, it matches the C-LARA-2 collaboration pattern increasingly well: the human often states goals, constraints, and judgements conversationally, while the AI uses shared repository memory, roadmaps, issues, tests, and prior decisions to turn that into concrete implementation and documentation. The report should present this as **context-rich co-worker interaction**, not as magic short prompting; it works because the repository supplies durable context and because human review remains active.
- The limits to emphasize are quality control and evidential governance: the AI still needs better ways to check its own work, detect regressions, notice when user-facing controls or processing quality have drifted, export durable records for review, reconcile exact costs, and protect the restricted assistant from privacy and prompt-injection risks.
- The report should therefore present AI autonomy and self-understanding as promising but unfinished methodology.

## 2.7 Authorship implications

- The report-writing process itself may be relevant to a later paper on AI authorship.
- The cautious formulation is that C-LARA-2 may provide a concrete case where an AI-generated academic text meets many formal criteria normally associated with authorship, apart from being human.
- This should be flagged as an emerging line of analysis rather than made the main claim of the progress report.
- The self-understanding assistant adds a second kind of authorship evidence: not only AI-written text, but an AI-mediated record of how the project explains its own architecture, status, and plans from repository evidence. That evidence will be persuasive only after curated questions, exportable records, and human assessment are in place.

## 2.8 Discussion prompts for revision

- Is “AI-centered” clearer than “AI-autonomous” for the main report?
- Should the authorship discussion be a footnote, a short paragraph, or deferred to a separate paper?
- How much detail should be included about the AWS migration and other sysadmin work?
- Which self-understanding questions should be run, reviewed, and cited in the First Progress Report?
