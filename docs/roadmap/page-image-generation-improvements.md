# Roadmap: improved treatment of page image generation

This roadmap is a focused follow-up to [`image-generation-pipeline.md`](image-generation-pipeline.md). The existing image pipeline already covers style, element, and page-image generation at a broad level; this document defines the next page-image-specific improvements needed for reliable community review, regeneration, and publication workflows.

Tracked issue: **ISSUE-0017**. Related issue: **ISSUE-0007** for LLM prompt-construction indirection.

## Why this roadmap exists

The current page-image implementation has enough moving parts that the next changes need a single plan rather than isolated fixes. Important workflows now depend on page images being reviewable by community members, actionable by organisers, and compiled into HTML using the correct approved/preferred image.

## Current implementation baseline

As of 2026-05-18, the codebase already has several foundations:

- Per-page rows (`ProjectImagePage`) and generated variants (`ProjectImagePageVariant`).
- A `preferred_variant` relationship on each page row.
- Community member voting (`CommunityImageVote`) and organiser review notes (`CommunityOrganiserReview`).
- Community member and organiser review views for page-image variants.
- A generation path that can create requested variants for specific pages.
- HTML compilation support for page images when compile input receives a page-image map.

The work below is therefore not a greenfield redesign. It should harden and connect the pieces that already exist.

## Goals and requirements

### 1) Additive page-image generation

Generating page images must be able to **add new variants** to the existing set without replacing or deleting previous variants.

Requirements:

- Preserve existing variants, prompts, revised prompts, statuses, community votes, and preferred-variant selections unless an organiser explicitly changes them.
- Assign stable next variant indexes per page.
- Record the generation request that produced each variant, including requested filter/mode, prompt update text, image model, and timestamp.
- Make destructive replacement a separate explicit action, not the default regeneration behavior.

### 2) Generate only for selected page subsets

The generation UI and backend should support targeted page subsets. Required first filters:

- **Missing images only**: pages with no usable page image or no generated variants.
- **No approved/preferred image**: pages where there is no approved or preferred variant.
- **All images unacceptable**: pages where all current variants are rejected/downvoted or otherwise marked unusable.
- **Selected pages**: organiser/manual checkbox selection.

Implementation notes:

- Filters should resolve to a concrete page list before the generation task starts and log that list for auditability.
- The UI should show how many pages will be affected before submitting a batch task.
- If a page has an existing preferred/approved image and is not selected by the filter, it must remain untouched.

### 3) Improve prompt quality through LLM prompt indirection

ISSUE-0007 should become part of the page-image regeneration path, not just initial generation.

Requirements:

- Build an intermediate text-model call that receives source page text, page translation when available, style description, relevant element descriptions, current prompt, current community suggestions, and any organiser prompt update.
- Ask the text model to produce a clean image-generation prompt suitable for the chosen image model.
- Persist the intermediate prompt-construction input and output for audit and manual debugging.
- Allow organiser/user edited prompt text to override or amend the AI-produced prompt before image generation where appropriate.
- Avoid asking the image model to render text unless explicitly requested.

### 4) Improve community member review context

The community member image judging view (`communities/<community>/member/projects/<project>/judge/`) should show enough context for informed review.

Requirements:

- Display source page text for each page.
- Display page translation when available.
- Show all generated variants for that page with voting controls.
- Preserve each member's existing vote and note when revisiting the page.
- Make it clear which variant is currently preferred, if any, without making members responsible for final selection.

### 5) Add an organiser image-review dashboard from the organiser area

The community organiser home (`communities/<community>/organiser/`) should link clearly to an organiser image-review view for relevant community projects.

The organiser view should:

- Show each page with source text and translation.
- Show all variants, collected judgements, and community suggestions/notes.
- Highlight the currently preferred image for each page.
- Let the organiser set/change the preferred variant.
- Let the organiser mark variants/pages as approved, unacceptable, or needing regeneration.
- Submit regeneration tasks for:
  - all pages without approved/preferred images,
  - all pages whose variants are unacceptable,
  - selected pages,
  - optionally a fixed number of new variants per page.
- Include community member suggestions and organiser prompt updates in the regeneration prompt-construction input.

### 6) Compile HTML using preferred page images

The HTML compilation stage should use the preferred image for each page.

Requirements:

- If `ProjectImagePage.preferred_variant` exists and its image file exists, compile with that image.
- If no preferred variant exists, fall back to the page row's current image path only when it exists and is still considered usable.
- If no usable page image exists, compile without an image for that page rather than emitting a broken reference.
- Add diagnostics to compile task updates when requested image placement is enabled but preferred images are missing.
- Preserve existing top/bottom placement behavior.

