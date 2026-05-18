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
- Current implementation detail (`projects/<id>/annotation/manual/page-oriented/`):
  1. If `segmentation_phase_1` is missing, the user first inserts `<page>` and `||` boundaries.
  2. If `segmentation_phase_2` is missing, the user then inserts token boundaries with `|`/`¦`.
     - Initial token boundary suggestions now split punctuation separately (same default style as the dedicated segmentation phase 2 editor).
  3. Once segmentation exists, the page-oriented annotation table is shown for translation/MWE/lemma/gloss/romanization.
     - Whitespace-only tokens are intentionally hidden in this table, consistent with stage-specific annotation views.
- Navigation note: page-oriented manual annotation remains linked from annotation home, but is no longer linked from manual top-level.

#### Acceptance checks (phase-in)

- Annotator can complete all manual annotation for a page without leaving the page-oriented view.
- Page image is visible on the same screen when available.
- Show/hide controls work independently per page and layer.
- Saved outputs pass existing structural and cross-stage validation.
- Compile/publish behavior is unchanged relative to equivalent edits made in normal manual views.
- Phase 2 token-boundary defaults are punctuation-aware and preserve exact text hash constraints.
- Whitespace-only tokens are not rendered as editable rows in page-oriented annotation tables.

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

## 5) Audio for languages without usable TTS

Some low-resource languages will not have usable text-to-speech support. For these projects, audio should be optional at first, and then community-recorded. This is tracked in **ISSUE-0016**.

### 5.1 Phase A: no-TTS / no-audio mode

Status: **implemented as the first no-audio fallback**. Projects can now be configured to use either normal TTS audio or no audio / skip TTS. In no-audio mode, the audio pipeline stage skips external TTS calls, removes stale audio annotations from the stage payload, and compilation strips audio annotations before HTML rendering so the final pages do not contain broken audio links or empty audio controls.

Urgent target: have a safe minimal workflow before the Kok Kaper community visit on **2026-06-01**.

- Add a project/content-owner option, or an equivalent language/community setting, that marks the project language as not having useful TTS.
- When this setting is active, the pipeline audio stage must not request or insert TTS-generated audio.
- Compilation should continue successfully and final HTML should omit audio controls/references where no recorded audio exists.
- The UI should explain that audio has intentionally been disabled or deferred, rather than presenting it as a processing failure.

Acceptance checks:

- A non-TTS project can pass through the audio stage without external TTS calls.
- Published/compiled output contains no broken audio links or empty audio controls.
- Existing TTS-capable projects keep their current behavior.

### 5.2 Phase B: community-recorded audio dictionary

A better long-term workflow should let community members record the audio needed for texts. This should be designed as a community-specific **audio dictionary**, but probably not merged with the picture dictionary: picture-dictionary entries are lemma-oriented, while audio entries need to be surface-word- and segment-oriented.

Data/workflow requirements:

1. During the audio stage for a non-TTS project, record the surface words and segments requiring audio in the community audio dictionary.
2. Associate each word/segment entry with every text where it has been observed, so contributors can prioritize recordings by current teaching material.
3. Add a view reachable from community member pages, such as `communities/<community>/member/`, for a selected text's needed audio.
4. In that view, allow members to play existing recordings and record/rerecord word or segment audio using MediaRecorder or a similar browser API.
5. Decide whether to support multiple recording versions per entry, including a preferred/approved recording marker and review history.
6. When recorded audio exists for a non-TTS project, the audio annotation stage should insert the selected recordings into annotated text using the same downstream structure currently used for TTS-generated audio.

Open design questions:

- Permissions: which community roles may record, rerecord, approve, or retire audio?
- Moderation: should organiser approval be required before audio is used in compiled/published content?
- Storage: how should audio files be named, versioned, deduplicated, backed up, and associated with project artifacts?
- Granularity: when should the platform prefer a full segment recording over concatenating word recordings?
- Review UI: how should disagreements or multiple speaker variants be presented to organisers and learners?

## 6) Community model for Indigenous-language workflows

To support the Indigenous-language collaboration model used in C-LARA, add a first-class **Community** object
plus explicit community roles and moderation/review flows.

### 6.1 Core entities and roles

#### Community (new object)

Minimum fields:

- `name`
- `language` (or language code)
- `description` (optional)
- `is_active`
- audit timestamps (`created_at`, `updated_at`)

#### Community membership (new relation)

