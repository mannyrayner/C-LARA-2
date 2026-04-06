# Roadmap: manual annotation editor

This roadmap defines a **manual annotation editor** that is relevant across all C-LARA-2 languages, not only low-resource settings.

## Why this matters

Manual editing is required for:

- low-resource/AI-weak languages,
- quality control in high-resource languages,
- teacher-led curation workflows,
- safe correction of AI outputs before publishing.

## Scope and stage model

The editor must support all linguistic stages, but with **two different editing modes**:

1. **Segmentation operations** (structure editing, text-preserving):
   - `segmentation_phase_1`: edit page/segment boundaries.
   - `segmentation_phase_2`: edit content-element boundaries.
2. **Annotation operations** (annotation editing, structure-preserving):
   - translation,
   - MWE,
   - lemma,
   - gloss,
   - romanization,
   - audio metadata.

The crucial distinction is:

- segmentation edits operate on plain text and change boundaries only,
- annotation edits operate on already structured text (pages/segments/content elements) and must not change structure.

## Editing constraints (must enforce)

### A. Segmentation constraints

- **Never edit text content** in manual segmentation.
- In `segmentation_phase_1`, allow only add/remove/move:
  - page boundaries,
  - segment boundaries.
- In `segmentation_phase_2`, allow only add/remove/move:
  - content-element boundaries.
- Any operation that changes characters (insert/delete/replace) is invalid.

### B. Annotation constraints

- For translation/MWE/lemma/gloss/romanization/audio:
  - structure (pages/segments/content-element boundaries) is read-only,
  - only annotation fields are editable.
- Validation should reject any payload where structure differs from the approved segmentation snapshot.

### C. Cross-stage consistency constraints

- **MWE precedes lemma/gloss/audio logically**:
  - if content elements share an MWE membership, downstream annotations must remain compatible.
  - Example: elements within the same MWE must not get conflicting lemma analyses.
- **Translation should generally precede gloss**:
  - not an absolute hard dependency,
  - but UI should encourage translators/glossers to consult segment translations while glossing.

### D. UX and validation requirements

- Primary UI is structured (forms/tables/tree controls), with raw JSON as expert fallback only.
- Show validation errors at exact location (page / segment / content element / field).
- Block malformed edits at input time whenever possible (typed controls, constrained choices, relation pickers).
- Optional side-by-side compiled preview for context when available.

## Recommended architecture

- Validation layer shared between API and UI.
- Stage-specific schema validators + cross-stage consistency validators.
- Save as new version/checkpoint with audit metadata.
- Store immutable references to the segmentation snapshot used by each annotation stage.

## Human-in-the-loop revision flow

1. Run AI stage (optional).
2. Open review/editor view with diffs against prior version.
3. Accept/modify/reject entries.
4. Save reviewed stage output.
5. Continue with downstream pipeline stages.

### Key feature

A **lock reviewed annotations** option so later reruns avoid overwriting approved manual edits unless explicitly forced.

## Integration points

- Works with low-resource roadmap as the core enablement mechanism.
- Feeds corrected artifacts into compile and publish workflows.
- Provides auditable revisions for collaborative/community projects.

## Delivery plan (incremental, ergonomic-first)

### Step 1 — Segmentation editor MVP (structure only)

- Provide robust UI for:
  - page/segment boundaries (`segmentation_phase_1`),
  - content-element boundaries (`segmentation_phase_2`).
- Make text read-only in editor.
- Implement hard validation: text hash before/after must match.
- Version every save.

### Step 2 — Translation + gloss editor (structure locked)

- Introduce annotation editor on top of frozen segmentation structure.
- Translation and gloss side-by-side at segment level.
- Prefer workflow order: translation → gloss (soft guidance, not hard block).
- Enforce structure immutability and per-field validation.

### Step 3 — MWE editor as dependency anchor

- Add dedicated MWE editing view over content elements.
- Persist explicit MWE groups/IDs.
- Add cross-stage checks so lemma/gloss/audio edits cannot silently contradict MWE groupings.

### Step 4 — Lemma/gloss/audio consistency layer

- Add rule checks such as:
  - MWE-linked elements must satisfy shared-lemma consistency rules,
  - downstream annotations reference valid content elements/MWE IDs.
- Show actionable diagnostics and quick-fix suggestions.

### Step 5 — Romanization and advanced review UX

- Add romanization editor with language-aware validation.
- Add diff tools and change-history navigation.
- Improve batch review ergonomics (filter by validation issue type).

### Step 6 — Collaboration and approvals

- Assignment/review queues, approval states, and lock reviewed annotations.
- Conflict handling for concurrent editors.
- Explicit override workflow for reruns that would replace approved data.

## Success criteria

- Editors can complete and correct projects end-to-end without raw JSON surgery.
- Invalid structures are blocked with actionable diagnostics.
- Manual edits remain stable across pipeline reruns unless explicitly overridden.
- Segmentation edits never alter text characters.
- Annotation edits never alter segmentation structure.
- MWE/lemma/gloss/audio consistency violations are detected before save.


## RTL-specific editor requirements

- The editor must render tokens/segments with the correct base direction (`dir="rtl"`) for RTL languages and preserve that direction on save/reload.
- Cursor movement, token boundary highlighting, and selection behavior must be validated for RTL text and mixed RTL/LTR segments.
- Side-by-side views should keep source and annotation panes direction-aware independently (avoid forcing one global direction).
- Validation/error pinpointing must reference logical token indices consistently regardless of visual ordering.
- Diff/review views must avoid false diffs caused only by bidi control characters or display reordering.
