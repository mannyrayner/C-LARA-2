# C-LARA-2 issue overview (refreshed 2026-06-01T03:15:00Z)

## Recent progress
- Advanced **[ISSUE-0034](issues/ISSUE-0034.json)** from a prompt-wrapper prototype to a working admin-only `codex exec` assistant with async Django Q execution, heartbeat/status polling, request/result persistence, and structured answer metadata.
- Added **[ISSUE-0035](issues/ISSUE-0035.json)** to track intermittent Codex PR update-branch refusals reported from 2026-05-30 onward, with a dedicated roadmap for future incident evidence.
- Refreshed ISSUE-0034 roadmap/issue metadata to record the implemented `codex exec` path and remaining export/review, rate-limit, citation-sanitization, and curated-evaluation work.

## Near-term priorities
1. **[ISSUE-0031](issues/ISSUE-0031.json) (P1, reported)** — Improve compiled-content presentation context and configurable public access controls.
2. **[ISSUE-0030](issues/ISSUE-0030.json) (P1, reported)** — Fix image-generation workflow UX around element expansion auto-refresh and selection confirmation.
3. **[ISSUE-0029](issues/ISSUE-0029.json) (P1, reported)** — Autosave community judging inputs to prevent accidental data loss.
4. **[ISSUE-0026](issues/ISSUE-0026.json) (P1, reported)** — Define next-step community-recorded audio workflow for non-TTS languages.
5. **[ISSUE-0003](issues/ISSUE-0003.json) (P1, reported)** — Add efficient end-to-end pipeline test runner for systematic quality checks.
6. **[ISSUE-0025](issues/ISSUE-0025.json) (P1, reported)** — Add systematic UI regression tracking for disappearing controls/content.
7. **[ISSUE-0010](issues/ISSUE-0010.json) (P1, active)** — Import a representative legacy C-LARA project corpus and add batch import tooling.
8. **[ISSUE-0013](issues/ISSUE-0013.json) (P1, reported)** — Improve stage artifact persistence performance and timeout resilience.
9. **[ISSUE-0008](issues/ISSUE-0008.json) (P1, reported)** — Write C-LARA-2 technical report and academic papers.
10. **[ISSUE-0033](issues/ISSUE-0033.json) (P2, reported)** — Clean up and phase-track roadmap file maintenance.
11. **[ISSUE-0034](issues/ISSUE-0034.json) (P2, active)** — Add restricted project-understanding assistant with versioned evidence records.
12. **[ISSUE-0035](issues/ISSUE-0035.json) (P2, reported)** — Track intermittent Codex PR update-branch refusal.
13. **[ISSUE-0006](issues/ISSUE-0006.json) (P2, reported)** — Investigate segmentation_phase_2 token-span failures and rerun-path correctness.
14. **[ISSUE-0005](issues/ISSUE-0005.json) (P2, reported)** — Tune segmentation_phase_1 prompting to improve segment granularity by genre.
15. **[ISSUE-0004](issues/ISSUE-0004.json) (P2, reported)** — Introduce AI-based review gates for phase outputs with extensible evaluator architecture.
16. **[ISSUE-0007](issues/ISSUE-0007.json) (P2, reported)** — Use LLM prompt-construction indirection for page-image generation prompts.
17. **[ISSUE-0001](issues/ISSUE-0001.json) (P2, reported)** — Support hosted compiled legacy content registration in C-LARA-2.

## Notes/risks
- ISSUE-0034 now has a restricted admin UI and background `codex exec` execution path, but still lacks an explicit export/review workflow into `docs/project_understanding/`, reviewer assessment controls, billing/rate-limit integration, and citation/path sanitization for any wider audience.
- The Codex update-branch inconsistency is currently an external-tool/workflow risk rather than a confirmed C-LARA-2 code defect; useful next action is evidence capture rather than speculative code changes.
- Regression prevention remains constrained until **ISSUE-0003** and **ISSUE-0025** land with broader automated UI/pipeline coverage.

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