Many-to-many relation between users and communities with role metadata.

Roles:

- `organiser`
- `member`

#### Privilege model

- Platform **admin** can:
  - create/edit/deactivate communities,
  - associate a community with a language,
  - assign/remove community organisers.
- Community **organiser** (also admin in phase 1, per requirement) can:
  - add/remove community members,
  - manage community review workflows for projects/images.

### 6.2 Access control: community-only texts

Add project/content visibility mode:

- public (existing behavior),
- private/owner-collaborators (existing behavior),
- **community-only** (new).

For community-only resources:

- only members of the linked community may view content,
- organiser/admin retain management access,
- non-members see explicit access-denied messaging.

### 6.3 Community image review workflow (multi-variant page images)

For meaningful community review, page-image generation must support multiple candidates per page.

#### Generation changes

- Extend page-image generation settings to allow `variants_per_page` (e.g., 1..N).
- Persist each variant as a separate candidate asset under page scope with metadata:
  - variant index,
  - prompt/revised prompt,
  - generation model/settings,
  - provenance timestamps.

#### Reviewer workflow (community member)

- Access community projects.
- Review one page at a time.
- See all generated variants for that page on a single screen.
- For each variant, submit:
  - thumbs-up / thumbs-down,
  - optional comment when thumbs-down (improvement suggestion).

#### Organiser workflow

- View aggregate review outcomes for each page/variant.
- Mark specific variants/pages for regeneration.
- Trigger regeneration for flagged pages (possibly with revised prompts informed by comments).

### 6.4 Data model additions for image review

Add entities similar to:

- `ProjectPageImageVariant`
  - links project + page number + variant asset info.
- `CommunityImageReview`
  - links reviewer + project + page + variant,
  - verdict (`up`/`down`),
  - optional comment,
  - timestamp.
- `CommunityImageRegenerationFlag`
  - set by organiser,
  - includes reason/status/audit fields.

### 6.5 UI/API implications

- Admin tools:
  - create/manage communities,
  - assign organisers.
- Organiser tools:
  - assign community members,
  - monitor review status,
  - flag/regenerate images.
- Community review UI:
  - page-by-page navigator,
  - side-by-side variant gallery,
  - fast thumbs-up/down controls + comment capture.

### 6.6 Governance, safety, and audit

- Full audit trail for:
  - membership changes,
  - organiser actions,
  - review decisions,
  - regeneration flags.
- Optional anti-abuse controls:
  - per-user review rate limits,
  - duplicate-vote suppression rules,
  - organiser override logs.

### 6.7 Delivery phasing for community feature

#### Phase A (foundation)

- Community object + membership roles.
- Admin creates community, sets language, assigns organiser.
- Organiser assigns members.
- Community-only visibility gate for project/content viewing.

#### Phase B (review MVP)

- Multi-variant page-image generation.
- Community member page-by-page review UI (thumbs + optional comment).
- Organiser dashboard + regeneration flagging.

#### Phase C (workflow hardening)

- Regeneration pipeline integration with review feedback.
- Aggregated analytics/consensus indicators for organiser decisions.
- Extended audit/report exports for partner communities.

### 6.8 Success criteria for community feature

- Communities can be created and managed with clear role boundaries.
- Community-only texts are inaccessible to non-members.
- Community members can review image variants page-by-page with lightweight feedback controls.
- Organisers can act on community feedback and drive regeneration loops.
- Full community workflow is auditable and operationally manageable.

---

## Delivery phases

### Phase A
- Manual editor MVP for segmentation + lemma/gloss + translation.
- Strict validators and versioned saves.
- Non-TTS/no-audio pipeline mode for low-resource languages without usable TTS.
- Community foundation (community object, roles, and community-only access gate).

### Phase B
- Extend manual editor to MWE + romanization + audio metadata.
- Community-recorded audio dictionary MVP for surface words and segments.
- Diff/review tools for AI-assisted workflows.
- Community image review MVP with multi-variant page images and organiser flagging.

### Phase C
- Pivot-language image prompt pipeline and provenance UI.
- Full integration with community workflows.
- Community workflow hardening, analytics, and export/audit improvements.

## Success criteria

- A project in an AI-weak language can be completed end-to-end with manual annotations.
- Invalid edited structures are blocked with actionable feedback.
- Published outputs are usable and discoverable exactly like other projects.
- Indigenous-language community governance, image-review loops, and community-recorded audio workflows are supported end-to-end.
