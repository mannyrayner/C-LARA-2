# Roadmap: exercises from C-LARA-2 texts

This roadmap describes how C-LARA-2 should generate and deliver interactive exercises derived from a project text and its annotations.

## Current status (June 2026)

- Cloze: implemented in Django platform.
- Flashcards: implemented for text modes and first picture-dictionary-backed image modes.
- Picture-clue word scrambles: first implementation delivered from the project Exercises view, using picture-dictionary images as clues.
- Picture-clue crosswords: D1 first cut delivered as a static/reviewable generator from the project Exercises view.
- New Kok Kaper follow-up planning remains active for organiser-defined picture-dictionary sub-projects and playable crossword phases.

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

Generate a crossword-style layout using target words from a selected picture-dictionary-backed vocabulary. Clues are images, not written definitions. The target experience should feel like a normal crossword where possible: a rectangular grid, interlocking across/down words, black filler cells outside word areas, small clue numbers at word starts, and separate across/down clue lists. However, symmetry and newspaper-style aesthetics are explicitly out of scope for the first versions; small low-resource vocabularies should prioritize valid intersections, readability, and learner playability.

The initial implementation can reuse much of the word-scramble foundation:

- candidate extraction from current project words with picture-dictionary images,
- answer normalization and display-answer preservation,
- picture-clue media references,
- exercise-set lifecycle and publish/play views,
- per-clue **Show answer** behavior,
- partial-progress persistence in the learner/player UI.

### Generation flow

1. Select approved/game-ready target entries from the whole project or a saved sub-project.
2. Normalize answers for grid placement while preserving display forms for feedback.
3. Score candidate words for useful intersections, preferring shared letters that produce readable across/down crossings.
4. Use a simple greedy placement algorithm first, then add bounded backtracking if the greedy result is too sparse.
5. Place words only horizontally and vertically. Diagonals/backwards words are for word scrambles, not crosswords.
6. Crop the occupied rectangle and mark all non-word cells as black filler cells.
7. Assign clue numbers to cells that start one or more across/down answers.
8. Create clue records with image references, answer coordinates, direction, clue number, normalized answer, display answer, and source entry provenance.
9. If the vocabulary is too small to connect all words cleanly, allow one sparse disconnected mini-cluster only as a fallback; otherwise warn the organiser and suggest either fewer words, a larger source subset, or a word scramble instead.

### Player behavior

- Show the crossword grid in one pane and all picture clues at once in two scrollable clue panes: **Across** and **Down**.
- Use thumbnail-sized picture clues with clue number, optional short status, and no written answer by default.
- Let the learner fill any square at any time; clicking/tapping a cell should focus it and typing should advance along the active across/down clue where possible.
- Let the learner select a clue to highlight its cells in the grid.
- Persist partial entries locally and/or server-side so learners can leave and later return to a partially filled crossword.
- Provide a per-clue **Show answer** control that fills the corresponding letters and marks that clue as revealed. Revealed clues should remain visible after navigation/return, analogous to the persisted word-scramble answer paths.
- Provide optional controls to check a clue, clear a clue, check the whole puzzle, and reset the saved attempt.
- Keep written answers hidden until checked, revealed, or reviewed after completion.

### Suggested artifact shape

```text
exercises/
  crosswords/
    config.json       # source, size constraints, generation options
    grid.json         # rows/cols/cell types/clue numbers
    clues.json        # across/down clue records with image refs and answer paths
    attempt_state.json  # optional saved learner state if persisted server-side
```

Each clue record should include:

- `clue_id`, `number`, `direction` (`across` or `down`),
- normalized answer and display answer,
- start row/column and ordered cell coordinates,
- picture-dictionary entry id, image project id, and image path,
- source page/segment/token provenance,
- reveal/check status when storing learner attempt state.

### Quality controls

- Warn organisers when too few entries are available for a satisfying crossword.
- Prefer intersections between genuinely different words and reject ambiguous duplicate forms.
- Do not require rotational symmetry, black-square aesthetics, or dense professional layouts.
- Reject layouts with excessive isolated single words unless the organiser explicitly accepts a sparse fallback.
- Avoid placing words whose normalized form is too short, too long, or script-incompatible with the grid UI.
- Show a generation summary: selected words, placed words, unplaced words, number of intersections, disconnected components, and suggested fixes.
- Fall back to a word-scramble recommendation when crossword placement quality is too poor.

### Phased implementation plan

#### Phase D1 — generator and reviewable static crossword

Status: **First cut implemented.**

- Add a `crossword` exercise type and generation form under the existing project **Exercises** view.
- Reuse picture-dictionary-backed candidate extraction from image flashcards/word scrambles.
- Implement a deterministic greedy across/down placement algorithm with no symmetry requirement.
- Persist grid/clue metadata in `ExerciseItem.rationale` or equivalent JSON artifacts, using one exercise set per crossword.
- Render a detail/review page showing the grid, clue numbers, black cells, across/down picture clues, placed/unplaced word summary, and image provenance.
- Defer learner input and save-state complexity until D2.

#### Phase D2 — playable crossword MVP

- Add a learner player with editable cells, active clue selection, keyboard navigation, and two scrollable clue panes.
- Save partial attempts in browser storage first, keyed by exercise set and user where feasible.
- Add per-clue **Show answer**, check clue, clear clue, and check puzzle controls.
- Mark revealed answers distinctly from learner-entered answers so later scoring/reporting can distinguish help use from unaided completion.
- Support returning to the same crossword with saved entries, revealed clues, and completion state restored.

#### Phase D3 — robust persistence and organiser controls

- Move or mirror attempt state server-side for logged-in users so progress survives browser/device changes.
- Add organiser-facing generation diagnostics and acceptance controls: regenerate layout, accept sparse layout, adjust word count, and switch to word scramble.
- Support saved picture-dictionary sub-projects as the primary source-selection mechanism once sub-projects are implemented.
- Add regression tests for layout validity, clue numbering, saved partial attempts, show-answer persistence, and image-serving permissions.

#### Phase D4 — polish and accessibility

- Improve mobile/tablet layout for grid plus clue panes.
- Add ARIA labels and keyboard-only operation for cells and clue controls.
- Add optional print/export view for community sessions with limited connectivity.
- Add lightweight learner feedback/reporting for bad images, wrong words, or unusable crossword layouts.

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
    attempt_state.json  # optional if learner state is persisted server-side
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
- Picture-clue crosswords delivered in phases: first a static/reviewable layout generator, then a playable grid with saved partial attempts and per-clue show-answer controls, then robust persistence and organiser diagnostics.
- Shared image-readiness validation, player feedback, and publish/review lifecycle across all picture-based exercise types.
