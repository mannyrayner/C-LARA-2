# C-LARA-2 issue overview (refreshed 2026-07-08T03:55:00Z)
## Recent progress
- Removed the explicit `temperature=0` override from AI-assisted MWE prompt revision calls so `gpt-5.5` can use its supported default temperature.
- Set the AI-assisted MWE prompt-revision default model to `gpt-5.5`, while keeping `MWE_REVISION_MODEL` overridable for cheaper smoke tests.
- Added an AI-assisted MWE prompt-revision target for **ISSUE-0036** so cycle reports can produce auditable next-cycle prompt drafts while preserving anti-overfitting guardrails.
- Wired current-prompt MWE runs to the explicit selected-project gold JSONL by default, preserving declared `gold_mwes` in sanity-check outputs.
- Added explicit MWE gold declaration/check targets and high-level cycle/result targets to **ISSUE-0036**, so selected-project gold records are exported and verified before prompt cycles run.
- Added first cycle-specific prompt machinery to **ISSUE-0036** so MWE experiments can prepare, run, score, and propose improvements for generated prompt templates without editing production prompts.
- Added explicit `PROJECT_IDS` filtering to **ISSUE-0036** MWE run/score/proposal targets so the seven-project hand-curated subset does not accidentally include broader development-set records or examples.
- Added visible per-record progress and incremental `progress.jsonl`/`outputs.jsonl` writes to the **ISSUE-0036** MWE current-prompt run command so long API runs no longer look idle.
- Kept the snapshot and MWE prompt-scoring workflow active for maintainer testing on the seven-project English development set.
- Revalidated the overview inventory against canonical per-issue JSON after updating **ISSUE-0036**.

## Near-term priorities
1. **ISSUE-0039** — Build a unified picture-dictionary source-of-truth workspace.
2. **ISSUE-0031** — Improve compiled-content presentation context and configurable public access controls.
3. **ISSUE-0030** — Fix image-generation workflow UX around element expansion auto-refresh and selection confirmation.
4. **ISSUE-0029** — Autosave community judging inputs to prevent accidental data loss.
5. **ISSUE-0037** — Create subset projects from community picture dictionaries.
6. **ISSUE-0026** — Define next-step community-recorded audio workflow for non-TTS languages.
7. **ISSUE-0005** — Tune segmentation_phase_1 prompting to improve segment granularity by genre.
8. **ISSUE-0003** — Add efficient end-to-end pipeline test runner for systematic quality checks.
9. **ISSUE-0036** — Systematize creation and evaluation of few-shot examples for linguistic annotation.
10. **ISSUE-0041** — Add named project snapshots with restore and gold-standard metadata.
11. **ISSUE-0013** — Improve stage artifact persistence performance and timeout resilience.
12. **ISSUE-0025** — Add systematic UI regression tracking for disappearing controls/content.
13. **ISSUE-0010** — Import a representative legacy C-LARA project corpus and add batch import tooling.
14. **ISSUE-0008** — Write C-LARA-2 technical report and academic papers.
15. **ISSUE-0033** — Clean up and phase-track roadmap file maintenance.
16. **ISSUE-0034** — Add restricted project-understanding assistant with versioned evidence records.
17. **ISSUE-0035** — Track intermittent Codex PR update-branch refusal.
18. **ISSUE-0006** — Investigate segmentation_phase_2 token-span failures and rerun-path correctness.
19. **ISSUE-0004** — Introduce AI-based review gates for phase outputs with extensible evaluator architecture.
20. **ISSUE-0001** — Support hosted compiled legacy content registration in C-LARA-2.

## Notes/risks
- **ISSUE-0036** now has an MWE prompt-scoring scaffold with incremental run tracking, proposal trace counts, explicit subset filtering, and explicit gold export/checks, high-level cycle summaries, and generated prompt-cycle scaffolding, but it intentionally writes candidate guidance rather than auto-editing production prompts; human review should guard against overfitting to development projects and should pass `PROJECT_IDS` when evaluating hand-curated subsets.
- **ISSUE-0041** snapshot save/restore now prunes nested snapshots before recursion and handles deep artifact directory/file copies more robustly on Windows/Cygwin, but destructive restore still needs careful UX/audit hardening before adding partial component restores.
- **ISSUE-0039** remains active/P0 for Sophie-facing picture-dictionary workflow completion; avoid letting infrastructure tasks displace the current UI/product review blockers.
- Regression prevention remains constrained until **ISSUE-0003** and **ISSUE-0025** land with broader automated pipeline and UI coverage.

