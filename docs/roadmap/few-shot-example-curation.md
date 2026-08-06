# Few-shot example curation and evaluation roadmap

## Why this exists

Recent work on `segmentation_phase_2` variants, especially the `boundary_first` mechanism, suggests that prompt and few-shot choices can materially affect annotation quality. The current examples are useful for experimentation, but they were mostly created in one-off AI-assisted passes. That makes it hard to know whether an example is linguistically correct, whether it covers the right phenomena, and whether adding more examples is actually improving the pipeline.

This is now a P1 roadmap item because maintainers are seeing many annotation errors, and because a disciplined few-shot curation/evaluation workflow could become strong evidence for the First Progress Report: C-LARA-2 should show that AI-assisted evaluation is guiding real annotation improvements rather than merely producing plausible-looking prompt edits.

Related issue: [ISSUE-0036](../issues/issues/ISSUE-0036.json).

## Current progress note (2026-06-19)

The first French `segmentation_phase_2` / `boundary_first` curation workflow has now moved beyond the initial smoke test. The earlier 40-candidate `clitic_compound_v2` run established that the generate → validate → hostile-review → human-audit loop was useful: eight retained examples were all judged correct by maintainer review, and validation-failed candidates are now excluded from AI review.

On 2026-06-15, the first full-sized batch for this experiment was generated and reviewed through the experiment Makefile:

- `make curate RUN=1` generated 80 candidates.
- `make review RUN=1 REQUEST_ID=20260615-072115Z` AI-reviewed all 80 candidates, with severity counts `fatal: 3`, `serious: 5`, `minor: 0`, and `none: 72`.
- `make audit-reviews RUN=1 REQUEST_ID=20260615-072115Z` human-audited the AI review output. The human reviewer accepted all AI judgements, while noting that some decisions were borderline.

On 2026-06-19, the imported French corpus was summarized using the new experiment target `make summarize-corpus RUN=1`. The maintainer-reported run for user `mannyrayner`, language `fr`, exact match found:

- 53 French projects, all with `segmentation_phase_2` artifacts;
- 1600 segments;
- 17344 current segmentation tokens in total;
- 10566 non-whitespace tokens and 6778 whitespace-only tokens;
- 53625 token-surface characters including whitespace and 45704 excluding whitespace;
- 60 segments with no tokens and no empty token surfaces.

These figures are large enough for a meaningful first report experiment if we use the data conservatively. The corpus should not be treated as a single undifferentiated benchmark. The next autonomous planning step is to split it into a small development subset for prompt/few-shot/evaluator iteration and a held-out test subset for the first reportable comparison. The split should be deterministic, manifest-based, and stratified by project size where practical, so that subsequent Make targets can rerun the same inputs without accidental leakage from development decisions into the final test set.

The run also exposed an important implementation lesson. One generated candidate in the earlier smoke test had lost interword spaces in the boundary-marked representation, e.g. an input like `L'ami de Marie habite ici.` paired with units that concatenated as `L'amideMariehabiteici.`. The deterministic validation logic already catches this by checking that concatenated unit surfaces exactly match the input, but the review command initially still sent validation-failed candidate records to AI review. That path has now been tightened so AI review only runs over schema-valid candidates and records skipped validation failures in the review summary. This reinforces the architecture: deterministic preservation/schema checks must be a hard gate before linguistic judgement.


## Preliminary reset step: redo `segmentation_phase_2` with 5.6 before MWE work

Before restarting MWE prompt learning on the seven English texts, redo the upstream
`segmentation_phase_2` artifacts with `gpt-5.6` and manually freeze those
segmentations. This is not a 5.5-vs-5.6 comparison; it is the clean starting
point for the 5.6-only prompt-learning series, so downstream MWE, lemma, and
gloss gold must be derived only after the new segmentation is accepted.

Use the MWE workbench target, because it writes the refreshed
`segmentation_phase_2.json` artifacts into the normal per-project run directories
that the manual editor and the later MWE refresh/export commands treat as the
latest project state. The workbench's generated bookkeeping remains under
`generated/gpt-5.6-prompt-learning-v1/`, while the processing output that MWE
needs is the latest saved project artifact, not a copied JSONL file in the
segmentation workbench.

```bash
cd experiments/linguistic_processing/mwe/focused_multilingual

# Preserve old flat generated/ outputs first; the archive is provenance only.
make archive-pre-5-6 RUN=1

# Optional: establish or refresh the project split manifests in the 5.6 namespace.
make extract-split-corpus CORPUS_USER=mannyrayner LANGUAGES=en

# Rebuild only segmentation_phase_2 for the seven English projects with gpt-5.6.
make refresh-segmentation-phase-2 RUN=1 \
  PROJECT_IDS="239,245,254,255,257,261,263"

# Before any manual correction, archive these initial 5.6 outputs for later
# accuracy/error analysis against the corrected segmentation.
make archive-initial-segmentation-phase-2 RUN=1 \
  PROJECT_IDS="239,245,254,255,257,261,263"
```

The archive target copies the current latest `segmentation_phase_2.json` for each
selected project to
`generated/gpt-5.6-prompt-learning-v1/segmentation_phase_2_initial_outputs/`
and writes a manifest recording source project ids, source artifact paths, model,
and archive paths. Run it after the 5.6 segmentation refresh has completed and
before opening the annotations for manual correction; otherwise the preserved
"initial output" may already include human edits.

After that command, review and correct `segmentation_phase_2` in the ordinary
project/manual annotation workflow until these seven projects are frozen. Only
then continue downstream, preserving the corrected segmentation by starting the
full MWE-side refresh at `translation` rather than rerunning segmentation again:

```bash
make refresh-annotations RUN=1 \
  PROJECT_IDS="239,245,254,255,257,261,263" \
  REFRESH_START_STAGE=translation \
  REFRESH_END_STAGE=gloss

make extract-split-corpus CORPUS_USER=mannyrayner LANGUAGES=en
```

This sequencing prevents the earlier problem from recurring: MWE, lemma, and
gloss manual cleanup cannot become gold evidence until it is anchored to the new
5.6 `segmentation_phase_2` artifacts.

### Seven-English-project checkpoint and prompt provenance (2026-08-06)

Manual correction is complete on the laptop for English projects
`239,245,254,255,257,261,263`. The reviewer reports that the page-oriented
workflow completed without further problems and that the 5.6 MWE output is
visibly better than the earlier material. These seven projects now form a small
development gold set, not a held-out test set.

Freeze both layers before doing any more processing on these projects:

```bash
cd experiments/linguistic_processing/mwe/focused_multilingual

# Preserve the corrected segmentation payloads separately from the archived
# uncorrected 5.6 outputs.
make archive-corrected-segmentation-phase-2 RUN=1 \
  PROJECT_IDS="239,245,254,255,257,261,263"

# Snapshot the projects and export an explicit, immutable-by-convention MWE
# gold subset plus summary and review files in the 5.6 experiment namespace.
make declare-mwe-gold RUN=1 \
  PROJECT_IDS="239,245,254,255,257,261,263" \
  MWE_LANGUAGE=en SPLIT=development

make check-mwe-gold RUN=1 \
  PROJECT_IDS="239,245,254,255,257,261,263" \
  MWE_LANGUAGE=en SPLIT=development
```

The corrected segmentation archive is written under
`generated/gpt-5.6-prompt-learning-v1/segmentation_phase_2_gold/seven-en/` with
a provenance manifest. The MWE command creates named project snapshots and
exports `selected_segments.jsonl`, `summary.json`, and `review.md` under
`generated/gpt-5.6-prompt-learning-v1/mwe_gold/en-development/`. Copy or commit
these experiment outputs to the normal backed-up experiment-results location
before modifying the seven projects again.

For this checkpoint, the prompt provenance implied by the tracked command and
configuration is:

