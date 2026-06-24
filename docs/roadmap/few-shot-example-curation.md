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
13. **Then: report and test freeze.** Use the development comparison and sweep-analysis summaries to choose one candidate setting or ensemble strategy, decide whether/when to add the AI-evaluator layer, then run the held-out test default/candidate pair once and build `report` from the frozen comparison outputs.

Until these targets are complete, the roadmap should treat the Makefile as the most concrete source of truth for what happens next. The broader sections below describe the architecture we are building toward; the experiment workspace describes the first repeatable slice through that architecture.


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
