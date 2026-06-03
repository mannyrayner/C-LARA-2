# C-LARA-2 issue overview (refreshed 2026-06-03T03:00:00Z)

## Recent progress

- Escalated **ISSUE-0036** to P1 after maintainer review: current annotation errors are frequent, and a principled few-shot curation pipeline is promising both for quality improvements and for First Progress Report evidence.
- Expanded `docs/roadmap/few-shot-example-curation.md` into an explicit generate → adversarial review → repair → gold acceptance architecture with schema validation, critic severity labels, consensus scoring, auditable example records, and incremental invocation/storage/review workflows; the `curate_fewshots` command now covers traced, fan-out/fan-in segmentation_phase_2 candidate generation and validation, and `review_fewshots` adds the first language-specific hostile-review step framed as plain word/unit-boundary review rather than C-LARA-2-internal processing terminology, with French clitic guidance, concrete boundary examples, preflight request checks, and longer review timeouts.
- Closed **ISSUE-0007** in the current issue registry because page-image prompt-construction indirection is now implemented; future page-image prompt work should be filed as concrete follow-ons.
- Advanced **ISSUE-0034** from a prompt-wrapper prototype toward an admin-only repository-grounded project-understanding assistant with asynchronous execution, status polling, request/result persistence, and cost/metadata capture.
- Expanded the evaluator/autonomy roadmap around **ISSUE-0003**, **ISSUE-0004**, **ISSUE-0005**, and **ISSUE-0006** so segmentation and MWE improvements can be measured systematically for the First Progress Report.

## Near-term priorities

1. **ISSUE-0031** — improve compiled-content presentation context and configurable public access controls.
2. **ISSUE-0030** — fix image-generation workflow UX around element expansion auto-refresh and selection confirmation.
3. **ISSUE-0029** — autosave community judging inputs to prevent accidental data loss.
4. **ISSUE-0026** — define the next-step community-recorded audio workflow for non-TTS languages.
5. **ISSUE-0003 / ISSUE-0036 / ISSUE-0004** — use the pipeline runner, curated few-shot generation/review, and AI-based review gates to compare default and candidate processing variants.
6. **ISSUE-0005 / ISSUE-0006** — treat segmentation prompt/few-shot changes as measurable experiments rather than anecdotal prompt tuning.
7. **ISSUE-0010 / ISSUE-0013** — continue legacy corpus import and stage-artifact resilience work needed for representative quality checks.
8. **ISSUE-0034** — add export/review, budget/rate-limit, and evidence-record controls before wider use of project-understanding answers.

## Notes/risks

- Few-shot curation is now P1 because annotation errors are visible in current work and because the proposed generate/review/repair/acceptance pipeline can produce strong report evidence; it still depends on **ISSUE-0003** and **ISSUE-0004** for systematic measurement, and it should support incremental top-up batches for new languages or new failure modes rather than one large generation run.
- The boundary-first segmentation experiments should not be treated as proven improvements until **ISSUE-0004** evaluator records compare default and candidate outputs on representative cases.
- The disabled admin shutdown control remains intentionally hidden; under `make run-platform-with-real-q`, closing the development terminal is currently the reliable workaround for reincarnating Q processes.
- **ISSUE-0034** remains restricted/admin-only until export/review controls, citation/path sanitization, exact-cost reconciliation, and hard budget/rate-limit controls are in place.
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