- **Model:** `gpt-5.6`.
- **English `segmentation_phase_2`:** mechanism `chunk_decomposition`, prompt
  variant `chunk_decomposition_multilingual_v1`, source split `development`,
  with chunk consistency enabled. No `chunk_prompt_cycle` was pinned in
  `config/stage_parameters.json`, so the runtime selected the latest available
  English development cycle: cycle 2,
  `prompts/segmentation_phase_2/variants/chunk_decomposition_multilingual_v1/en/development/cycle_2/prompt.md`.
- **English MWE:** `prompts/mwe/en/template.txt`, together with the two sorted
  few-shot files `prompts/mwe/en/fewshots/example1.json` and `example2.json`.
  No replacement MWE template was supplied by `refresh-annotations`.

This provenance should be made stronger in future runs: manifests should record
the resolved prompt path, cycle, few-shot paths, and content hashes rather than
requiring reconstruction from the checkout and stage parameters.

### Immediate measurements and next experiment sequence

First quantify the current 5.6 MWE baseline against the newly frozen gold:

```bash
make run-current-mwe RUN=1 \
  PROJECT_IDS="239,245,254,255,257,261,263" \
  MWE_LANGUAGE=en SPLIT=development

make score-current-mwe RUN=1 \
  PROJECT_IDS="239,245,254,255,257,261,263" \
  MWE_LANGUAGE=en SPLIT=development
```

The score output is the baseline for prompt learning, not a publishable test
estimate: the same seven projects will be used to diagnose errors and revise the
prompt. Report exact-match and component-level MWE measures together with raw
counts, and retain per-segment errors for qualitative analysis.

The first 5.6 MWE baseline was run on 2026-08-06 and scored **F1 0.862,
precision 0.863, recall 0.860** on this seven-project development gold set. This
is a substantial practical improvement over the earlier work, while remaining a
development result rather than a held-out estimate.

For `segmentation_phase_2`, compare the already archived initial 5.6 payloads
against the newly archived corrected payloads. Add a deterministic paired scorer
that reports at least exact tokenization, boundary precision/recall/F1, projects,
segments, tokens, and error counts grouped by phenomenon. The first explicit
English diagnostic category must be apostrophe clitics and contractions such as
`it's`, `we'll`, and `don't`; cycle 2 currently says not to split morphology
unless it is a standalone word and gives no English-clitic rule, which is a
plausible source of the observed errors.

Then proceed in this order:

1. Use only the seven-project development gold to run 5.6-based prompt-learning
   cycles for both `segmentation_phase_2` and MWE. Preserve baseline and every
   candidate prompt, manifest, score, and error report.
2. Draw additional English projects from the unused training/development pool.
   Freeze the prompt-learning procedure before treating a separate subset as
   validation; do not repeatedly tune on validation or test.
3. Start French and German with small manually audited development samples and
   the same archive -> correct -> freeze -> baseline -> learn protocol. Keep
   language-specific phenomena and prompts separate while sharing metrics and
   reporting structure.
4. Work backward from the ALTA 2026 deadline of 11 September: freeze the research
   questions and evaluation protocol early, reserve a genuinely untouched test
   set, and prioritize reproducible 5.6 prompt-learning gains plus error analysis
   over a transient 5.5-vs-5.6 comparison.

### English 5.6 recursive `segmentation_phase_2` prompt-learning runbook

Use the existing chunk-decomposition recursive improvement workbench, but start
a fresh 5.6 series from the seven manually corrected English projects. Do not run
the ordinary multilingual splitter for this first baseline: it would distribute
the seven projects between development, validation, and test. Instead, explicitly
extract all seven as development gold:

```bash
cd experiments/linguistic_processing/segmentation_phase_2/chunk_decomposition_multilingual

make prepare-seven-en-development-gold RUN=1 \
  EXPERIMENT_SERIES=gpt-5.6-seven-en-prompt-learning-v1 \
  PROJECT_IDS="239,245,254,255,257,261,263" \
  CORPUS_USER=mannyrayner MAX_DEVELOPMENT_CHUNKS=100000
```

This reads the latest, manually corrected `segmentation_phase_2` artifacts,
creates chunk records only for the selected projects, assigns all of them to
development, and freezes the resulting records as
`generated/gpt-5.6-seven-en-prompt-learning-v1/gold/en-development.jsonl`. The
dedicated series name prevents this extraction and its cycle numbers from
overwriting other 5.6 multilingual experiments. Confirm from
the generated manifest that the development project ids are exactly the seven
ids above before spending API calls.

Run cycle 1 with the same English cycle-2 prompt used for the initial 5.6 project
processing, so the score is an apples-to-apples baseline:

The runner deliberately leaves `temperature` unset: `gpt-5.6` accepts only its
default value and rejects the formerly hard-coded `temperature=0`. If a run made
with the older runner failed with that 400 error, update the checkout and rerun
the same command; predictions are written only after the batch completes and the
target uses `--overwrite`.

**Invalidated first attempt:** an initial run reported 4370/4370 correct. This
was gold leakage, not model performance: the runner serialized the complete
local scoring record into the API prompt, including `gold_parts` and
`gold_segments_display`. The runner now constructs an explicit model-facing
record containing only `chunk_surface` for segmentation (or `chunk_surface` and
candidate parts for rating). Discard any predictions, briefs, or revisions made
with the leaking runner and rerun cycle 1 from the unchanged seed prompt. Do not
advance to cycle 2 from the invalidated perfect-score revision.

**Corrected cycle-1 baseline (2026-08-06):** after removing gold fields from the
model-facing record, the same 4,370 development chunks scored **accuracy
0.9881**, with 4,318 correct chunks, 40 over-splits, and 12 under-splits. This is
chunk exact-match accuracy, not boundary F1. The errors are strongly concentrated
in English apostrophe clitics/contractions, with a smaller hyphen-separation
class. The generated cycle-1 revision addresses these patterns with general
rules and examples for possessive/contracted `'s`, other apostrophe clitics,
negative `n't`, surrounding quotation marks, and hyphens. Preserve the cycle-1
brief and revision as experiment evidence.

```bash
make run-prompt RUN=1 \
  EXPERIMENT_SERIES=gpt-5.6-seven-en-prompt-learning-v1 \
  MODEL=gpt-5.6 REVISION_MODEL=gpt-5.6 \
  JUDGE_LANGUAGE=en SPLIT=development PROMPT_KIND=segmentation \
  CURRENT_PROMPT=../../../../prompts/segmentation_phase_2/variants/chunk_decomposition_multilingual_v1/en/development/cycle_2/prompt.md \
  PROMPT_IMPROVEMENT_CYCLE_NUMBER=1 \
  PROMPT_LIMIT=0 MAX_CONCURRENCY=20 PROGRESS_EVERY=25

make prepare-prompt-improvement RUN=1 \
  EXPERIMENT_SERIES=gpt-5.6-seven-en-prompt-learning-v1 \
  MODEL=gpt-5.6 REVISION_MODEL=gpt-5.6 \
  JUDGE_LANGUAGE=en SPLIT=development PROMPT_KIND=segmentation \
  CURRENT_PROMPT=../../../../prompts/segmentation_phase_2/variants/chunk_decomposition_multilingual_v1/en/development/cycle_2/prompt.md \
  PROMPT_IMPROVEMENT_CYCLE_NUMBER=1
```

Inspect `cycle_1/prompt_improvement_brief.md` and `prompt_revision.md`. Review
every divergence before trusting the revision; use this to catch extraction or
gold slips, but do not change a defensible gold decision merely because the
model disagrees:

```bash
make review-prompt-divergences RUN=1 \
  EXPERIMENT_SERIES=gpt-5.6-seven-en-prompt-learning-v1 \
  JUDGE_LANGUAGE=en SPLIT=development PROMPT_KIND=segmentation \
  PROMPT_IMPROVEMENT_CYCLE_NUMBER=1 DIVERGENCE_REVIEW_LIMIT=0
```

