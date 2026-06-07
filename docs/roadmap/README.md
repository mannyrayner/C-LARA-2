# Roadmap documents for reimplementation of C-LARA (C-LARA-2)

**Overall goal**  
Reimplement [C-LARA](https://www.c-lara.org/) in a more rational way, learning from the initial project.

## Brief description of core C-LARA-2 functionality

- **Functionality from C-LARA:** We want to reproduce the core C-LARA functionality.
	- Use AI to create multimodal text documents suitable for language learners. These should at a minimum include illustrations, translations, lemma tagging, glosses and audio. 
	- It is essential to support multi-word expressions (MWEs) and have them interact cleanly with lemma tagging and glossing. In the final generated document, clicking or hovering over one element of an MWE accesses information attached to the whole MWE.
	- It is essential to support creation of high-quality images that are consistent both in style (different images have the same style) and content (when a person, object etc occurs in more than one image it is depicted similarly).
	- C-LARA-2 should be sufficiently downward-compatible that C-LARA projects can easily be imported.
	- It should be possible to post the multimodal documents on the web, in a social-network like structure that permits rating, commenting etc.
	- Full information about C-LARA can be found in numerous papers posted on the C-LARA site.
- **New functionality:** User feedback suggests some new functionality would be much appreciated.
	- Teachers want it to be easier to create the texts. Instead of providing a detailed description of the text they want to generated, they would prefer to give a brief description and then enter a dialogue with the AI to refine it. If they have a group of related texts, they want to describe the group as a whole, maybe in terms of the intended functionality and users, and have the AI suggest possible texts.
	- Learners want to have the option of accessing non-traditional audio/image oriented texts that work well on mobile phones, e.g. audiobooks, podcasts, manga.

## Important subgoals

- **Involve the AI more:** Various versions of OpenAI's GPT already played an important part in the first version of C-LARA. Here, we want to increase the AI's involvement:
	- The AI should understand the platform (functionality, software architecture, history etc) as well as possible.
	- The AI should play as large a part as possible in implementing the new code.
	- The AI should to as large an extent as possible be able to explain and discuss the platform.
- **Better documentation:** In order to be able to involve the AI in the way described above, the documentation needs to be much better:
	- All code files will be systematically documented (docstrings etc) according to a recognised standard.
	- There will be global web-accessible documentation in the Github repo, i.e. here.
	- The AI will play a central role in _developing_ the documentation. 
	- As we proceed with the project, we will constantly check that the AI is in practice able to use the doc, and revise if necessary.
	
## Main steps in roadmap

### Immediate priorities (April 2026)

- **Priority 1:** Adelaide deployment with C-LARA and C-LARA-2 running safely side-by-side.
- **Priority 2:** Structured manual annotation editor so human reviewers can correct all stages without raw JSON surgery.

### 1. Set up GitHub repository and add initial documentation.

Status: **Done.** The C-LARA-2 repo is at https://github.com/mannyrayner/C-LARA-2.

### 2. Initial core functionality: text generation and segmentation

Status: **Done.** The foundational pieces for the text pipeline are implemented and tested:

- Annotated text representation and utilities.
- OpenAI wrapper with heartbeat, telemetry, retries, and unit/integration coverage.
- Text generation (`text_gen`) to produce starter texts from descriptions.
- Segmentation phase 1 (pages/segments) and phase 2 (tokenization) using the generic annotation harness.
- Generic per-segment annotation fan-out/fan-in infrastructure reused by later steps.
- Prompts and few-shots for the above operations.
- Tests under `tests/` (OpenAI-gated where applicable); run with [`make -C tests test`](../../Makefile).

See [roadmap/segmentation-pipeline.md](segmentation-pipeline.md) for the specification that guided these implementations.

### 3. Full linguistic annotation pipeline

Status: **Done (with expanded romanization support).** The detailed plan lives in [roadmap/linguistic-pipeline.md](linguistic-pipeline.md).

- Implemented: translation, MWE detection, lemma tagging, glossing, audio annotation, HTML compilation, and a flexible `run_full_pipeline` helper.
- Romanization stage: the former “pinyin stage” is now a general **romanization** stage.
  - `pypinyin` for Mandarin,
  - `indic_transliteration` for Hindi,
  - AI-backed romanization fallback for other languages.
- This lets us support language-specific local romanizers when available, while still keeping a generic AI path.

### 4. Write spec for basic Django platform functionality, and implement it

Status: **In progress (strong initial implementation landed).** See [roadmap/django-platform.md](django-platform.md) for the platform plan and implementation notes.

Implemented highlights now include:
- Account flows and project workspace.
- Compile orchestration with monitor/status polling and persisted per-run artifacts.
- Publish toggle and browseable **Content** tab with published-content search and per-content metadata pages.
- Bundle export (self-contained ZIP with HTML/audio/images + README).

### 5. Write spec for image creation functionality, and implement it

Status: **Initial implementation done.** See [roadmap/image-generation-pipeline.md](image-generation-pipeline.md).

Implemented highlights:
- Style → recurring elements → page-image workflow.
- Project-scoped artifact persistence for prompts, metadata, and images.
- Integration with compile/HTML pipeline so generated page images can appear in final HTML.
- ZIP export support for sharing compiled outputs and image assets.

### 6. Social-network functionality roadmap

Status: **New roadmap document added.** See [roadmap/social-network-functionality.md](social-network-functionality.md).

Initial delivered functionality:
- Publishing a project.
- Browsing published content via the Content tab.
- Per-content metadata page (including access counter and link to compiled page 1).

Planned next functionality:
- Comments and ratings.
- Multi-user project roles (`OWNER`, `ANNOTATOR`, `VIEWER`).
- Language-centered communities with organizer/member roles.
- Community-driven image rating/regeneration loops.

### 7. Support for languages where AI annotation is weak or unavailable

Status: **New roadmap document added.** See [roadmap/low-resource-languages.md](low-resource-languages.md).

Planned direction:
- Manual editing UI for all annotation layers, with strict structural validation.
- Human-in-the-loop revision workflow for AI-produced annotations.
- Image generation still enabled via pivot-language translations.
- Full compatibility with publish/content/community workflows for these projects.


### 8. Deployment and migration roadmap

Status: **New roadmap document added.** See [roadmap/deployment-and-migration.md](deployment-and-migration.md).

Priorities:
- Urgent: Adelaide dual-run deployment with existing C-LARA (target before end of April 2026).
- Done for supported legacy JSON exports: structured import from legacy C-LARA data to the C-LARA-2 data model.
- Next: host portability and backup export/import workflows (likely AWS Sydney target).

Key constraint: the urgent Adelaide deployment approach must remain upward-compatible with migration and relocation work.

### 9. Exercise generation roadmap

Status: **Initial cloze implementation delivered.** See [roadmap/exercises.md](exercises.md).

Focus:
- Cloze and flashcard generation from existing project artifacts.
- Picture-dictionary-backed exercise generation, now including planned word scrambles and crosswords with picture clues.
- Distractor generation/validation, puzzle layout validation, and review workflows.
- Learner-facing exercise player and future spaced repetition support.

Implemented now:
- Generate cloze exercise sets from latest run segments.
- Theme options include vocabulary, grammar, morphology, and grammar/morphology.
- Publish/unpublish exercise sets and expose published links on content pages.
- Picture-dictionary-backed flashcards are in place; next planned work is organiser-created sub-projects plus picture-clue word scrambles and crosswords.

### 10. Alignment roadmap (phonetic + text/audio/translation)

Status: **New roadmap document added.** See [roadmap/alignment.md](alignment.md).

Focus:
- 2a: Phonetic decomposition and phonetic compile mode with cache/provenance.
- 2b: Triple alignment pipeline (text + high-quality audio + translation), with LARA-style baseline and AI-assisted improvements.
- Metrics-first delivery with review queues for uncertain segments.


### 11. Manual annotation editor roadmap

Status: **New roadmap document added.** See [roadmap/manual-annotation-editor.md](manual-annotation-editor.md).

Focus:
- Cross-language manual editing for all annotation layers.
- Shared validators, versioned saves, and diff/review tools.
- Human-in-the-loop quality control for both low-resource and high-resource languages.


### 12. Freeform dialogue-based top-level roadmap

Status: **New roadmap document added.** See [roadmap/dialogue-top-level.md](dialogue-top-level.md).

Focus:
- Optional conversational UX layer on top of existing C-LARA-2 workflows.
- Transparent action planning with explicit assumptions, alternatives, and backtracking.
- Strong onboarding support for nontechnical users, with “show me the underlying UI” handoff.


### 13. AI-judges evaluation roadmap

Status: **Report-driven first evaluator plan added.** See [roadmap/ai-judges-evaluation.md](ai-judges-evaluation.md).

Focus:
- First-version AI evaluation of default versus candidate phase-processing variants for segmentation phase 1, segmentation phase 2, and MWE detection, using the existing pipeline runner.
- Near-term support for ISSUE-0004, with concrete before/after evaluation hooks for ISSUE-0005 and ISSUE-0006 before the First Progress Report.
- Longer-term panel-based AI scoring, aggregation, disagreement analysis, optional foreman summarization, and human-audit calibration.


### 14. Few-shot example curation and evaluation roadmap

Status: **New P1 roadmap document added.** See [roadmap/few-shot-example-curation.md](few-shot-example-curation.md). Tracked by [ISSUE-0036](../issues/issues/ISSUE-0036.json).

Focus:
- Generate many candidate few-shot examples per operation/language and cover edge cases such as clitics, compounds, punctuation, idioms, named entities, discontinuous MWEs, and ambiguous glosses.
- Validate candidates with deterministic schema/preservation checks before linguistic judgement.
- Use adversarial critic models, repair passes, consensus scoring, and auditable gold-acceptance records so examples can be trusted and traced.
- Connect prompt/few-shot changes to ISSUE-0004 evaluator records for the First Progress Report.


### 15. Source project export/import bundles roadmap

Status: **Initial implementation delivered, with legacy C-LARA JSON import support.** See [roadmap/source-project-bundles.md](source-project-bundles.md).

Focus:
- ZIP export/import of editable source artifacts from latest (or selected) runs.
- Direct import of supported legacy C-LARA JSON export bundles into normal C-LARA-2 projects.
- Full preservation of text annotations and image-pipeline metadata/provenance.
- Server↔laptop portability for debugging, handover, backup, and migration workflows, including documented AWS/SSH transfer details for large legacy corpus uploads.

Implemented now:
- Export source bundle from project detail.
- Import source bundle from project list, always creating a new project.
- Import supported legacy C-LARA JSON ZIP bundles (flat or single-root layouts with `annotated_text.json` and `metadata.json`) through the same import flow.
- Convert legacy annotations, pinyin, glossary/lemma data, audio references, and image metadata into C-LARA-2 artifacts while preserving original legacy files under `legacy_clara/`.
- Imported project title is kept when unique for that user, otherwise suffixed (`(2)`, `(3)`, ...).
- Adelaide legacy corpus folder has been transferred to AWS; the operational runbook records the need for inbound SSH security-policy access and explicit EC2 `.pem` key use with `rsync`.

### 16. Conventional UX roadmap (project workspace IA)

Status: **New roadmap document added.** See [roadmap/conventional-ux.md](conventional-ux.md).

Focus:
- Keep the non-dialogue UX coherent as feature surface grows.
- Define canonical control placement across top-level/annotation/images/exercises pages.
- Reduce cognitive load through conditional controls and latest-first summaries.


### 17. Credits and billing roadmap

Status: **Phase A baseline delivered; roadmap active.** See [roadmap/credits-and-billing.md](credits-and-billing.md).

Focus:
- Per-user credit balances tied to AI/API usage cost.
- Hard balance gate for AI calls when funds are insufficient.
- Admin recharge, user-provided API keys, and optional user-to-user transfers.
- Future online top-up integration (e.g., PayPal/Stripe) once accounting baseline is stable.

Implemented now:
- Credit account + immutable ledger.
- OpenAI usage charges with token/cost records.
- Compile low-balance gate.
- Admin manual credit adjustments.
- Project-level cost total and request-type breakdown.


### 18. Right-to-left (RTL) language support roadmap

Status: **New roadmap document added.** See [roadmap/rtl-support.md](rtl-support.md).

Focus:
- Central language-direction declarations (start with Arabic and Persian).
- Propagate text direction metadata through annotation, storage, APIs, and compile artifacts.
- Ensure robust RTL behavior in conventional UX, manual annotation editor, and compiled HTML output.


### 19. Multi-word expression (MWE) strategy roadmap

Status: **New roadmap document added.** See [roadmap/mwe-strategy.md](mwe-strategy.md).

Focus:
- ID-scope policy and deterministic normalization across pages/stages.
- MWE integrity across mwe → lemma → gloss → compile HTML.
- Regression testing and diagnostics for inconsistent model output.


### 20. Picture dictionaries roadmap

Status: **New roadmap document added.** See [roadmap/picture-dictionaries.md](picture-dictionaries.md).

Focus:
- Community-owned shared picture dictionaries keyed by lexical identity (lemma/POS).
- Optional picture-gloss pipeline stage building on lemma output.
- Organiser-created sub-projects extracted from picture dictionaries using natural-language selection plus manual review.
- HTML interaction and exercise extensions using dictionary-backed image glosses, flashcards, word scrambles, and crosswords.

### 21. Issue tracking and human-suggestion loop roadmap

Status: **New roadmap document added.** See [roadmap/issue-tracking-and-human-suggestions.md](issue-tracking-and-human-suggestions.md).

Focus:
- Lightweight issue states (`reported`, `active`, `closed`) and explicit priorities.
- Repository-native, Codex-first issue JSON store (one file per issue + focus index + timestamped index archive).
- Deadline/dependency-aware issues with human-facing browser + simple user suggestion capture + admin export + Codex-mediated incorporation loop.

### 22. Reports and academic papers roadmap

Status: **New roadmap document added.** See [roadmap/reports-and-papers.md](reports-and-papers.md).

Focus:
- Concise first C-LARA-2 progress report by 2026-06-15, tracked by [ISSUE-0008](../issues/issues/ISSUE-0008.json).
- EuroCALL 2026 paper preparation, accepted with a confirmed 2026-07-31 deadline.
- ALTA 2026 target and related-work positioning around AI-centered, repo-native software/documentation/test co-development, plus a possible David Gunkel AI-authorship paper.

### 23. Efficiency and stage-artifact persistence roadmap

Status: **New roadmap document added.** See [roadmap/efficiency-and-stage-artifacts.md](efficiency-and-stage-artifacts.md).

Focus:
- Centralize pipeline stage artifact read/write operations behind a format-independent API.
- Preserve JSON compatibility while benchmarking faster internal formats for large imported projects.
- Explore trusted admin-only binary/pickle-like migration artifacts for the one-off Adelaide corpus, without weakening safety for normal user uploads or source-bundle interchange.
- Record artifact read/write timings and expose project/run-level diagnostics so performance decisions are evidence-based.

### 24. Mobile access roadmap

Status: **New roadmap document added.** See [roadmap/mobile-access.md](mobile-access.md).

Focus:
- Treat phones and tablets as first-class access devices for learner-facing flows.
- Start with browsing published/compiled texts, then extend to content browsing, exercises, and default-driven background content creation.
- Treat dense linguistic annotation editing as the difficult mobile case, while exploring lightweight triage/review angles.

### 25. Community judging autosave roadmap

Status: **Planning document added; implementation intentionally deferred until after June 1 Kok Kaper visit.** See [roadmap/community-judging-autosave.md](community-judging-autosave.md).

Focus:
- Prevent accidental loss of community member judgements on judge pages.
- Add autosave-on-change with clear saved-state feedback and fallback submit compatibility.
- Deliver in a low-risk rollout window after current field visit commitments.


### 26. Authenticated project-understanding assistant roadmap

Status: **Implemented first authenticated version; AWS/laptop Codex CLI setup documented.** See [roadmap/platform-self-knowledge-assistant.md](platform-self-knowledge-assistant.md). Tracked by [ISSUE-0034](../issues/issues/ISSUE-0034.json).

Focus:
- Authenticated-user question answering about C-LARA-2 architecture, goals, status, issue structure, plans, tests, prompts, and relevant public GitHub source files, exposed through the top-level Assistant navigation item.
- Repo-grounded answers that distinguish implemented vs planned functionality, cite supporting files, and admit unsupported or uncertain answers.
- Versioned `docs/project_understanding/`-style evidence records with model/prompt metadata and human assessment fields for the initial report's autonomy/authorship evidence case, plus deployment checks for `codex exec` on laptops and the AWS Gunicorn/Q-worker environment.




### 27. First progress report roadmap

Status: **Folded into the consolidated reports roadmap.** See [roadmap/reports-and-papers.md](reports-and-papers.md).

Focus:
- Markdown-first publication workspace for the first progress report (target 2026-06-15).
- Structured section outline with later LaTeX conversion path.
- Explicit links from publication drafting to issue/roadmap evidence.
