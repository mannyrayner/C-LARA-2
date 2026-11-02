# Google word-audio comparison pilot, 2 November 2026

Manny reports correct pronunciation of all four standalone French test words
(four, court, repose, queue) with both WaveNet and Neural2. This is reported human
listening evidence on four selected problem words, not an independent listening
assessment by the developer or an estimate of general accuracy. It motivates
broader sampling after persistent isolated-word errors with the OpenAI pipeline.
It does not establish which engines the Google Translate product uses.

The new administrator-owner Tools comparison reuses durable experiment claims,
ratings, privacy and settlement. French has three methods and Swedish two.
Samples may be random, single-word homographs, expressions, forms or manually
chosen; exact duplicate lexical items are collapsed. Randomised labels are
revealed after ratings. Exports and paired summaries expose both improvements
and regressions. Fresh OpenAI outputs use the current lexical policy, including
carrier extraction for eligible MWEs. All requests are offline-mocked in tests.

The initial installation targets the Windows account with working user ADC.
Server generation needs separate authentication configuration. Neither provider
defaults nor existing dictionary recordings are changed. The next decision is
whether listening evidence supports a language-specific default and reversible
regeneration tool.

See docs/howto/community-word-audio-comparison.md for the trial procedure,
billing distinctions, privacy checks and the limits of the comparison.

Validation: 890 Community Dictionaries/admin-tools regression tests passed.
After the final single-word challenge filter and recovery coverage, all 14 focused
provider-comparison tests passed. Django checks, migration drift, French/Slovak
catalogue compilation and global-workspace validation passed. Google/OpenAI
requests were mocked; linguistic quality still requires Manny's live annotation.