If review changes any gold record, rerun `run-prompt` and
`prepare-prompt-improvement` for the same cycle before advancing. Then run cycle
2; its `prompt.md` is copied automatically from cycle 1's
`prompt_revision.md`:

Before running the commands below, confirm that divergence review is complete
and that any gold corrections have been followed by a fresh cycle-1 run and
brief. No `CURRENT_PROMPT` override is needed for cycle 2: `prepare-cycle` uses
`cycle_1/prompt_revision.md` as its source.

```bash
make run-prompt RUN=1 \
  EXPERIMENT_SERIES=gpt-5.6-seven-en-prompt-learning-v1 \
  MODEL=gpt-5.6 REVISION_MODEL=gpt-5.6 \
  JUDGE_LANGUAGE=en SPLIT=development PROMPT_KIND=segmentation \
  PROMPT_IMPROVEMENT_CYCLE_NUMBER=2 \
  PROMPT_LIMIT=0 MAX_CONCURRENCY=20 PROGRESS_EVERY=25

make prepare-prompt-improvement RUN=1 \
  EXPERIMENT_SERIES=gpt-5.6-seven-en-prompt-learning-v1 \
  MODEL=gpt-5.6 REVISION_MODEL=gpt-5.6 \
  JUDGE_LANGUAGE=en SPLIT=development PROMPT_KIND=segmentation \
  PROMPT_IMPROVEMENT_CYCLE_NUMBER=2

make review-prompt-divergences RUN=1 \
  EXPERIMENT_SERIES=gpt-5.6-seven-en-prompt-learning-v1 \
  JUDGE_LANGUAGE=en SPLIT=development PROMPT_KIND=segmentation \
  PROMPT_IMPROVEMENT_CYCLE_NUMBER=2 DIVERGENCE_REVIEW_LIMIT=0
```

Repeat the run -> improvement brief/revision -> human divergence review loop
only while development performance or the qualitative error analysis improves.
Track contraction/clitic errors separately rather than allowing a high overall
accuracy to conceal them. Summarize all completed cycles with:

```bash
make summarize-prompt-improvement-cycles RUN=1 \
  EXPERIMENT_SERIES=gpt-5.6-seven-en-prompt-learning-v1 \
  JUDGE_LANGUAGE=en SPLIT=development PROMPT_KIND=segmentation
```

Do not run `validate-development-prompt` yet: this explicitly selected corpus
contains development gold only. First choose a promising cycle and freeze the
learning procedure, then manually establish gold for unused English projects in
a separate validation subset. Validation may select among already-defined
candidates but must not generate another revision; test remains untouched until
the cycle-selection rule is fixed.

Before selecting more texts, rerun cycle 1 with the non-leaking runner and obtain
the real seven-project baseline. The reported 100% result cannot be used to
decide whether another sample is needed or whether cycle 2 is better.

After the corrected baseline and at least one development revision, selecting
two or three unused English projects is a good next step. First inspect what is
actually left in the original MWE development assignment on the laptop (the
generated manifests are intentionally not in Git):

```bash
cd experiments/linguistic_processing/mwe/focused_multilingual

python3 - <<'PY'
import json
from pathlib import Path

used = {239, 245, 254, 255, 257, 261, 263}
path = Path("generated/gpt-5.6-prompt-learning-v1/corpus_splits/en/split_manifest.json")
manifest = json.loads(path.read_text(encoding="utf-8"))
rows = [
    row for row in manifest["project_assignments"]
    if row["split"] == "development" and int(row["project_id"]) not in used
]
for row in sorted(rows, key=lambda item: (item.get("source_chars", 0), item["project_id"])):
    print(row["project_id"], row.get("source_chars", 0), row["title"])
print(f"remaining development projects: {len(rows)}")
PY
```

If this prints at least three candidates, choose a small, medium, and larger text
where practical. Process them with 5.6, archive the untouched outputs, and only
then review them in the manual editor. Keep this sample separate from the seven
projects. If its results influence another prompt revision, call it additional
development data; if it is used only once to choose among already-frozen cycles,
call it validation. Never call it test after inspecting or correcting it.

For selected ids `<NEW_PROJECT_IDS>`, use the MWE workbench sequence:

```bash
# Generate and preserve the new segmentation baseline.
make refresh-segmentation-phase-2 RUN=1 PROJECT_IDS="<NEW_PROJECT_IDS>"
make archive-initial-segmentation-phase-2 RUN=1 \
  PROJECT_IDS="<NEW_PROJECT_IDS>" \
  INITIAL_SEGMENTATION_ARCHIVE_DIR="generated/gpt-5.6-prompt-learning-v1/segmentation_phase_2_initial_outputs_followup_en" \
  INITIAL_SEGMENTATION_ARCHIVE_LABEL="initial-gpt-5.6-followup-en-segmentation-phase-2"

# Manually review/correct segmentation_phase_2, then run the downstream stages
# without overwriting that correction.
make refresh-annotations RUN=1 \
  PROJECT_IDS="<NEW_PROJECT_IDS>" \
  REFRESH_START_STAGE=translation REFRESH_END_STAGE=gloss

# Preserve the generated downstream baseline before manually reviewing MWE.
make snapshot-gold-projects RUN=1 \
  PROJECT_IDS="<NEW_PROJECT_IDS>" \
  SNAPSHOT_NAME_PREFIX="Pre-manual-MWE gpt-5.6 follow-up English baseline"
```

Then review MWE in the page-oriented editor. This yields a second paired sample:
uncorrected/corrected segmentation plus uncorrected/corrected MWE, without
contaminating either baseline through premature manual editing.

## Short-term plan: first French boundary-first experiment

The current working plan is concentrated in the versioned experiment workspace at
`experiments/linguistic_processing/segmentation_phase_2/fr_boundary_first_clitic_compound_v2/`.
That directory, and especially its `Makefile`, is the executable checklist for the first key experiment.
Use it as the primary handover artifact when resuming this thread: it names the target operation, language,
mechanism, curated set, corpus summary outputs, input fixtures, parameter bundles, evaluator config, and the intended command sequence.

The short-term objective is now broader than the original tiny diagnostic sample but still narrow enough for a clean report result: determine whether a curated French `segmentation_phase_2` / `boundary_first` few-shot set for clitics and transparent compounds improves boundary quality on a held-out sample drawn from imported legacy French projects, and whether AI judging can provide useful comparative evidence with human spot-checking. I am taking the initiative to structure the next implementation steps as follows:

