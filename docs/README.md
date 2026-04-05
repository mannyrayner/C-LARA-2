# C-LARA-2 Docs

Welcome! This folder collects the specs and notes that drive the current implementation work.

## Quick links

- **How-to**: [Quickstart](howto/quickstart.md)
- **How-to**: [Run the Django platform locally](howto/run-django-platform.md)
- **Architecture Decision Records (ADRs)**: [ADR-0001: Documentation & Structure](adr/0001-documentation-and-structure.md)

## Roadmaps and current status

Grouped roughly by delivery maturity, with more complete items first.

### Implemented / largely implemented

- **Segmentation pipeline (implemented)**: [roadmap/segmentation-pipeline.md](roadmap/segmentation-pipeline.md)
- **Linguistic pipeline (implemented; romanization generalized)**: [roadmap/linguistic-pipeline.md](roadmap/linguistic-pipeline.md)

### Initial implementation delivered (active expansion)

- **Django platform (initial implementation delivered, expanding)**: [roadmap/django-platform.md](roadmap/django-platform.md)
- **Image generation pipeline (initial implementation delivered)**: [roadmap/image-generation-pipeline.md](roadmap/image-generation-pipeline.md)
- **Social-network functionality (initial implementation delivered)**: [roadmap/social-network-functionality.md](roadmap/social-network-functionality.md)
- **Exercises roadmap (initial implementation delivered)**: [roadmap/exercises.md](roadmap/exercises.md)
- **Source project export/import roadmap (initial implementation delivered)**: [roadmap/source-project-bundles.md](roadmap/source-project-bundles.md)
- **Conventional UX roadmap (initial implementation delivered)**: [roadmap/conventional-ux.md](roadmap/conventional-ux.md)
- **MWE strategy roadmap (initial implementation delivered)**: [roadmap/mwe-strategy.md](roadmap/mwe-strategy.md)

### Priority roadmap items (immediate attention)

- **Deployment and migration roadmap (priority)**: [roadmap/deployment-and-migration.md](roadmap/deployment-and-migration.md)
- **Manual annotation editor roadmap (priority)**: [roadmap/manual-annotation-editor.md](roadmap/manual-annotation-editor.md)
- **Credits and billing roadmap (priority)**: [roadmap/credits-and-billing.md](roadmap/credits-and-billing.md)

### Newer/planned roadmap tracks

- **Low-resource/AI-weak language support**: [roadmap/low-resource-languages.md](roadmap/low-resource-languages.md)
- **Alignment roadmap**: [roadmap/alignment.md](roadmap/alignment.md)
- **Dialogue top-level roadmap**: [roadmap/dialogue-top-level.md](roadmap/dialogue-top-level.md)
- **AI-judges evaluation roadmap**: [roadmap/ai-judges-evaluation.md](roadmap/ai-judges-evaluation.md)
- **RTL support roadmap**: [roadmap/rtl-support.md](roadmap/rtl-support.md)

### Process/meta roadmap docs

- **Top-level roadmap index**: [roadmap/README.md](roadmap/README.md)
- **Backtracking-from-errors incident log**: [roadmap/backtracking-from-errors.md](roadmap/backtracking-from-errors.md)

## What’s implemented so far

- OpenAI client wrapper with heartbeat/telemetry and retry handling.
- Text generation (`text_gen`), segmentation phases 1 and 2 (Mandarin via `jieba`), translation, MWE detection, lemma tagging, glossing, Chinese pinyin annotation (`pypinyin`), audio annotation (TTS stub/OpenAI + caching), HTML compilation to a two-pane reader with concordance/audio hooks, and a `run_full_pipeline` helper that stitches the operations end-to-end.
- Prompt templates and few-shots for AI-backed operations, plus unit/integration tests (OpenAI-gated where appropriate).

## Testing & CI

- Run the suite from the repo root: `make -C tests test` (pytest + pytest-asyncio,
  logs to `tests/test_results.log`).
- GitHub Actions (`.github/workflows/ci.yml`) runs the same suite with coverage
  and uploads JUnit/coverage artifacts for each build.

_This file is the landing page for the docs folder._
