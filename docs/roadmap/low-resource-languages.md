# Roadmap: support for low-resource / AI-weak languages

This roadmap document covers cases where LLM-based annotation quality is poor or unavailable for the project language.

## Why this matters

Some languages are underrepresented in model training data. For these, fully automated annotation can be unreliable.
C-LARA-2 should still support these languages for teaching and content publishing.

## Product goal

Allow complete project lifecycle (annotation, image generation, HTML compilation, publication, social/community workflows)
for low-resource languages, with manual-first annotation and strong structural validation.

---

## 1) Manual annotation editor

This is now tracked as a cross-language roadmap item: **`docs/roadmap/manual-annotation-editor.md`**.

For low-resource languages, manual editing remains the central enabling workflow and should be treated as a prerequisite for broad adoption.

### 1.1 New feature: page-oriented manual annotation mode

For low-resource/AI-weak workflows, teams have requested a **page-oriented editing mode** similar to earlier C-LARA behavior.
This mode is intended for projects where annotators know in advance that annotation will be manual from the start.

#### Product intent

- Present **all annotation information for one page in one place**.
- Keep editing affordances and validation semantics consistent with the normal manual editor
  (see `docs/roadmap/manual-annotation-editor.md`).
- Include the page image (if available) so linguistic annotation and visual context are co-located.
- Reduce context switching between stage-specific screens.

#### Core UI behavior

For each page:

1. Show page text/segments/content elements in logical order.
2. Show current values for enabled annotation layers (translation, MWE, lemma, gloss, romanization, audio metadata as available).
3. Show page image if present (top or bottom according to project setting).
4. Provide **per-page show/hide controls** for annotation layers:
   - toggle translation
   - toggle MWE
   - toggle lemma
   - toggle gloss
   - toggle romanization
   - toggle audio metadata
5. Persist editor visibility preferences per user/project (nice-to-have in first cut; required in later iteration).

#### Editing and validation model

This mode is a **presentation/workflow layer**, not a separate annotation format.

- Save payloads must remain stage-compatible with existing validators.
- Segmentation constraints remain unchanged:
  - no character-level edits in segmentation views,
  - boundaries only.
- Annotation constraints remain unchanged:
  - structure locked to segmentation snapshot,
  - edit annotation fields only.
- Cross-stage checks (especially MWE/lemma/gloss consistency) are reused exactly as in normal manual editing.

#### Navigation and ergonomics

- Primary navigation is page-by-page (previous/next/jump-to-page).
- Optional quick links from validation errors to the exact page/segment/content element field.
- Optional “focus mode” per page for dense annotation tasks.
- Optional compact vs expanded row layout to support long morphological annotations.

#### Implementation notes (first cut)

- Reuse existing manual editor form components and validators wherever possible.
- Add a page-oriented container view that composes existing annotation widgets by page.
- Keep API contracts stable; avoid introducing parallel stage schemas.
- Ensure compatibility with generated images and image placement settings.

#### Acceptance checks (phase-in)

- Annotator can complete all manual annotation for a page without leaving the page-oriented view.
- Page image is visible on the same screen when available.
- Show/hide controls work independently per page and layer.
- Saved outputs pass existing structural and cross-stage validation.
- Compile/publish behavior is unchanged relative to equivalent edits made in normal manual views.

---

## 2) Human-in-the-loop revision for AI output

Even in stronger languages, manual revision is valuable.

### Workflow
1. Run AI stage (optional).
2. Open review/editor view with diffs against prior version.
3. Accept/modify/reject entries.
4. Save reviewed stage output.
5. Continue with downstream pipeline stages.

### Key feature
“Lock reviewed annotations” option so later reruns avoid overwriting approved manual edits unless explicitly forced.

---

## 3) Image generation via pivot-language support

Even when annotation quality is weak, image generation can still be strong if prompts are generated from a pivot language
(e.g., English or French).

### Plan
- Add optional pivot translation step for image prompts only.
- Maintain explicit provenance:
  - source text snippet,
  - pivot translation,
  - final image prompt.
- Let user edit pivot text before image generation.

This preserves access to style/element/page-image functionality for low-resource-language projects.

---

## 4) Compatibility with publishing and community features

Low-resource-language projects should be first-class citizens in the social layer.

### Must support
- publish + content browsing,
- metadata and access tracking,
- comments/ratings,
- community assignment,
- image feedback/regeneration loops.

No feature should assume that annotations are AI-generated.

---

## Delivery phases

### Phase A
- Manual editor MVP for segmentation + lemma/gloss + translation.
- Strict validators and versioned saves.

### Phase B
- Extend manual editor to MWE + romanization + audio metadata.
- Diff/review tools for AI-assisted workflows.

### Phase C
- Pivot-language image prompt pipeline and provenance UI.
- Full integration with community workflows.

## Success criteria

- A project in an AI-weak language can be completed end-to-end with manual annotations.
- Invalid edited structures are blocked with actionable feedback.
- Published outputs are usable and discoverable exactly like other projects.
