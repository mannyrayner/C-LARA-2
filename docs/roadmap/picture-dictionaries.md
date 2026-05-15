# Picture dictionaries roadmap

This document is deliberately split into two parts:

1. **Part A: user-level plan** — a short, plain-language description intended for linguists, community organisers, and reviewers such as Sophie.
2. **Part B: implementation notes** — more detailed technical guidance for developers and project maintainers.

---

# Part A — User-level plan

## A1) Main idea

A **picture dictionary** should be the central shared resource for community vocabulary work.

For a community such as Kok Kaper, the picture dictionary is the place where organisers and linguists collect words, attach or generate pictures, review whether the pictures are appropriate, and then reuse the approved material in several ways:

- **picture glossing** in C-LARA texts: when a learner clicks/taps a word, an image can appear as part of the glossing support;
- **picture flashcards**: learners can practise matching images and words;
- **future language games**: later activities can reuse the same approved word/image entries.

The important point is that the dictionary is the trusted source. Games and glosses should draw from the dictionary instead of creating separate word/image lists.

## A2) Who the first version is for

The first version can start from a concrete approved seed project: the migrated legacy C-LARA project **50 words in Kok Kaper**, which contains one Kok Kaper word and one community-approved illustration per page. This gives a low-risk path to an initial dictionary because the lexical/image pairs already exist and have been seen by the community.

The first version needs to work well for two kinds of users.

### Sophie / linguist / community organiser

Sophie needs a practical preparation and review workspace where she can:

- add new words to the community picture dictionary;
- generate images for words that do not yet have pictures;
- regenerate or replace unsuitable images;
- approve entries that are ready for community use;
- prepare a simple flashcard activity before a visit or review session;
- note problems reported by community members.

### Community members / learners

Community members need a simple, non-technical experience where they can:

- see a picture and choose the right word;
- see a word and choose the right picture;
- use large, clear buttons and images suitable for a tablet, laptop, or projected session;
- optionally flag when a picture or card seems wrong.

The first version should avoid exposing project-internal details to community members.

## A3) First concrete activity: picture flashcards

The initial language-game feature should be **multiple-choice picture flashcards** in both directions:

1. **Image → word**: show an image and ask the learner to choose the matching word from alternatives.
2. **Word → image**: show a word and ask the learner to choose the matching image from alternatives.

Flashcards should normally use only entries that have been approved or marked ready for games. Distractors should come from the same picture dictionary. AI can help rank or filter distractors, but the curated dictionary should remain the source of the possible answers.

## A4) Picture dictionary workflow

The Community Organiser picture-dictionary interface should be the main place for routine work.

For the Kok Kaper MVP, the first organiser action should be able to register or import **50 words in Kok Kaper** directly as a community picture dictionary. The conversion should keep the existing project/page/image structure where possible, but add the metadata needed for dictionary ownership, lexical entry identity, readiness/game-use flags, and provenance.

Organisers should be able to:

1. create a dictionary from a suitable one-word-per-page project such as **50 words in Kok Kaper**;
2. add words;
3. add candidate words from an existing text/project;
4. generate images only for newly added or missing-image words;
5. regenerate images for selected entries;
6. approve, reject, or exclude entries from games;
7. build or preview a flashcard deck;
8. open the learner-facing flashcard activity.

There can still be an advanced link to the underlying C-LARA-2 project for debugging or expert work, but routine dictionary work should not require navigating to that project.

## A5) Proposed delivery sequence

Because discussion and development time are limited, delivery should be staged.

### Step 1 — Agree the user workflow with Sophie

Before implementation, confirm the practical details:

- how many words are needed for the first useful Kok Kaper deck;
- whether the first session will use laptop, tablet, or projector;
- whether community members should see only the community-language word, or also a gloss/translation;
- whether audio is needed in the first version or can wait;
- what kinds of image/card problems Sophie wants to record.

### Step 2 — Seed the first dictionary from the approved Kok Kaper project

