# Roadmap: manual annotation editor

This roadmap defines a **manual annotation editor** that is relevant across all C-LARA-2 languages, not only low-resource settings.

## Why this matters

Manual editing is required for:

- low-resource/AI-weak languages,
- quality control in high-resource languages,
- teacher-led curation workflows,
- safe correction of AI outputs before publishing.

## Scope

Provide an editing interface for all annotation stages, including:

- segmentation (pages/segments/tokens),
- translation,
- MWE,
- lemma,
- gloss,
- romanization,
- audio metadata.

## Requirements

- JSON editing should not be raw-only by default; provide structured form/table views.
- Enforce formal consistency constraints before save:
  - token arrays remain aligned with segment surface,
  - MWE ids remain valid and refer to existing tokens,
  - required annotation fields have correct type,
  - no broken references in audio/image paths.
- Show clear validation errors with pinpointed location (page/segment/token).

## Recommended architecture

- Validation layer shared between API and UI.
- Stage-specific schema validators + cross-stage consistency checks.
- Save as new version/checkpoint with audit metadata.

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

## Delivery phases

### Phase A

- Editor MVP for segmentation + translation + lemma/gloss.
- Strict validators and versioned saves.

### Phase B

- Extend editor to MWE + romanization + audio metadata.
- Diff/review tools for AI-assisted workflows.

### Phase C

- Collaboration enhancements: assignment, review queues, and approval states.
- Better conflict handling for concurrent edits.

## Success criteria

- Editors can complete and correct projects end-to-end without raw JSON surgery.
- Invalid structures are blocked with actionable diagnostics.
- Manual edits remain stable across pipeline reruns unless explicitly overridden.
