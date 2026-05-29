# First C-LARA-2 progress report roadmap

This roadmap defines the repository structure, workflow, and initial content plan for the **first C-LARA-2 progress report** (target date: **2026-06-15**). The report should now be treated as a short interim report rather than a long technical catalogue.

It is a focused execution companion to:
- [reports-and-papers.md](reports-and-papers.md)
- [ISSUE-0008](../issues/issues/ISSUE-0008.json)

The EuroCALL 2026 full-paper deadline is now confirmed as **2026-07-31**, so the progress report should remain concise and reusable as the source for that paper.

## Why this roadmap exists

We need a concrete writing workspace and repeatable production workflow for the first project report, while keeping the process aligned with the issues-driven Codex workflow used across C-LARA-2.

## Scope

### In scope

- Create and maintain a concise report workspace under `docs/publications/progress_report_1/`.
- Use a **Markdown-first** drafting process, with later migration to LaTeX if needed.
- Maintain a top-level document that links to section documents.
- Capture an initial outline spanning:
  - project history (LARA → C-LARA → C-LARA-2),
  - user-facing functionality,
  - implementor-facing functionality,
  - AI-autonomy methodology,
  - medium-term future work grounded in current issues, with special emphasis on more autonomous AI self-checking, mobile support, and platform audio recording.

### Out of scope (for now)

- Final paper-ready LaTeX styling and bibliography polishing.
- Venue-specific formatting for EuroCALL/ALTA.

## Repository structure (phase A)

Create and maintain the following structure:

- `docs/publications/progress_report_1/markdown/`
  - `README.md` (top-level outline + links to section docs)
  - section files (one per major heading)
- `docs/publications/progress_report_1/latex/`
  - placeholder `README.md` with planned `\include{...}` mapping from markdown sections

## Drafting workflow

1. Draft in Markdown section files first.
2. Keep top-level `markdown/README.md` as the canonical table of contents and status tracker.
3. After section maturity, mirror structure in `latex/` and convert section-by-section.
4. Keep major claims traceable to roadmap/issue artifacts where possible.

## Initial outline requirements

The initial top-level outline should include:

1. **Project lineage and motivation** (LARA → C-LARA → C-LARA-2).
2. **Stable vs evolving themes**
   - multimodal pedagogical content (stable),
   - increasing AI autonomy (evolving).
3. **AI role decomposition in C-LARA-2**
   - text/annotation generation,
   - coherent image generation,
   - code implementation,
   - project-management/documentation support,
   - publication drafting support,
   - sysadmin/deployment tasks (including AWS setup/migration orchestration guided by Codex and GPT-5),
   with explicit human advice/review/acceptance role and emphasis on rapid rewriting/flexibility.
4. **User-facing functionality**
   - cleaned-up authoring flow,
   - structured editing for low-resource languages,
   - exercise generation,
   - picture dictionaries, picture glossing, picture flashcards, and exercise integration.
5. **Implementor-facing functionality**
   - roadmap-as-memory pattern,
   - issue suggestion ingestion and Codex update loop,
   - migration of legacy projects (format conversion + server installation workflow).
6. **Medium-term future work (issue-grounded)**
   - user-facing items (mobile, direct audio recording, alignment support), especially for low-resource languages,
   - implementor-facing items (autonomous process/UX drift tracking).

## Authorship-paper note

The initial progress report may also become evidence for a possible paper with David Gunkel on AI authorship. Keep the report-production method explicit: Codex drafts and maintains the committed text, while humans advise, review, and accept/reject. Frame any claim that the AI meets formal authorship criteria apart from being human as an open research/ethics question.

## Cross-links to issue roadmap items

When outlining future work, map sections to active issues/roadmaps, especially:

- [ISSUE-0008](../issues/issues/ISSUE-0008.json) (report/papers umbrella)
- [ISSUE-0025](../issues/issues/ISSUE-0025.json) (UI drift tracking)
- [ISSUE-0026](../issues/issues/ISSUE-0026.json) (community-recorded audio workflow)
- [mobile-access.md](mobile-access.md)
- [alignment.md](alignment.md)
- [reports-and-papers.md](reports-and-papers.md)

## Completion criteria for this roadmap item

- Publication workspace directories exist under `docs/publications/progress_report_1/`.
- Markdown top-level outline exists and links to section placeholders.
- LaTeX folder exists with conversion plan placeholder.
- ISSUE-0008 notes reference this roadmap and the new workspace workflow.