Add a direct import/registration path from a suitable one-word-per-page C-LARA-2 project into a community picture dictionary. The immediate target is **50 words in Kok Kaper**, migrated from legacy C-LARA to the AWS C-LARA-2 server. The conversion should be deliberately minimal: preserve the existing word/page/image material, add dictionary metadata and curation flags, and make the result available in the Community Organiser dictionary interface.

### Step 3 — Make picture-dictionary maintenance easier

Move routine operations into the Community Organiser picture-dictionary interface, especially generating images only for new or missing-image entries.

### Step 4 — Build the minimal flashcard activity

Create image-to-word and word-to-image multiple-choice flashcards from approved picture-dictionary entries.

### Step 5 — Add review and feedback loops

Allow Sophie to preview decks and allow simple problem reports such as “wrong picture”, “wrong word”, or “bad distractor”.

### Step 6 — Generalise for other communities

Once the Kok Kaper workflow is stable, reuse it for similar communities, especially New Caledonian communities where there is direct contact.

## A6) What should wait until later

The first version should stay small. The following are useful, but should not block the initial Kok Kaper flashcards:

- many different game types;
- detailed learner analytics;
- adaptive difficulty;
- fully conversational AI control of every operation;
- complex sense-disambiguation workflows.

---

# Part B — Implementation notes

## B1) Existing concept and scope

A **picture dictionary** is a shared lexical resource that links lexical entries to images.

Each entry minimally contains:

- surface form(s),
- lemma,
- part of speech (POS),
- language,
- one or more associated images,
- optional metadata (source, curation status, notes, difficulty level, tags).

The primary goals are:

1. richer reading support ("picture glosses" for lexical items),
2. picture-based exercise/game types,
3. reusable community curation of word/image material.

## B2) Project-as-dictionary implementation pattern

The current pragmatic implementation realises a picture dictionary using existing project infrastructure:

- one project per dictionary,
- one page per lexical entry,
- existing lemma/POS annotation to disambiguate entries,
- existing image-generation pipeline for dictionary images.

This keeps the first implementation low-risk by reusing current storage, UI, and generation components. However, the project should be treated as a backing implementation detail. The user-facing object is the community picture dictionary.

### B2.1 Legacy/project-to-dictionary seed import

The first Kok Kaper implementation should include a narrow import/registration path for a project that already has dictionary-like structure:

- source project: **50 words in Kok Kaper**, now migrated from legacy C-LARA to the AWS C-LARA-2 server;
- expected layout: one lexical item per page, with an accompanying illustration for each item;
- conversion goal: create or register a community picture dictionary without rebuilding the content from scratch;
- preservation rule: keep the existing project/page/image assets and provenance as far as possible;
- added metadata: community/language ownership, dictionary entry keys, source project reference, readiness/game-use state, and import timestamp;
- validation: flag pages that do not contain exactly one usable lexical item or one usable image for organiser review rather than silently including bad entries.

This seed-import path should be intentionally smaller than general arbitrary-project extraction. General extraction can still use the broader "add words from text/project" workflow, but the approved Kok Kaper word list gives a faster, safer route to the first community game.

## B3) Lexical entry identity

For lookup and deduplication, use a canonical key such as:

`(language, lemma, pos)`

with optional refinement later, for example a sense identifier, if ambiguity requires it.

## B4) Ownership, governance, and sharing model

Picture dictionaries are community-level shared resources.

- **Owner role:** community organiser.
- **Visibility:** available to members of the associated language community.
- **Edit permissions:** organiser-managed, initially organiser-only; later optionally delegated editors.

Auditability requirements:

- who added/removed entries,
- when entry images were generated or regenerated,
- who approved/rejected entries or images,
- provenance of bulk imports.

## B5) Entry readiness and curation states

Picture games and picture glossing should not blindly use every dictionary entry. The implementation should distinguish at least these practical states, either explicitly or by inferred flags:

- **candidate** — entry added but not reviewed;
- **needs image** — no usable image yet;
- **image generated** — image exists but has not been approved;
- **approved / game-ready** — entry can be used in flashcards and picture glossing;
- **excluded from games** — entry remains in the dictionary but is not used as a card or distractor;
- **needs review** — entry or image has been flagged by Sophie/community members.