## Complete issue inventory
| Issue | Status | Priority | Summary |
|---|---|---|---|
| [ISSUE-0001](issues/ISSUE-0001.md) | reported | P2 | Support hosted compiled legacy content registration in C-LARA-2. |
| [ISSUE-0002](issues/ISSUE-0002.md) | closed | P1 | Support migration of legacy C-LARA projects into C-LARA-2. |
| [ISSUE-0003](issues/ISSUE-0003.md) | reported | P1 | Add efficient end-to-end pipeline test runner for systematic quality checks. |
| [ISSUE-0004](issues/ISSUE-0004.md) | reported | P2 | Introduce AI-based review gates for phase outputs with extensible evaluator architecture. |
| [ISSUE-0005](issues/ISSUE-0005.md) | reported | P1 | Tune segmentation_phase_1 prompting to improve segment granularity by genre. |
| [ISSUE-0006](issues/ISSUE-0006.md) | reported | P2 | Investigate segmentation_phase_2 token-span failures and rerun-path correctness. |
| [ISSUE-0007](issues/ISSUE-0007.md) | closed | P2 | Use LLM prompt-construction indirection for page-image generation prompts. |
| [ISSUE-0008](issues/ISSUE-0008.md) | reported | P1 | Write C-LARA-2 technical report and academic papers. |
| [ISSUE-0009](issues/ISSUE-0009.md) | closed | P1 | Auto-regenerate and validate source project bundle stage artifacts before export/import. |
| [ISSUE-0010](issues/ISSUE-0010.md) | active | P1 | Import a representative legacy C-LARA project corpus and add batch import tooling. |
| [ISSUE-0011](issues/ISSUE-0011.md) | closed | P1 | Add image-based language games for community use. |
| [ISSUE-0012](issues/ISSUE-0012.md) | closed | P2 | Adjust project creation defaults for AI generation and page images. |
| [ISSUE-0013](issues/ISSUE-0013.md) | reported | P1 | Improve stage artifact persistence performance and timeout resilience. |
| [ISSUE-0014](issues/ISSUE-0014.md) | closed | P1 | Audit and adjust AWS service limits before broader rollout. |
| [ISSUE-0015](issues/ISSUE-0015.md) | closed | P1 | Let community organisers manage community membership. |
| [ISSUE-0016](issues/ISSUE-0016.md) | closed | P1 | Validate no-audio/skip-TTS fallback on Kok Kaper. |
| [ISSUE-0017](issues/ISSUE-0017.md) | closed | P1 | Improve page-image generation, review, and regeneration workflows. |
| [ISSUE-0018](issues/ISSUE-0018.md) | closed | P2 | Use main-branch issue registry data when processing human issue suggestions. |
| [ISSUE-0019](issues/ISSUE-0019.md) | closed | P3 | Ensure favicon reliably appears on AWS deployment. |
| [ISSUE-0020](issues/ISSUE-0020.md) | closed | P0 | Improve picture-dictionary compile flow for low-resource languages and organiser feedback. |
| [ISSUE-0021](issues/ISSUE-0021.md) | closed | P1 | Add GPT-Image-2 as selectable model for element and page image generation. |
| [ISSUE-0022](issues/ISSUE-0022.md) | closed | P1 | Handle large project ZIP imports without nginx 413 failures on AWS. |
| [ISSUE-0023](issues/ISSUE-0023.md) | closed | P3 | Allow manual segmentation phase 1 editor when segmentation artifact exists but source text is empty. |
| [ISSUE-0024](issues/ISSUE-0024.md) | closed | P3 | Stabilize and verify natural-language search controls on Published Content view. |
| [ISSUE-0025](issues/ISSUE-0025.md) | reported | P1 | Add systematic UI regression tracking for disappearing controls/content. |
| [ISSUE-0026](issues/ISSUE-0026.md) | reported | P1 | Define next-step community-recorded audio workflow for non-TTS languages. |
| [ISSUE-0027](issues/ISSUE-0027.md) | closed | P2 | Add user credit transfer and user-provided OpenAI API key billing option. |
| [ISSUE-0028](issues/ISSUE-0028.md) | closed | P1 | Ensure picture-dictionary image generation produces text-free images. |
| [ISSUE-0029](issues/ISSUE-0029.md) | reported | P1 | Autosave community judging inputs to prevent accidental data loss. |
| [ISSUE-0030](issues/ISSUE-0030.md) | reported | P1 | Fix image-generation workflow UX around element expansion auto-refresh and selection confirmation. |
| [ISSUE-0031](issues/ISSUE-0031.md) | reported | P1 | Improve compiled-content presentation context and configurable public access controls. |
| [ISSUE-0032](issues/ISSUE-0032.md) | closed | P0 | Fix community judging image visibility for non-owner community members. |
| [ISSUE-0033](issues/ISSUE-0033.md) | reported | P2 | Clean up and phase-track roadmap file maintenance. |
| [ISSUE-0034](issues/ISSUE-0034.md) | active | P1 | Add restricted project-understanding assistant with versioned evidence records. |
| [ISSUE-0035](issues/ISSUE-0035.md) | reported | P2 | Track intermittent Codex PR update-branch refusal. |
| [ISSUE-0036](issues/ISSUE-0036.md) | active | P1 | Systematize creation and evaluation of few-shot examples for linguistic annotation. |
| [ISSUE-0037](issues/ISSUE-0037.md) | active | P1 | Create subset projects from community picture dictionaries. |
| [ISSUE-0038](issues/ISSUE-0038.md) | closed | P1 | Keep picture-dictionary images synchronized when words are deleted. |
| [ISSUE-0039](issues/ISSUE-0039.md) | active | P0 | Build a unified picture-dictionary source-of-truth workspace. |
| [ISSUE-0040](issues/ISSUE-0040.md) | closed | P1 | Make page-oriented manual annotation saves resilient for large projects. |
| [ISSUE-0041](issues/ISSUE-0041.md) | active | P1 | Add named project snapshots with restore and gold-standard metadata. |
