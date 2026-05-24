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
  - preview/confirm behavior before expensive generation,
  - improved context presentation for reviewers.
- These are important prerequisites for dictionary quality curation, even when the final dictionary UI remains separate.

---

## 2) Near-term priorities (next implementation window)

These are the items that should be treated as immediate roadmap work.

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

### 2.5 Enforce text-free dictionary images (linked to ISSUE-0028)

Image-based flashcards are now working in both directions, but they are undermined when dictionary images contain visible written words.

- Treat “no overlaid readable text in the generated image” as a default quality requirement for picture-dictionary images.
- Strengthen generation/regeneration prompts with explicit text-free constraints.
- Add organiser-facing diagnostics so entries can be flagged/rejected when text is detected in generated images.
- Add lightweight regression checks for dictionary image assets used by flashcards.

Track implementation in **ISSUE-0028** (`docs/issues/issues/ISSUE-0028.json`).

---

## 3) Longer-term goals

### 3.1 Mature picture-based learning activities

- Expand beyond the initial flashcard scope while preserving curation quality.
- Maintain both directions as first-class modes:
  - image → word,
  - word → image.
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

- many additional game types,
- heavy analytics,
- adaptive personalization,
- complex sense-disambiguation UX.

The immediate focus should remain:

1. reliable low-resource compile fallback,
2. explicit organiser feedback during compile/generation,
3. usable and predictable organiser entry-list presentation.
