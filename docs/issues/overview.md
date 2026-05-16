# C-LARA-2 issues overview

_Last updated: 2026-05-16T13:54:58Z_

This document summarizes the current issue registry for quick human review. Canonical machine-readable records remain in `docs/issues/issues/*.json` and `docs/issues/index.json`.

## Recent progress

- **[ISSUE-0014](issues/ISSUE-0014.json)** has been added from human suggestion #4 as a **P1 pre-rollout operational readiness issue**: AWS has warned that one or more Free Tier service limits are already above 85% in May while usage is still very limited, so service limits, budgets, quotas, and expected beta traffic costs need review before wider launch.
- **[ISSUE-0011](issues/ISSUE-0011.json)** now records that a first picture-dictionary-backed **image → word** flashcard mode has been implemented. The remaining image-game work is narrower: curation/game-ready flags, picture glossing where appropriate, word → image flashcards, and learner/community feedback for bad cards.
- **[ISSUE-0013](issues/ISSUE-0013.json)** remains the main performance/resilience track for large imported legacy projects and stage-artifact persistence.
- **[ISSUE-0010](issues/ISSUE-0010.json)** remains active as the representative Adelaide legacy corpus import/triage track; that corpus should also feed the systematic comparison runner in ISSUE-0003.

## Near-term priorities

1. **[ISSUE-0014](issues/ISSUE-0014.json) (P1)** — Audit the AWS services triggering the May Free Tier warning, estimate beta usage/cost, configure budgets/alerts and service-quota checks, and document any limit/resource changes needed before C-LARA-2 is opened to more users.
2. **[ISSUE-0003](issues/ISSUE-0003.json) (P1)** — Add an efficient end-to-end pipeline test runner; first target legacy-vs-C-LARA-2 comparisons over the imported corpus from ISSUE-0010, with AI-assisted gross-difference review where exact matching is inappropriate.
3. **[ISSUE-0011](issues/ISSUE-0011.json) (P1, active, deadline 2026-06-01)** — Continue the Kok Kaper image-game fast path after the seed dictionary and first image→word flashcards: validate/curate game-ready entries, then add word→image play and feedback/reporting for image/card problems.
4. **[ISSUE-0010](issues/ISSUE-0010.json) (P1)** — Import and triage a representative legacy C-LARA corpus from the Adelaide material now reaching C-LARA-2 on AWS; include known divergence checks before growing into multi-bundle batch import with heartbeat progress.
5. **[ISSUE-0013](issues/ISSUE-0013.json) (P1)** — Implement the efficiency roadmap: centralize stage-artifact read/write operations, benchmark JSON against faster formats, record read/write timings, and keep trusted admin-only binary migration experiments separate from untrusted user uploads.
6. **[ISSUE-0008](issues/ISSUE-0008.json) (P1, deadline 2026-06-15)** — Draft the long C-LARA-2 internal technical report and use it as the source for the accepted EuroCALL 2026 paper and possible ALTA 2026 submission.
7. **[ISSUE-0006](issues/ISSUE-0006.json) (P2)** — Investigate segmentation_phase_2 token-span failures and rerun-path correctness, preferably using ISSUE-0003 diagnostics where possible.
8. **[ISSUE-0005](issues/ISSUE-0005.json) (P2)** — Tune segmentation_phase_1 prompting so prose and poetry segment granularity better matches expected legacy behavior.
9. **[ISSUE-0004](issues/ISSUE-0004.json) (P2)** — Introduce AI-based review gates with a pluggable evaluator architecture after the test-runner foundation is available.
10. **[ISSUE-0007](issues/ISSUE-0007.json) (P2)** — Improve page-image generation by routing prompt construction through an LLM-backed indirection layer.
11. **[ISSUE-0001](issues/ISSUE-0001.json) (P2)** — Support registration of hosted compiled legacy content in C-LARA-2; use the same AWS staging/rsync runbook and the imported C-LARA corpus as complementary test material.
12. **[ISSUE-0012](issues/ISSUE-0012.json) (P2)** — Adjust project creation defaults for AI text generation and top page-image placement.

## Completed issues

1. **[ISSUE-0002](issues/ISSUE-0002.json) (completed 2026-05-09)** — Support migration of legacy C-LARA projects into C-LARA-2 through direct import of supported legacy JSON export ZIP bundles.
2. **[ISSUE-0009](issues/ISSUE-0009.json) (completed 2026-05-06)** — Auto-regenerate and validate source project bundle stage artifacts before export/import.

## Notes and risks

- **AWS readiness is now a launch blocker:** ISSUE-0014 is high priority even though it is not an application bug; the platform should not invite broader usage until the team knows which AWS services are near limits, what the expected costs are, and what alarms/quotas/runbooks are in place.
- **Kok Kaper image games:** ISSUE-0011 should still keep the first community-facing scope narrow. The implemented image→word flashcards are a useful first step, but game readiness still depends on dictionary curation, approved entries, word→image mode, and a simple way to flag bad images/words/distractors.
- **Low-resource-language distractors:** image/card distractors for Indigenous language work should come from the curated picture dictionary where possible, with translations passed to AI ranking/filtering so the model need not know the source language.
- **Legacy corpus dependency:** ISSUE-0003 depends on ISSUE-0010 for its first high-value evaluation corpus; the runner can be designed earlier, but legacy-vs-C-LARA-2 comparisons need enough imported material to be useful.
- **Stage-artifact abstraction:** ISSUE-0013 should first centralize read/write operations behind a format-independent API so pipeline logic is not tied to `Path.read_text`/`json.loads` or `Path.write_text`/`json.dumps`.
- **Trusted one-off migration format:** ISSUE-0013 may use pickle or a similar binary representation only for the trusted Adelaide migration handoff. Keep that separate from ordinary user uploads and long-term source-bundle interchange.
- **Writing scope:** ISSUE-0008 should use the internal report as the master source, then, subject to co-author approval, split it into a user-facing EuroCALL 2026 paper and an implementor-facing ALTA 2026 paper to avoid duplicated effort.
