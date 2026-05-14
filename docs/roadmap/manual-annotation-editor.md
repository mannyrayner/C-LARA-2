# Roadmap: manual annotation editor

This roadmap defines the **manual annotation editor** for C-LARA-2. It is now largely an implementation-status and next-UX-improvements roadmap rather than a greenfield plan: structured editors exist for individual linguistic stages, and the page-oriented editor supports editing all stages together in a page-centric workflow.

## Current status (May 2026)

Most of the core roadmap is now implemented and stable:

- **Stage-specific structured editors** exist for the main manual editing path:
  - `segmentation_phase_1`: edit page and segment boundaries while preserving text characters.
  - `segmentation_phase_2`: edit token/content-element boundaries while preserving text characters.
  - translation: edit segment-level translation annotations.
  - MWE: edit token-level MWE IDs and segment-level MWE summaries.
  - lemma/POS: edit token-level lemma and POS annotations.
  - gloss: edit token-level gloss annotations.
  - pinyin/romanization: edit token-level romanization annotations.
- **Page-oriented editing** is implemented at `projects/<id>/annotation/manual/page-oriented/` and gives annotators a page-by-page view over segmentation and annotation data.
- **Validation and save behavior** are stable enough for normal manual curation:
  - segmentation saves preserve the underlying character sequence;
  - annotation saves preserve the approved segmentation/token structure;
  - saves create versioned stage artifacts where appropriate;
  - whitespace-only tokens are hidden in annotation tables to reduce visual noise;
  - edited stage artifacts remain compatible with downstream compile/publish workflows.

The remaining work is therefore mainly about **ergonomics**, **cross-stage quick fixes**, and **collaborative review**, rather than building the basic editor from scratch.

## Why this matters

Manual editing is required for:

- low-resource/AI-weak languages,
- quality control in high-resource languages,
- teacher-led curation workflows,
- safe correction of AI outputs before publishing.

The current editors make this possible, but Branislav and Rina's UX feedback highlights that some cross-stage tasks are still too laborious, especially MWE correction.

## Scope and stage model

The editor supports all linguistic stages through two editing modes:

1. **Segmentation operations** (structure editing, text-preserving):
   - `segmentation_phase_1`: edit page/segment boundaries.
   - `segmentation_phase_2`: edit content-element/token boundaries.
2. **Annotation operations** (annotation editing, structure-preserving):
   - translation,
   - MWE,
   - lemma/POS,
   - gloss,
   - romanization,
   - audio metadata where surfaced.

The crucial distinction remains:

- segmentation edits operate on plain text and change boundaries only,
- annotation edits operate on already structured text (pages/segments/content elements) and must not change structure.

## Editing constraints (must enforce)

### A. Segmentation constraints

- **Never edit text content** in manual segmentation.
- In `segmentation_phase_1`, allow only add/remove/move:
  - page boundaries,
  - segment boundaries.
- In `segmentation_phase_2`, allow only add/remove/move:
  - content-element/token boundaries.
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

## MWE editing: hard case and next UX priority

MWE correction is now the main known pain point.

The problem is that MWE status is not isolated in one field. A single conceptual correction can require coordinated edits across:

- token-level MWE IDs in the MWE stage;
- segment-level MWE group summaries in the MWE stage;
- lemma/POS choices that may have been made under the assumption that the words form one lexical unit;
- gloss choices that may also have been made under the same assumption.

Today, removing an MWE or creating a new MWE can require manually editing many fields. This is error-prone and discouraging, even though the underlying stage-specific editors work.

### Proposed quick-fix operation: remove MWE status

Goal: let an annotator designate a group of words currently tagged as an MWE and issue one command: **Remove MWE status**.

Proposed behavior:

1. User selects an existing MWE group, or selects the token span corresponding to it.
2. UI shows a confirmation dialog summarizing the affected page, segment, tokens, current MWE ID(s), lemma(s), and gloss(es).
3. The system asks an AI helper, with the relevant local stage context, to propose a coordinated patch that:
   - removes the relevant MWE IDs from the MWE stage token annotations;
   - removes or updates the segment-level MWE group summary;
   - updates lemma/POS annotations where they were only valid for the MWE analysis;
   - updates gloss annotations where they were only valid for the MWE analysis;
   - leaves unrelated tokens and annotations unchanged.
4. The user reviews a structured diff before applying the patch.
5. The save path validates that segmentation structure is unchanged and that MWE/lemma/gloss references remain consistent.

### Proposed quick-fix operation: treat words as an MWE

Goal: let an annotator designate a group of words currently not tagged as an MWE and issue one command: **Treat as MWE**.

Proposed behavior:

1. User selects a contiguous token span, or a small set of tokens if non-contiguous MWEs are eventually supported.
2. UI checks that the selection is valid for the current stage policy.
3. The system asks an AI helper, with the relevant page/segment context, to propose a coordinated patch that:
   - creates a stable MWE ID and group summary in the MWE stage;
   - tags the selected tokens with that MWE ID;
   - proposes lemma/POS treatment for the MWE as a lexical unit;
   - proposes gloss treatment for the MWE as a lexical unit;
   - preserves token surfaces and segmentation boundaries.
4. The user reviews a structured diff, with options to accept all, edit fields, or cancel.
5. The save path validates all affected stages together.

### Design principles for AI-assisted MWE quick fixes

