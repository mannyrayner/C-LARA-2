# Manual annotation editor roadmap

## Purpose

Provide a structured, language-agnostic manual annotation workflow so human annotators can correct or replace AI output without editing raw JSON.

The editor must respect pipeline dependencies, preserve data integrity, and make it obvious which stages are ready to edit versus blocked by missing prerequisites.

## Design principles

- **Dependency-first UX**: users should edit stages in an order that matches true data dependencies.
- **Non-destructive editing**: every save is versioned and auditable.
- **Constraint-guided UI**: invalid states are prevented where possible; otherwise flagged clearly.
- **Hybrid workflow**: manual edits and AI regeneration should coexist safely.
- **Low-resource readiness**: support fully manual progression when AI quality is insufficient.

## Stage model and dependency graph

For manual editing, we treat **segmentation phase 1 + segmentation phase 2** as one **virtual Segmentation stage**.

### Virtual Segmentation stage (phase1 + phase2)

- **Input**: raw plain text.
- **Internal phase 1 output**: pages and segments.
- **Internal phase 2 output**: lexical units per segment.
- **Manual UX**: show immutable text with editable boundary markers for:
  - page boundaries,
  - segment boundaries,
  - lexical-unit boundaries.
- **Constraint**: text content itself cannot be modified in this stage.

### Downstream stage dependencies

- **Translation** depends on Segmentation only.
- **MWE** depends on Segmentation only.
- **Lemma** depends on MWE (+ tokenization from Segmentation).
- **Gloss** depends on MWE (+ tokenization; and may optionally use Translation context).
- **Audio** depends on MWE and Lemma (and tokenization).
- **Pinyin/Romanization** depends on tokenization from Segmentation (MWE not required).

## Stage-by-stage UX specification

### 1) Segmentation (virtual)

**Presentation**
- Entire text shown in reading order.
- Visual markers distinguish pages, segments, lexical units.
- Optional synchronized tree panel (`Page > Segment > Lexical unit`) for fast navigation.

**Allowed actions**
- Add/remove/move page boundaries.
- Add/remove/move segment boundaries.
- Split/merge lexical units.

**Disallowed actions**
- Editing raw text characters.

**Validation**
- No empty pages/segments.
- Lexical units must partition each segment (no overlaps/gaps).
- Deterministic export back to canonical segmented representation.

### 2) Translation

**Presentation**
- Segment-by-segment table: source segment + editable translation.

**Allowed actions**
- Add, modify, clear translation for each segment.
- Bulk tools: copy previous machine translation, clear all, regenerate selected ranges.

**Validation**
- Every segment has at most one active translation per target language.
- Unsaved translations block stage completion.

**Notes**
- Translation output should be available to later stages as context (especially Gloss, optionally MWE hints).

### 3) MWE

**Presentation**
- Segment text tokenized into lexical units.
- Annotator can assign MWE ids (`m1`, `m2`, …) to lexical units.
- Segment-level MWE metadata panel for optional labels (e.g., `m1 = phrasal verb`).

**Allowed actions**
- Tag/untag lexical units with one MWE id.
- Rename or delete MWE ids.
- Add optional MWE-level notes/category fields.

**Validation**
- An MWE id must occur on at least two lexical units in the segment.
- All units sharing an MWE id are treated as one MWE object.
- Segment-local ids are permitted in editor; page-global uniqueness can be applied in post-processing.

**Example**
- Segment: *She threw it away.*
- Units `threw` + `away` both tagged `m1`.
- Optional annotation: `m1 = phrasal verb`.

### 4) Lemma and Gloss

These two stages are separate outputs but share crucial constraints from MWE.

**Presentation**
- Token-level grid for each segment with visible MWE overlays.
- For each lexical unit (or MWE group), editable lemma and gloss fields.

**Allowed actions**
- Edit lemma values.
- Edit gloss values.
- Apply edit to all members of an MWE in one action.

**Validation**
- **MWE consistency rule**: components of the same MWE must have consistent MWE-linked annotation behavior (same MWE id and aligned group treatment).
- Highlight conflicts inline; prevent finalization until resolved.

### 5) Audio

**Presentation**
- Segment and lexical/MWE rows each show:
  - current audio status,
  - play controls,
  - provenance (TTS provider/model vs human recording),
  - optional POS/context used for generation.

**Dependencies and behavior**
- Uses MWE structure because MWE audio is generated/stored per full MWE span.
- Uses lemma/POS information for homograph disambiguation when invoking TTS.

**Allowed actions**
- Play current audio for segment/token/MWE.
- Regenerate TTS for selected items.
- (Future) record/re-record human audio when recording workflow is enabled.

**Validation**
- Ensure expected audio assets exist for all required units.
- Surface stale audio when upstream text/lemma/MWE changes invalidate previous renders.

### 6) Pinyin/Romanization

**Presentation**
- Segment displayed as lexical units with editable romanization field per unit.

**Dependencies and behavior**
- Requires Segmentation tokenization.
- Does **not** require MWE annotations.

**Allowed actions**
- Edit romanization values manually.
- Regenerate selected rows via language-specific or AI-backed romanization.

## Implementation plan (phased delivery)

### Phase A — Foundation (data + API + audit)

- Introduce editor-side stage state machine (`not_started`, `in_progress`, `ready_for_review`, `approved`).
- Add versioned save records with `who/when/why` metadata and diff snapshots.
- Add dependency gate checks so stages cannot be finalized out of order.

### Phase B — Segmentation editor (virtual stage)

- Build the combined boundary editor for page/segment/lexical-unit markers.
- Implement strict partition validation and deterministic serializer.
- Add keyboard-first operations for split/merge and boundary navigation.

### Phase C — Translation + MWE editors

- Deliver segment translation editor with bulk operations.
- Deliver token-level MWE editor with multi-select tagging and MWE metadata panel.
- Add validations for minimum MWE cardinality and id integrity.

### Phase D — Lemma + Gloss editors

- Add synchronized lemma/gloss workspace with visible MWE groupings.
- Implement “apply to MWE” and conflict-highlighting workflows.
- Add review mode showing unresolved constraints before approval.

### Phase E — Audio + Romanization editors

- Add audio playback/regeneration UI with provenance and stale-state detection.
- Add romanization editor/regeneration controls.
- Integrate queue/background-job status updates for regeneration actions.

### Phase F — Human recording and low-resource hardening

- Add recording/upload/re-record UX and asset lifecycle management.
- Add offline-first/manual-first path where AI suggestions are optional.
- Add reviewer assignment + approval workflow for educational/community QA.

## Concrete engineering notes

- Prefer storing editor outputs in canonical pipeline-compatible structures to avoid bespoke conversion layers.
- Add migration-safe schema for stage versions and per-stage approvals.
- Implement optimistic locking (or row-version checks) to avoid concurrent overwrite.
- Include regression fixtures for MWE consistency and segmentation partition invariants.
- Ensure compile/export consumes approved manual annotations by default, with explicit fallback toggles.

## Acceptance criteria

- Annotators can complete Segmentation → Translation → MWE → Lemma/Gloss → Audio → Romanization in dependency order without raw JSON edits.
- Invalid MWE or segmentation states are blocked or clearly actionable.
- Every manual edit is auditable and reversible.
- Low-resource workflow remains usable when AI generation is unavailable or poor.
