# C-LARA-2 issues overview

_Last updated: 2026-05-20T00:17:41Z_

This document summarizes the current issue registry for quick human review. Canonical machine-readable records remain in `docs/issues/issues/*.json` and `docs/issues/index.json`.

## Recent progress

- Added **[ISSUE-0018](issues/ISSUE-0018.json)** from a new human suggestion about confusion in issue processing when the server checkout is stale relative to recently merged work.
- The new issue scopes a deterministic data-source fix: suggestion processing should read issue/roadmap context from the canonical checked-in `main` branch snapshot (or an equivalent explicit remote ref), rather than the local checked-out repo state.
- ISSUE-0018 also requires visibility and resilience work: display which repository ref/snapshot was used and define fallback behaviour for offline or fetch-error states.
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
15. **[ISSUE-0018](issues/ISSUE-0018.json) (P2)** — Make issue-suggestion processing resolve issue/roadmap context from canonical `main`-branch data instead of potentially stale local checkouts, with explicit ref reporting and robust fallback behaviour.

## Completed issues

1. **[ISSUE-0015](issues/ISSUE-0015.json) (completed 2026-05-18)** — Let community organisers add existing users as ordinary community members, list memberships, and remove ordinary members while keeping organiser-role changes protected.
2. **[ISSUE-0002](issues/ISSUE-0002.json) (completed 2026-05-09)** — Support migration of legacy C-LARA projects into C-LARA-2 through direct import of supported legacy JSON export ZIP bundles.
3. **[ISSUE-0009](issues/ISSUE-0009.json) (completed 2026-05-06)** — Auto-regenerate and validate source project bundle stage artifacts before export/import.

## Notes and risks

- **Suggestion-processing trust risk:** if admins cannot tell which issue registry snapshot was used for triage, suggestion handling can drift and create duplicate or contradictory issue entries.
- **Operational dependency risk:** ISSUE-0018 likely requires dependable remote-ref fetching/caching, so behaviour under GitHub/API/network failure needs explicit fallback semantics and operator messaging.
- **Publication scope cohesion:** publication planning remains in ISSUE-0008 rather than being split into multiple fragmented issues; this keeps deadlines and cross-paper dependencies in one place.
- **Page-image roadmap scope:** ISSUE-0017 is intentionally broader than ISSUE-0007. Prompt indirection is one requirement; the full page-image workflow also needs additive variant generation, subset regeneration, review context, organiser preferred-image decisions, and compile-time preferred-image selection.