- AI should propose patches, not silently apply them.
- Patches should be scoped to the selected page/segment/token span unless the user explicitly requests a broader corpus-level change.
- The prompt should include only the relevant local context plus compact schema instructions.
- The response should be normalized into a typed patch format before touching stage artifacts.
- Validation must enforce text/structure immutability and cross-stage consistency after the patch.
- The UI should show human-readable diffs, not raw JSON patches, by default.
- Every accepted quick fix should be saved as an auditable version/checkpoint.

## Recommended architecture

The implemented editors should be extended with a reusable **cross-stage patch layer**:

- Validation layer shared between API and UI.
- Stage-specific schema validators + cross-stage consistency validators.
- Save as new version/checkpoint with audit metadata.
- Store immutable references to the segmentation snapshot used by each annotation stage.
- Add a typed patch representation for coordinated operations across MWE, lemma, and gloss.
- Add AI-assisted patch proposal functions that produce candidate changes for review.
- Add diff rendering for cross-stage patches at token/span granularity.

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
- Gives AI-judges/evaluation workflows cleaner human-reviewed stage artifacts to compare against generated outputs.

## Page-oriented manual annotation view (implemented behavior)

The page-oriented view (`projects/<id>/annotation/manual/page-oriented/`) is a workflow wrapper over the same stage payloads and validators; it does **not** define a parallel schema.

Current behavior:

1. **Phase 1 fallback**: if `segmentation_phase_1` is missing, the view asks the annotator to add `<page>` / `||` boundaries.
2. **Phase 2 fallback**: if `segmentation_phase_2` is missing, the view asks for token boundaries using `|` or `¦`.
   - Default token suggestions are punctuation-aware (punctuation split into separate tokens, as in the dedicated segmentation-phase-2 editor).
3. **Annotation mode**: once segmentation exists, the view presents per-page annotation fields (translation, MWE, lemma, gloss, romanization) plus page image when available.
   - Whitespace-only tokens are hidden in annotation tables (same presentation approach as stage-specific annotation editors).
4. **All-stage editing path**: annotators can review and correct the main linguistic layers together on a single page-oriented screen, which is now the preferred broad review workflow.

Navigation/entry points:

- Page-oriented mode is linked from annotation home.
- It is intentionally **not** linked from manual annotation top-level.

Persistence constraints in page-oriented mode:

- Segmentation phase 2 saves are anchored to the run that contains the active segmentation phase 1 payload.
- Stage payloads remain fully compatible with existing downstream validators and compile/publish flows.

## Updated delivery plan

### Completed/stable baseline

- Stage-specific manual editors for segmentation, translation, MWE, lemma/POS, gloss, and romanization.
- Page-oriented editor for page-by-page all-stage review and correction.
- Text-preserving segmentation validation.
- Structure-preserving annotation validation.
- Versioned saves/checkpoints for reviewed stage outputs.
- Downstream compile compatibility for edited artifacts.

### Next Step 1 — MWE quick-fix design spike

- Define the typed patch format for cross-stage MWE/lemma/gloss edits.
- Define selection models for:
  - existing MWE group selection;
  - token-span selection for new MWE creation.
- Define validation rules for removing and creating MWEs.
- Draft prompts for AI-assisted patch proposal.
- Decide how much context to include (single segment, page, neighbouring segments, or glossary hints).

### Next Step 2 — Remove MWE status quick fix

- Add UI affordance to select an existing MWE group and choose **Remove MWE status**.
- Ask AI for a coordinated patch over MWE, lemma, and gloss artifacts.
- Render the proposed patch as a structured diff.
- Allow accept/edit/cancel.
- Save all affected stage artifacts atomically if validation passes.

### Next Step 3 — Treat words as MWE quick fix

- Add UI affordance to select tokens and choose **Treat as MWE**.
- Ask AI for MWE ID/group, lemma/POS, and gloss proposals.
- Render the proposed patch as a structured diff.
- Allow accept/edit/cancel.
- Save all affected stage artifacts atomically if validation passes.

### Next Step 4 — Batch MWE review ergonomics

- Add filters for segments with MWE IDs, suspected missing MWEs, or inconsistent MWE/lemma/gloss data.
- Add keyboard shortcuts for common decisions.
- Add “apply similar fix” only after explicit user confirmation and validation.

### Next Step 5 — Collaboration and approvals

- Assignment/review queues, approval states, and lock reviewed annotations.
- Conflict handling for concurrent editors.
- Explicit override workflow for reruns that would replace approved data.

## Success criteria

- Editors can complete and correct projects end-to-end without raw JSON surgery.
- Invalid structures are blocked with actionable diagnostics.
- Manual edits remain stable across pipeline reruns unless explicitly overridden.
- Segmentation edits never alter text characters.
- Annotation edits never alter segmentation structure.
- Page-oriented all-stage editing is the normal broad review route.
- Removing an incorrect MWE can be done with one reviewed command rather than many manual field edits.
- Adding a missing MWE can be done with one reviewed command rather than many manual field edits.
- MWE/lemma/gloss/audio consistency violations are detected before save.

## RTL-specific editor requirements

- The editor must render tokens/segments with the correct base direction (`dir="rtl"`) for RTL languages and preserve that direction on save/reload.
- Cursor movement, token boundary highlighting, and selection behavior must be validated for RTL text and mixed RTL/LTR segments.
- Side-by-side views should keep source and annotation panes direction-aware independently (avoid forcing one global direction).
- Validation/error pinpointing must reference logical token indices consistently regardless of visual ordering.
- Diff/review views must avoid false diffs caused only by bidi control characters or display reordering.