## Data model and state considerations

The existing `ProjectImagePage` / `ProjectImagePageVariant` split is a good starting point. Possible additions should be considered only if the current fields cannot support the workflow cleanly:

- A generation request/audit model for batch regeneration tasks.
- Variant/page review status beyond `draft/generated/approved`, for example `unacceptable` or a separate organiser decision field.
- A normalized table for organiser regeneration flags, if notes and statuses are insufficient.
- Cached per-page translation/context fields if computing them dynamically becomes expensive.

Avoid duplicating source-of-truth fields. `preferred_variant` should remain the canonical selection used by compile and display code.

## Proposed delivery phases

### Phase A: roadmap and UI clarity

Status: **started/implemented for the existing review entry points**. The roadmap exists and is linked from the broader image-generation roadmap; member and organiser community pages now label the image-review actions explicitly; member and organiser review views label the current preferred image/variant.

- Create this roadmap and link it from the broader image-generation roadmap.
- Make sure organiser/member entry points are discoverable.
- Ensure existing views label the preferred variant clearly.

### Phase B: review context and preferred-image compile behavior

Status: **implemented**. Member and organiser image-review views now show source page text and available page translations, and compile resolves page-image placement from the selected `preferred_variant` first with safe omission/diagnostics when preferred image files are missing.

- Add source page text and page translation to member review and organiser review views.
- Confirm compile uses `preferred_variant` in all page-image placement paths.
- Add regression tests for preferred-variant selection and missing-image fallback.

### Phase C: prompt-construction indirection (ISSUE-0007)

Rationale: this can be implemented and tested independently after the review/compile foundations are in place. It also gives the later regeneration workflow a stronger prompt-construction contract before organiser-facing batch controls are expanded.

Status: **initial implementation in progress**. Page-image generation now runs a text-model prompt-construction step inside fan-out/fan-in before image rendering. The constructor input includes global summary/excerpt, current page plus neighboring page text, style context, and relevant element descriptions/image paths; outputs are normalized and persisted to telemetry for audit/debugging.

Implementation strategy (current first version):
- Build a per-page constructor payload with summary + local context (previous/current/next page text), style text, and relevant element metadata.
- Ask the text model to return only a final image-generation prompt (no JSON/markdown) using that payload.
- Normalize constructor output with safety fallback to the deterministic base prompt if output is empty/invalid.
- Record constructor request/response alongside page-image request telemetry for reproducibility.
- Keep constructor and image calls inside fan-out/fan-in so prompt construction happens in parallel per page before each image call.

- Add the text-model prompt-construction step.
- Feed community suggestions and organiser prompt updates into the prompt-construction input.
- Persist prompt-construction provenance and expose it for debugging/review.
- Add focused tests for prompt-construction inputs, outputs, provenance persistence, and text-rendering guardrails.

### Phase D: additive, subset, and organiser regeneration workflow

Rationale: additive/subset generation and organiser regeneration controls are tightly coupled in practice. Delivering them together makes the workflow easier to test end-to-end: page selection filters resolve to concrete batches, organiser controls submit those batches, generated variants are appended safely, and review state remains intact.

- Implement backend selection helpers for missing-only, no-approved/preferred-only, all-unacceptable, and selected-pages filters.
- Make generation append new variants by default.
- Show affected-page counts before batch submission.
- Persist generation request metadata.
- Expand the organiser review dashboard with page filters, preferred-variant controls, approval/unacceptable decisions, and batch regeneration actions.
- Add progress/status feedback for long-running regeneration tasks.
- Keep the workflow safe under partial failures: successful pages should remain available even if some pages fail.
- Add end-to-end tests covering subset selection, organiser batch submission, additive variant creation, preserved votes/preferred selections, and regeneration audit metadata.

### Phase E: hardening and operational checks

- Add remaining cross-phase tests for subset selection, additive generation, preferred variant compile behavior, review context, and prompt indirection.
- Add cost/concurrency guardrails for batch regeneration.
- Add audit/event logs sufficient to reconstruct why a page image was regenerated.

## Acceptance checks

- A project with existing page-image variants can generate additional variants without losing prior variants, votes, prompts, or preferred selections.
- Organisers can generate images only for pages matching missing/no-approved/all-unacceptable filters, and for manually selected pages.
- Prompt construction can use an LLM intermediate step and stores enough provenance to debug the final image prompt.
- Community members see source page text and page translation while judging variants.
- Organisers can see aggregate votes/notes, preferred image status, and submit regeneration tasks based on review outcomes.
- HTML compilation uses each page's preferred image when available and omits images cleanly where no usable image exists.
