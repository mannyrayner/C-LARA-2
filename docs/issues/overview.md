# C-LARA-2 issues overview

_Last updated: 2026-05-18T09:00:03Z_

This document summarizes the current issue registry for quick human review. Canonical machine-readable records remain in `docs/issues/issues/*.json` and `docs/issues/index.json`.

## Recent progress

- **[ISSUE-0017](issues/ISSUE-0017.json)** has been added from human suggestion #7, with a new focused roadmap at [`docs/roadmap/page-image-generation-improvements.md`](../roadmap/page-image-generation-improvements.md). It covers additive page-image variant generation, subset regeneration, ISSUE-0007 prompt indirection, member/organiser review context, preferred-image selection, and compile-time preferred-image use.
- **[ISSUE-0007](issues/ISSUE-0007.json)** is now explicitly linked into the broader ISSUE-0017 page-image roadmap: prompt-construction indirection should support both first-pass page generation and organiser/community-informed regeneration.
- **[ISSUE-0016](issues/ISSUE-0016.json)** is active and Phase A is implemented: project owners can select no audio / skip TTS, the audio stage avoids TTS calls and strips stale audio annotations, and compiled HTML omits audio controls when no recorded audio exists. Phase B remains the community-recorded word/segment audio dictionary.
- **[ISSUE-0015](issues/ISSUE-0015.json)** is closed: community organisers can add existing users as ordinary members from the organiser page, view current memberships, and remove ordinary members. Organiser-role changes remain protected from the organiser UI.
- **[ISSUE-0011](issues/ISSUE-0011.json)** records that a first picture-dictionary-backed **image → word** flashcard mode has been implemented. The remaining image-game work is narrower: curation/game-ready flags, picture glossing where appropriate, word → image flashcards, and learner/community feedback for bad cards.

## Near-term priorities

1. **[ISSUE-0014](issues/ISSUE-0014.json) (P1)** — Continue AWS operational readiness work: configure AWS Budgets/alerts, monitor service-level EC2/RDS cost breakdowns, estimate monthly run-rate under beta usage, and review whether EC2/RDS resources can be right-sized or scheduled before C-LARA-2 is opened to more users.
2. **[ISSUE-0016](issues/ISSUE-0016.json) (P1, active, deadline 2026-06-01)** — Validate the no-audio/skip-TTS fallback with Kok Kaper material, then design and implement the follow-up community-recorded audio dictionary for surface words and segments.
3. **[ISSUE-0003](issues/ISSUE-0003.json) (P1)** — Add an efficient end-to-end pipeline test runner; first target legacy-vs-C-LARA-2 comparisons over the imported corpus from ISSUE-0010, with AI-assisted gross-difference review where exact matching is inappropriate.
4. **[ISSUE-0011](issues/ISSUE-0011.json) (P1, active, deadline 2026-06-01)** — Continue the Kok Kaper image-game fast path after the seed dictionary and first image→word flashcards: validate/curate game-ready entries, then add word→image play and feedback/reporting for image/card problems.
5. **[ISSUE-0017](issues/ISSUE-0017.json) (P1)** — Implement the page-image improvements roadmap: show source/translation context in community review, use preferred page images in compile, add additive/subset regeneration, feed community suggestions into prompt indirection, and harden organiser review/regeneration workflows.
6. **[ISSUE-0010](issues/ISSUE-0010.json) (P1)** — Import and triage a representative legacy C-LARA corpus from the Adelaide material now reaching C-LARA-2 on AWS; include known divergence checks before growing into multi-bundle batch import with heartbeat progress.
7. **[ISSUE-0013](issues/ISSUE-0013.json) (P1)** — Implement the efficiency roadmap: centralize stage-artifact read/write operations, benchmark JSON against faster formats, record read/write timings, and keep trusted admin-only binary migration experiments separate from untrusted user uploads.
8. **[ISSUE-0008](issues/ISSUE-0008.json) (P1, deadline 2026-06-15)** — Draft the long C-LARA-2 internal technical report and use it as the source for the accepted EuroCALL 2026 paper and possible ALTA 2026 submission.
9. **[ISSUE-0006](issues/ISSUE-0006.json) (P2)** — Investigate segmentation_phase_2 token-span failures and rerun-path correctness, preferably using ISSUE-0003 diagnostics where possible.
10. **[ISSUE-0005](issues/ISSUE-0005.json) (P2)** — Tune segmentation_phase_1 prompting so prose and poetry segment granularity better matches expected legacy behavior.
11. **[ISSUE-0004](issues/ISSUE-0004.json) (P2)** — Introduce AI-based review gates with a pluggable evaluator architecture after the test-runner foundation is available.
12. **[ISSUE-0007](issues/ISSUE-0007.json) (P2)** — Implement LLM prompt-construction indirection for page-image generation prompts as a component of ISSUE-0017.
13. **[ISSUE-0001](issues/ISSUE-0001.json) (P2)** — Support registration of hosted compiled legacy content in C-LARA-2; use the same AWS staging/rsync runbook and the imported C-LARA corpus as complementary test material.
14. **[ISSUE-0012](issues/ISSUE-0012.json) (P2)** — Adjust project creation defaults for AI text generation and top page-image placement.

