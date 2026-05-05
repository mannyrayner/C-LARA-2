# C-LARA-2 Docs

Welcome! This folder collects specifications, architecture notes, and delivery roadmaps for C-LARA-2.

## Quick links

- **How-to**: [Quickstart](howto/quickstart.md)
- **How-to**: [Run the Django platform locally](howto/run-django-platform.md)
- **How-to**: [Locate compile progress logs](howto/compile-logs.md)
- **How-to**: [Credits and billing operations](howto/credits-and-billing.md)
- **How-to**: [Clone a project snapshot](howto/clone-project.md)
- **ADRs**: [ADR-0001: Documentation & Structure](adr/0001-documentation-and-structure.md)
- **Issues**: [Current issues overview](issues/)

## Roadmaps and status

- **Top-level roadmap**: [roadmap/README.md](roadmap/README.md)
- **Segmentation pipeline (implemented)**: [roadmap/segmentation-pipeline.md](roadmap/segmentation-pipeline.md)
- **Linguistic pipeline (implemented; romanization generalized)**: [roadmap/linguistic-pipeline.md](roadmap/linguistic-pipeline.md)
- **Django platform (initial implementation delivered, expanding)**: [roadmap/django-platform.md](roadmap/django-platform.md)
- **Image generation pipeline (initial implementation delivered)**: [roadmap/image-generation-pipeline.md](roadmap/image-generation-pipeline.md)
- **Social-network functionality (new roadmap)**: [roadmap/social-network-functionality.md](roadmap/social-network-functionality.md)
- **Low-resource/AI-weak language support (new roadmap)**: [roadmap/low-resource-languages.md](roadmap/low-resource-languages.md)
- **Deployment and migration roadmap (new)**: [roadmap/deployment-and-migration.md](roadmap/deployment-and-migration.md)
- **Exercises roadmap (initial cloze implementation delivered)**: [roadmap/exercises.md](roadmap/exercises.md)
- **Alignment roadmap (new)**: [roadmap/alignment.md](roadmap/alignment.md)
- **Manual annotation editor roadmap (new)**: [roadmap/manual-annotation-editor.md](roadmap/manual-annotation-editor.md)
- **Dialogue top-level roadmap (new)**: [roadmap/dialogue-top-level.md](roadmap/dialogue-top-level.md)
- **AI-judges evaluation roadmap (new)**: [roadmap/ai-judges-evaluation.md](roadmap/ai-judges-evaluation.md)
- **Source project export/import roadmap (initial implementation delivered)**: [roadmap/source-project-bundles.md](roadmap/source-project-bundles.md)
- **Conventional UX roadmap (new)**: [roadmap/conventional-ux.md](roadmap/conventional-ux.md)
- **Credits and billing roadmap (new)**: [roadmap/credits-and-billing.md](roadmap/credits-and-billing.md)
- **RTL support roadmap (new)**: [roadmap/rtl-support.md](roadmap/rtl-support.md)
- **MWE strategy roadmap (new)**: [roadmap/mwe-strategy.md](roadmap/mwe-strategy.md)

## Current implementation snapshot

Implemented in the codebase today includes:

- End-to-end text pipeline with text generation, segmentation (phase 1/2), translation, MWE, lemma, gloss, romanization (`pypinyin`/`indic_transliteration`/AI fallback), audio generation/caching, and HTML compilation.
- Image workflow (style → recurring elements → page images) integrated with compile output so generated images can be included in final HTML.
- Django platform with account/project flows, compile monitor/status polling, publish/content browsing pages, and self-contained ZIP export (HTML + audio + images).
- Project cloning workflow to create a new project snapshot with copied fields and latest run-file versions.
- Credits/billing Phase A baseline: per-user credit accounts + immutable ledger entries, low-balance compile gate, OpenAI usage charge rows with model/token accounting, admin credit adjustments, and project-level accumulated cost display.

## Immediate priorities (April 2026)

This summary mirrors `docs/roadmap/README.md`.

1. **Adelaide deployment** with C-LARA and C-LARA-2 running safely side-by-side.
2. **Structured manual annotation editor** so human reviewers can correct all stages without raw JSON editing.
3. **Billing hardening**: validate pricing sync workflow and reporting before production rollout.

## Testing & CI

- Run tests from repo root: `make -C tests test`.
- CI (`.github/workflows/ci.yml`) runs automated checks and uploads artifacts.

_This file is the landing page for the docs folder and should stay aligned with `docs/roadmap/README.md`._
