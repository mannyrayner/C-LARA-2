# C-LARA-2 issue overview (refreshed 2026-06-16T12:25:00Z)
## Recent progress
- Implemented the first cut of **ISSUE-0039**: the organiser page now has a unified picture-dictionary table for word, lemma, POS, gloss/translation, image-generation prompt, and selected image.
- Updated **ISSUE-0039** from `reported` to `active` because implementation has started, while leaving it open for prompt variants, batch image generation, dictionary context fields, and tighter subset/exercise integration.
- Updated the picture-dictionaries roadmap to clarify that Kok Kaper classroom use is not currently live, but the workflow should become viable for Sophie review before 2026-07-13.
- Regenerated this overview from canonical issue JSON so the complete inventory reflects all current `reported`, `active`, and `closed` states.

## Near-term priorities

1. **ISSUE-0039** — build a unified picture-dictionary source-of-truth workspace.
2. **ISSUE-0031** — improve compiled-content presentation context and configurable public access controls.
3. **ISSUE-0030** — fix image-generation workflow UX around element expansion auto-refresh and selection confirmation.
4. **ISSUE-0029** — autosave community judging inputs to prevent accidental data loss.
5. **ISSUE-0037** — create subset projects from community picture dictionaries.
6. **ISSUE-0026** — define next-step community-recorded audio workflow for non-TTS languages.
7. **ISSUE-0005** — tune segmentation_phase_1 prompting to improve segment granularity by genre.
8. **ISSUE-0003** — add efficient end-to-end pipeline test runner for systematic quality checks.
9. **ISSUE-0036** — systematize creation and evaluation of few-shot examples for linguistic annotation.
10. **ISSUE-0025** — add systematic UI regression tracking for disappearing controls/content.
11. **ISSUE-0010** — import a representative legacy C-LARA project corpus and add batch import tooling.
12. **ISSUE-0013** — improve stage artifact persistence performance and timeout resilience.
13. **ISSUE-0008** — write C-LARA-2 technical report and academic papers.
14. **ISSUE-0033** — clean up and phase-track roadmap file maintenance.
15. **ISSUE-0034** — add restricted project-understanding assistant with versioned evidence records.
16. **ISSUE-0035** — track intermittent Codex PR update-branch refusal.
17. **ISSUE-0006** — investigate segmentation_phase_2 token-span failures and rerun-path correctness.
18. **ISSUE-0004** — introduce AI-based review gates for phase outputs with extensible evaluator architecture.
19. **ISSUE-0001** — support hosted compiled legacy content registration in C-LARA-2.

## Notes/risks

- **ISSUE-0039** is intentionally broader than the first cut; laptop/Sophie testing should validate whether the unified table is the right organiser surface before adding heavier prompt-variant and batch-generation controls.
- **ISSUE-0037** remains active for the already implemented subdictionary/subset-project workflow and Sophie review, but its long-term data ownership should align with **ISSUE-0039**.
- **ISSUE-0038** is closed for the low-resource dictionary deletion path, but **ISSUE-0039** should preserve stable entry/image identity so future synchronization no longer depends on page-number-only assumptions.
- **ISSUE-0005** should be handled together with **ISSUE-0003**, **ISSUE-0004**, and **ISSUE-0036** so segmentation prompt changes are evaluated against repeatable examples rather than anecdotal improvements.
- Regression prevention remains constrained until **ISSUE-0003** and **ISSUE-0025** land with broader automated pipeline and UI coverage.

## Complete issue inventory

| Issue | Status | Priority | Summary |
|---|---|---|---|
| [ISSUE-0001](issues/ISSUE-0001.json) | reported | P2 | Support hosted compiled legacy content registration in C-LARA-2. |
| [ISSUE-0002](issues/ISSUE-0002.json) | closed | P1 | Support migration of legacy C-LARA projects into C-LARA-2. |
| [ISSUE-0003](issues/ISSUE-0003.json) | reported | P1 | Add efficient end-to-end pipeline test runner for systematic quality checks. |
| [ISSUE-0004](issues/ISSUE-0004.json) | reported | P2 | Introduce AI-based review gates for phase outputs with extensible evaluator architecture. |
| [ISSUE-0005](issues/ISSUE-0005.json) | reported | P1 | Tune segmentation_phase_1 prompting to improve segment granularity by genre. |
| [ISSUE-0006](issues/ISSUE-0006.json) | reported | P2 | Investigate segmentation_phase_2 token-span failures and rerun-path correctness. |
| [ISSUE-0007](issues/ISSUE-0007.json) | closed | P2 | Use LLM prompt-construction indirection for page-image generation prompts. |
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
| [ISSUE-0020](issues/ISSUE-0020.json) | closed | P0 | Improve picture-dictionary compile flow for low-resource languages and organiser feedback. |
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
| [ISSUE-0033](issues/ISSUE-0033.json) | reported | P2 | Clean up and phase-track roadmap file maintenance. |
| [ISSUE-0034](issues/ISSUE-0034.json) | active | P2 | Add restricted project-understanding assistant with versioned evidence records. |
| [ISSUE-0035](issues/ISSUE-0035.json) | reported | P2 | Track intermittent Codex PR update-branch refusal. |
| [ISSUE-0036](issues/ISSUE-0036.json) | reported | P1 | Systematize creation and evaluation of few-shot examples for linguistic annotation. |
| [ISSUE-0037](issues/ISSUE-0037.json) | active | P1 | Create subset projects from community picture dictionaries. |
| [ISSUE-0038](issues/ISSUE-0038.json) | closed | P1 | Keep picture-dictionary images synchronized when words are deleted. |
| [ISSUE-0039](issues/ISSUE-0039.json) | active | P0 | Build a unified picture-dictionary source-of-truth workspace. |
