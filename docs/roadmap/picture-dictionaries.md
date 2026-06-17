# Picture dictionaries roadmap

This roadmap is organized by delivery status so it is easy to see:

1. what is already implemented,
2. what should happen next (near-term),
3. what remains longer-term.

It also preserves the original user-facing intent: picture dictionaries should be the shared, community-trusted resource for image glossing and image-based learning activities.

---

## 1) Current status (implemented or substantially in place)

### 1.1 Core product direction is established

- Picture dictionaries are treated as a community-level lexical resource linked to images.
- The project-as-dictionary pattern is in use for pragmatic delivery:
  - one project per dictionary,
  - one page per entry,
  - lexical metadata (surface/lemma/POS) coming from project processing,
  - image generation/review reusing existing page-image infrastructure.

### 1.2 Seed-dictionary path has been proven

- The Kok Kaper seed flow (legacy project material into a first dictionary) is no longer hypothetical; this has been validated as a practical bootstrap path.
- The “dictionary as central curated source” principle is now shared across review/game planning discussions.

### 1.3 Community/organiser workflow foundations are in place

- Organiser workflows for dictionary-adjacent image review/regeneration now include:
  - explicit page filtering,
  - selection-preserving “selected pages” regeneration,
  - preview/confirm behavior before expensive generation,
  - improved context presentation for reviewers.
- These are important prerequisites for dictionary quality curation, even when the final dictionary UI remains separate.

### 1.4 Text-free image constraints are now wired through generation paths

- The project image setting **“Disallow visible text in images”** is now carried through to organiser-requested page-image regeneration prompts, including picture-dictionary projects that reuse page-image infrastructure.
- This is essential for picture dictionaries because visible written words in the image can invalidate image → word flashcards, make word → image flashcards too easy, and undermine low-text or no-text learner activities.
- The current implementation covers prompt construction for generation/regeneration. Follow-on work should still add automatic image-level diagnostics for accidental visible text in generated assets.

### 1.5 AI diagnostics now help catch low-resource word/gloss mix-ups

- Organiser dictionary workflows now include AI-based language-ID diagnostics for the common low-resource picture-dictionary error where the source-language word and gloss/translation are accidentally swapped.
- The checker classifies the page text and gloss/translation fields against the gloss language, shows warnings for likely problem rows, and provides a collapsible trace table for debugging odd classifications.
- Results are cached at the language-ID item level so repeated checks are cheaper, and the UI displays a “checking consistency” message while review-time checks are running.
- The diagnostics are deliberately advisory: they should alert organisers to suspicious entries, not block legitimate low-resource words that coincidentally resemble English/French forms.

---

## 2) Near-term priorities (next implementation window)

These are the items that should be treated as immediate roadmap work.

### 2.0 Build a unified source-of-truth dictionary workspace (ISSUE-0039)

The next major picture-dictionary step should reduce the current fragmentation between project pages, annotation artifacts, image-generation state, subset artifacts, and organiser review screens. Treat the **picture dictionary itself** as the organiser-facing source of truth, with C-LARA projects and exercise sources derived from it. This is urgent for making Kok Kaper classroom use a viable possibility by 2026-07-13 and is also a strong user-facing example for the EuroCALL 2026 paper due 2026-07-31.

Target entity model:

- A picture dictionary is a curated lexical/image resource associated with one C-LARA-2 project, but conceptually distinct from the project.
- Each dictionary entry should expose and persist, at minimum:
  - surface word,
  - lemma,
  - POS,
  - gloss/translation in the gloss language,
  - organiser suggestions for image generation,
  - concrete prompt variants passed to the image-generation API,
  - generated/selected image variants,
  - readiness, approval, and exercise-exclusion metadata.
- The dictionary should also include a style description and optional background/context information. Prompt generation should combine the surface word or low-resource translation, background/context, style description, and organiser suggestions.

Target organiser workspace:

1. Show a configurable overview where organisers choose visible fields; the default Kok Kaper-style view should probably show surface word, gloss/translation, and selected image.
2. Allow direct editing of entry fields without requiring a detour through page-oriented project editors.
3. Batch-select entries and create or refresh prompt variants.
4. Batch-select entries and generate/regenerate images from current prompts, creating prompts first when necessary.
5. Create, retrieve, and modify named subdictionaries by adding/removing entries while preserving provenance to the canonical dictionary.
6. Create supported exercises from the full dictionary or a subdictionary.
7. After every mutating operation, synchronize derived project/stage/subset/exercise artifacts so the project remains a consistent projection of the dictionary rather than an independent competing source.

Sequencing guidance:

- **First cut implemented (2026-06-16):** the community organiser page now has a unified table showing word, lemma, POS, gloss/translation, image-generation prompt, and selected image together. Saving edits updates the dictionary registry, derived project pages/source text, and annotation stage artifacts.
- **Second cut implemented (2026-06-16):** the unified block now includes dictionary-level background information, the style brief, per-row selection checkboxes, per-row organiser suggestions, and selected-row controls to create prompts, create images, or create prompts plus images. Background and suggestions are persisted in workspace metadata. Prompt creation now calls the configured text model to produce concrete editable prompts from row metadata/background/style/suggestions, and selected-row image creation uses the existing page-variant generation path while selecting the newest generated variant back into the dictionary view.
- UX cleanup implemented (2026-06-17): the unified entry rows are grouped into a narrower two-tier layout, with Select all, Select incomplete, Select none, Display all, and Display incomplete only controls at the top of the table. Incomplete rows now include entries missing lemma, POS, gloss/translation, prompt, or image. The older placeholder-sync/compile controls have been removed from the organiser page in favour of direct dictionary operations, and selected rows can now ask AI to create missing lemma/POS/translation information, missing/default prompts, and missing images as needed; surface-only prompts are only considered missing when the row has no image, to avoid separating a liked image from the prompt that produced it. Next, make this workspace more useful for Sophie testing by adding richer prompt-variant management, clearer image-generation progress feedback, and tighter exercise/subdictionary integration from the same selected-row workspace.
- Then fold existing subset-project and exercise-source workflows into the same source-of-truth model, keeping **ISSUE-0037** for the already active subdictionary implementation/review track.
- We do not need to preserve an existing live classroom workflow yet, but still prefer incremental migration behind the organiser workflow so laptop/Sophie testing can identify issues early; keep regression checks around image identity, deleted words, subset synchronization, and exercise generation.


### 2.1 Improve **Compile dictionary** behavior for low-resource languages

For `communities/xxx/organiser/` dictionary compile:

- Support deterministic **partial compile** when full AI pipeline stages are not viable:
  1. reliably fill `segmentation_phase_1` and `segmentation_phase_2`,
  2. create placeholder stage artifacts for translation, MWE, lemma, gloss, and pinyin,
  3. clearly mark placeholders as manual-completion-required.
- Finish with explicit organiser guidance explaining exactly what was auto-produced vs placeholder-only.
- Provide a direct link to page-by-page manual annotation so the organiser can immediately continue the workflow.

### 2.2 Improve compile feedback/progress in AI-enabled languages

- Current feedback should not stop at “linguistic pipeline complete”.
- Add clear post-linguistic status updates for dictionary image generation, including:
  - image generation started,
  - progress updates where possible,
  - completion summary (success/failure counts).

### 2.3 Make organiser dictionary entry lists consistent and easy to scan

In the picture-dictionary entries list under `communities/xxx/organiser/`:

- Show entries in **alphabetical order** (case-insensitive, by display form).
- Use a **uniform, project-derived display format** with surface + lemma + POS, e.g.:
  - `homme (lemma: homme) [NOUN]`
  - `femme (lemma: femme) [NOUN]`
  - `habiter (lemma: habiter) [VERB]`
  - `petit (lemma: petit) [ADJ]`
  - `maison (lemma: maison) [NOUN]`

This is both a usability improvement and a consistency requirement for selection/filtering operations.

### 2.4 Keep dictionary curation status explicit

- Continue to enforce practical readiness states (candidate / needs image / image generated / approved-game-ready / excluded / needs review).
- Ensure game generation and glossing use curated-ready entries, not raw/unreviewed entries.

### 2.5 Consolidate text-free dictionary image quality (linked to ISSUE-0028)

Image-based flashcards are now working in both directions, but they are undermined when dictionary images contain visible written words.

- Treat “no overlaid readable text in the generated image” as a default quality requirement for picture-dictionary images.
- Keep the implemented generation/regeneration prompt wiring covered by tests, especially the organiser review path that creates additional variants.
- Add organiser-facing diagnostics so entries can be flagged/rejected when text is detected in generated images.
- Add lightweight regression checks for dictionary image assets used by flashcards.

Track remaining image-quality work in **ISSUE-0028** (`docs/issues/issues/ISSUE-0028.json`).

### 2.6 Refine low-resource dictionary consistency diagnostics

The first advisory AI diagnostics are in place, but they should be treated as a practical alert system rather than a solved classifier.

- Continue tuning the single-field language-ID prompt and warning wording as more Kok Kaper/English and other low-resource examples are reviewed.
- Preserve the collapsible trace table because it is useful for debugging false positives/negatives.
- Consider adding a “mark checked / ignore this warning” organiser action if repeated benign warnings become distracting.
- Keep diagnostics non-blocking except in explicit add-row flows where the organiser can immediately correct a suspected swap.