## Completed issues

1. **[ISSUE-0015](issues/ISSUE-0015.json) (completed 2026-05-18)** — Let community organisers add existing users as ordinary community members, list memberships, and remove ordinary members while keeping organiser-role changes protected.
2. **[ISSUE-0002](issues/ISSUE-0002.json) (completed 2026-05-09)** — Support migration of legacy C-LARA projects into C-LARA-2 through direct import of supported legacy JSON export ZIP bundles.
3. **[ISSUE-0009](issues/ISSUE-0009.json) (completed 2026-05-06)** — Auto-regenerate and validate source project bundle stage artifacts before export/import.

## Notes and risks

- **Page-image roadmap scope:** ISSUE-0017 is intentionally broader than ISSUE-0007. Prompt indirection is one requirement; the full page-image workflow also needs additive variant generation, subset regeneration, review context, organiser preferred-image decisions, and compile-time preferred-image selection.
- **Community review context:** member and organiser image-review pages should show source text and translation before asking people to judge images; otherwise feedback may be unreliable, especially in low-resource-language community sessions.
- **Preferred image is the compile contract:** `ProjectImagePage.preferred_variant` should remain the canonical image selection for each page. Generation/regeneration should not overwrite that selection unless the organiser explicitly changes it.
- **Low-resource audio has a hard near-term date:** ISSUE-0016 Phase A has landed as a narrow no-audio/skip-TTS fallback. It should be validated on Kok Kaper projects before **2026-06-01**; the richer recording workflow should be designed in parallel but should not destabilize the fallback.
- **AWS readiness remains a launch blocker:** ISSUE-0014 is high priority even though it is not an application bug. The April/May bills suggest EC2 and RDS are the main cost drivers; before broader usage, the team should know the expected run-rate, define acceptable monthly spend, set alarms, and document what to do if costs rise unexpectedly.
- **Kok Kaper image games:** ISSUE-0011 should still keep the first community-facing scope narrow. The implemented image→word flashcards are a useful first step, but game readiness still depends on dictionary curation, approved entries, word→image mode, and a simple way to flag bad images/words/distractors.
- **Legacy corpus dependency:** ISSUE-0003 depends on ISSUE-0010 for its first high-value evaluation corpus; the runner can be designed earlier, but legacy-vs-C-LARA-2 comparisons need enough imported material to be useful.
- **Stage-artifact abstraction:** ISSUE-0013 should first centralize read/write operations behind a format-independent API so pipeline logic is not tied to `Path.read_text`/`json.loads` or `Path.write_text`/`json.dumps`.
- **Writing scope:** ISSUE-0008 should use the internal report as the master source, then, subject to co-author approval, split it into a user-facing EuroCALL 2026 paper and an implementor-facing ALTA 2026 paper to avoid duplicated effort.
