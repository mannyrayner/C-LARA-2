# C-LARA-2 issue overview (refreshed 2026-06-13T00:54:28Z)

## Recent progress

- Incorporated human suggestion #27 as **ISSUE-0037**, covering named subset projects derived from community picture dictionaries with optional AI-assisted subset proposal, manual adjustment, canonical-image inheritance, and exercise-source integration.
- Updated the picture-dictionary roadmap so subset projects are explicitly tracked as follow-on work after recent improvements to organiser review, text-free image prompt propagation, and low-resource dictionary consistency diagnostics.
- Recent picture-dictionary work has now wired **Disallow visible text in images** into organiser-requested image regeneration and added advisory AI language-ID diagnostics for likely low-resource word/gloss mix-ups; remaining work is refinement, not first proof of concept.
- The issue registry continues to treat **ISSUE-0036** few-shot curation, **ISSUE-0003** pipeline evaluation, and **ISSUE-0004** AI review gates as the main quality-measurement cluster for report evidence and future prompt changes.
- **ISSUE-0034** remains active as the restricted project-understanding assistant matures toward exportable, human-reviewable evidence records.

## Near-term priorities

1. **ISSUE-0031** — improve compiled-content presentation context and configurable public access controls.
2. **ISSUE-0030** — fix image-generation workflow UX around element expansion auto-refresh and selection confirmation.
3. **ISSUE-0029** — autosave community judging inputs to prevent accidental data loss.
4. **ISSUE-0026** — define the next-step community-recorded audio workflow for non-TTS languages.
5. **ISSUE-0003 / ISSUE-0036 / ISSUE-0004** — use the pipeline runner, curated few-shot generation/review, and AI-based review gates to compare default and candidate processing variants.
6. **ISSUE-0005 / ISSUE-0006** — treat segmentation prompt/few-shot changes as measurable experiments rather than anecdotal prompt tuning.
7. **ISSUE-0010 / ISSUE-0013** — organize the imported legacy corpus into diagnostic/evaluation subsets and continue stage-artifact resilience work needed for representative quality checks.
8. **ISSUE-0008** — finish the concise progress-report draft, including recent picture-dictionary and AI-centered workflow examples.
9. **ISSUE-0037** — design and implement named subset projects derived from canonical community picture dictionaries.
10. **ISSUE-0034** — add export/review, budget/rate-limit, and evidence-record controls before wider use of project-understanding answers.

## Notes/risks

- **ISSUE-0037** should avoid creating a second image-curation surface for subset dictionaries. Subsets should inherit canonical picture-dictionary images/content and should not expose the normal organiser review/regeneration view directly, otherwise organisers could create confusing divergent approval states.
- The AI language-confusion diagnostics for picture dictionaries are intentionally advisory. They can catch common source/gloss mix-ups, but false positives/negatives are expected and the trace table remains important for human review.
- Text-free image prompt propagation is now implemented, but image-level detection of accidental visible text remains follow-on quality-control work under the picture-dictionary roadmap and related image-quality issues.
- Few-shot curation and segmentation changes should not be promoted to defaults until **ISSUE-0003** and **ISSUE-0004** provide systematic comparison evidence.
- Regression prevention remains constrained until **ISSUE-0003** and **ISSUE-0025** land with broader automated pipeline and UI coverage.

## Complete issue inventory

| Issue | Status | Priority | Summary |
|---|---|---|---|
| [ISSUE-0001](issues/ISSUE-0001.json) | reported | P2 | Support hosted compiled legacy content registration in C-LARA-2. |
| [ISSUE-0002](issues/ISSUE-0002.json) | closed | P1 | Support migration of legacy C-LARA projects into C-LARA-2. |
| [ISSUE-0003](issues/ISSUE-0003.json) | reported | P1 | Add efficient end-to-end pipeline test runner for systematic quality checks. |
| [ISSUE-0004](issues/ISSUE-0004.json) | reported | P2 | Introduce AI-based review gates for phase outputs with extensible evaluator architecture. |
| [ISSUE-0005](issues/ISSUE-0005.json) | reported | P2 | Tune segmentation_phase_1 prompting to improve segment granularity by genre. |
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
| [ISSUE-0037](issues/ISSUE-0037.json) | reported | P2 | Create subset projects from community picture dictionaries. |
