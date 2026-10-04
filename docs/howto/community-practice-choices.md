# Multiple-choice Community Dictionary flashcards

**Acceptance update, 4 October:** Manny accepted the multiple-choice follow-up,
checked it in and now reports the combined practice release deployed and working
on AWS. Earlier pending statements below describe the original delivery date;
a detailed device matrix and external learner trials are still unrecorded.

3 October 2026. Manny reports that the first practice update works, and requests
multiple-choice answers like the flashcards people liked in C-LARA-2. This
increment makes **Multiple choice** the default under **Practise → Flashcards**;
**Reveal the answer** retains the preceding self-assessment mode. All six
picture/text/audio directions support both styles.

## Behaviour

- Up to four real answers from the chosen dictionary/category appear in random
  positions. A smaller pool can provide two or three choices. No invented filler
  words, paid AI calls or additional configuration are needed.
- Text answers are buttons; picture answers are clickable pictures. Recording
  answers have separate playback and **Choose recording A/B/C/D** controls.
  Listening is not an answer submission. Only one recording plays at a time.
- A wrong answer invites another try and disables that option. A correct answer
  highlights the match, offers the optional translation/word page, then **Next
  card**. **Show answer** and **Skip** remain available. The session counts answers
  correct on the first attempt; retries and revealed/skipped answers do not count
  as first-time correct. Nothing is saved after leaving the page.
- Choices exclude identical/near-duplicate words, contained phrases and obvious
  longest-word variants, identical nonempty translations, shared recordings,
  shared selected images, and entries linked to any common accepted picture.
  This prevents known sofa/cat picture associations becoming false distractors,
  including when each word also has its own selected photograph.
- This is conservative filtering, not semantic validation. Unknown synonyms,
  untagged objects in a photo and duplicate uploads with separate identities can
  still be ambiguous. Testing real dictionaries will show whether an explicit
  question-exclusion/feedback control is needed. Reveal mode remains useful for
  ambiguous material. When no two distinct options can be assembled, the app
  suggests another category or Reveal mode instead of inventing options.

Current accepted-material, membership, withdrawal, stale-TTS and no-store checks
apply to both prompts and distractors. Changes to additional picture links also
invalidate an open game. No new schema, dependencies or durable exercise copies.

## Install

Apply this incremental patch **after** the already installed
`community_dictionary_practice.patch`; do not reapply that original patch.
Save `community_dictionary_practice_choices.patch` in `/home/github/` and stop
the laptop development server.

```bash
cd /home/github/c-lara-2
git apply --check ../community_dictionary_practice_choices.patch &&
git apply --index ../community_dictionary_practice_choices.patch
git diff --cached --check

cd platform_server
../.venv/Scripts/python.exe -E manage.py check &&
../.venv/Scripts/python.exe -E manage.py test community_dictionary
```

Expect **215 tests, OK**. No migration is needed. Restart normally:

```bash
../.venv/Scripts/python.exe -E manage.py runserver --insecure
```

Choose Practise, a flashcard direction, and Multiple choice. Try picture and audio
answers as well as words, including a wrong answer followed by the correct one.
Both practice patches can be checked in together after acceptance. AWS needs the
usual static collection and service restart, with no additional migration.

## Verification and reuse

Three existing C-LARA duplicate-check functions are moved unchanged into the
shared `core.picture_games` module and reimported under their old names. The
Community adapter adds accepted-picture-link and translation checks. It does
not call the older AI distractor generator or use its placeholder options.

215 app tests pass, including ten new choice tests, and three existing C-LARA
flashcard/distractor tests pass. An AST comparison verifies the helper extraction.
Chromium rehearses all six choice directions, audio playback versus selection,
wrong/correct/revealed/skipped answers, first-attempt scoring, session completion
and invalidation, alongside the earlier reveal-mode and puzzle flows. Phone-width
screens are inspected; fixtures are synthetic pictures/audio. Real-media
ambiguity, physical-device behaviour and learner preference remain human trials.
