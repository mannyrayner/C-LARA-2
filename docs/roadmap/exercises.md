# Roadmap: exercises from C-LARA-2 texts

This roadmap describes how C-LARA-2 should generate and deliver interactive exercises derived from a project text and its annotations.

## Current status (June 2026)

- Cloze: implemented in Django platform.
- Flashcards: implemented for text modes and first picture-dictionary-backed image modes.
- Picture-clue word scrambles: first implementation delivered from the project Exercises view, using picture-dictionary images as clues.
- New Kok Kaper follow-up planning remains active for organiser-defined picture-dictionary sub-projects and picture-clue crosswords.

## Goals

- Automatically generate pedagogically useful exercises from existing project artifacts.
- Support multiple exercise families, starting with:
  1. **Cloze** exercises.
  2. **Flashcards** (text/audio/image variants).
  3. **Picture-clue word scrambles** using dictionary images as clues.
  4. **Picture-clue crosswords** using dictionary images as clues.
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

## Shared source selection: picture-dictionary sub-projects

Some picture-related exercises work best with a deliberately small vocabulary. For Kok Kaper and similar communities, add an organiser workflow that creates a reusable sub-project/subset from a larger picture dictionary.

### Core flow

1. Community Organiser selects a parent project or community picture dictionary.
2. Organiser enters a natural-language selection command, for example “animals”, “food words”, “beginner-friendly household words”, or “words Sophie wants for tomorrow’s workshop”.
3. The system proposes a page/entry subset using available text, gloss/translation, lemma/POS, and picture-dictionary metadata.
4. A review screen displays the candidate list with thumbnails and readiness warnings.
5. Organiser adds/removes/reorders entries manually and saves the subset with a name.
6. Exercise generation can then target the subset instead of the whole parent project.

### Requirements

- Keep the source vocabulary stable once saved, so regenerated exercises remain within the same intended teaching set unless the organiser edits the subset.
- Preserve parent-page provenance and approved image references.
- Show unavailable entries explicitly when an exercise type requires images or game-ready status.
- Allow manual-only subsets as a fallback when the natural-language command is not useful.

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

## Exercise family C: word scrambles with picture clues

### Core concept

Generate a rectangular grid of letters containing target words from a selected project, picture dictionary, or organiser-defined sub-project. Each target word is presented through its approved dictionary image rather than through a written clue. At play-time, the learner chooses grid letters to match the current picture clue.

### Generation flow

1. Select target entries from approved/game-ready picture-dictionary items.
2. Normalize target forms for the puzzle alphabet/script while retaining the display form for feedback.
3. Place words in a rectangular grid horizontally, vertically, and optionally diagonally/backwards depending on difficulty.
4. Fill unused cells with distractor letters sampled from the target language/project where possible.
5. Attach each embedded word to an image clue, source entry id, and accepted answer metadata.

### Player behavior

- Show one or more picture clues beside the grid.
- Let the learner select a continuous path of letters, or tap/click start and end cells for straight-line words.
- Mark found words, provide immediate feedback, and keep picture clues visible as the primary prompt.
- Avoid showing the written answer until the learner has found it, asks for a hint, or reviews the finished puzzle.
- Provide a **Show answer** control that highlights the correct path and draws a thin line through the target letters; after each checked turn, show the same highlighted answer path and persist revealed/found paths into following turns so feedback remains unambiguous.

### Quality controls

- Reject entries whose normalized form is too short/long for the selected grid.
- Avoid duplicate normalized answers in a single puzzle.
- Prefer grids where all target words are placed without excessive accidental extra words.
- Surface missing/uncurated images before generation, since picture clues are mandatory.

## Exercise family D: crosswords with picture clues

### Core concept

Generate a crossword-style layout using target words from a selected picture-dictionary-backed vocabulary. Clues are images, not written definitions. Symmetry and newspaper-style aesthetics are not required; small low-resource vocabularies should prioritize valid intersections and playability.

### Generation flow

1. Select approved/game-ready target entries from the whole project or a saved sub-project.
2. Normalize answers for grid placement while preserving display forms for feedback.
3. Use a simple greedy/backtracking placement algorithm to maximize intersections.
4. Permit sparse/asymmetrical layouts and disconnected mini-clusters only when the vocabulary is too small to connect everything cleanly.
5. Create clue records with image references, answer coordinates, direction, and source entry provenance.

### Player behavior

- Show numbered across/down slots with picture thumbnails as the clues.
- Let the learner type or select letters in the grid; support mobile-friendly cell navigation.
- Reveal/check individual answers and whole-puzzle completion.
- Keep written answers hidden until checked/revealed/reviewed.

### Quality controls

- Warn organisers when too few entries are available for a satisfying crossword.
- Prefer intersections between genuinely different words and reject ambiguous duplicate forms.
- Do not require rotational symmetry, black-square aesthetics, or dense professional layouts.
- Fall back to a word-scramble recommendation when crossword placement quality is too poor.

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
  word_scrambles/
    config.json
    grid.json
    clues.json
  crosswords/
    config.json
    grid.json
    clues.json
  source_subsets/
    config.json
    pages.json
    provenance.json
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
  - choose sources (whole text, selected pages, selected vocab lists, picture-dictionary sub-projects),
  - for picture exercises, preview required images and entry readiness before generation,
  - generate/regenerate/review/publish.
- Community Organiser picture-dictionary page:
  - create a named sub-project from a natural-language selection command,
  - review and manually adjust the proposed page/entry list,
  - launch compatible exercise generation from the saved subset.

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

### Phase 4

- Organiser-defined picture-dictionary sub-projects using natural-language selection plus manual adjustment.
- Picture-clue word scrambles generated from whole dictionaries or saved sub-projects. First version now demonstrates rapid user-requested feature delivery suitable for inclusion in the First Progress Report, with a narrow implementation estimate of roughly twelve minutes of AI time plus about one hour of human AI-expert steering/review time; any public description involving Australian Aboriginal language material must still be cleared with Sophie and the relevant community/end-users.
- Picture-clue crosswords with simple non-symmetrical layouts suitable for small vocabularies.
- Shared image-readiness validation, player feedback, and publish/review lifecycle across all picture-based exercise types.