1. **Done: orient and validate the experiment workspace.** Use `make plan` and `make validate-config` in the experiment directory to confirm the tracked default/candidate parameter files, evaluator config, and diagnostic inputs.
2. **Done for request `20260615-072115Z`: curate, AI-review, and human-audit candidates.** `make curate RUN=1` generated 80 candidates; `make review RUN=1 REQUEST_ID=20260615-072115Z` reviewed all 80 with 72 `none`, 5 `serious`, and 3 `fatal` judgements; `make audit-reviews RUN=1 REQUEST_ID=20260615-072115Z` accepted the AI judgements after human audit.
3. **Done for corpus sizing: summarize the imported French material.** `make summarize-corpus RUN=1` has produced JSON/CSV/Markdown summaries under `generated/corpus_summary/`; the reported run gives 53 projects and 1600 segments.
4. **Implemented command/target: create deterministic corpus manifests.** `make split-corpus RUN=1` calls `split_french_evaluation_corpus` over `generated/corpus_summary/corpus_summary.json` and writes `generated/corpus_splits/development.jsonl`, `generated/corpus_splits/test.jsonl`, and `generated/corpus_splits/split_manifest.json`. The split uses project-level separation, size stratification, a stable seed, and segment caps; the development split is for prompt/evaluator adjustment, while the test split must remain untouched until the comparison procedure is fixed.
5. **Implemented command/target: derive usable assets from accepted records.** `make derive-processing-examples RUN=1 REQUEST_ID=<audited-processing-id>` calls `derive_fewshot_assets --asset-kind processing`, reads reviewed and human-audited curation items for the processing target set, and writes compact prompt-facing examples for the `clitic_compound_v2` candidate variant. `make derive-evaluator-examples RUN=1 EVALUATOR_TARGET_SET=clitic_compound_v2_evaluator REQUEST_ID=<audited-evaluator-id>` now calls `derive_fewshot_assets --asset-kind evaluator` and writes a separate evaluator exemplar pool plus manifest under `generated/derived_assets/evaluator/`, so the evaluation prompt can avoid reusing the exact processing few-shot examples.
6. **Implemented first runner: run default and candidate processing variants.** `run_linguistic_pipeline_experiment` now supports the first experiment slice: `segmentation_phase_2` over JSONL split manifests. The Makefile's `run-default` and `run-candidate` targets process the same `SPLIT=development` or `SPLIT=test` records with default or curated-set parameter bundles, writing `outputs.jsonl`, per-record stage artifacts, and a run manifest. Candidate runs now expose `FEWSHOT_COUNT=small|medium|all|N`, so the development split can test whether adding more accepted examples helps, tops out, or becomes counterproductive before locking a test-setting.
7. **Implemented human spot-check target: judge segmentation outputs.** `judge-default` and `judge-candidate` call `judge_segmentation_outputs`, which displays each output as a compact `Input surface` / `Segments` prompt, appends judgements continuously for interruption-safe review, and shares a cache keyed by input surface plus the boundary-whitespace-trimmed token sequence so repeated identical segmentations are not judged twice while still being copied into the current run's judgement file for later comparison. The prompt supports `b <id>` corrections during judging and after a set is complete, giving the human supervisor an efficient development-audit loop before the automated evaluator/comparison targets are finalized.
8. **Current development milestone: default vs small candidate judged.** The development split has now completed `run-default`, `run-candidate FEWSHOT_COUNT=small`, `judge-default`, and `judge-candidate`; the judgement tool's correction flow and boundary-whitespace-normalised cache reuse have both been exercised successfully by the human collaborator.
9. **Next: development-set few-shot tranche sweep.** Keep the held-out test split untouched while running and judging additional development candidates, starting with `FEWSHOT_COUNT=medium` and `FEWSHOT_COUNT=all`. Compare default/small/medium/all judgement files on development data to decide whether more curated examples help, plateau, or hurt, then freeze one candidate setting and comparison rule before any test-set run.
10. **Implemented first comparison layer, deliberately using human judgement files.** `compare_segmentation_judgements` powers the Makefile's current `evaluate` and `compare` targets over human judgement JSONL files, not over the derived evaluator exemplars. It takes the latest human judgement per record, compares default against one or more candidate tranches, emits JSON/Markdown summaries, and writes flagged candidate wins/losses/disagreements for review. The target name `evaluate` is therefore slightly provisional: at this stage it means "evaluate from collected human judgements" rather than "call an AI evaluator."
11. **Implemented AI-evaluator calibration, with base and augmented exemplar sets kept separate.** The AI-evaluator targets consume `EVALUATOR_EXAMPLES_JSONL`, which defaults to `generated/derived_assets/evaluator/evaluator_examples.jsonl`, while `compare_segmentation_judgements` remains the human-judgement comparison layer. After scoring AI evaluator variants against development gold judgements, `make augment-evaluator-examples RUN=1` can extract adjudicated disagreement cases (by default false accepts where the corrected gold judgement is `reject`) into `generated/derived_assets/evaluator_augmented/evaluator_examples.jsonl`. This preserves the original evaluator exemplar set and gives us a controlled development-only comparison of base versus augmented evaluator prompts before freezing the evaluator source for held-out test use.
12. **Implemented sweep-correlation diagnostics.** `analyze_segmentation_judgement_sweep` and the Makefile's `analyze-sweep` target measure pairwise failure overlap across candidate tranches, record accept/reject patterns, write explicit per-run disagreement examples plus a human-readable Markdown table with rejected segmentations highlighted, and compute a judgement-level majority-vote proxy. This directly addresses whether few-shot failures are correlated or close enough to independent that an ensemble strategy may be useful.
13. **Implemented multilingual chunk-prompt validation gate.** The `chunk_decomposition_multilingual` workspace now supports iterative development cycles for English, French, and German chunk segmentation prompts, with reviewer correction of gold divergences and a separate `validate-development-prompt` target. Development cycles may revise prompts, but validation copies a chosen development `prompt_revision.md` into a `generated/prompt_validation/...` directory, runs it over the validation gold split, and writes only predictions plus a diagnostic brief. This preserves the methodological line: use development errors to edit, use validation to decide whether the chosen prompt generalises, and touch test only after the cycle and decision rule are fixed.
14. **Then: report and test freeze.** Use the development comparison, multilingual validation reports, and sweep-analysis summaries to choose one candidate setting or prompt cycle, decide whether/when to add the AI-evaluator layer, then run the held-out test default/candidate pair once and build `report` from the frozen comparison outputs.

Until these targets are complete, the roadmap should treat the Makefile as the most concrete source of truth for what happens next. The broader sections below describe the architecture we are building toward; the experiment workspace describes the first repeatable slice through that architecture.


### Chunk-decomposition consistency plan

The first promoted `chunk_decomposition` runs show a new quality issue that is different from simple surface preservation: the same lexical item can be decomposed differently in different occurrences. This is most visible for borderline compounds, where either "leave as one word" or "split as a transparent compound" may be defensible in isolation, but inconsistent treatment across a project is undesirable for learners and for downstream evaluation. The issue is not surprising because the runtime deliberately fans out whitespace chunks and may send repeated or near-repeated units to the model in parallel.

The initial plan is to make consistency a first-class objective without losing the benefits of per-chunk prompting:

1. **Define a stable lexical consistency key.** Strip chunk-initial and chunk-final punctuation/quotes/brackets into `prefix`, `core`, and `suffix`, while preserving the exact original surface for reconstruction. The consistency key should normally be `(language, normalized_core)` rather than the full chunk, so forms such as `Wort`, `Wort,`, and `"Wort"` can share one decomposition decision. The normalizer should reuse the existing equivalent-glyph repair idea for apostrophes, quotes/guillemets, and dash/hyphen variants, but it must not erase linguistically meaningful characters.
2. **Implemented first version: cache and reuse decisions within a run.** Before launching fan-out requests, group chunks by exact surface so repeated identical chunks in one text share one model call, then run a postprocessing consistency pass keyed by normalized core. Fan-in wraps the chosen core decomposition with the original occurrence's punctuation parts. This addresses parallelism directly: repeated chunks should not race each other into inconsistent outputs. A `chunk_consistency` stage parameter can switch this per-run cache/postprocessing layer on or off for experiments.
3. **Separate core decomposition from punctuation handling.** The model prompt and trace should distinguish the `core_surface` being normalized for consistency from the full `chunk_surface` being reconstructed. This is important because repeated words often appear with different chunk-final punctuation, and punctuation should not force a new lexical decision.
4. **Persist a cross-text decision cache, with efficiency as an explicit goal.** For project-level and corpus-level consistency, add a versioned decision cache keyed by language, prompt variant/split/cycle, model, and normalized core. Runtime use should be opt-in at first, probably via a stage parameter such as `chunk_consistency_cache_path`, so we can compare local-only consistency against shared-cache behavior. Cache records should include provenance: prompt variant/cycle, source examples, accepted parts, first-seen context, model, timestamp, and enough versioning information to invalidate stale entries safely. If this proves reliable, promote it from a consistency aid into an efficiency feature: repeated whitespace chunks across a project, corpus, or future run should be served from cache without another model call, which should materially reduce `segmentation_phase_2` latency and cost.
5. **Handle ambiguous items conservatively.** Some compounds are genuinely borderline. The cache should be able to mark a key as `ambiguous` or `do_not_cache` when human review or conflicting high-confidence evidence suggests that context may matter. The default should prefer consistency for identical normalized cores, but the design should leave an escape hatch rather than forcing false uniformity.
6. **Keep separable-verb and related cross-stage phenomena out of segmentation-only hacks.** Germanic separable verbs are a useful warning case: a non-separated form may reasonably remain undecomposed in `segmentation_phase_2`, while the separated verb plus particle should be recognised later as a multiword unit and should share a lemma with the non-separated form. The general mechanism should therefore be cross-stage and language-configurable rather than German-specific: MWE detection should be able to mark discontinuous or separated predicate units, and lemma tagging should be able to inherit or assign a shared lemma for tokens that carry such an MWE/separable-predicate annotation. Similar cross-stage consistency cases are likely in other languages, so the roadmap should treat this as a reusable "related forms share lemma despite different surface segmentation" pattern.
7. **Expose consistency in trace and review tooling.** Extend `segmentation_phase_2_chunk_trace` with fields such as `consistency_key`, `core_surface`, `cache_status` (`miss`, `hit`, `in_flight_join`, `persistent_hit`, `ambiguous_skip`), and `canonical_parts`. The chunk workbench can then report inconsistent decisions for the same key and feed them into `review_chunk_prompt_divergences` or a new lightweight `review_chunk_consistency` command. For the persistent cache, aggregate hit-rate, avoided-call count, and estimated cost/latency savings should be reported alongside linguistic consistency diagnostics.
8. **Evaluate before making it default.** Add small unit tests for grouping, punctuation wrapping, single-flight concurrency, persistent-cache reads/writes, and trace fields. Then run the German examples that exposed the issue through the workbench and compare: current independent fan-out, per-run grouped consistency, and optional persistent-cache consistency. Promote the consistency layer only if it reduces inconsistent decompositions without increasing surface-preservation failures or over-splitting, and only promote persistent reuse by default after measuring both annotation quality and call reduction.