For the first implementation, a simple boolean or status field is acceptable if it supports safe deck construction.

## B6) Organiser operations

Provide explicit organiser-facing commands/actions from the Community Organiser picture-dictionary interface.

### B6.0 Create from a dictionary-like project

- Input: a C-LARA-2 project whose pages already correspond to dictionary entries, initially **50 words in Kok Kaper**.
- Behaviour: register the project as a picture dictionary or create a dictionary backing project with minimal structural changes.
- Add community/language metadata, source-project provenance, readiness defaults, and game eligibility flags.
- Validate one-entry/one-image assumptions and send exceptions to organiser review.

### B6.1 Compile/refresh dictionary

- Build/refresh dictionary artifacts and indexes.
- Validate canonical keys and detect conflicts/duplicates.
- If no usable image style exists yet, require an organiser-provided **style brief** at compile time and auto-generate style artifacts before image generation starts.
- Show explicit organiser feedback that compilation has started as a long-running action, then report annotation/image outcomes.

### B6.2 Add given words

- Input: explicit word list, optionally with lemma/POS hints.
- Behaviour: create missing entries without forcing immediate full-dictionary regeneration.

### B6.3 Remove or deactivate given words

- Input: explicit word list or canonical keys.
- Behaviour: remove entries, or preferably soft-delete/deactivate them for audit and recovery.

### B6.4 Add words from text/project

- Input: source text/project.
- Behaviour:
  1. run or consume lemma+POS analysis,
  2. extract candidate `(lemma, pos)` pairs,
  3. add only missing entries,
  4. allow organiser review before making them game-ready.

Suggested first-version filter for pictureability:

- exclude function words by POS (`DET`, `AUX`, `PART`, etc.),
- exclude very high-frequency stop items,
- optionally whitelist concrete POS classes first (`NOUN`, `VERB`, `ADJ`),
- allow organiser review before commit or before game use.

### B6.5 Generate images for new/missing entries

This should be a first-class action.

- Default scope: entries with no usable image.
- Optional scope: selected entries only.
- Avoid regenerating already-approved images unless explicitly requested.
- Preserve per-entry diagnostics from the image-generation run.

### B6.6 Regenerate selected images

- Allow organisers to regenerate images for entries that were rejected, flagged, or judged culturally inappropriate.
- Keep old image/provenance where useful for audit/debugging.

### B6.7 Approve/reject entries and images

- Let organisers mark entries as approved/game-ready.
- Let organisers exclude entries from games even if they remain useful in the dictionary.
- Record simple review notes where possible.

## B7) Picture glossing pipeline stage

Introduce or refine an optional pipeline stage, e.g. `picture_gloss`.

Preconditions:

1. lemma stage output exists,
2. a suitable picture dictionary is configured for the project/language,
3. dictionary index lookup is available for `(language, lemma, pos)`,
4. matching dictionary entries are approved or otherwise allowed for glossing.

Output:

- annotation payload linking tokens to picture-gloss candidates,
- confidence/status flags (exact match, fallback match, unresolved),
- reference to the dictionary entry/image used.

Failure handling:

- unresolved items should not block compilation,
- fallback to existing behaviour (audio/concordance only).

## B8) Rendering and learner UX for picture glosses

If a lexical item has a picture gloss, HTML interaction should be enhanced:

- click/tap lexical item,
- show image gloss in the same interaction surface as existing lexical support,
- keep current audio + concordance behaviour, now augmented by picture.

Design principle:

- picture glosses are additive, not disruptive; existing lexical UX remains intact.

## B9) Flashcard/game generation from picture dictionaries

Picture dictionaries enable new exercise families.

### B9.1 Image → word multiple-choice

- Learner sees an image.
- Learner chooses the correct word from distractors.

### B9.2 Word → image multiple-choice

- Learner sees a word.
- Learner chooses the correct image from distractors.

### B9.3 Deck construction

For each target item:

