# Sentence forms alongside shared dictionary lemmas

## Implemented first version

- Sentence vocabulary shows the actual form before the shared lemma, with its own
  contextual translation and audio. Identical forms reuse the lemma presentation.
- Capture, guided pictures, writing practice and language-port vocabulary request
  contextual glosses in their existing analysis. Shared lemma/sense pages remain
  shared. Discontinuous expressions offer labelled whole-sentence playback.
- Owner-approved **Tools → Add missing sentence forms** estimates before spending,
  uses the existing bounded batch/audio queue and credit ledger, skips completed
  work, and retries missing audio without repeating successful text analysis.
- Exact source revisions, attribution, dependency withdrawal and public-media
  checks apply to forms and their recordings. Editors can correct contextual
  translations; subsequent backfills preserve valid corrections.
- Additional audio is included in estimates. Existing guided-picture standing
  consent needs renewal because the cost scope changed.

The existing vocabulary relation represents one occurrence per sentence/lemma-sense
link. This version does not model every repeated occurrence or create paradigms.

## Validation

- Full Community Dictionaries suite: **784 tests passed**, 176.462 seconds.
- New form coverage includes actual capture/audio dispatch, guided completion and
  retry, target-language port vocabulary, discontinuous expressions, public
  presentation, withdrawal/restoration, human corrections, stale-input rejection,
  budget pauses, insufficient credit, and incremental backfill.
- Four schema-preparation unit tests passed. A disposable SQLite database was
  migrated from 0026 to 0027 through the helper, with a verified backup, successful
  repeat invocation and existing content preserved.
- Django model/migration consistency, French/Slovak catalogue compilation and
  whitespace checks passed. `sqlmigrate` confirms that 0027 emits no schema SQL:
  it only records the additional contribution-kind choice.

All provider calls in these tests were mocked. No paid provider calls, production
data changes, laptop installation or AWS installation were performed for this
feature during implementation. Actual contextual translations, pronunciation and
phone ergonomics remain the purpose of the user trial.

## Release boundary

The choice-only migration and reviewed preparation helper are isolated in commit
`d0e8b043645841046ede4fffa864135dcdb5ff2c`. The feature follows it as a code-only
commit. The installed controller, IAM policy and SSM document remain unchanged.
The [deployment runbook](../../docs/howto/community-sentence-forms-deployment.md)
retains explicit preparation and laptop acceptance before AWS.