This should now be treated as a staged design slice for `chunk_decomposition_multilingual`: the first per-run consistency layer exists, but the remaining work is to harden the grouping/keying rules, add persistent cross-text caching as both a consistency and efficiency feature, and finally connect separable-predicate/related-form cases to MWE and lemma-tagging rather than overloading token segmentation.


### Test-set run checklist for the French boundary-first experiment

The development work has now chosen two evaluator sources worth preserving: the original evaluator exemplar set under `generated/derived_assets/evaluator/` and the augmented evaluator exemplar set under `generated/derived_assets/evaluator_augmented/`, which includes development-only adjudicated disagreement cases. The test set should be run once the chosen processing tranche and evaluator comparison settings have been frozen. The following commands are intended to be cut and pasted from the experiment directory; replace placeholders before running.

```bash
cd experiments/linguistic_processing/segmentation_phase_2/fr_boundary_first_clitic_compound_v2

# 0. Orientation/sanity checks. These should not modify experiment results.
make plan
make validate-config

# 1. Confirm the split manifests exist. Re-run only if generated/corpus_splits/
#    is missing or known to be stale; the seed/caps must remain unchanged.
make split-corpus RUN=1

# 2. Run the frozen processing variants on the held-out test split.
make run-default RUN=1 SPLIT=test
make run-candidate RUN=1 SPLIT=test FEWSHOT_COUNT=<chosen-processing-fewshot-count>

# 3. Collect human gold judgements on the test split. This is required if we
#    want to measure how well the AI evaluator is working on held-out data.
make judge-default RUN=1 SPLIT=test JUDGE_LIMIT=0
make judge-candidate RUN=1 SPLIT=test FEWSHOT_COUNT=<chosen-processing-fewshot-count> JUDGE_LIMIT=0

# 4. Run the original/base AI evaluator on the test default and candidate outputs.
#    Repeat for small/medium/all if we want a base evaluator sweep on test.
make ai-evaluate-default RUN=1 SPLIT=test EVALUATOR_FEWSHOT_COUNT=small
make ai-evaluate-candidate RUN=1 SPLIT=test FEWSHOT_COUNT=<chosen-processing-fewshot-count> EVALUATOR_FEWSHOT_COUNT=small

# 5. Run the augmented AI evaluator on the same held-out outputs, without
#    overwriting the base evaluator files. Use the absolute path printed by `pwd`.
AUGMENTED_EVALUATOR_EXAMPLES="$(pwd)/generated/derived_assets/evaluator_augmented/evaluator_examples.jsonl"
make ai-evaluate-default RUN=1 SPLIT=test \
  EVALUATOR_EXAMPLES_JSONL="$AUGMENTED_EVALUATOR_EXAMPLES" \
  EVALUATOR_SCORE_PREFIX=evaluator-augmented-fewshots \
  EVALUATOR_ACCURACY_LABEL=augmented-accuracy \
  EVALUATOR_FEWSHOT_COUNT=small
make ai-evaluate-candidate RUN=1 SPLIT=test \
  FEWSHOT_COUNT=<chosen-processing-fewshot-count> \
  EVALUATOR_EXAMPLES_JSONL="$AUGMENTED_EVALUATOR_EXAMPLES" \
  EVALUATOR_SCORE_PREFIX=evaluator-augmented-fewshots \
  EVALUATOR_ACCURACY_LABEL=augmented-accuracy \
  EVALUATOR_FEWSHOT_COUNT=small

# 6. Score AI-vs-human agreement on the test split and review divergences.
#    Correct only clear human slips; leave genuine/borderline disagreements unchanged.
make score-ai-evaluator-default RUN=1 SPLIT=test EVALUATOR_FEWSHOT_COUNTS="small medium all"
make score-ai-evaluator-candidate RUN=1 SPLIT=test FEWSHOT_COUNT=<chosen-processing-fewshot-count> EVALUATOR_FEWSHOT_COUNTS="small medium all"
make score-ai-evaluator-default RUN=1 SPLIT=test \
  EVALUATOR_SCORE_PREFIX=evaluator-augmented-fewshots \
  EVALUATOR_ACCURACY_LABEL=augmented-accuracy \
  EVALUATOR_FEWSHOT_COUNTS="small medium all"
make score-ai-evaluator-candidate RUN=1 SPLIT=test \
  FEWSHOT_COUNT=<chosen-processing-fewshot-count> \
  EVALUATOR_SCORE_PREFIX=evaluator-augmented-fewshots \
  EVALUATOR_ACCURACY_LABEL=augmented-accuracy \
  EVALUATOR_FEWSHOT_COUNTS="small medium all"
make review-ai-evaluator-default RUN=1 SPLIT=test \
  EVALUATOR_SCORE_PREFIX=evaluator-augmented-fewshots \
  EVALUATOR_ACCURACY_LABEL=augmented-accuracy \
  REVIEW_DISAGREEMENT_LIMIT=0
make review-ai-evaluator-candidate RUN=1 SPLIT=test \
  FEWSHOT_COUNT=<chosen-processing-fewshot-count> \
  EVALUATOR_SCORE_PREFIX=evaluator-augmented-fewshots \
  EVALUATOR_ACCURACY_LABEL=augmented-accuracy \
  REVIEW_DISAGREEMENT_LIMIT=0

# 7. Re-score after any clear-slip corrections, then produce human and AI comparisons.
make score-ai-evaluator-default RUN=1 SPLIT=test EVALUATOR_FEWSHOT_COUNTS="small medium all"
make score-ai-evaluator-candidate RUN=1 SPLIT=test FEWSHOT_COUNT=<chosen-processing-fewshot-count> EVALUATOR_FEWSHOT_COUNTS="small medium all"
make score-ai-evaluator-default RUN=1 SPLIT=test \
  EVALUATOR_SCORE_PREFIX=evaluator-augmented-fewshots \
  EVALUATOR_ACCURACY_LABEL=augmented-accuracy \
  EVALUATOR_FEWSHOT_COUNTS="small medium all"
make score-ai-evaluator-candidate RUN=1 SPLIT=test \
  FEWSHOT_COUNT=<chosen-processing-fewshot-count> \
  EVALUATOR_SCORE_PREFIX=evaluator-augmented-fewshots \
  EVALUATOR_ACCURACY_LABEL=augmented-accuracy \
  EVALUATOR_FEWSHOT_COUNTS="small medium all"
make evaluate RUN=1 SPLIT=test FEWSHOT_COUNT=<chosen-processing-fewshot-count>
make compare-ai-evaluator RUN=1 SPLIT=test FEWSHOT_COUNT=<chosen-processing-fewshot-count> EVALUATOR_FEWSHOT_COUNT=small
make compare-ai-evaluator RUN=1 SPLIT=test \
  FEWSHOT_COUNT=<chosen-processing-fewshot-count> \
  EVALUATOR_EXAMPLES_JSONL="$AUGMENTED_EVALUATOR_EXAMPLES" \
  EVALUATOR_SCORE_PREFIX=evaluator-augmented-fewshots \
  EVALUATOR_ACCURACY_LABEL=augmented-accuracy \
  EVALUATOR_FEWSHOT_COUNT=small
```