1. select an eligible approved/game-ready dictionary entry;
2. select the prompt image or prompt word;
3. generate a candidate distractor pool from the same dictionary;
4. prefer distractors with compatible POS, difficulty, tags, or semantic domain where available;
5. optionally use AI to rank/filter candidate distractors;
6. persist the deck/card snapshot so review sessions are stable even if the dictionary later changes.

AI should be used as a ranker/filter over curated dictionary candidates, not as the only source of answers.

### B9.4 Review/session modes

Consider three modes:

- **Practice mode:** learner-friendly play with simple feedback.
- **Review mode:** Sophie/community organisers can mark card-level issues such as bad image, wrong word, bad distractor, or culturally inappropriate content.
- **Session/demo mode:** large uncluttered UI for in-person community visits.

### B9.5 Future variants

- typed response instead of multiple choice,
- graded distractors by semantic similarity,
- adaptive difficulty via learner history,
- audio-first or audio-supported cards.

## B10) Natural-language help

Natural-language help should support the picture-dictionary and game workflows, but it should not block the flashcard MVP.

Initial read-only help should answer questions such as:

- “How do I add new words?”
- “How do I generate images for words I just added?”
- “Why is this word not appearing in the flashcard game?”
- “How do I replace a bad picture?”
- “How do I prepare a game for a community session?”

Later, the dialogue layer can safely execute selected operations with confirmation, following the broader dialogue roadmap.

## B11) Suggested implementation phases

### Phase A — User workflow agreement

- Confirm the first Kok Kaper workflow with Sophie.
- Decide first-session constraints: device, deck size, display language(s), audio needs, and feedback categories.

### Phase B — Seed import from 50 words in Kok Kaper

- Add a direct create/register action for dictionary-like projects, starting with **50 words in Kok Kaper**.
- Preserve existing word/image material and add community dictionary metadata plus readiness/game flags.
- Report any page that fails the one-word/one-image assumption for organiser review.

### Phase C — Picture-dictionary UX consolidation

- Make routine dictionary operations available from the Community Organiser interface.
- Keep “open backing project” as an advanced/debug action.
- Add missing-only image generation as a first-class action.

### Phase D — Minimal flashcards

- Generate image→word and word→image multiple-choice cards from approved dictionary entries.
- Use same-dictionary distractors with deterministic fallback and optional AI ranking.
- Provide a simple learner-facing play screen.

### Phase E — Review and feedback loop

- Add organiser deck preview.
- Add card-level problem reporting.
- Feed reported issues back into dictionary review status.

### Phase F — Generalisation

- Reuse the workflow for other communities, especially New Caledonian communities where there is direct contact.
- Add configuration for community-specific display conventions and optional audio.

## B12) Open questions

1. Should the first version require explicit approval before an entry can appear in games, or allow all entries with images unless excluded?
2. Should v1 allow only one image per `(lemma, pos)`, or multiple ranked images?
3. How should we handle polysemy beyond POS (sense-level disambiguation)?
4. Should dictionary entries be soft-deleted for audit/recovery?
5. Should organiser operations be synchronous for small sets and queued for bulk sets?
6. How should communities discover/reuse dictionaries across projects?
7. What is the minimum useful flashcard deck size for the first Kok Kaper session?
8. Should imported entries from **50 words in Kok Kaper** be marked game-ready by default because the community has already approved them, or should Sophie explicitly approve them in C-LARA-2?

## B13) Success criteria

- Sophie/community organisers can build and maintain a usable dictionary with low friction.
- Newly added words can get images without regenerating the whole dictionary.
- Projects can optionally enable picture glossing without breaking existing flows.
- Compiled HTML displays picture glosses when available.
- Image→word and word→image flashcards work end-to-end from approved dictionary entries.
- Community feedback can identify problematic images/cards for later review.

---

## Cross-reference

- Image-pipeline details and dictionary-specific image options are tracked in:
  - [image-generation-pipeline.md](image-generation-pipeline.md)
- Dialogue/NL-help details are tracked in:
  - [dialogue-top-level.md](dialogue-top-level.md)
