# Roadmap: exercises from C-LARA-2 texts

This roadmap describes how C-LARA-2 should generate and deliver interactive exercises derived from a project text and its annotations.

## Current status (April 2026)

- Cloze: implemented in Django platform.
- Flashcards (first version): implemented for **form → meaning** multiple-choice using glossed tokens, with AI distractor generation and publish/play flows shared with cloze.
- Next flashcard priority: image-based Kok Kaper cards generated from a picture dictionary seeded from the migrated **50 words in Kok Kaper** project.

## Goals

- Automatically generate pedagogically useful exercises from existing project artifacts.
- Support multiple exercise families, starting with:
  1. **Cloze** exercises.
  2. **Flashcards** (text/audio/image variants).
- Reuse existing pipeline annotations (segmentation, lemma, gloss, translation, audio, images, MWE) as exercise input.
- Store generated exercises as project artifacts so they can be reviewed, regenerated, and published.

## Exercise family A: cloze

### Core flow
1. Select candidate segments from the text.
2. Choose one target item to blank out (word or MWE component/pattern).
3. Generate distractors using AI calls constrained by context and difficulty.
4. Package as multiple-choice cloze item.

### Target-selection options
- surface token,
- lemma,
- MWE unit,
- POS-constrained token classes,
- frequency-based or pedagogical curriculum filters.

### Distractor generation constraints
- Same broad lexical category as answer when possible.
- Similar length/form to reduce trivial elimination.
- Avoid duplicates and near-identical inflections.
- Respect language and script.

### Quality controls
- AI-generated distractors validated by rule checks.
- Regenerate item if distractors are too easy/too close/correct in context.
- Optional teacher-review queue before publishing.

## Exercise family B: flashcards

### Core concept
A flashcard presents one information type and asks learner to choose the correct item from another type, with distractors.

### Initial card modes
- **Form → meaning**: word/MWE surface to translation/gloss options.
- **Meaning → form**: translation/gloss prompt to word/MWE options.
- **Audio → form/meaning**: play token/MWE audio and choose text/meaning.
- **Image → form/meaning**: show AI-generated image and choose lexical item/meaning.
- **Form → image**: show a word/phrase and choose the matching image from alternatives.

### Candidate data sources
- token surface,
- lemma,
- gloss/translation,
- token/MWE audio,
- generated image assets,
- picture-dictionary entries and approved/game-ready images,
- POS/MWE metadata.

### Distractors
- AI-generated + retrieval-based hybrid:
  - start from in-project confusable items,
  - for picture-dictionary-backed image cards, first draw distractors from the same approved dictionary so all options are community-curated,
  - supplement with AI proposals only when the curated pool is too small,
  - validate by constraints (POS/script/frequency/semantic distance).

## Storage and lifecycle

Suggested artifact structure:

```text
exercises/
  cloze/
    config.json
    items.json
  flashcards/
    config.json
    items.json
    media_refs.json
```

Each item should store provenance:
- source page/segment/token ids,
- generation prompt/options,
- distractor strategy,
- timestamp and model info.

## UI roadmap

### Authoring side
- Project tab: **Exercises**.
- Controls:
  - choose exercise type,
  - choose count/difficulty,
  - choose sources (whole text, selected pages, selected vocab lists),
  - generate/regenerate/review/publish.

### Learner side
- Exercise player with immediate feedback.
- Session-level score + review mode.
- Optional spaced-repetition queue for flashcards.

## Integration with social features

- Allow comments/ratings per exercise set (future).
- Community-curated exercise packs for language groups.
- Track “problem items” that many users miss; feed into regeneration.

## Incremental delivery plan

### Phase 1 (MVP)
- Cloze multiple-choice using token-level blanks.
- Flashcards: form ↔ meaning and meaning ↔ form.
- Manual regenerate button and JSON artifact persistence.

### Phase 2
- Audio-based flashcards.
- MWE-aware cloze/flashcards.
- Difficulty calibration and distractor QA improvements.

### Phase 3
- Image-based flashcards, with the Kok Kaper MVP as the first concrete target.
  - Seed card candidates from the community picture dictionary created from **50 words in Kok Kaper**.
  - **Prompt = image, options = text** (choose the correct word/meaning for an image).
  - **Prompt = text, options = image** (choose the matching image for a word/phrase).
  - Use same-dictionary approved entries as distractors, with optional AI ranking/filtering.
- Reuse existing project image artifacts and metadata so image exercises do not require a separate media pipeline.
- Keep the first learner UI simple enough for community sessions: large images, large answer buttons, and a quick way to flag bad images/words/distractors.
- Spaced repetition and performance analytics.
- Community sharing/rating of exercise sets.