If we decide to run an evaluator sweep on the test split, repeat steps 4 and 5 with `EVALUATOR_FEWSHOT_COUNT=medium` and `EVALUATOR_FEWSHOT_COUNT=all`, and set `EVALUATOR_SCORE_PREFIX=evaluator-augmented-fewshots EVALUATOR_ACCURACY_LABEL=augmented-accuracy` when scoring augmented evaluator files. Do **not** use test-set disagreements to create a new augmented evaluator set; any additional evaluator calibration must come from development data only. It is methodologically sound to use AI/human divergences on the test split to find likely human clerical slips, provided corrections are conservative: change only cases that are clearly careless annotation errors, keep borderline linguistic judgements unchanged, and preserve the correction log. After this audit pass, `make evaluate RUN=1 SPLIT=test ...` is the authoritative human-backed report number, while `compare-ai-evaluator` is supporting evidence about how closely the AI evaluator tracks the same comparison.


### Concrete evaluator-exemplar command sequence

The evaluator few-shot examples should be produced by rerunning the same curation/review/audit pipeline, but with a **different target set** from the processing examples. This is the key safety valve against accidental overwrite and against methodological circularity. The original processing examples live under the `clitic_compound_v2` target set; evaluator examples should use a separate target such as `clitic_compound_v2_evaluator`. Because the target set is part of the curation directory path, using `CURATION_TARGET_SET=clitic_compound_v2_evaluator` writes a separate candidate/review/audit tree instead of replacing the existing `clitic_compound_v2` segmentation set.

The intended command sequence is:

```bash
# 0. Work in the experiment directory. Dry-run first if unsure.
cd experiments/linguistic_processing/segmentation_phase_2/fr_boundary_first_clitic_compound_v2
make plan
make validate-config

# 1. Generate a separate evaluator candidate pool.
#    This does NOT overwrite the segmentation/processing pool because the target set differs.
make curate RUN=1 CURATION_TARGET_SET=clitic_compound_v2_evaluator

# 2. Review the evaluator candidate pool. Use the request id printed by step 1.
make review RUN=1 \
  CURATION_TARGET_SET=clitic_compound_v2_evaluator \
  REQUEST_ID=<evaluator-curation-request-id>

# 3. Human-audit the evaluator review output. This creates the audit gate for evaluator examples.
make audit-reviews RUN=1 \
  CURATION_TARGET_SET=clitic_compound_v2_evaluator \
  REQUEST_ID=<evaluator-curation-request-id> \
  AUDIT_LIMIT=0

# 4. Derive evaluator exemplars only. This reads the evaluator target set and writes
#    generated/derived_assets/evaluator/evaluator_examples.jsonl plus a manifest;
#    it does not touch prompts/segmentation_phase_2/variants/clitic_compound_v2/fewshots/.
make derive-evaluator-examples RUN=1 \
  EVALUATOR_TARGET_SET=clitic_compound_v2_evaluator \
  REQUEST_ID=<evaluator-curation-request-id>
```

For comparison, the processing examples continue to use the existing processing target set and derivation command:

```bash
make derive-processing-examples RUN=1 REQUEST_ID=<audited-processing-request-id>
```

The next AI-evaluator implementation should consume `generated/derived_assets/evaluator/evaluator_examples.jsonl`, not the processing prompt few-shot directory. It should then compare AI evaluator decisions against the human judgement JSONL files already collected on the development split.


### Autonomy note for report evidence

This experiment is also becoming a concrete example of AI autonomy in the project workflow. The AI assistant has not only implemented requested commands; it has proposed the experimental sequence, converted loose maintainer goals into reproducible Make targets, specified leakage controls, formulated hypotheses and audit gates, and updated the report-facing documentation as the design evolved. Human input has remained essential as supervision, plausibility checking, and acceptance, but the experimental design and implementation are increasingly AI-led. This should be cited cautiously in the report as process evidence rather than as a claim that the scientific conclusions are autonomous or unaudited.

## Core architecture: generate → adversarial review → repair → gold acceptance

The target architecture is a pipeline for few-shot examples themselves:

1. **Generate candidates generously.** For each operation/language/mechanism, generate more examples than will be used in prompts. Candidate batches should deliberately cover edge cases such as punctuation, clitics, compounds, named entities, idioms, discontinuous MWEs, ambiguous glosses, and examples where the correct action is to leave default boundaries unchanged.
2. **Validate against an explicit schema.** Before asking for linguistic judgement, run deterministic checks: valid JSON/XML or boundary-marked text, token surfaces line up with source text, MWE spans refer to existing tokens, gloss counts match token/MWE units, no duplicated or missing items, and no empty units unless explicitly allowed.
3. **Use critic models as adversarial reviewers.** Prompt critic models to find the strongest reason an example should *not* be used as a few-shot example. Require severity labels such as `fatal`, `serious`, `minor`, or `none` rather than a rubber-stamp yes/no judgement.
4. **Repair before discard.** If critics find plausible defects, ask a stronger repair model to preserve the pedagogical intent while producing a corrected example. Re-run schema validation and adversarial criticism on repaired candidates.
5. **Use consensus scoring, not unanimity.** Score each candidate using schema pass/fail, linguistic confidence, critic agreement, and severity penalties. For core/high-cost examples, require a final arbiter call that sees the original example, critiques, and repairs.
6. **Accept into an auditable gold library.** Accepted examples should carry provenance: original generated example, operation/language/mechanism, validation results, critic comments, repairs, final accepted version, acceptance rationale, model/prompt versions, and timestamps.

## Scope

In scope:

- Few-shot examples for linguistic annotation prompts, starting with:
  - `segmentation_phase_1` segment-boundary selection,
  - `segmentation_phase_2` tokenization/boundary repair,
  - MWE detection.
- Ordered example sets and tranche sizes (`minimal`, `small`, `medium`, `all`) that can be selected through stage parameters.
- AI-assisted generation, adversarial criticism, repair, and acceptance of candidate examples.
- Evaluation of example-set variants using the pipeline runner and AI-based judges.
- Versioned, auditable example records in addition to compact prompt assets.

Out of scope for the first pass:

- Full expert linguistic validation for every language.
- A large multilingual gold corpus before the evaluator workflow exists.
- Replacing human review where expert judgement is available; the goal is to make review targeted and evidence-based.

## Initial problem statement

Few-shot examples are currently easy to add but hard to trust. Known risks include:

- linguistically wrong examples being amplified by prompts;
- examples that overfit to one language or phenomenon;
- example ordering that makes `fewshot_count` tranches arbitrary;
- example sets that appear better by anecdote but are not measured against default processing;
- prompts and examples drifting apart as mechanisms such as `boundary_first` evolve;
- lack of traceability when annotation failures may be caused or reinforced by bad few-shot examples.

## Proposed workflow