### 2.7 Add organiser-created dictionary subset projects (ISSUE-0037)

Sophie’s Kok Kaper follow-up request is tracked as **ISSUE-0037**, now raised to **P1** because this is needed for real classroom testing beginning around 2026-07-13. It adds an immediately useful authoring workflow: a Community Organiser should be able to carve out a smaller vocabulary from an existing picture-dictionary project and save it as a named subset project/exercise source.

First-cut status (implemented and ready for server deployment/Sophie review):

- Community organisers can manually create a named subset project from selected active dictionary entries under `communities/.../organiser/`, with candidate rows showing translations/glosses to make selection/debugging easier.
- Existing subset projects can be loaded back into the organiser page, edited, and re-saved.
- Organisers can ask AI to pre-fill the checked entries from a natural-language subset description; for low-resource dictionaries the selection prompt is explicitly translation/gloss-driven and the organiser must still review/adjust before saving.
- Each subset writes provenance artifacts under `picture_dictionary_subsets/<subset_id>/` and creates a lightweight project with source text/stage artifacts derived from the selected dictionary rows.
- Subsets are hidden from the organiser image-review dashboard, and direct review URLs redirect organisers back to the main organiser page, so image curation remains on the canonical picture dictionary.
- The flow has been exercised successfully end to end: description-based prefill, subset creation, and flashcard exercise generation from the subdictionary work as intended. Next step is deployment to the server on 2026-06-14 and Sophie review before July classroom testing.

Remaining follow-on work after deployment/user review:

- Improve automatic synchronization after canonical dictionary images/text are changed outside the subset edit/save flow.
- Show exercise-specific exclusion/readiness reasons when a selected entry is not approved/game-ready.

User goal:

- Start from a community picture dictionary or ordinary project with one-page-per-entry structure.
- Enter a natural-language command such as “make a set for animals”, “words useful for a family visit”, or “the 12 easiest words for beginners”.
- Optionally let the system propose matching pages/entries from a natural-language description, then show a review screen where the organiser can add/remove pages manually before saving.
- Use the resulting subset as a stable source vocabulary for flashcards, word scrambles, crosswords, and later activity types, while keeping the main picture dictionary as the canonical source of images and entry content.

Implementation expectations:

1. Reuse existing page/entry metadata wherever possible: surface form, lemma, POS, translation/gloss, readiness status, and approved image reference.
2. Keep the parent project/dictionary unchanged; the subset project should be a derived artifact or lightweight project clone with provenance back to parent page ids.
3. Keep subset content synchronized with the main picture dictionary where practical: changes to canonical images or entry text should be reflected in subsets rather than forked silently.
4. Do **not** expose normal organiser image-review/regeneration actions directly on subset projects; image curation should happen in the main picture dictionary to avoid confusing divergent approval states.
5. Require organiser confirmation before creating or overwriting a subset project, and allow later retrieval/editing of the selected page list.
6. Default exercise generation to approved/game-ready entries, while allowing organisers to see why pages were excluded.
7. Support manual adjustment even when the natural-language selection is imperfect; the AI proposal is a convenience, not the authority.

Suggested artifact shape:

```text
picture_dictionary_subsets/
  <subset_id>/
    config.json        # name, parent project, command, filters, created_by
    pages.json         # ordered selected parent page/entry ids + display labels
    provenance.json    # AI proposal, manual additions/removals, timestamps
```

---

## 3) Longer-term goals

### 3.1 Mature picture-based learning activities

- Maintain both flashcard directions as first-class modes:
  - image → word,
  - word → image.
- Add the newly requested picture-clue puzzle activities once sub-project source selection is available:
  - word scrambles with image clues,
  - crosswords with image clues and simple non-symmetrical layouts.
- Improve distractor quality and lightweight learner feedback/reporting loops.

### 3.2 Broaden governance and delegation safely

- Keep organiser-managed ownership model, with possible delegated editor roles later.
- Improve auditability for who changed entries/images/status and when.

### 3.3 Generalize beyond initial Kok Kaper workflow

- Reuse the same pattern for other communities once low-resource compile + curation UX is stable.
- Keep “dictionary as shared canonical source” consistent across glossing, games, and related workflows.

---

## 4) Scope boundaries and sequencing

To keep delivery realistic, the following should not block near-term goals:

- many additional game types beyond the currently requested flashcards, word scrambles, and crosswords,
- heavy analytics,
- adaptive personalization,
- complex sense-disambiguation UX.

The immediate focus should remain:

1. reliable low-resource compile fallback,
2. explicit organiser feedback during compile/generation,
3. usable and predictable organiser entry-list presentation,
4. continued refinement of text-free image quality and language-confusion diagnostics,
5. organiser-created sub-projects as the source-selection foundation for picture-clue exercises.
