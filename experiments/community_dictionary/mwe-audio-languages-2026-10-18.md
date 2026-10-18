# Carrier audio: paired dictionary results and additional languages

18 October 2026. Extension base: `15b87f3`, the deployed optional MWE pilot.

## Human-reported integrated trial and exported evidence

Manny reports successful laptop installation and a six-entry toy French trial
(3 acceptable and 3 minor before; 6 acceptable after; all audio IDs changed).
He then installed on AWS and evaluated all entries admitted by the MWE filter in
Finley's French and Finley's Swedish. Paired exports confirm:

| Dictionary | Entries | Before acceptable / minor / major | After acceptable / minor / major | Improved / same / worse |
| --- | ---: | --- | --- | --- |
| French | 58 | 21 / 26 / 11 | 54 / 4 / 0 | 33 / 25 / 0 |
| Swedish | 8 | 1 / 7 / 0 | 5 / 3 / 0 | 4 / 4 / 0 |

The same entry IDs, text and translations occur in each pair; follow-up set IDs
reference the corresponding baseline. There are no missing or unscored units.
French has 48 distinct written labels across its 58 sense/page units. Do not
silently deduplicate by spelling or describe this as 58 distinct expressions.

French entry 2042 (`se dresser`, to stand upright) retains audio 7062 and its minor
rating. The exports do not establish why replacement was skipped or failed.
The other 57 French entries have new audio; 54/57 are acceptable (94.7%). The three
minor new recordings are `se coucher`, `se tenir`, and `pieds nus`. All 11 prior
major problems became acceptable. Overall deployed-set acceptability is 54/58
(93.1%), compared with 21/58 (36.2%) before.

All eight Swedish recordings changed. `hålla i`, `i siluett`, `titta på`, and
`i mitten` improved from minor to acceptable. `ha på sig`, `gå på`, and `gå ner`
remain minor (poor prosody); `andra sidan` remains acceptable. Acceptability rose
from 1/8 (12.5%) to 5/8 (62.5%).

Derived paired rows and original export filenames/SHA-256 hashes are retained in
`mwe-audio-paired-2026-10-18/`. Original source CSVs were read without alteration.
These are Manny's unblinded, sequential ratings, not new independent listening by
the implementation agent. There is no concurrent direct-regeneration control,
no inter-rater result, and no evidence of classroom learning gains. Neither these
data nor linguistic similarity validate audio in the four additional languages.
Swedish compounding plausibly reduces coverage of a whitespace-based selector;
it does not itself explain the remaining prosody problems. The eight-item set
cannot establish comparative language difficulty or single-word performance.

## Requested extension

Manny requests the same reversible batch experiment for German, Italian,
Icelandic and Japanese. The five European languages now share conservative
space-based eligibility, with native-language carrier instructions. Existing
French/Swedish requests, extraction parameters and five-attempt ceiling remain
unchanged. Ordinary generation and English-homograph guidance remain unchanged.

Japanese requires explicit owner selection, with no default selection and no
kanji-count or whitespace heuristic for MWEs. Selected compounds can be tested,
but are not relabelled as MWEs. Accepted human recordings, sentence pages, stale
audio and successful existing carrier replacements remain protected. A quoted
batch can create a private word-audio baseline for exactly its entries before
approval; the existing closed-set follow-up supplies the same entry IDs afterwards.

New native-language prompts have not been live-tested here. Start with Italian
and German listening, keep Icelandic/Japanese experimental, and retain the prior
recordings for restoration and paired evaluation. No paid calls or deployment are
performed by this implementation task.

## Verification

Focused carrier/batch/evaluation tests cover language routing, exact generated
carrier text, Japanese explicit selection and no-selection rejection, protection
of human/sentence/other-dictionary entries, new-language billing/publication/
restore, unchanged old French/Swedish recipe skipping, and paired baselines.
All 653 Community Dictionaries tests passed on Linux (157.4 seconds), including
26 carrier/batch tests. The focused carrier/evaluation run passed 65 tests.
`manage.py check` passed and `makemigrations --check --dry-run` reported no changes.
Automated provider responses are mocked. No physical-phone or live provider
acceptance is claimed for this extension. No schema or dependency changes are required.
