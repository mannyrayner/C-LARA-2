# Manual picture/word links — 1 October 2026 (Adelaide)

## Human evidence and scope

Manny accepted the preceding recording/logout changes on his laptop and asked for
check-in/AWS instructions. At the next breakfast he reports Community Dictionaries
working well with about fifty Swedish entries: Cathy's everyday and earlier photos
plus English meanings, followed by Manny's Swedish text and recorded audio.
This is joint-use evidence, not an instrumented device matrix or a learning-outcome
study. His sofa/cat example motivates many-to-many associations.

After discussion he requests a bounded first cut: manually select extra words
from existing entries, ship Pictures/Words views together, and let a learner hear
a linked word and reveal its translation while staying on the image. Opening a
word page is a separate action. AI tagging is explicitly outside this increment.
The original messages are retained with global workspace revision 28.

## Implementation

Base: verified GitHub main `b945623017bb1c938a9273353a62bec5bd808de5`, tree
`cce77ea85e98d2275a8f6e3272988412a8b1f4c5`. The isolated local baseline is a
synthetic commit with exactly that tree; its SHA is not the remote commit.
Deliverable: `community_dictionary_picture_word_links.patch`.

Reuses membership, accepted contributions, private range-streamed media, current
TTS matching, unsaved-draft protection and ordinary Django templates. Migration
0005 adds `ImageWordLink`: one accepted picture contribution to an existing word
entry, with creator/time and a uniqueness constraint. The original association
remains implicit. Mutations are editor-only, incremental and idempotent. Word
pages collect original and extra pictures; picture queries are scoped at both
ends. Export manifest version 2 includes links and attribution without new media
copies. Human-owned project intentions are unchanged.

## Checks and limits

- All **95 Community Dictionaries tests** pass on Python 3.12 / Django 5.2.17:
  77 existing tests plus 18 new tests. Coverage includes preserved original
  data, many-to-many links, retries/unlink, roles, private dictionaries, invalid
  media/targets, model constraints, alternate pictures, updated words/current
  TTS, search/pagination, homographs, deletion, export/fixture restoration, POST
  and CSRF. Intentional mocked-provider errors precede OK.
- `makemigrations --check --dry-run` reports no changes. The browser harness
  migrates a disposable database and does not use the live user's database.
- `lexicon_browser.cjs` passes under Chromium 153 in Pixel 7/iPhone 13 viewport
  configurations and a desktop viewport. Synthetic image/audio only. It covers
  menu linking, two words per picture/two pictures per word, hidden/revealed
  translations without navigation, real HTML audio time progression, one player
  at a time, round-trip word/gallery navigation, preservation of unsaved comments
  before unlink, search across both views, member restrictions, playback failure
  feedback, JavaScript-disabled fallback, and horizontal-overflow checks.
- An initial browser check exposed a brief event-ordering window when switching
  recordings. Listen now pauses other audio synchronously as well as handling
  native audio play events. The subsequent rehearsal passed. Two initial backend
  assertions also identified unescaped HTML query separators in new navigation;
  these were corrected and the full 95-test set passed.
- Screenshots were inspected locally. No community photograph, credentials or
  real user data were added to the repository. No paid AI call, remote push,
  AWS deployment or physical-phone test was performed by the agent.

Run the optional browser rehearsal with the existing Playwright/Chromium setup:

```bash
python -c 'from pathlib import Path; from experiments.community_dictionary.browser_rehearsal import main; main(Path("experiments/community_dictionary/lexicon_browser.cjs").resolve())' /tmp/community-word-links
```

Next: Manny/Cathy try the links with their real entries, then repeat after server
deployment on a physical phone. Record friction before expanding the scope.

## Later same-morning laptop acceptance

Manny reports that the new functionality works first time and the sofa/cat
example comes out exactly as intended. His laptop dictionary is small, so he
proposes check-in and a fuller trial on the server with the existing larger
Swedish dictionary. The corresponding human message is preserved in global
workspace revision 29. This closes the initial laptop acceptance step; it does
not establish server deployment or physical-phone acceptance of this increment.

The follow-up `community_dictionary_word_links_acceptance.patch` changes only
documentation and derived project state. It preserves the 95-test/browser evidence
above, validates the global workspace/archive, and checks incremental applicability
after the delivered functional patch. No application code or migration changes,
remote push, AWS access or additional provider calls are involved.
