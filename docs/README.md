# C-LARA-2 Docs

Welcome! This folder collects the specs and notes that drive the current implementation work.

## Quick links

- **How-to**: [Quickstart](howto/quickstart.md)
- **Architecture Decision Records (ADRs)**: [ADR-0001: Documentation & Structure](adr/0001-documentation-and-structure.md)

## Roadmaps and current status

- **Segmentation pipeline (implemented)**: [roadmap/segmentation-pipeline.md](roadmap/segmentation-pipeline.md) – covers text generation, segmentation phases 1 and 2, and the generic annotation harness now used across the codebase.
- **Linguistic pipeline (in progress)**: [roadmap/linguistic-pipeline.md](roadmap/linguistic-pipeline.md) – details translation, lemma, gloss, MWE, pinyin, audio, and compilation steps; translation is currently implemented for EN→FR.
- **Top-level roadmap**: [roadmap/README.md](roadmap/README.md) – step-by-step milestones with notes on what is done versus planned.

## What’s implemented so far

- OpenAI client wrapper with heartbeat/telemetry and retry handling.
- Text generation (`text_gen`), segmentation phases 1 and 2, and translation using the generic annotation flow.
- Prompt templates and few-shots for the above operations, plus unit/integration tests (OpenAI-gated where appropriate).

## Testing & CI

- Run the suite from the repo root: `make -C tests test` (pytest + pytest-asyncio,
  logs to `tests/test_results.log`).
- GitHub Actions (`.github/workflows/ci.yml`) runs the same suite with coverage
  and uploads JUnit/coverage artifacts for each build.

_This file is the landing page for the docs folder._
