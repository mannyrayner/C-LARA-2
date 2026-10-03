# Community Dictionaries: Practise

First cut, 3 October 2026. One request covers six flashcard directions, picture
crosswords and C-LARA's picture-clue word-search game. This is implemented and
locally verified; Manny reports laptop success. AWS deployment of **practice** is pending.
Manny subsequently reports that this first practice update works, and requests
multiple-choice answers. See the [choice follow-up](community-practice-choices.md)
for the current default. The preceding image-generation/Settings release has
received Manny's AWS acceptance. See the [experiment record](../../experiments/community_dictionary/practice-2026-10-03.md).

## Use it

Open a shared dictionary and choose **Practise**. All active members can play;
AI enablement and editor status are not required. Optionally choose a category.

- **Flashcards:** picture → words, words → picture, recording → words, words →
  recording, recording → picture, picture → recording. Up to ten eligible entries
  are shuffled. Recall, **Show answer**, then **Again** or **Got it**. Again moves
  the card to the end; Skip removes it from this session. Translation is optional
  behind a disclosure. Recordings use explicit playback controls, not autoplay.
  Picture/audio cards can work without any written word.
- **Picture crossword:** choose a numbered clue (or tap its grid squares), inspect
  the picture and type its word. Correct answers fill the grid and reveal the
  accepted spelling. The translation is an optional hint. **Show answer** is
  recorded separately from a correct answer in the page's completion count.
- **Word scramble:** this retains the meaning of C-LARA's existing command:
  a **word search**, rather than rearranging shuffled letter tiles. Picture clues
  show which words to find. Tap a word's first and last letters, in either order;
  horizontal, vertical and diagonal selections are supported. A duplicate
  occurrence of the same answer elsewhere in the grid also counts.

On a phone, the picture clue appears directly above the grid. **Larger grid**
gives larger squares with horizontal scrolling; **Fit grid** returns to the compact
layout. Games have no timer, leaderboard or AI grading. Their counts are only
session feedback, not a saved assessment of the learner.

## Content and boundaries

The games use accepted entry wording, accepted pictures (including additional
image/word links), and accepted recordings. A selected main image is preferred;
otherwise an available accepted picture is used. Synthetic audio whose source
text or language differs from the current entry is excluded. Generated pictures
and synthetic voices retain visible labels. Private collections, archived entries,
hidden style entries and pending/rejected/withdrawn material are excluded.

Flashcards use self-assessment deliberately: one picture may support several
words. A crossword clue selects one accepted dictionary word, with translation
available to clarify the intended interpretation; it does not claim that other
descriptions of the picture are wrong.

Letter grids use up to eight distinct words, 2–12 letters long. Spaces, hyphens
and apostrophes are omitted; accents and non-English letters are retained after
Unicode NFC normalization and uppercasing. The inherited builders have one Unicode
code point per square. Words containing remaining combining marks, digits or
unsupported punctuation are excluded from grids, never silently simplified;
they remain available in flashcards. Crosswords can contain a separate group if
not all selected words interlock. Small categories may not provide a useful puzzle.
The builders are heuristic; a repeated selection can yield the same layout.

No content or progress is copied into a saved exercise, IndexedDB or localStorage.
There are no paid calls or new database tables. Refreshing/leaving loses the
session. Each interaction rechecks current membership and a digest of relevant
accepted content. The open page also rechecks every 30 seconds while visible and
when returning from another app. A change or failed connection clears the game
and asks the learner to start again. Media requests separately require active
membership and a currently accepted, non-archived contribution, with no-store
headers. Existing withdrawal/restoration rules remain authoritative.

This is not instantaneous recall of already delivered material: a displayed image,
cached audio buffer, screenshot or previously downloaded data cannot be remotely
erased. The periodic check can leave an already displayed page visible until the
next check; new actions/media requests are revalidated. Games require connectivity.

## Install on the laptop

Apply `community_dictionary_practice.patch` over the image-generation and
Settings/photo release accepted and deployed on 3 October. Save the patch in
`/home/github/`, stop the laptop development server, then:

```bash
cd /home/github/c-lara-2
git status --short
git apply --check ../community_dictionary_practice.patch &&
git apply --index ../community_dictionary_practice.patch
git diff --cached --check

cd platform_server
../.venv/Scripts/python.exe -E manage.py check &&
../.venv/Scripts/python.exe -E manage.py test community_dictionary
```

The starting checkout should be clean. Expect **205 tests**, `OK`; simulated
provider-failure log messages in existing tests are intentional. No migration or
dependency installation is required. Restart normally:

```bash
../.venv/Scripts/python.exe -E manage.py runserver --insecure
```

Try each direction with the Swedish material; check category selection, Again,
translation disclosure, audio playback, a crossword and tapping the word-search
grid. Use a temporary dictionary for a two-account withdrawal/restore check.
We need physical-phone feedback on square sizes, keyboard behaviour and audio.

After acceptance, commit/push this patch. AWS needs the normal clean `main` pull,
`umask 022`, `manage.py check`, `collectstatic --noinput`, and restart of the three
application services. This release has no schema/media rewrite. Do not repeat
the old 0008/0009 migration/reset procedure. Existing backups remain valuable.

## Reuse and verification

The pure word-search/crossword builders are extracted unchanged from
`projects.views` to `src/core/picture_games.py`. Existing project views import
their former names, preserving the C-LARA behaviour. Community Dictionaries
supplies its own current, permission-scoped vocabulary and an interactive phone
interface. Flashcards reuse the community lexicon/media rules and implement a
small reveal/self-assessment player; they do not import compiled-project exercises
or their persistent browser state.

205 app tests pass, including 16 new practice tests; both existing C-LARA puzzle
generation tests also pass. An AST comparison confirms that the extracted builder
functions are unchanged. Browser checks cover all six modes, playback,
Again/completion, Unicode crossword answers, word-search endpoints, grid resizing,
category filtering, invalidation and connection failure, at 320/390/1280 widths.
These checks use disposable SQLite and synthetic media, not production or paid
services. They do not establish learning benefits, community acceptance, physical
device compatibility or long-term reliability.
