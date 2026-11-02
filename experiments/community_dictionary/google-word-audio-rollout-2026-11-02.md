# Optional Google lexical audio and reversible conversion

The owner reports a completed random French comparison of 30 lexical items:
OpenAI 25 acceptable, 3 minor and 2 major; WaveNet and Neural2 each 30 acceptable.
Each paired Google comparison has five Google-only acceptable cases and no
OpenAI-only acceptable case. This is encouraging single-evaluator evidence for
these voices on this sample, not proof of universal superiority, an estimate for
other languages, or an independent evaluation by the coding agent.

The resulting implementation offers an explicit dictionary-level Google voice
selection for future lemmas and inflected forms. Sentence and feedback speech
remain on OpenAI. No existing content or default is changed automatically.
Language coverage follows Google's available voices, with configurable discovery
rather than assuming every language has a WaveNet or Neural2 voice. The same
blinded comparison/CSV workflow remains available for annotation.

The conversion tool generates private candidates, records provider/voice/cost,
then supports individual acceptance, bulk acceptance without falsely claiming a
pronunciation review, and restoration of unchanged earlier audio. Human audio,
source edits and withdrawal are protected. Existing files are retained. Frozen
provider settings prevent an old quote or picture request from silently changing
provider. Normal form reuse compares the selected voice.

Deployment is divided into additive schema preparation (one preference table)
and an ordinary code-only feature release. Linux Google access is opt-in, using
explicit AWS IMDSv2 workload identity configuration and service-account
impersonation. Laptop user ADC is retained. Legacy key files are not consumed.
No production deployment, live synthesis, or IAM mutation was performed during
implementation. Live voice quality and AWS federation remain deployment-side
checks by the owner.

Validation: all 908 Community Dictionaries/admin-tools tests and four schema-controller
tests pass. Django system and migration-drift checks pass. Focused tests cover real
picture/form/individual-word routing, source changes and withdrawal, grouping,
human/reviewed/matching skips, bulk publication/restoration, provider provenance,
quote and capture snapshots, language coverage, explicit billing consent,
voice discovery, and federation-file validation. API calls are mocked.

See [the runbook](../../docs/howto/community-google-word-audio.md).
