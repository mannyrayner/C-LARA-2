# Picture dictionaries roadmap

## 1) Concept and scope

A **picture dictionary** is a shared lexical resource that links lexical entries to images.

Each entry minimally contains:
- surface form(s),
- lemma,
- part of speech (POS),
- language,
- one or more associated images,
- optional metadata (source, curation status, notes, difficulty level, tags).

The primary goal is to support:
1. richer reading support ("picture glosses" for lexical items), and
2. picture-based exercise types.

---

## 2) Pragmatic first implementation in C-LARA-2

### 2.1 Project-as-dictionary pattern

The fastest path is to realise a picture dictionary using existing project infrastructure:
- one project per dictionary,
- one page per lexical entry,
- existing lemma/POS annotation to disambiguate entries,
- existing image-generation pipeline for dictionary images.

This keeps v1 low-risk by reusing current storage, UI, and generation components.

### 2.2 Lexical entry identity

For lookup and deduplication, use a canonical key such as:

`(language, lemma, pos)`

with optional refinement later (e.g. sense id) if ambiguity requires it.

---

## 3) Ownership, governance, and sharing model

Picture dictionaries are community-level shared resources.

- **Owner role:** community organiser.
- **Visibility:** available to members of the associated language community.
- **Edit permissions:** organiser-managed (initially organiser-only; later optionally delegated editors).

Auditability requirements:
- who added/removed entries,
- when entry images were (re)generated,
- provenance of bulk imports.

---

## 4) Organiser operations

Provide explicit organiser-facing commands/actions.

## 4.1 Compile dictionary
- Build/refresh dictionary artifacts and indexes.
- Validate canonical keys and detect conflicts/duplicates.

## 4.2 Add given words
- Input: explicit word list (optionally with lemma/POS hints).
- Behaviour: create missing entries and queue image generation as needed.

## 4.3 Remove given words
- Input: explicit word list or canonical keys.
- Behaviour: remove entries (or soft-delete with recovery window in later versions).

## 4.4 Add words from text (only if missing)
- Input: source text/project.
- Behaviour:
  1. run/consume lemma+POS analysis,
  2. extract candidate `(lemma, pos)` pairs,
  3. add only missing entries.

Suggested v1 filter for pictureability:
- exclude function words by POS (DET, AUX, PART, etc.),
- exclude very high-frequency stop items,
- optionally whitelist concrete POS classes first (NOUN, VERB, ADJ),
- allow organiser review before commit.

---

## 5) New linguistic pipeline stage: picture glossing

Introduce an optional pipeline stage, e.g. `picture_gloss`.

Preconditions:
1. lemma stage output exists,
2. a suitable picture dictionary is configured for the project/language,
3. dictionary index lookup is available for `(language, lemma, pos)`.

Output:
- annotation payload linking tokens to picture-gloss candidates,
- confidence/status flags (exact match, fallback match, unresolved).

Failure handling:
- unresolved items should not block compilation,
- fallback to existing behaviour (audio/concordance only).

---

## 6) Rendering and learner UX

If a lexical item has a picture gloss, HTML interaction should be enhanced:
- click/tap lexical item,
- show image gloss in the same interaction surface as existing lexical support,
- keep current audio + concordance behaviour, now augmented by picture.

Design principle:
- picture glosses are additive, not disruptive; existing lexical UX remains intact.

---

## 7) Exercise extensions using picture dictionaries

Picture dictionaries enable new exercise families.

## 7.1 Image → word multiple-choice
- learner sees an image,
- chooses correct word from distractors.

## 7.2 Word → image multiple-choice
- learner sees a word,
- chooses correct image from distractors.

Future variants:
- typed response instead of MCQ,
- graded distractors by semantic similarity,
- adaptive difficulty via learner history.

---

## 8) Suggested phased delivery

## Phase A (quick win)
- Create dictionary as standard project pattern (one page per entry).
- Add organiser commands: compile/add/remove/add-from-text.
- Reuse existing image pipeline for entry images.
- First-cut compile semantics:
  - run linguistic pipeline from `segmentation_phase_2` to `compile_html`,
  - run dictionary-targeted image generation using shared style if available,
  - default image options for dictionaries:
    - **no-context** (do not pass full story context or element context),
    - **missing-only** (generate only for pages currently missing an image).

## Phase B
- Add optional `picture_gloss` pipeline stage.
- Wire lookup outputs into compiled HTML interaction.

## Phase C
- Add picture-based exercise generators and runtime handlers.
- Improve filtering/disambiguation and governance tooling.

---

## 9) Open questions

1. Should v1 allow only one image per `(lemma, pos)`, or multiple ranked images?
2. How should we handle polysemy beyond POS (sense-level disambiguation)?
3. Should dictionary entries be soft-deleted for audit/recovery?
4. Should organiser operations be synchronous (small sets) and queued (bulk)?
5. How should communities discover/reuse dictionaries across projects?

---

## 10) Success criteria

- Organisers can build and maintain a usable dictionary with low friction.
- Projects can optionally enable picture glossing without breaking existing flows.
- Compiled HTML displays picture glosses when available.
- At least one picture-based exercise type is functional end-to-end.

---

## Cross-reference

- Image-pipeline details and dictionary-specific image options are tracked in:
  - [image-generation-pipeline.md](image-generation-pipeline.md)
