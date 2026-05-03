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
- Next: structured migration tooling from C-LARA data to C-LARA-2 data model.
- Next: host portability and backup export/import workflows (likely AWS Sydney target).

Key constraint: the urgent Adelaide deployment approach must remain upward-compatible with migration and relocation work.

### 9. Exercise generation roadmap

Status: **Initial cloze implementation delivered.** See [roadmap/exercises.md](exercises.md).

Focus:
- Cloze and flashcard generation from existing project artifacts.
- Distractor generation/validation and review workflows.
- Learner-facing exercise player and future spaced repetition support.

Implemented now:
- Generate cloze exercise sets from latest run segments.
- Theme options include vocabulary, grammar, morphology, and grammar/morphology.
- Publish/unpublish exercise sets and expose published links on content pages.

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

Status: **New roadmap document added.** See [roadmap/ai-judges-evaluation.md](ai-judges-evaluation.md).

Focus:
- Panel-based AI scoring for outputs from key processing stages.
- Aggregation, disagreement analysis, and optional foreman summarization.
- Human-audit calibration to keep AI evaluation useful and methodologically grounded.


### 14. Source project export/import bundles roadmap

Status: **Initial implementation delivered.** See [roadmap/source-project-bundles.md](source-project-bundles.md).

Focus:
- ZIP export/import of editable source artifacts from latest (or selected) runs.
- Full preservation of text annotations and image-pipeline metadata/provenance.
- Server↔laptop portability for debugging, handover, backup, and migration workflows.

Implemented now:
- Export source bundle from project detail.
- Import source bundle from project list, always creating a new project.
- Imported project title is kept when unique for that user, otherwise suffixed (`(2)`, `(3)`, ...).

### 15. Conventional UX roadmap (project workspace IA)

Status: **New roadmap document added.** See [roadmap/conventional-ux.md](conventional-ux.md).

Focus:
- Keep the non-dialogue UX coherent as feature surface grows.
- Define canonical control placement across top-level/annotation/images/exercises pages.
- Reduce cognitive load through conditional controls and latest-first summaries.


### 16. Credits and billing roadmap

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


### 17. Right-to-left (RTL) language support roadmap

Status: **New roadmap document added.** See [roadmap/rtl-support.md](rtl-support.md).

Focus:
- Central language-direction declarations (start with Arabic and Persian).
- Propagate text direction metadata through annotation, storage, APIs, and compile artifacts.
- Ensure robust RTL behavior in conventional UX, manual annotation editor, and compiled HTML output.


### 18. Multi-word expression (MWE) strategy roadmap

Status: **New roadmap document added.** See [roadmap/mwe-strategy.md](mwe-strategy.md).

Focus:
- ID-scope policy and deterministic normalization across pages/stages.
- MWE integrity across mwe → lemma → gloss → compile HTML.
- Regression testing and diagnostics for inconsistent model output.


### 19. Picture dictionaries roadmap

Status: **New roadmap document added.** See [roadmap/picture-dictionaries.md](picture-dictionaries.md).

Focus:
- Community-owned shared picture dictionaries keyed by lexical identity (lemma/POS).
- Optional picture-gloss pipeline stage building on lemma output.
- HTML interaction and exercise extensions using dictionary-backed image glosses.

### 20. Issue tracking and human-suggestion loop roadmap

Status: **New roadmap document added.** See [roadmap/issue-tracking-and-human-suggestions.md](issue-tracking-and-human-suggestions.md).

Focus:
- Lightweight issue states (`reported`, `active`, `closed`) and explicit priorities.
- Repository-native, Codex-first issue JSON store (one file per issue + focus index + timestamped index archive).
- Deadline/dependency-aware issues with human-facing browser + simple user suggestion capture + admin export + Codex-mediated incorporation loop.