### 1. Define operation/language phenomenon matrices

For each stage and mechanism, define a compact phenomenon list before generating examples. For `segmentation_phase_2`, the first list should include:

- apostrophe clitics where default punctuation splitting is too fine;
- bound clitic strings that need new internal boundaries;
- transparent compounds that should be split;
- cases where default boundaries should be left alone;
- cases where provisional markers should be deleted.

For MWE detection, the first list should include:

- continuous idioms;
- phrasal verbs and light-verb constructions;
- named entities that should not be misclassified as MWEs;
- discontinuous or interrupted expressions where supported by the representation;
- ambiguous cases where the expected decision should be explicit.

### 2. Generate candidate pools

Generate candidate examples in batches larger than the target prompt tranche size. Store raw candidates separately from prompt assets so rejected and repaired examples remain inspectable.

Candidate metadata should include operation, language, mechanism/variant, intended phenomenon, generator model, generator prompt version, and generation timestamp.

### 3. Run deterministic validation

Before linguistic criticism, validate each candidate against stage-specific rules. Initial validators should check:

- JSON/XML parseability or boundary-marker format;
- source-text preservation modulo permitted markers;
- token/MWE/gloss span consistency;
- no missing, duplicated, or empty annotation units unless explicitly allowed;
- stable sorting/tranche metadata;
- compatibility with the prompt template that would consume the example.

### 4. Run adversarial critic review

Critic prompts should ask for defects, not approval. A useful review shape is:

- strongest reason not to use this as a few-shot example;
- severity: `fatal`, `serious`, `minor`, or `none`;
- affected annotation units/spans;
- suggested repair, if possible;
- confidence and brief rationale.

Multiple critic models or prompt variants can be used when the example is central to a default prompt set.

### 5. Repair and re-review

If a defect is plausible and repairable, run a repair step that preserves the intended phenomenon and pedagogical purpose. The repaired candidate then returns to deterministic validation and critic review. Fatal unrepaired examples stay in the audit trail but are not promoted.

### 6. Score and accept gold examples

Maintain a score such as:

```text
schema_pass + linguistic_confidence + critic_agreement - severity_penalties
```

Use thresholds to decide whether a candidate is rejected, repaired again, accepted into an experimental set, or accepted into a gold/default set. For high-impact examples, add an arbiter model call that sees the original, validation results, critiques, and repairs before final acceptance.

### 7. Promote prompt assets deliberately

Accepted gold examples can be copied into compact prompt-facing few-shot files under `prompts/<stage>/...`. Experimental examples should remain named variants until evaluator evidence supports promotion to defaults.

## Auditable example records

Prompt-facing files should stay small, but the project should also be able to store richer records for accepted and rejected candidates. A future record could include:

- `example_id`;
- operation, language, mechanism, variant, and intended phenomenon;
- original generated example;
- deterministic validation results;
- critic model/prompt versions and comments;
- repair attempts;
- final accepted version;
- acceptance score and rationale;
- generator/critic/repair/arbiter model versions;
- links to pipeline/evaluator runs that used the example.

These records matter because later annotation failures should be traceable back to the few-shot examples that may have influenced them.


## Invocation, storage, use, and review model

In practice, curation should be incremental rather than a single large generation run. We should be able to ask for "more French `segmentation_phase_2/boundary_first` clitic examples" or "a first MWE idiom batch for Drehu" without disturbing existing accepted examples.

### Invocation surfaces

Start with two complementary invocation paths:

1. **Management command for repeatable generation experiments.** The first minimal command is `python manage.py curate_fewshots --operation segmentation_phase_2 --language fr --mechanism boundary_first --phenomena clitic,compound --count 40 --target-set clitic_compound_v2`. It generates candidate JSON examples with trace output and fan-out/fan-in shards (`--batch-size`, `--max-concurrency`), validates them deterministically, stores auditable records, and can optionally write valid examples into a prompt variant. This is the right surface for bulk generation, laptop/server runs, scripted reruns, and reproducible report evidence.
2. **Management command for AI review.** The initial second-step command is `python manage.py review_fewshots --operation segmentation_phase_2 --language fr --mechanism boundary_first --target-set clitic_compound_v2 --request-id <request-id>`. If no language-specific review template exists, it first creates several AI-drafted templates, reconciles them with another AI call, stores the final template under the curation tree, then reviews candidates concurrently and writes `reviews/*.review.json` plus a summary. It accepts `--timeout-s` for slower models. The review prompt is deliberately framed as a plain word/unit-boundary task: deterministic validation has already checked preservation, so the AI reviewer sees an `input` and `boundary_marked` string and judges whether the material between boundary markers should count as word-like or meaningful units, with language-specific guidance and concrete positive/negative examples such as clitic splitting, transparent compound splitting, false compound rejection, and cases where default boundaries should remain unchanged.
3. **Admin UI for small requests and review.** Add an admin-only page where a maintainer can create a curation request, inspect generated candidates, run critic/repair passes, and promote accepted examples. The UI should be able to request additional examples for an existing operation/language/set and should show existing coverage by phenomenon and tranche.

Both paths should create a durable curation request record before calling models. A request should include operation, language, mechanism, target set, requested phenomena, requested count, generator/critic/repair model choices, prompt versions, submitter, timestamp, and notes.

### Incremental batches

A few-shot set should be built from many batches. Each batch should have a stable ID and status, for example:

- `requested`;
- `generated`;
- `schema_validated`;
- `critic_reviewed`;
- `repair_pending`;
- `repaired`;
- `accepted_experimental`;
- `accepted_gold`;
- `rejected`;
- `promoted_to_prompt_assets`.

This lets us top up an existing language or operation without rerunning the whole pipeline. If a language later shows a new failure mode, we add a targeted batch for that phenomenon and evaluate whether it improves outputs.

### Storage layout

Prompt-facing few-shot files should remain compact under `prompts/<operation>/...`, but curation records should be stored separately so rejected and repaired examples remain auditable. A proposed repository layout is:

```text
docs/few_shot_curation/
  segmentation_phase_2/
    fr/
      boundary_first/
        clitic_compound_v2/
          requests/20260602-001.json
          candidates/EXAMPLE-0001.json
          reviews/EXAMPLE-0001.critic-gpt-5.3.json
          repairs/EXAMPLE-0001.repair-gpt-5.5.json
          accepted/EXAMPLE-0001.json
          manifest.json
```

The `manifest.json` should list accepted examples, their ordering/tranche membership, validation status, scores, and the prompt-asset files they were copied into. Generated and reviewed examples can be large; compact prompt assets should be derived outputs, not the only source of truth.


### Pipeline experiment CLI for curated few-shot testing

To test curated sets properly, add a third management-command surface that invokes linguistic processing directly rather than going through the annotation UI. A provisional command name is:

```bash
python manage.py run_linguistic_pipeline_experiment \
  --project <project-id-or-slug> \
  --start-stage segmentation_phase_1 \
  --end-stage mwe \
  --stage-parameters-json '{"segmentation_phase_2":{"mechanism":"boundary_first","variant":"clitic_compound_v2","fewshot_count":"small"}}' \
  --run-label fr-clitic-compound-v2-small
```

The command should also accept `--stage-parameters-file <json-file>` so longer parameter bundles can be versioned and reused. For experiments based on curated examples, the important stage-parameter keys are the already-supported prompt/few-shot selectors, for example `mechanism`, `variant` or `fewshot_variant`, and `fewshot_count`. The command should resolve those settings to actual prompt/template/few-shot files and record both the requested parameter bundle and the resolved files in the run artifact.

Minimum options for the first version:

- `--project` or `--source-file` / `--source-json` to select the input material;
- `--l1` and `--l2` when the input is not an existing project;
- `--start-stage` and `--end-stage` using the same stage names as `FullPipelineSpec`;
- `--stage-parameters-json` and/or `--stage-parameters-file`;
- `--persist-intermediates` (default on for experiments);
- `--output-root` and `--run-label`;
- `--dry-run` to print the resolved stage plan, prompt/few-shot variant files, and output paths without model calls.

