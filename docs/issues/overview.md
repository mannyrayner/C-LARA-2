# Issues Overview (updated 2026-08-13T00:00:00Z)

## Recent progress

_Focus: Applied Manny’s full outstanding-issue review, closed stale completed work, revived important low-hanging tasks, and exposed the 24 August Indigenous-community and early-October ComputEL-10 path._

- Closed **ISSUE-0006** as previously resolved and **ISSUE-0034** as complete for now; reconfirmed closed **ISSUE-0040**.
- Reframed **ISSUE-0003** around documenting and maintaining the existing regularly used pipeline runner.
- Revived **ISSUE-0005**, **ISSUE-0025**, **ISSUE-0029**, **ISSUE-0030**, and **ISSUE-0031** as concrete low-hanging quality/usability work.
- Raised **ISSUE-0026** and **ISSUE-0029** for the 24 August community visit and planned ComputEL-10 work.
- Kept **ISSUE-0037** and **ISSUE-0039** open only for pre-visit verification because they appear resolved.
- Recorded the 12 August Codex update-branch recurrence and restart/new-task workaround under **ISSUE-0035**.
- Activated **ISSUE-0044** for an urgent Francis Bond discussion and retained mid-September for **ISSUE-0045**.

## Near-term priorities

1. **ISSUE-0042** — Prepare C-LARA global-workspace experiments for the Digital Minds Research Sprint.
2. **ISSUE-0043** — Resolve the EuroCALL 2026 AI-authorship dispute for two submitted papers.
3. **ISSUE-0026** — Define next-step community-recorded audio workflow for non-TTS languages.
4. **ISSUE-0044** — Choose the next annotation and AI-authorship publication targets.
5. **ISSUE-0029** — Autosave community judging inputs to prevent accidental data loss.
6. **ISSUE-0010** — Import a representative legacy C-LARA project corpus and add batch import tooling.
7. **ISSUE-0001** — Support hosted compiled legacy content registration in C-LARA-2.
8. **ISSUE-0005** — Tune segmentation_phase_1 prompting to improve segment granularity by genre.
9. **ISSUE-0025** — Add systematic UI regression tracking for disappearing controls/content.
10. **ISSUE-0030** — Fix image-generation workflow UX around element expansion auto-refresh and selection confirmation.
11. **ISSUE-0031** — Improve compiled-content presentation context and configurable public access controls.
12. **ISSUE-0037** — Create subset projects from community picture dictionaries.
13. **ISSUE-0039** — Build a unified picture-dictionary source-of-truth workspace.
14. **ISSUE-0036** — Systematize creation and evaluation of few-shot examples for linguistic annotation.
15. **ISSUE-0045** — Deliver a lightweight mobile content-and-exercises experience.
16. **ISSUE-0003** — Document and maintain the existing end-to-end pipeline test runner.
17. **ISSUE-0033** — Clean up and phase-track roadmap file maintenance.
18. **ISSUE-0035** — Track intermittent Codex PR update-branch refusal.
19. **ISSUE-0013** — Improve stage artifact persistence performance and timeout resilience.
20. **ISSUE-0004** — Introduce AI-based review gates for phase outputs with extensible evaluator architecture.

## Notes/risks

- **ISSUE-0042** is critical and in progress immediately before the Sprint.
- **ISSUE-0043** may receive a response on 13 August when the responsible EuroCALL contact returns.
- **ISSUE-0026** is the most substantial pre-24-August user need; **ISSUE-0029** is probably easier and should not be displaced unnecessarily.
- **ISSUE-0010** and **ISSUE-0001** remain near-complete low-hanging legacy work; use the completion attempt to determine whether **ISSUE-0013** is still real.
- **ISSUE-0037** and **ISSUE-0039** should close promptly if focused pre-visit verification passes.
- **ISSUE-0035** remains unexplained despite a useful restart/new-task recovery procedure.
- **ISSUE-0004** has no active path and is intentionally P3.

## Complete issue inventory

