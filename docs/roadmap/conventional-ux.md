# Conventional UX roadmap (project workspace)

This document tracks the **conventional (non-dialogue) UX** for C-LARA-2 so we keep a clear, stable user journey while features continue to expand.

## Why this exists

As we add annotation, image and exercise features, controls can easily drift into the wrong pages and increase cognitive load. This roadmap defines where controls should live and what each project sub-page is for.

## UX principles

- **One page, one responsibility:** each page should focus on one part of the workflow.
- **Progressive disclosure:** show advanced/conditional controls only when needed.
- **Teacher-first clarity:** default views should avoid exposing multiple internal versions unless explicitly requested.
- **Predictable navigation:** top-level project page should always be the primary hub.

## Canonical project navigation

For each project, the navigation should be:

1. **Top-level project page**
   - Purpose: project identity, publication/collaboration/admin actions, and entry points.
   - Should include:
     - links to sub-pages (Annotation, Images, Exercises),
     - bundle export controls,
     - publish/unpublish,
     - delete,
     - collaborators management,
     - “View via server” link when compiled output exists.

2. **Annotation page**
   - Purpose: linguistic pipeline execution and language processing options.
   - Should include:
     - pipeline stage run controls,
     - model selection,
     - language processing options (segmentation/romanization),
     - page-image placement (compile-time setting),
     - run progress and intermediate artifact links.
   - Should *not* include image generation controls, exercise browsing/generation, or collaborator management.

3. **Images page**
   - Purpose: image workflow hub and existing image asset browsing.
   - Should include:
     - links into Style/Elements/Pages workflows,
     - summaries of existing style/element/page assets,
     - conditional “Segment text into pages (phase 1)” control if page segmentation output is not yet available,
     - explicit long-running-action feedback (spinner/progress text) for expensive image-generation operations.

4. **Exercises page**
   - Purpose: exercise workflow hub and learner-facing exercise publishing state.
   - Should include:
     - exercise generation entry points,
     - browse links to existing exercise sets,
     - publish/unpublish controls (for authorized users),
     - default summary listing only the **most recent set per exercise type**.

## Near-term implementation checklist

- [x] Top-level sub-page split (Annotation / Images / Exercises).
- [x] Move collaborator management to top-level page.
- [x] Move “View via server” to top-level page.
- [x] Move segmentation phase-1 trigger from Annotation to Images and gate it on need.
- [x] Show existing image assets in Images hub.
- [x] Show latest-per-type exercise sets in Exercises hub.
- [ ] Add explicit “show history” UI for older exercise-set versions (optional advanced mode).
- [ ] Add compact progress indicators (ready/incomplete) on top-level sub-page buttons.

## Relationship to other roadmap docs

- `docs/roadmap/django-platform.md` covers broad platform architecture and implementation details.
- `docs/roadmap/image-generation-pipeline.md` covers image generation internals.
- `docs/roadmap/exercises.md` covers exercise generation logic and pedagogy.
- This document focuses specifically on **user-facing placement and navigation conventions**.


## Localization and inclusion track

### Localization for designated interface languages
- Support a configurable set of UI languages.
- Use AI-generated draft translations for fast bootstrap, followed by human review/edit workflows.
- Keep locale strings versioned so UI copy updates can be retranslated incrementally.

### Smartphone-first UX
- Prioritize phone layouts for key learner/teacher flows (read/play/exercises/review).
- Define compact navigation patterns and larger touch targets for annotation/exercise actions.
- Budget page weight and media loading for lower-bandwidth mobile contexts.

### Indigenous-user UX considerations
- Validate copy, navigation metaphors, and onboarding with Indigenous users/educators during design reviews.
- Provide culturally appropriate defaults and avoid forcing Western classroom assumptions in core flows.
- Track feedback items explicitly in UX backlog and verify fixes in follow-up sessions.


## Right-to-left (RTL) UX requirements

Practical target languages for first delivery: **Arabic** and **Persian**.

- Introduce a shared language-direction registry (`ltr`/`rtl`) used by server and templates.
- Apply `dir` and `lang` attributes at page/container level so browser bidi handling is predictable.
- Mirror key layout patterns for RTL (navigation alignment, card/list metadata placement, button groups, pagination direction).
- Ensure mixed-script readability (Arabic/Persian with Latin tokens, numbers, URLs, model names).
- Verify mobile layouts in RTL mode (touch targets, overflow, truncation, exercise options).
- Add regression checklist/screenshots for both LTR and RTL on project, annotation, images, exercises, and content pages.
