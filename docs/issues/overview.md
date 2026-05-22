# C-LARA-2 issues overview

_Last updated: 2026-05-22T06:01:39Z_

This document summarizes the current issue registry for quick human review. Canonical machine-readable records remain in `docs/issues/issues/*.json` and `docs/issues/index.json`.

## Recent progress

- **[ISSUE-0018](issues/ISSUE-0018.json)** is now closed: issue-suggestion processing now uses canonical `main`-branch issue registry data (with local fallback) and reports the source in admin prompt text.
- **[ISSUE-0019](issues/ISSUE-0019.json)** is now closed based on a human update confirming the favicon currently appears correctly on AWS deployment.
- **[ISSUE-0017](issues/ISSUE-0017.json)** remains the current page-image umbrella issue, with ISSUE-0007 kept as a linked prompt-indirection subproblem.
- **[ISSUE-0016](issues/ISSUE-0016.json)** remains active after Phase A no-audio/skip-TTS delivery; the community-recorded dictionary extension remains pending.

## Near-term priorities

1. **[ISSUE-0014](issues/ISSUE-0014.json) (P1)** — Continue AWS operational readiness work (budgets/alerts, run-rate, right-sizing/scheduling) before wider rollout.
2. **[ISSUE-0016](issues/ISSUE-0016.json) (P1, active, deadline 2026-06-01)** — Validate no-audio/skip-TTS fallback on Kok Kaper and design the follow-up community-recorded audio dictionary.
3. **[ISSUE-0020](issues/ISSUE-0020.json) (P1)** — Improve picture-dictionary compile for low-resource workflows and organiser feedback: partial artifacts + explicit manual-completion handoff.
4. **[ISSUE-0011](issues/ISSUE-0011.json) (P1, active, deadline 2026-06-01)** — Continue picture-dictionary/game workflow hardening: curation/game-ready signals, word→image mode, and feedback loops.
5. **[ISSUE-0017](issues/ISSUE-0017.json) (P1)** — Complete page-image generation/review/regeneration stabilization, especially organiser workflow polish and reliability.
6. **[ISSUE-0003](issues/ISSUE-0003.json) (P1)** — Build efficient end-to-end pipeline test runner with corpus-driven quality checks.
7. **[ISSUE-0010](issues/ISSUE-0010.json) (P1)** — Expand representative legacy corpus imports and tooling.
8. **[ISSUE-0013](issues/ISSUE-0013.json) (P1)** — Improve stage artifact persistence performance and timeout resilience.
9. **[ISSUE-0008](issues/ISSUE-0008.json) (P1, deadline 2026-06-15)** — Draft technical report and publication outputs.
10. **[ISSUE-0019](issues/ISSUE-0019.json) (P3)** — Fix AWS favicon serving/caching mismatch (minor but visible UX issue).

## Completed issues

1. **[ISSUE-0019](issues/ISSUE-0019.json) (completed 2026-05-22)** — Favicon currently confirmed to display correctly on AWS deployment; issue closed after operator verification.
2. **[ISSUE-0018](issues/ISSUE-0018.json) (completed 2026-05-20)** — Use canonical `main`-branch issue registry data (with fallback visibility) during issue-suggestion processing.
3. **[ISSUE-0015](issues/ISSUE-0015.json) (completed 2026-05-18)** — Let community organisers add existing users as ordinary community members, list memberships, and remove ordinary members while keeping organiser-role changes protected.
4. **[ISSUE-0002](issues/ISSUE-0002.json) (completed 2026-05-09)** — Support migration of legacy C-LARA projects into C-LARA-2 through direct import of supported legacy JSON export ZIP bundles.
5. **[ISSUE-0009](issues/ISSUE-0009.json) (completed 2026-05-06)** — Auto-regenerate and validate source project bundle stage artifacts before export/import.

## Notes and risks

- **AWS/static serving variance:** favicon behaviour can differ by browser and deployment settings; the `/favicon.ico` redirect reduces risk from implicit browser requests that bypass `<link rel="icon">`.
- **Publication scope cohesion:** publication planning remains in ISSUE-0008 rather than being split into multiple fragmented issues; this keeps deadlines and cross-paper dependencies in one place.
- **Page-image roadmap scope:** ISSUE-0017 is intentionally broader than ISSUE-0007. Prompt indirection is one requirement; the full page-image workflow also needs additive variant generation, subset regeneration, review context, organiser preferred-image decisions, and compile-time preferred-image selection.