| Issue | Status | Priority | Summary |
|---|---|---|---|
| [ISSUE-0001](issues/ISSUE-0001.md) | active | P1 | Support hosted compiled legacy content registration in C-LARA-2. |
| [ISSUE-0002](issues/ISSUE-0002.md) | closed | P1 | Support migration of legacy C-LARA projects into C-LARA-2. |
| [ISSUE-0003](issues/ISSUE-0003.md) | active | P1 | Document and maintain the existing end-to-end pipeline test runner. |
| [ISSUE-0004](issues/ISSUE-0004.md) | reported | P3 | Introduce AI-based review gates for phase outputs with extensible evaluator architecture. |
| [ISSUE-0005](issues/ISSUE-0005.md) | active | P1 | Tune segmentation_phase_1 prompting to improve segment granularity by genre. |
| [ISSUE-0006](issues/ISSUE-0006.md) | closed | P2 | Investigate segmentation_phase_2 token-span failures and rerun-path correctness. |
| [ISSUE-0007](issues/ISSUE-0007.md) | closed | P2 | Use LLM prompt-construction indirection for page-image generation prompts. |
| [ISSUE-0008](issues/ISSUE-0008.md) | closed | P1 | Publish the first C-LARA-2 progress report. |
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
| [ISSUE-0025](issues/ISSUE-0025.md) | active | P1 | Add systematic UI regression tracking for disappearing controls/content. |
| [ISSUE-0026](issues/ISSUE-0026.md) | active | P0 | Define next-step community-recorded audio workflow for non-TTS languages. |
| [ISSUE-0027](issues/ISSUE-0027.md) | closed | P2 | Add user credit transfer and user-provided OpenAI API key billing option. |
| [ISSUE-0028](issues/ISSUE-0028.md) | closed | P1 | Ensure picture-dictionary image generation produces text-free images. |
| [ISSUE-0029](issues/ISSUE-0029.md) | active | P0 | Autosave community judging inputs to prevent accidental data loss. |
| [ISSUE-0030](issues/ISSUE-0030.md) | active | P1 | Fix image-generation workflow UX around element expansion auto-refresh and selection confirmation. |
| [ISSUE-0031](issues/ISSUE-0031.md) | active | P1 | Improve compiled-content presentation context and configurable public access controls. |
| [ISSUE-0032](issues/ISSUE-0032.md) | closed | P0 | Fix community judging image visibility for non-owner community members. |
| [ISSUE-0033](issues/ISSUE-0033.md) | active | P1 | Clean up and phase-track roadmap file maintenance. |
| [ISSUE-0034](issues/ISSUE-0034.md) | closed | P1 | Add restricted project-understanding assistant with versioned evidence records. |
| [ISSUE-0035](issues/ISSUE-0035.md) | active | P1 | Track intermittent Codex PR update-branch refusal. |
| [ISSUE-0036](issues/ISSUE-0036.md) | active | P1 | Systematize creation and evaluation of few-shot examples for linguistic annotation. |
| [ISSUE-0037](issues/ISSUE-0037.md) | active | P1 | Create subset projects from community picture dictionaries. |
| [ISSUE-0038](issues/ISSUE-0038.md) | closed | P1 | Keep picture-dictionary images synchronized when words are deleted. |
| [ISSUE-0039](issues/ISSUE-0039.md) | active | P1 | Build a unified picture-dictionary source-of-truth workspace. |
| [ISSUE-0040](issues/ISSUE-0040.md) | closed | P1 | Make page-oriented manual annotation saves resilient for large projects. |
| [ISSUE-0041](issues/ISSUE-0041.md) | active | P1 | Add named project snapshots with restore and gold-standard metadata. |
| [ISSUE-0042](issues/ISSUE-0042.md) | active | P0 | Prepare C-LARA global-workspace experiments for the Digital Minds Research Sprint. |
| [ISSUE-0043](issues/ISSUE-0043.md) | active | P0 | Resolve the EuroCALL 2026 AI-authorship dispute for two submitted papers. |
| [ISSUE-0044](issues/ISSUE-0044.md) | active | P0 | Choose the next annotation and AI-authorship publication targets. |
| [ISSUE-0045](issues/ISSUE-0045.md) | active | P1 | Deliver a lightweight mobile content-and-exercises experience. |
