# C-LARA-2 issues overview

_Last updated: 2026-05-20T01:30:00Z_

This document summarizes the current issue registry for quick human review. Canonical machine-readable records remain in `docs/issues/issues/*.json` and `docs/issues/index.json`.

## Recent progress

- **[ISSUE-0018](issues/ISSUE-0018.json)** is now closed: issue-suggestion processing now uses canonical `main`-branch issue registry data (with local fallback) and reports the source in admin prompt text.
- **[ISSUE-0019](issues/ISSUE-0019.json)** has been deprioritised/shelved for now: several favicon fixes were attempted, but AWS behaviour remains inconsistent; follow-up troubleshooting steps are now recorded in the issue notes.
- **[ISSUE-0017](issues/ISSUE-0017.json)** remains the current page-image umbrella issue, with ISSUE-0007 kept as a linked prompt-indirection subproblem.
- **[ISSUE-0016](issues/ISSUE-0016.json)** remains active after Phase A no-audio/skip-TTS delivery; the community-recorded dictionary extension remains pending.

## Near-term priorities

1. **[ISSUE-0014](issues/ISSUE-0014.json) (P1)** — Continue AWS operational readiness work: configure AWS Budgets/alerts, monitor service-level EC2/RDS cost breakdowns, estimate monthly run-rate under beta usage, and review whether EC2/RDS resources can be right-sized or scheduled before C-LARA-2 is opened to more users.
2. **[ISSUE-0016](issues/ISSUE-0016.json) (P1, active, deadline 2026-06-01)** — Validate the no-audio/skip-TTS fallback with Kok Kaper material, then design and implement the follow-up community-recorded audio dictionary for surface words and segments.
3. **[ISSUE-0003](issues/ISSUE-0003.json) (P1)** — Add an efficient end-to-end pipeline test runner; first target legacy-vs-C-LARA-2 comparisons over the imported corpus from ISSUE-0010, with AI-assisted gross-difference review where exact matching is inappropriate.
4. **[ISSUE-0011](issues/ISSUE-0011.json) (P1, active, deadline 2026-06-01)** — Continue the Kok Kaper image-game fast path after the seed dictionary and first image→word flashcards: validate/curate game-ready entries, then add word→image play and feedback/reporting for image/card problems.
5. **[ISSUE-0017](issues/ISSUE-0017.json) (P1)** — Implement the page-image improvements roadmap: show source/translation context in community review, use preferred page images in compile, add additive/subset regeneration, feed community suggestions into prompt indirection, and harden organiser review/regeneration workflows.
6. **[ISSUE-0010](issues/ISSUE-0010.json) (P1)** — Import and triage a representative legacy C-LARA corpus from the Adelaide material now reaching C-LARA-2 on AWS; include known divergence checks before growing into multi-bundle batch import with heartbeat progress.
7. **[ISSUE-0013](issues/ISSUE-0013.json) (P1)** — Implement the efficiency roadmap: centralize stage-artifact read/write operations, benchmark JSON against faster formats, record read/write timings, and keep trusted admin-only binary migration experiments separate from untrusted user uploads.
8. **[ISSUE-0008](issues/ISSUE-0008.json) (P1, deadline 2026-06-15)** — Deliver the internal technical report and derive the EuroCALL (mid-August 2026) and ALTA (mid-September 2026) papers, while explicitly documenting the issues-driven Codex+human workflow used to produce them.
9. **[ISSUE-0006](issues/ISSUE-0006.json) (P2)** — Investigate segmentation_phase_2 token-span failures and rerun-path correctness, preferably using ISSUE-0003 diagnostics where possible.
10. **[ISSUE-0005](issues/ISSUE-0005.json) (P2)** — Tune segmentation_phase_1 prompting so prose and poetry segment granularity better matches expected legacy behavior.
11. **[ISSUE-0004](issues/ISSUE-0004.json) (P2)** — Introduce AI-based review gates with a pluggable evaluator architecture after the test-runner foundation is available.
12. **[ISSUE-0007](issues/ISSUE-0007.json) (P2)** — Implement LLM prompt-construction indirection for page-image generation prompts as a component of ISSUE-0017.
13. **[ISSUE-0001](issues/ISSUE-0001.json) (P2)** — Support registration of hosted compiled legacy content in C-LARA-2; use the same AWS staging/rsync runbook and the imported C-LARA corpus as complementary test material.
14. **[ISSUE-0012](issues/ISSUE-0012.json) (P2)** — Adjust project creation defaults for AI text generation and top page-image placement.
15. **[ISSUE-0019](issues/ISSUE-0019.json) (P3, shelved)** — Favicon inconsistency on AWS remains unresolved; defer active work and resume with deployment/static-pipeline diagnostics when higher-priority items allow.

## Completed issues

1. **[ISSUE-0018](issues/ISSUE-0018.json) (completed 2026-05-20)** — Use canonical `main`-branch issue registry data (with fallback visibility) during issue-suggestion processing.
2. **[ISSUE-0015](issues/ISSUE-0015.json) (completed 2026-05-18)** — Let community organisers add existing users as ordinary community members, list memberships, and remove ordinary members while keeping organiser-role changes protected.
3. **[ISSUE-0002](issues/ISSUE-0002.json) (completed 2026-05-09)** — Support migration of legacy C-LARA projects into C-LARA-2 through direct import of supported legacy JSON export ZIP bundles.
4. **[ISSUE-0009](issues/ISSUE-0009.json) (completed 2026-05-06)** — Auto-regenerate and validate source project bundle stage artifacts before export/import.

## Notes and risks

- **AWS/static serving variance:** favicon behaviour can differ by browser and deployment settings; the `/favicon.ico` redirect reduces risk from implicit browser requests that bypass `<link rel="icon">`.
- **Publication scope cohesion:** publication planning remains in ISSUE-0008 rather than being split into multiple fragmented issues; this keeps deadlines and cross-paper dependencies in one place.
- **Page-image roadmap scope:** ISSUE-0017 is intentionally broader than ISSUE-0007. Prompt indirection is one requirement; the full page-image workflow also needs additive variant generation, subset regeneration, review context, organiser preferred-image decisions, and compile-time preferred-image selection.
