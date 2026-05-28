# C-LARA-2 issues overview
_Last updated: 2026-05-28T21:30:00Z_

## Recent progress
- Reopened **[ISSUE-0020](issues/ISSUE-0020.json)** as a **P0** follow-up after organiser testing showed the low-resource picture-dictionary add-word flow is still too cumbersome.
- Refocused **ISSUE-0020** around a low-resource organiser workflow: tabular word/lemma/POS/gloss entry, direct annotation/stage updates, and a clearer “Create new images” action with pending-image counts.
- Processed the duplicate **[ISSUE-0032](issues/ISSUE-0032.json)** fixed/closed confirmation with no state change, because the issue is already closed.
- Archived the previous focus index and regenerated this overview from canonical `docs/issues/issues/*.json` status values.

## Near-term priorities
1. **[ISSUE-0020](issues/ISSUE-0020.json) (P0, reported)** — Improve picture-dictionary compile flow for low-resource languages and organiser feedback.
2. **[ISSUE-0031](issues/ISSUE-0031.json) (P1, reported)** — Improve compiled-content presentation context and configurable public access controls.
3. **[ISSUE-0030](issues/ISSUE-0030.json) (P1, reported)** — Fix image-generation workflow UX around element expansion auto-refresh and selection confirmation.
4. **[ISSUE-0029](issues/ISSUE-0029.json) (P1, reported)** — Autosave community judging inputs to prevent accidental data loss.
5. **[ISSUE-0026](issues/ISSUE-0026.json) (P1, reported)** — Define next-step community-recorded audio workflow for non-TTS languages.
6. **[ISSUE-0003](issues/ISSUE-0003.json) (P1, reported)** — Add efficient end-to-end pipeline test runner for systematic quality checks.
7. **[ISSUE-0025](issues/ISSUE-0025.json) (P1, reported)** — Add systematic UI regression tracking for disappearing controls/content.
8. **[ISSUE-0010](issues/ISSUE-0010.json) (P1, active)** — Import a representative legacy C-LARA project corpus and add batch import tooling.
9. **[ISSUE-0013](issues/ISSUE-0013.json) (P1, reported)** — Improve stage artifact persistence performance and timeout resilience.
10. **[ISSUE-0008](issues/ISSUE-0008.json) (P1, reported)** — Write C-LARA-2 technical report and academic papers.
11. **[ISSUE-0006](issues/ISSUE-0006.json) (P2, reported)** — Investigate segmentation_phase_2 token-span failures and rerun-path correctness.
12. **[ISSUE-0005](issues/ISSUE-0005.json) (P2, reported)** — Tune segmentation_phase_1 prompting to improve segment granularity by genre.
13. **[ISSUE-0004](issues/ISSUE-0004.json) (P2, reported)** — Introduce AI-based review gates for phase outputs with extensible evaluator architecture.
14. **[ISSUE-0007](issues/ISSUE-0007.json) (P2, reported)** — Use LLM prompt-construction indirection for page-image generation prompts.
15. **[ISSUE-0001](issues/ISSUE-0001.json) (P2, reported)** — Support hosted compiled legacy content registration in C-LARA-2.

## Notes/risks
- **ISSUE-0020** is back at the top of the queue because the current low-resource path still forces organisers to move between the community organiser page and the page-oriented editor, which is confusing for routine dictionary expansion.
- The reopened scope should be implemented carefully so low-resource dictionary row metadata stays synchronized with generated stage artifacts and does not regress the AI-capable language flow.
- **ISSUE-0031** remains relevant for broader compiled-content and permission-boundary hardening after the targeted **ISSUE-0032** fix.

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
| [ISSUE-0011](issues/ISSUE-0011.json) | closed | P1 | Add image-based language games for community use. |
| [ISSUE-0012](issues/ISSUE-0012.json) | closed | P2 | Adjust project creation defaults for AI generation and page images. |
| [ISSUE-0013](issues/ISSUE-0013.json) | reported | P1 | Improve stage artifact persistence performance and timeout resilience. |
| [ISSUE-0014](issues/ISSUE-0014.json) | closed | P1 | Audit and adjust AWS service limits before broader rollout. |
| [ISSUE-0015](issues/ISSUE-0015.json) | closed | P1 | Let community organisers manage community membership. |
| [ISSUE-0016](issues/ISSUE-0016.json) | closed | P1 | Validate no-audio/skip-TTS fallback on Kok Kaper. |
| [ISSUE-0017](issues/ISSUE-0017.json) | closed | P1 | Improve page-image generation, review, and regeneration workflows. |
| [ISSUE-0018](issues/ISSUE-0018.json) | closed | P2 | Use main-branch issue registry data when processing human issue suggestions. |
| [ISSUE-0019](issues/ISSUE-0019.json) | closed | P3 | Ensure favicon reliably appears on AWS deployment. |
| [ISSUE-0020](issues/ISSUE-0020.json) | reported | P0 | Improve picture-dictionary compile flow for low-resource languages and organiser feedback. |
| [ISSUE-0021](issues/ISSUE-0021.json) | closed | P1 | Add GPT-Image-2 as selectable model for element and page image generation. |
| [ISSUE-0022](issues/ISSUE-0022.json) | closed | P1 | Handle large project ZIP imports without nginx 413 failures on AWS. |
| [ISSUE-0023](issues/ISSUE-0023.json) | closed | P3 | Allow manual segmentation phase 1 editor when segmentation artifact exists but source text is empty. |
| [ISSUE-0024](issues/ISSUE-0024.json) | closed | P3 | Stabilize and verify natural-language search controls on Published Content view. |
| [ISSUE-0025](issues/ISSUE-0025.json) | reported | P1 | Add systematic UI regression tracking for disappearing controls/content. |
| [ISSUE-0026](issues/ISSUE-0026.json) | reported | P1 | Define next-step community-recorded audio workflow for non-TTS languages. |
| [ISSUE-0027](issues/ISSUE-0027.json) | closed | P2 | Add user credit transfer and user-provided OpenAI API key billing option. |
| [ISSUE-0028](issues/ISSUE-0028.json) | closed | P1 | Ensure picture-dictionary image generation produces text-free images. |
| [ISSUE-0029](issues/ISSUE-0029.json) | reported | P1 | Autosave community judging inputs to prevent accidental data loss. |
| [ISSUE-0030](issues/ISSUE-0030.json) | reported | P1 | Fix image-generation workflow UX around element expansion auto-refresh and selection confirmation. |
| [ISSUE-0031](issues/ISSUE-0031.json) | reported | P1 | Improve compiled-content presentation context and configurable public access controls. |
| [ISSUE-0032](issues/ISSUE-0032.json) | closed | P0 | Fix community judging image visibility for non-owner community members. |
