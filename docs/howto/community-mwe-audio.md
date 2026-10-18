# Optional expression-audio regeneration pilot

Extended 18 October 2026 against `15b87f3` after laptop and AWS French/Swedish
acceptance and paired listening evaluations. The new German, Italian, Icelandic
and Japanese prompts still need live listening tests.

## Use

As dictionary owner, open **Settings → Regenerate AI expression audio**. Initially
this pilot supports French, Swedish, German, Italian and Icelandic multi-word
entries, plus explicitly selected Japanese word entries, with saved TTS enabled. Choose
**Show estimate**, then approve the allowance and automatic publication explicitly.
Nothing is sent to OpenAI while preparing the estimate.

For the five European languages, the batch selects accepted word pages with an eligible multi-word expression and
current AI-generated audio. It skips sentences, single words, entries with human
recordings, and accepted replacements from this recipe. A shared word page is
processed once. This first version identifies expressions conservatively from
multiple whitespace-separated words (maximum 12 words/120 characters, no sentence
punctuation). It does not perform another MWE analysis.

Japanese has no automatic selection: on the same page the owner chooses the
specific existing AI recordings to replace, up to 500 entries. A Japanese compound
such as 対局 or 対岸 is not classified as an MWE from its character count. It can be
included explicitly as an experiment, but satisfactory audio need not be replaced.
No word segmentation model, added spaces, reading guesses or extra AI analysis are
introduced. Single-word European compounds and unspaced separable-verb lemmas
(for example German `anziehen`) remain outside the automatic batch.

The new route is deliberately an optional batch pilot: ordinary generation still
uses the existing enriched guidance for English homographs and ordinary generation
for other entries. Regenerating the MWE subset produces the proposed three-way
hybrid collection without changing those single-word recordings. It does not yet
change the default route for future individual recordings or new dictionaries.

Each expression retains the latest existing recording's named voice, falling back
to Marin only if that name is unavailable. The tested carriers are:

- French: `On commence. EXPRESSION. C’est fini.`
- Swedish: `Vi börjar. EXPRESSION. Vi avslutar.`

New, as-yet unevaluated carriers:

- German: `Wir beginnen. AUSDRUCK. Wir sind fertig.`
- Italian: `Cominciamo. ESPRESSIONE. Abbiamo finito.`
- Icelandic: `Við byrjum. ORÐASAMBAND. Við erum búin.`
- Japanese: `始めます。 語句。 終わりました。`

Each request uses instructions in its target language. French and Swedish prompts,
the extraction algorithm, retry ceiling and recipe ID are unchanged. Previously
successful replacements are therefore skipped after this extension is installed.

The prompt requests approximately 600 ms silence between the three parts. The
extractor requires exactly two internal quiet gaps of at least 250 ms, with
plausible carrier/target durations. It keeps 120 ms boundary margins (bounded by
half each pause) and adds 200 ms playback padding. It does not resample, amplify,
recognise words, or certify pronunciation. There are at most five synthesis calls
per approved item, retrying completed silent or structurally ambiguous output.
Timeouts, provider errors and malformed WAVs stop the item without automatic retry.

Successful extracts are published, and previous synthetic recordings become
superseded, with original files and provenance retained. Failed or changed items
keep their original recordings. The progress page provides **Restore earlier
audio from this job**, which protects later edits, human recordings and withdrawn
material. Both versions remain in storage. Source withdrawal propagates through
text/revision dependencies. Only the owner can operate these controls.

After finishing/cancelling a job, another estimate selects still-eligible items;
completed carrier replacements are skipped. Resume recovers queue work, not paid
attempts with an uncertain outcome. Cancellation allows in-flight charges to settle.
The existing bounded queue is reused; no switch to real Django Q is required.

## Cost and privacy

Only expression text, language, voice and carrier instructions are sent. No image,
source recording or translation is sent to the provider. Normal key/credit
selection is used. The rough estimate assumes 1.4 requests per expression; the
allowance covers five 16-second full recordings each. The measured full carrier
duration and input bytes of completed calls, including rejected extracts, feed the
existing application cost estimator. This is not provider token accounting or an
invoice. C-LARA charging is capped at the approved allowance; a provider invoice
can differ, particularly for interrupted requests. Unused credit is returned once.
Raw carrier audio is temporary; the saved extract retains attempt measurements and
recipe provenance. The existing dictionary recordings are never deleted by this job.

## Before-and-after word audio evaluation

For each language independently:

1. Before regeneration, open **Evaluate**, create a set with **Word audio only**.
   Use all eligible pages or a fixed random sample. For an MWE-focused comparison,
   check **Only multi-word entries in French, Swedish, German, Italian or Icelandic**. This evaluates lexical pages,
   including any protected human recordings present in the sample.
2. Finish your ratings and close the set. Export the CSV. Do this before changing
   the audio: the evaluator deliberately stops new ratings of stale snapshots.
3. Run the expression-audio replacement batch.
4. On the closed baseline set, use **Repeat these word-audio items**. This creates
   new snapshots for the identical word-entry IDs, with only the word-audio question.
   It also works from an older sentence-and-vocabulary evaluation set: the word
   units from that set define the follow-up. No replacement sample is silently drawn.
5. Rate, close and export the follow-up. CSV columns `word_entry_id`,
   `audio_contribution_id`, `based_on_set_id`, `scope` and `mwe_only` identify the
   paired material. Original ratings and recordings remain attached to the baseline.

For Japanese, choose the entries and prepare the free estimate first. On that
estimate, **Create word-audio baseline for these entries** freezes precisely its
selected word pages and their current recordings. This also works for European
language batches. Finish and close the baseline before approving regeneration;
repeat its word-audio items afterwards as above. Baselines are limited to 500
entries and remain private to members by default. This selection is not represented
as an automatic MWE classification in the export (`mwe_only` is false).
An expired estimate may still supply a baseline if its source material is current;
prepare a fresh estimate after evaluation and reselect the same Japanese entries.
Changed or withdrawn source material prevents creation of a misleading baseline.

If source pages disappear or languages change, the follow-up stops rather than
substituting other entries. At most 500 word pages can be included in a set.
Permissions and withdrawal checks still apply to historical results/media.

Compare acceptable/minor/major judgements on the same entries, noting both
improvements and regressions, and separate changed MWE audio from unchanged words.
A single evaluator's sequential before/after study is useful initial evidence, but
is not a blinded comparison or inter-rater study. A failed generation is an
operational failure, not evidence that the old audio improved.

## Installation and verification

Migration `0025_mwe_audio_pilot` adds a batch marker and evaluation metadata; it
changes no recordings or existing evaluations. No new Python dependencies or
service configuration are needed. Apply on the laptop, run `check`, the app tests,
`migrate` and `showmigrations`, then test estimate/approval/playback/restoration on a
small dictionary before AWS deployment. Take the usual SQLite backup first.

The subsequent four-language extension requires **no additional migration,
dependency installation, static collection or environment/queue changes**. It
requires the original `0025_mwe_audio_pilot` to be installed already. See
`experiments/community_dictionary/mwe-audio-languages-2026-10-18.md` for evidence
and the boundary between evaluated languages and new experimental prompts.

Provider calls in the automated tests are mocked. Linux verification does not
replace a Windows laptop or physical-phone acceptance test.
