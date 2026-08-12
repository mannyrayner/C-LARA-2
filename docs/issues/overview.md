# Issues Overview (updated 2026-08-12T00:00:00Z)

## Recent progress

_Focus: Recorded human outcomes for publications and picture dictionaries, split the publication work, and clarified the post-Sprint sequence around legacy migration, autonomy, mobile access, and learned annotation prompts._

- Closed **ISSUE-0008** after the first C-LARA-2 progress report was posted on ResearchGate on 23 July.
- Added **ISSUE-0043** for the unresolved EuroCALL AI-authorship dispute affecting two on-time submissions.
- Added **ISSUE-0044** for future publication choices and the possible Francis Bond MWE collaboration.
- Added **ISSUE-0045** for a lightweight mobile content-and-exercises experience desired before mid-September.
- Recorded Sophie's positive initial picture-dictionary review and the next community-use checkpoint on 24 August.
- Moved near-complete legacy migration immediately behind the time-critical Sprint and EuroCALL work, followed by learned annotation prompts and mobile access.

## Near-term priorities

1. **ISSUE-0042** — Prepare C-LARA global-workspace experiments for the Digital Minds Research Sprint.
2. **ISSUE-0043** — Resolve the EuroCALL 2026 AI-authorship dispute for two submitted papers.
3. **ISSUE-0010** — Import a representative legacy C-LARA project corpus and add batch import tooling.
4. **ISSUE-0001** — Support hosted compiled legacy content registration in C-LARA-2.
5. **ISSUE-0036** — Systematize creation and evaluation of few-shot examples for linguistic annotation.
6. **ISSUE-0045** — Deliver a lightweight mobile content-and-exercises experience.
7. **ISSUE-0044** — Choose the next annotation and AI-authorship publication targets.
8. **ISSUE-0039** — Build a unified picture-dictionary source-of-truth workspace.
9. **ISSUE-0031** — Improve compiled-content presentation context and configurable public access controls.
10. **ISSUE-0030** — Fix image-generation workflow UX around element expansion auto-refresh and selection confirmation.
11. **ISSUE-0029** — Autosave community judging inputs to prevent accidental data loss.
12. **ISSUE-0037** — Create subset projects from community picture dictionaries.
13. **ISSUE-0026** — Define next-step community-recorded audio workflow for non-TTS languages.
14. **ISSUE-0005** — Tune segmentation_phase_1 prompting to improve segment granularity by genre.
15. **ISSUE-0003** — Add efficient end-to-end pipeline test runner for systematic quality checks.
16. **ISSUE-0041** — Add named project snapshots with restore and gold-standard metadata.
17. **ISSUE-0013** — Improve stage artifact persistence performance and timeout resilience.
18. **ISSUE-0025** — Add systematic UI regression tracking for disappearing controls/content.
19. **ISSUE-0033** — Clean up and phase-track roadmap file maintenance.
20. **ISSUE-0034** — Add restricted project-understanding assistant with versioned evidence records.
21. **ISSUE-0035** — Track intermittent Codex PR update-branch refusal.
22. **ISSUE-0006** — Investigate segmentation_phase_2 token-span failures and rerun-path correctness.
23. **ISSUE-0004** — Introduce AI-based review gates for phase outputs with extensible evaluator architecture.

## Notes/risks

- **ISSUE-0042** remains the immediate time-bounded Sprint focus; experiment outcomes and rating/retention choices remain intentionally open for another day of evidence.
- **ISSUE-0043** is an external-governance and travel-cost risk: both papers were submitted, but the committee has not answered the authorship challenge.
- **ISSUE-0010** and **ISSUE-0001** are now the first post-Sprint completion target because human guidance says legacy migration is nearly finished.
- **ISSUE-0039** and **ISSUE-0037** have positive initial user feedback, but stronger community evidence is expected only after 24 August.
- **ISSUE-0045** has a desired mid-September outcome but needs a bounded effort/scope discussion before implementation confidence is possible.
- Regression prevention remains constrained until **ISSUE-0003** and **ISSUE-0025** land with broader automated pipeline and UI coverage.

## Complete issue inventory

| Issue | Status | Priority | Summary |
|---|---|---|---|
| [ISSUE-0001](issues/ISSUE-0001.md) | active | P1 | Support hosted compiled legacy content registration in C-LARA-2. |
| [ISSUE-0002](issues/ISSUE-0002.md) | closed | P1 | Support migration of legacy C-LARA projects into C-LARA-2. |
| [ISSUE-0003](issues/ISSUE-0003.md) | reported | P1 | Add efficient end-to-end pipeline test runner for systematic quality checks. |
| [ISSUE-0004](issues/ISSUE-0004.md) | reported | P2 | Introduce AI-based review gates for phase outputs with extensible evaluator architecture. |
| [ISSUE-0005](issues/ISSUE-0005.md) | reported | P1 | Tune segmentation_phase_1 prompting to improve segment granularity by genre. |
| [ISSUE-0006](issues/ISSUE-0006.md) | reported | P2 | Investigate segmentation_phase_2 token-span failures and rerun-path correctness. |
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
| [ISSUE-0042](issues/ISSUE-0042.md) | active | P0 | Prepare C-LARA global-workspace experiments for the Digital Minds Research Sprint. |
| [ISSUE-0043](issues/ISSUE-0043.md) | active | P0 | Resolve the EuroCALL 2026 AI-authorship dispute for two submitted papers. |
| [ISSUE-0044](issues/ISSUE-0044.md) | reported | P1 | Choose the next annotation and AI-authorship publication targets. |
| [ISSUE-0045](issues/ISSUE-0045.md) | reported | P1 | Deliver a lightweight mobile content-and-exercises experience. |