The command should write an auditable experiment directory, e.g.:

```text
docs/pipeline_experiments/
  runs/
    20260604-fr-clitic-compound-v2-small/
      config.json
      resolved_stage_parameters.json
      input_snapshot.json
      stage_outputs/
      processing_parameters.json
      manifest.json
```

This fills the gap between curated example creation and evaluator work: it lets maintainers run the same project or source sample with the default few-shot set, then with a curated set, while preserving exactly which examples and stage parameters were used.

### Using curated examples

Accepted examples should become usable in three closely related ways:

1. **Experimental processing variants.** Algorithmically post-process selected accepted records into the compact prompt-facing shape expected by the stage, then copy them into a named prompt/few-shot variant under `prompts/<operation>/variants/<variant>/fewshots/`. For `segmentation_phase_2`, this can be as simple as preserving the accepted `input` and converting the accepted boundary units into the JSON `output.tokens` representation. The source curation record remains the auditable source of truth; the prompt file is a derived asset. Existing stage parameters such as `{"segmentation_phase_2": {"mechanism": "boundary_first", "variant": "clitic_compound_v2", "fewshot_count": "small"}}` should select the derived set for processing.
2. **Evaluation exemplars.** Wrap the same accepted records in evaluator templates that ask a model to *check* an output rather than *produce* one. The positive/negative examples, severity definitions, and repair notes from curation become a rubric for judging whether new outputs have similarly appropriate word-like or meaningful units.
3. **Default promotion.** After evaluator evidence shows that a set improves outputs, promote a selected tranche to the operation/language default few-shot directory, preserving links back to curation record IDs.

The evaluator should record operation, language, mechanism, prompt variant, few-shot set, tranche size, candidate record IDs, any derived prompt/evaluator asset paths, and score deltas so a report claim can identify exactly what changed.

### Review workflow

Review should not require a maintainer to read every raw model output. The admin/review surface should prioritize:

- candidates with fatal/serious critic findings;
- candidates selected for `minimal` or `small` tranches;
- examples proposed for default promotion;
- examples associated with a known annotation failure mode;
- disagreements between critics and repair/arbiter outcomes.

A human reviewer can then accept, reject, request more repair, or mark an example as experimental-only. The review decision and rationale should be stored in the same curation record.

## Near-term implementation steps

The immediate checklist is the French `clitic_compound_v2` Makefile workflow described above. In roadmap terms:

1. **Done in minimal form:** add validation utilities for `segmentation_phase_2` few-shot candidates. Extend these validators to MWE and later lemma/gloss examples.
2. **Done in minimal form:** implement a traced, fan-out/fan-in candidate-generation command for `segmentation_phase_2`, initially useful for French `boundary_first` experiments.
3. **Done in minimal form:** implement a second-step AI review command that creates/reconciles language-specific word/unit-boundary review templates when needed, then runs hostile-review calls over generated candidates. The prompt avoids project-internal terms and focuses on whether proposed boundary markers define appropriate word-like or meaningful units.
4. **Done in first smoke-test form:** run and manually inspect a French `clitic_compound_v2` batch; eight retained examples from an initial 40-candidate set were all judged correct by maintainer review, while validation-failed candidates are now excluded from AI review.
5. **Done for the first full-sized batch:** generate 80 candidates with `make curate RUN=1`, review request `20260615-072115Z` with `make review RUN=1 REQUEST_ID=20260615-072115Z`, and human-audit the review output with `make audit-reviews RUN=1 REQUEST_ID=20260615-072115Z`. The AI review labelled 72 examples `none`, 5 `serious`, and 3 `fatal`; the human audit accepted all AI judgements, with some borderline cases noted.
6. **Current executable handover:** keep `experiments/linguistic_processing/segmentation_phase_2/fr_boundary_first_clitic_compound_v2/Makefile` aligned with this plan and use its dry-run targets (`plan`, `validate-config`, `run-default`, `run-candidate`, `judge-default`, `judge-candidate`, `evaluate`, `compare`, `analyze-sweep`) to show the intended sequence.
7. **Done in first implementation:** derive processing examples and evaluator exemplar assets with `derive_fewshot_assets`; processing and evaluator derivations can now be run separately over different target sets, so processing examples are active inputs to candidate runs while the independently curated evaluator exemplars are staged for a later AI-judge command.
8. **Done in first implementation:** run `run_linguistic_pipeline_experiment` over deterministic split manifests and collect human judgements with `judge_segmentation_outputs`.
9. **Done in first implementation:** compare default and candidate human judgement files with `compare_segmentation_judgements`; this is the current implementation behind `evaluate`/`compare`. Sweep-level overlap and voting diagnostics are handled by `analyze_segmentation_judgement_sweep`.
10. **Next implementation step:** add an AI-evaluator command that consumes `generated/derived_assets/evaluator/evaluator_examples.jsonl` and the evaluator config to judge output pairs or individual segmentations, then compare its decisions against the human development judgements.
11. Add repair prompts and re-review loops for candidates with fatal/serious/minor findings.
12. Expand persisted records from candidate/request/accepted/manifest files to include repair, arbiter, and human-review records.
13. Run the first documented default-vs-`clitic_compound_v2` held-out test experiment, inspect the flagged examples, and then decide whether the set remains experimental, needs more curation, or should be promoted toward default prompts.
14. After the French segmentation slice is stable, reuse the same curation/evaluation pattern for MWE detection and additional languages.

## Relationship to other roadmap items

- [AI judges evaluation](ai-judges-evaluation.md): provides the evaluator architecture and comparison workflow.
- [Segmentation pipeline](segmentation-pipeline.md): owns the segmentation stages where the first experiments are happening.
- [MWE strategy](mwe-strategy.md): should receive the same curation/evaluation treatment once segmentation experiments are stable.
- [Reports and papers](reports-and-papers.md): can use this work as evidence that C-LARA-2 improvements are being guided by AI-assisted evaluation rather than ad hoc prompt editing.

## Success criteria

- Few-shot example sets are versioned, selectable, and documented by stage/mechanism.
- Tranche choices are meaningful and ordered from simplest/highest-confidence examples to broader coverage.
- Automated checks catch preservation/schema mistakes before examples are used in runs.
- Adversarial critics and repair steps improve the accepted library rather than just rejecting many examples.
- AI-based evaluators can show whether a prompt/few-shot change improves outputs on representative cases.
- The First Progress Report can cite at least one concrete example where evaluation of few-shot variants led to a better processing choice.

## 2026-07-04 English MWE development pilot

The focused multilingual MWE workbench has produced a small but useful first English development sample after page-oriented manual correction. Seven EN development projects (`239`, `245`, `254`, `255`, `257`, `261`, `263`) now have refreshed project metadata showing 336 segments, 5,104 tokens, and 140 manually corrected MWEs. This is not large enough for a final benchmark claim, but it is large enough for a first prompt-improvement loop because the current baseline MWE quality is poor and the error patterns should be visible.

Use this sample as **development gold only**. The next experiment should freeze the project IDs above, export segment records from the latest corrected `mwe.json` artifacts, score the current MWE prompt against those gold token groups, and then run one or two prompt/few-shot variants before touching validation or test projects. The comparison should score token-set MWE groups within segments rather than relying on local MWE ID strings, since MWE IDs are bookkeeping labels local to a segment.

This is also a report-facing AI-autonomy vignette. The human collaborator supplied expert MWE corrections and judged that the refreshed counts looked plausible; the AI assistant diagnosed the metadata-counting problem, added tooling to refresh fixed-split project metadata from latest artifacts, proposed a leakage-controlled experimental sequence, and recorded the evolving plan in issue, roadmap, and report files. The report should present this as supervised AI-led experimental orchestration, not as unsupervised scientific conclusion-making.
