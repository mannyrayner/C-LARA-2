# C-LARA-2 issues overview

_Last updated: 2026-05-23T00:10:17Z_

This document summarizes the current issue registry for quick human review. Canonical machine-readable records remain in `docs/issues/issues/*.json` and `docs/issues/index.json`.

## Recent progress

- **[ISSUE-0014](issues/ISSUE-0014.json)** has been closed based on human update suggestion #7; further AWS rollout problems should be tracked as focused new issues.
- **[ISSUE-0017](issues/ISSUE-0017.json)** has been closed based on human update suggestion #8; future page-image regressions/enhancements should be tracked as specific new issues.
- **[ISSUE-0022](issues/ISSUE-0022.json)** remains closed after confirmed resolution of large ZIP upload limits on AWS.

## Near-term priorities

1. **[ISSUE-0016](issues/ISSUE-0016.json) (P1, active, deadline 2026-06-01)** — Validate the no-audio/skip-TTS fallback with Kok Kaper material, then design and implement the follow-up community-recorded audio dictionary for surface words and segments.
2. **[ISSUE-0003](issues/ISSUE-0003.json) (P1)** — Add an efficient end-to-end pipeline test runner; first target legacy-vs-C-LARA-2 comparisons over the imported corpus from ISSUE-0010, with AI-assisted gross-difference review where exact matching is inappropriate.
3. **[ISSUE-0011](issues/ISSUE-0011.json) (P1, active, deadline 2026-06-01)** — Continue the Kok Kaper image-game fast path after the seed dictionary and first image→word flashcards: validate/curate game-ready entries, then add word→image play and feedback/reporting for image/card problems.
4. **[ISSUE-0010](issues/ISSUE-0010.json) (P1)** — Import and triage a representative legacy C-LARA corpus from the Adelaide material now reaching C-LARA-2 on AWS; include known divergence checks before growing into multi-bundle batch import with heartbeat progress.
5. **[ISSUE-0013](issues/ISSUE-0013.json) (P1)** — Implement the efficiency roadmap: centralize stage-artifact read/write operations, benchmark JSON against faster formats, record read/write timings, and keep trusted admin-only binary migration experiments separate from untrusted user uploads.
6. **[ISSUE-0008](issues/ISSUE-0008.json) (P1, deadline 2026-06-15)** — Deliver the internal technical report and derive the EuroCALL (mid-August 2026) and ALTA (mid-September 2026) papers, while explicitly documenting the issues-driven Codex+human workflow used to produce them.
7. **[ISSUE-0006](issues/ISSUE-0006.json) (P2)** — Investigate segmentation_phase_2 token-span failures and rerun-path correctness, preferably using ISSUE-0003 diagnostics where possible.
8. **[ISSUE-0005](issues/ISSUE-0005.json) (P2)** — Tune segmentation_phase_1 prompting so prose and poetry segment granularity better matches expected legacy behavior.
9. **[ISSUE-0004](issues/ISSUE-0004.json) (P2)** — Introduce AI-based review gates with a pluggable evaluator architecture after the test-runner foundation is available.
10. **[ISSUE-0007](issues/ISSUE-0007.json) (P2)** — Implement LLM prompt-construction indirection for page-image generation prompts as a component of page-image workflows.
11. **[ISSUE-0001](issues/ISSUE-0001.json) (P2)** — Support registration of hosted compiled legacy content in C-LARA-2.
12. **[ISSUE-0012](issues/ISSUE-0012.json) (P2)** — Adjust project creation defaults for AI text generation and top page-image placement.

## Completed issues

1. **[ISSUE-0017](issues/ISSUE-0017.json) (completed 2026-05-23)** — Page-image generation/review/regeneration umbrella work considered complete for current scope.
2. **[ISSUE-0014](issues/ISSUE-0014.json) (completed 2026-05-23)** — AWS service-limit audit/adjustment considered complete for current rollout scope.
3. **[ISSUE-0022](issues/ISSUE-0022.json) (completed 2026-05-22)** — Resolved large ZIP import failures on AWS using deployment-and-migration guidance.
4. **[ISSUE-0019](issues/ISSUE-0019.json) (completed 2026-05-22)** — Favicon confirmed to display correctly on AWS deployment.
5. **[ISSUE-0018](issues/ISSUE-0018.json) (completed 2026-05-20)** — Use canonical `main`-branch issue registry data during issue-suggestion processing.
6. **[ISSUE-0015](issues/ISSUE-0015.json) (completed 2026-05-18)** — Community organiser membership management.
7. **[ISSUE-0002](issues/ISSUE-0002.json) (completed 2026-05-09)** — Legacy project migration import support.
8. **[ISSUE-0009](issues/ISSUE-0009.json) (completed 2026-05-06)** — Auto-regenerate and validate source project bundle artifacts.

## Notes and risks

- Closing broad umbrella issues (ISSUE-0014, ISSUE-0017) reduces active noise, but new concrete regressions should be opened promptly as narrowly scoped follow-ups.
- Publication scope cohesion remains important in ISSUE-0008 as deadlines approach.
