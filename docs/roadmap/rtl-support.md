# Roadmap: right-to-left (RTL) language support

This roadmap captures the work required to provide robust RTL support in C-LARA-2, matching existing C-LARA behavior.

Initial high-priority RTL languages:
- Arabic
- Persian

## 1) Direction metadata as a first-class platform concept

### Requirement
Maintain a canonical language-direction mapping used consistently across pipeline, platform, and rendering.

### Plan
- Add a central declaration source (e.g. config/registry) mapping language codes to writing direction (`ltr` or `rtl`).
- Include direction metadata in project settings and compile/run metadata where relevant.
- Ensure APIs/views/templates can read the same source of truth (no duplicated hard-coded lists).

## 2) Pipeline and annotation implications

### Requirement
Annotation data must remain structurally stable regardless of visual text direction.

### Plan
- Keep token indexing and offsets based on logical order, not visual order.
- Verify segmentation/tokenization behavior for Arabic/Persian punctuation and whitespace patterns.
- Ensure MWE/lemma/gloss alignment remains index-safe in RTL and mixed-script segments.
- Preserve direction metadata through artifact save/load and source bundle export/import.

## 3) Conventional UX and annotation-editor implications

### Requirement
Project and editing interfaces must be direction-aware.

### Plan
- Apply `dir` and `lang` attributes at page/section level.
- Mirror layout for major navigation/control regions where needed.
- Validate mixed-script UI elements (numbers, URLs, model IDs, filenames) in RTL contexts.
- Add explicit RTL scenarios to UX and editor acceptance checklists.

## 4) Compile/HTML rendering implications

### Requirement
Compiled learner-facing HTML must render RTL text naturally and consistently.

### Plan
- Set document/section direction in compiled HTML based on language metadata.
- Ensure hover/click behavior, concordance links, and popups/tooltips remain visually correct in RTL.
- Validate placement of generated page images and captions in RTL reading flow.
- Check PDF/print paths (if used) for direction and punctuation stability.

## 5) Testing strategy

- Add fixture texts for Arabic and Persian in segmentation/annotation/compile tests.
- Add end-to-end compile checks asserting direction markers in HTML output.
- Add platform UI tests (or smoke checklist) in both LTR and RTL modes for key pages.
- Add regression tests for mixed-script tokens to catch bidi edge cases early.

## Incremental delivery phases

### Phase A
- Central direction registry + project-level direction exposure.
- Compiled HTML direction markers + smoke checks for Arabic/Persian.

### Phase B
- Annotation/editor RTL usability fixes and mixed-script robustness.
- UX mirroring for key project/exercise/content screens.

### Phase C
- Full regression suite coverage and docs/playbooks for adding further RTL languages.

## Success criteria

- Arabic and Persian projects are usable end-to-end without direction-related layout or annotation corruption.
- Direction handling comes from one source of truth and is not duplicated ad hoc.
- RTL behavior is covered by automated tests and explicit manual smoke checks.
