# C-LARA-2 issues overview

_Last updated: 2026-05-23T14:00:00Z_

This is the canonical human-facing issue registry. Canonical machine-readable records remain in `docs/issues/issues/*.json` and focus ordering in `docs/issues/index.json`.

## Recent progress

- Closed **[ISSUE-0024](issues/ISSUE-0024.json)** after verification that Published Content natural-language search controls are stable.
- Closed **[ISSUE-0021](issues/ISSUE-0021.json)** after maintainer confirmation that GPT-Image-2 model selection support is complete.
- Closed **[ISSUE-0019](issues/ISSUE-0019.json)** after maintainer confirmation that favicon behavior on AWS is now working well.
- Closed **[ISSUE-0020](issues/ISSUE-0020.json)** after maintainer confirmation that low-resource picture-dictionary compile-flow improvements are complete.
- Closed **[ISSUE-0023](issues/ISSUE-0023.json)** for manual segmentation phase-1 editor fallback when segmentation artifacts exist but source text is empty.
- Closed **[ISSUE-0022](issues/ISSUE-0022.json)** by addressing AWS large ZIP import failures (`nginx 413`).
- Closed **[ISSUE-0014](issues/ISSUE-0014.json)** and **[ISSUE-0017](issues/ISSUE-0017.json)** as completed roadmap slices.
- Added **[ISSUE-0025](issues/ISSUE-0025.json)** to track systematic UI regression detection after repeated reports of disappearing controls/content in platform views.
- Closed **[ISSUE-0016](issues/ISSUE-0016.json)** after reducing scope to Kok Kaper no-audio/skip-TTS fallback validation and confirming completion.
- Added **[ISSUE-0026](issues/ISSUE-0026.json)** to track definition of the next-step community-recorded audio workflow for non-TTS languages.

## Near-term priorities

1. **[ISSUE-0026](issues/ISSUE-0026.json) (P1, reported)** — Define next-step community-recorded audio workflow for non-TTS languages.
2. **[ISSUE-0011](issues/ISSUE-0011.json) (P1, active, deadline 2026-06-01)** — Continue image-based game hardening (curation signals, game-readiness, and feedback loops).
3. **[ISSUE-0010](issues/ISSUE-0010.json) (P1, active)** — Expand representative legacy corpus imports and batch-tooling readiness.
4. **[ISSUE-0003](issues/ISSUE-0003.json) (P1, reported)** — Build efficient end-to-end pipeline test runner and quality diagnostics.
5. **[ISSUE-0008](issues/ISSUE-0008.json) (P1, reported, deadline 2026-06-15)** — Produce technical report and publication outputs.
6. **[ISSUE-0025](issues/ISSUE-0025.json) (P1, reported)** — Add template/view UI inventory snapshots and change-alert workflow to catch unintended UI regressions quickly.

## Notes and risks

- **Low-resource delivery remains cross-cutting** across audio workflow design (ISSUE-0026), image games (ISSUE-0011), and dictionary compile flow (ISSUE-0020).
- **Validation and regression infrastructure is still a dependency** for safer iteration speed (ISSUE-0003).
- **UI regressions need first-class monitoring** so disappearing controls/content are detected immediately (ISSUE-0025).
- **Closed-issue hygiene must stay strict**: overview status values should always reflect per-issue JSON state.

## Complete issue inventory

| Issue | Status | Priority | Summary |
|---|---|---|---|
| [ISSUE-0001](issues/ISSUE-0001.json) | reported | P2 | Support hosted compiled legacy content registration in C-LARA-2. |
| [ISSUE-0002](issues/ISSUE-0002.json) | closed | P1 | Support migration of legacy C-LARA projects into C-LARA-2. |
| [ISSUE-0003](issues/ISSUE-0003.json) | reported | P1 | Add efficient end-to-end pipeline test runner for systematic quality checks. |
| [ISSUE-0004](issues/ISSUE-0004.json) | reported | P2 | Introduce AI-based review gates for phase outputs with extensible evaluator architecture. |
| [ISSUE-0005](issues/ISSUE-0005.json) | reported | P2 | Tune segmentation_phase_1 prompting to improve segment granularity by genre. |
| [ISSUE-0006](issues/ISSUE-0006.json) | reported | P2 | Investigate segmentation_phase_2 token-span failures and rerun-path correctness. |
| [ISSUE-0007](issues/ISSUE-0007.json) | reported | P2 | Use LLM prompt-construction indirection for page-image generation prompts. |
| [ISSUE-0008](issues/ISSUE-0008.json) | reported | P1 | Write C-LARA-2 technical report and academic papers. |
| [ISSUE-0009](issues/ISSUE-0009.json) | closed | P1 | Auto-regenerate and validate source project bundle stage artifacts before export/import. |
| [ISSUE-0010](issues/ISSUE-0010.json) | active | P1 | Import a representative legacy C-LARA project corpus and add batch import tooling. |
| [ISSUE-0011](issues/ISSUE-0011.json) | active | P1 | Add image-based language games for community use. |
| [ISSUE-0012](issues/ISSUE-0012.json) | reported | P2 | Adjust project creation defaults for AI generation and page images. |
| [ISSUE-0013](issues/ISSUE-0013.json) | reported | P1 | Improve stage artifact persistence performance and timeout resilience. |
| [ISSUE-0014](issues/ISSUE-0014.json) | closed | P1 | Audit and adjust AWS service limits before broader rollout. |
| [ISSUE-0015](issues/ISSUE-0015.json) | closed | P1 | Let community organisers manage community membership. |
| [ISSUE-0016](issues/ISSUE-0016.json) | closed | P1 | Validate no-audio/skip-TTS fallback on Kok Kaper. |
| [ISSUE-0017](issues/ISSUE-0017.json) | closed | P1 | Improve page-image generation, review, and regeneration workflows. |
| [ISSUE-0018](issues/ISSUE-0018.json) | closed | P2 | Use main-branch issue registry data when processing human issue suggestions. |
| [ISSUE-0019](issues/ISSUE-0019.json) | closed | P3 | Ensure favicon reliably appears on AWS deployment. |
| [ISSUE-0020](issues/ISSUE-0020.json) | closed | P1 | Improve picture-dictionary compile flow for low-resource languages and organiser feedback. |
| [ISSUE-0021](issues/ISSUE-0021.json) | closed | P1 | Add GPT-Image-2 as selectable model for element and page image generation. |
| [ISSUE-0022](issues/ISSUE-0022.json) | closed | P1 | Handle large project ZIP imports without nginx 413 failures on AWS. |
| [ISSUE-0023](issues/ISSUE-0023.json) | closed | P3 | Allow manual segmentation phase 1 editor when segmentation artifact exists but source text is empty. |
| [ISSUE-0024](issues/ISSUE-0024.json) | closed | P3 | Stabilize and verify natural-language search controls on Published Content view. |
| [ISSUE-0025](issues/ISSUE-0025.json) | reported | P1 | Add systematic UI regression tracking for disappearing controls/content. |
| [ISSUE-0026](issues/ISSUE-0026.json) | reported | P1 | Define next-step community-recorded audio workflow for non-TTS languages. |
