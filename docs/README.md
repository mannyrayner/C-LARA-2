# C-LARA-2 Docs

Welcome! This folder collects specifications, architecture notes, and delivery roadmaps for C-LARA-2.

## Quick links

- **How-to**: [Quickstart](howto/quickstart.md)
- **How-to**: [Run the Django platform locally](howto/run-django-platform.md)
- **How-to**: [Locate compile progress logs](howto/compile-logs.md)
- **ADRs**: [ADR-0001: Documentation & Structure](adr/0001-documentation-and-structure.md)

## Roadmaps and status

- **Top-level roadmap**: [roadmap/README.md](roadmap/README.md)
- **Segmentation pipeline (implemented)**: [roadmap/segmentation-pipeline.md](roadmap/segmentation-pipeline.md)
- **Linguistic pipeline (implemented; romanization generalized)**: [roadmap/linguistic-pipeline.md](roadmap/linguistic-pipeline.md)
- **Django platform (initial implementation delivered, expanding)**: [roadmap/django-platform.md](roadmap/django-platform.md)
- **Image generation pipeline (initial implementation delivered)**: [roadmap/image-generation-pipeline.md](roadmap/image-generation-pipeline.md)
- **Social-network functionality (new roadmap)**: [roadmap/social-network-functionality.md](roadmap/social-network-functionality.md)
- **Low-resource/AI-weak language support (new roadmap)**: [roadmap/low-resource-languages.md](roadmap/low-resource-languages.md)
- **Deployment and migration roadmap (new)**: [roadmap/deployment-and-migration.md](roadmap/deployment-and-migration.md)

## Current implementation snapshot

Implemented in the codebase today includes:

- End-to-end text pipeline with text generation, segmentation (phase 1/2), translation, MWE, lemma, gloss, romanization (`pypinyin`/`indic_transliteration`/AI fallback), audio generation/caching, and HTML compilation.
- Image workflow (style → recurring elements → page images) integrated with compile output so generated images can be included in final HTML.
- Django platform with account/project flows, compile monitor/status polling, publish/content browsing pages, and self-contained ZIP export (HTML + audio + images).

## Testing & CI

- Run tests from repo root: `make -C tests test`.
- CI (`.github/workflows/ci.yml`) runs automated checks and uploads artifacts.

_This file is the landing page for the docs folder and should stay aligned with `docs/roadmap/README.md`._
