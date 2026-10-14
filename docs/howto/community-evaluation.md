# Evaluate Community Dictionaries

Implemented first version, 14 October 2026. No AI calls or credit charges.
This measures the quality of learning material, not learning gains or ease of use.

## Start small

1. Open **Profile → Add or update language competences**. Record reading and
   listening separately for both the text language and the explanation language.
   Use the names shown in the dictionary (suggestions appear while typing).
   Varieties and relevant experience are optional. These reports are not public.
2. As dictionary owner, open the new **Evaluate** tab. Create an evaluation set:
   sentence pages with linked vocabulary, or standalone word pages; a random
   sample (default 30) or all eligible pages (maximum 500).
3. For a quick laptop rehearsal, choose two or three pages. Start an evaluation,
   select the aspects you feel able to judge and say whether you helped create
   or correct the dictionary. The consent checkbox explains the information
   shared with its owner. Start a second account's session on the **same set**
   when testing agreement.
4. Judge one page at a time, using **Acceptable**, **Minor problem**, **Major
   problem**, or **Cannot judge**. No score is preselected. Comments are optional.
   **Save and next** saves the page atomically and advances. **Skip for now**
   leaves no ratings for that page; revisit it from **Your session**. Skipping a
   previously rated page clears your ratings for that page, while the set is open.
5. Saved progress can be resumed on another device. Unsaved form changes are not
   uploaded or kept in browser storage; a browser leaving-page warning is supplied
   where supported. Save before switching apps or closing a phone browser.
6. When everyone has finished, the owner selects **Finish collection and view
   results** and confirms. Closing prevents further ratings and cannot be undone;
   create a new set for another round. This keeps results from influencing later
   ratings in the same set. Only the owner can see results or download the CSV.

Active members can evaluate. Owners can explicitly allow **signed-in visitors**
for an individual set, provided public browsing is enabled and the dictionary is
not hidden. This adds an Evaluate link to the public dictionary navigation.
Anonymous visitors must log in before rating. Disabling public browsing blocks
visitor evaluation and media access immediately. Voluntarily withdrawn members
cannot regain evaluation access through this visitor option.

A competence of 2 (confident enough to assess) or 3 (fluent / highly proficient)
is required for the relevant task. Sentence-image match, sentence language and
vocabulary require target-language reading. Audio also requires target-language
listening. Translations require reading both languages. Competence is self-reported,
not independently certified. Each session retains the competence report and chosen
aspects at its start; later profile changes do not rewrite earlier sessions.

## Rubric and sampling

Seven dimensions: sentence/image match, sentence grammaticality/naturalness,
sentence audio, sentence translation, vocabulary extraction (including MWEs and
important omissions), word translation in context, and word audio. Accept plausible
alternative picture descriptions and legitimate language varieties. The rubric
has brief examples on each evaluation page.

The candidate population contains accepted sentence or word text. Proposed,
withdrawn, removed or archived material is excluded. Missing picture/audio/
translation/vocabulary at sampling is recorded separately. The selected image and
latest accepted current audio are used, not every alternative recording. Obsolete
synthetic recordings are excluded. Extra manual picture tags are not treated as
sentence vocabulary: the sentence's current SentenceWord links define that task.

Sets record their population IDs, sample order, random seed, languages and rubric
version. The seed and sorted population reproduce the sample. A snapshot retains
component IDs and values, selected media metadata, exact vocabulary links and
limited provenance; files are not duplicated. Raw snapshots are not exposed by an
API or included in normal dictionary interchange exports. Full database/private
media backup remains necessary for operational recovery.

New ratings require the same snapshot to remain current. Editing text, replacing
chosen audio, changing links or recorded language-check state stops further ratings
on that sampled page; the session offers the remaining unchanged pages. Existing
ratings are retained against the sampled version. Results identify changed pages,
so those scores are not presented as assessments of the current dictionary.

A word translation or recording shared across sentences is offered once per set,
with the first sampled sentence supplying its context. Deduplication uses the word
entry (sense), exact component versions and languages, never spelling alone. This
avoids counting the same recording ten times; it does not evaluate every possible
context for a shared word sense.

## Privacy and contribution withdrawal

All evaluation pages and exports are private/no-store. Source permissions are
rechecked on every request, including individual media requests and CSV export.
Withdrawal, private relocation, archival, removal or a withdrawal hold prevents
redisclosure of affected snapshots, ratings and comments. Restoring unchanged
sources can make their evaluations available again. A departed evaluator's ratings
are also excluded while their participation is withdrawn. Existing database records
remain retained privately; no evaluation action overrides the withdrawal model.

Visitor access additionally requires current public-browsing permission and the
set's explicit visitor option. Visitors cannot retrieve retired content through
an old evaluation media URL. Summary/CSV access is owner-only, never public.
Account names, email addresses, API keys and media paths are absent from the CSV.
Rater aliases (R1, R2, ...) are local to a set; free-text comments or experience may
still identify someone, so exports are not claimed to be fully anonymous. They
must not be published automatically. Agree any research publication with participants.

The dictionary owner's normal interchange export does not add evaluation/profile
records. The separate evaluation CSV is for analysis; it is not a full backup.

## Reports and agreement

Reports show each dimension separately: distinct units, missing units, units
without submitted judgements, counts in each score category and acceptable
percentage of scored judgements. These are judgement-weighted percentages; reviewers
who complete more items supply more judgements. They are not per-entry majority
votes or a claim that independent language-learning outcomes have been measured.

“Cannot judge”, missing assets and singleton ratings are excluded from agreement.
Exact agreement counts all unordered pairs on overlapping scored units. Ordinal
Krippendorff's alpha uses coincidence weights 1/(m-1) for units with m ratings and
pooled ordinal rank distances across Acceptable / Minor / Major. Alpha can be
negative; it is undefined when there is no overlap or no variation. Reports show
both unit and pair counts and do not substitute 1.0 for an undefined result.

The CSV includes every accessible unit, including missing and unrated units, plus
per-judgement competence and involvement. It preserves rubric, sample seed,
content fingerprint and provenance/check indicators. It neutralises spreadsheet
formula prefixes in free text. The first version supplies no confidence intervals,
automatic adjudication or proficiency weighting. Withdrawn-source exclusions and
incomplete sessions can make a once-random sample incomplete; the report states this.

Recorded AI origin and explicit language checks are useful provenance indicators,
not proof that material is untouched automatic output or that an unmarked page has
never been reviewed. A comparison of initial generation and human correction needs
separate snapshots and an agreed analysis plan.

## AI evaluation: later experiment, not installed

The schema records evaluator kind, rubric and evaluator metadata; the human UI
always creates human records, and human reports exclude nonhuman records. There
is no AI evaluation runner, provider selection, majority-vote control or charge.
A later implementation can compare a single judge, repeated judging and diverse
models on these same versioned targets, after defining cost approval and provider
permissions. Audio judging must receive actual audio, not just its transcript.

Start with a human-rated sample and keep a separate diagnostic error set. A judge
that labels everything acceptable can look accurate when errors are rare. Repeated
model votes are not assumed statistically independent. Judge prompts should be
calibrated on a separate subset from the final comparison.

Methodological background:
- Artstein & Poesio (2008), *Inter-Coder Agreement for Computational Linguistics*:
  https://aclanthology.org/J08-4004/
- Verga et al. (2024), *Replacing Judges with Juries*:
  https://arxiv.org/abs/2404.18796
- Kohli (2026), *Nine Judges, Two Effective Votes* (preprint):
  https://arxiv.org/abs/2605.29800

These studies motivate testing evaluator reliability; they do not validate our
specific multilingual image/audio assessments.
