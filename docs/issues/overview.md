# C-LARA-2 issues overview

_Last updated: 2026-05-23T00:00:00Z_

This document summarizes the current issue registry for quick human review. Canonical machine-readable records remain in `docs/issues/issues/*.json` and `docs/issues/index.json`.

## Recent progress

- Added **[ISSUE-0020](issues/ISSUE-0020.json)** from human suggestion #11, covering picture-dictionary compile improvements: clearer organiser feedback during image generation, low-resource partial-pipeline placeholder artifacts, and direct handoff links to manual annotation.
- Added (or restored as canonical JSON in-repo) **[ISSUE-0019](issues/ISSUE-0019.json)** from human suggestion #10 to track AWS favicon reliability separately from broader infrastructure work.
- Community review/regeneration UX work under **[ISSUE-0017](issues/ISSUE-0017.json)** continues to converge, with member-side “show only unjudged” behavior now validated by user feedback; organiser-side filter-focused display remains active iteration work.

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

1. **[ISSUE-0023](issues/ISSUE-0023.json) (completed 2026-05-23)** — Manual segmentation phase 1 now works for imported dictionary projects that have segmentation artifacts but blank source text.
2. **[ISSUE-0015](issues/ISSUE-0015.json) (completed 2026-05-18)** — Community organisers can add/remove ordinary community members in organiser UI.
3. **[ISSUE-0002](issues/ISSUE-0002.json) (completed 2026-05-09)** — Legacy C-LARA ZIP import migration path implemented.
4. **[ISSUE-0009](issues/ISSUE-0009.json) (completed 2026-05-06)** — Export/import now auto-regenerates and validates source bundle artifacts.

## Notes and risks

- **Low-resource language workflows are now cross-cutting.** ISSUE-0016 (audio), ISSUE-0011 (picture dictionary/games), and ISSUE-0020 (dictionary compile/manual fallback) should be coordinated so organisers get one coherent non-AI workflow.
- **Organiser trust depends on transparent long-running actions.** For dictionary/image compile and regeneration, status/progress messaging should be explicit and tied to real stage transitions.
- **Deployment polish remains important.** ISSUE-0019 is low priority but highly visible; static asset/cache consistency on AWS should be treated as a small reliability patch, not a user workaround.
