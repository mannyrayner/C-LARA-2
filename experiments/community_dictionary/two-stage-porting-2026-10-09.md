# Sentence-first vocabulary conversion, 9 October 2026

## Human evidence

Manny reports that the previous sentence-port patch installs on AWS and converted
his 150-entry Swedish/English dictionary to French/English. He then identifies a
linguistic design fault: independently translated Swedish vocabulary does not
necessarily match the French sentence. In “Un bijou brillant en forme de lapin
repose sur du tissu”, the link should be to **reposer**, not to a translation of
Swedish **ligger på** such as **être couché ; se trouver**.

He proposes sentence translation/review followed by vocabulary creation from the
accepted wording, with bulk acceptance in either stage. Already accepted sentences
should skip translation. Shared word pages should merge by lemma and sense;
vocabulary review should show sentence and image, and edits should be tracked.

## Implementation

New sentence runs omit separately translated sentence-derived vocabulary.
Stage 2 quotes and approves its own fixed-input analyses and bounded word-speech
jobs. The normal capture workflow and conversion share lexical/MWE guidance,
validation and publication helpers. Accepted words use normalized lemma plus
sense gloss as identity; meaning differences are not silently collapsed. Existing
pages and recordings are reused, with one queued speech job per shared text revision.
Vocabulary review permits additions/removals, contextual editing, flags and bulk
acceptance. Current sentence/meaning/picture and word revisions are recorded;
changes trigger a visible needs-updating notice and a new explicit estimate.

The destination Settings control repairs the existing French version without
translating accepted sentences again. It retires only unchanged, unused legacy
word pages replaced by accepted vocabulary, preserving contributions, manual
edits/tags, independent words and withdrawal dependencies. Old unsaved derived-word
previews are discarded on repair approval so they cannot restore obsolete links.
Existing jobs keep the legacy stage through additive migration 0018.

## Local verification

- 410 Community Dictionaries tests pass (391 previous regressions plus 19 new
  two-stage cases), with mocked provider calls and disposable SQLite/media.
- New checks cover the `repose → reposer` path, final edited sentence inputs,
  image-context review, formset editing, same-sense reuse, different-sense separation,
  shared audio deduplication, revision tracking, bulk acceptance/flags, credit
  reservation through review/audio and final refund, analysis failure, cancellation
  during speech, owner-only access, source withdrawal and restoration, and legacy
  repair retaining sentence/media IDs while protecting human-edited word pages.
- The updated reproducible sentence-port browser rehearsal uses local Chromium at
  320, 390 and 1280 pixels. It exercises estimates and approval for both stages,
  sentence playback/review, vocabulary review with picture, editing and adding a
  word, saving, generated word audio, sentence/word views, and unchanged-run skips.
  No page errors or horizontal overflow were observed. Providers are mocked and
  the browser fixture uses synchronous dispatch; this is not AWS queue evidence.
- Django system checks and migration-drift checks pass. Installation needs the
  additive migration; it is not a code-only patch.

One initial test incorrectly expected withdrawal to change a contribution's status
rather than move it to its owner's private collection. The assertion was corrected
to verify private custody, disappearance from the shared entry and restoration.
No withdrawal-policy change was needed for that result.

## Limits and next observation

No production database, live provider, AWS queue or physical phone was accessed.
The 150-entry conversion report concerns the prior release, not this repair.
Windows laptop installation and live French vocabulary/TTS quality remain for
Manny to test. Synonymous but differently worded glosses can still create separate
pages, particularly in parallel suggestions; reviewers can use the same gloss to
merge the intended sense. This is a conservative first cut, not solved semantic
identity or an MWE accuracy claim. Matching sentence audio is kept; edited sentence
speech still uses its existing Create audio control.

The next useful trial is a small reviewed French version, then the existing larger
French version via Settings. Check `reposer`, a few shared words and distinct senses,
a modified sentence, a flag skipped by bulk acceptance, and word audio before
accepting the rest. Email recovery and broader MWE refinement remain deferred.
