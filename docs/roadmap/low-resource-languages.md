# Roadmap: support for low-resource / AI-weak languages

This roadmap document covers cases where LLM-based annotation quality is poor or unavailable for the project language.

## Why this matters

Some languages are underrepresented in model training data. For these, fully automated annotation can be unreliable.
C-LARA-2 should still support these languages for teaching and content publishing.

## Product goal

Allow complete project lifecycle (annotation, image generation, HTML compilation, publication, social/community workflows)
for low-resource languages, with manual-first annotation and strong structural validation.

---

## 1) Manual annotation editor (core requirement)

### Scope
Provide an editing interface for all annotation stages, including:
- segmentation (pages/segments/tokens),
- translation,
- MWE,
- lemma,
- gloss,
- romanization,
- audio metadata.

### Requirements
- JSON editing should not be raw-only by default; provide structured form/table views.
- Enforce formal consistency constraints before save:
  - token arrays remain aligned with segment surface,
  - MWE ids remain valid and refer to existing tokens,
  - required annotation fields have correct type,
  - no broken references in audio/image paths.
- Show clear validation errors with pinpointed location (page/segment/token).

### Recommended architecture
- Validation layer shared between API and UI.
- Stage-specific schema validators + cross-stage consistency checks.
- Save as new version/checkpoint with audit metadata.

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
