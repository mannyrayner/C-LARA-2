# French boundary-first segmentation experiment: `clitic_compound_v2`

This experiment is the first concrete test of the few-shot curation and AI-evaluation workflow described in
`docs/roadmap/ai-judges-evaluation.md`.

## Goal

Compare a default `segmentation_phase_2` processing run with a candidate run that uses curated French
`boundary_first` clitic/compound examples. The first version is deliberately narrow:

- language: French (`fr`);
- stage: `segmentation_phase_2`;
- candidate mechanism: `boundary_first`;
- candidate curated set: `clitic_compound_v2`;
- evaluation focus: whether proposed word-like / meaningful-unit boundaries are useful for learners.

## Versioned files

- `Makefile` — orchestration targets for the experiment steps.
- `configs/default_stage_parameters.json` — default processing bundle.
- `configs/candidate_stage_parameters.json` — curated-set candidate processing bundle.
- `configs/evaluator_config.json` — initial evaluator/repeated-judge configuration.
- `fixtures/input_records.jsonl` — small hand-authored diagnostic inputs.

## Non-versioned files

The `generated/` and `tmp/` directories are ignored. They are for command outputs, model responses,
intermediate pipeline artifacts, and local scratch data. Few-shot curation and review records produced by
`make curate RUN=1` and `make review RUN=1 ...` are written under `generated/few_shot_curation/` rather
than `docs/few_shot_curation/`, so experiment runs can remain local until explicitly promoted.

## Current corpus snapshot

A maintainer run of `make summarize-corpus RUN=1` on 2026-06-19 against the laptop C-LARA-2 account for `mannyrayner` reported a sufficiently large French evaluation corpus:

- 53 French (`fr`) projects, all with `segmentation_phase_2`;
- 1600 segments;
- 17344 current segmentation tokens total;
- 10566 non-whitespace tokens and 6778 whitespace-only tokens;
- 53625 token-surface characters including whitespace and 45704 excluding whitespace;
- 60 empty-token segments and 0 empty token surfaces.

This is enough material for a report-quality first experiment, provided that later targets create a deterministic development/test split and keep the held-out test portion isolated from prompt/evaluator iteration.

## Next implementation targets

I am taking the initiative to make the next targets data-oriented rather than immediately running more model calls. The current and next Makefile targets are:

1. `split-corpus` — consume `generated/corpus_summary/corpus_summary.json` and write deterministic development/test manifests under `generated/corpus_splits/`, with project-level separation, size stratification, and segment caps controlled by `DEV_PROJECT_FRACTION`, `MAX_DEVELOPMENT_SEGMENTS`, and `MAX_TEST_SEGMENTS`.
2. `derive-processing-examples` — convert accepted records from the audited processing curation request (`PROCESSING_TARGET_SET`, default `clitic_compound_v2`) into compact prompt-facing few-shot assets under `prompts/segmentation_phase_2/variants/clitic_compound_v2/fewshots/`.
3. `derive-evaluator-examples` — convert a separate audited evaluator curation request (`EVALUATOR_TARGET_SET`, default `clitic_compound_v2_evaluator`) into evaluator exemplars/rubric material under `generated/derived_assets/evaluator/evaluator_examples.jsonl`.
4. `run-default` / `run-candidate` — run fixed split manifests through default and candidate `segmentation_phase_2` processing with `run_linguistic_pipeline_experiment`; candidate runs can vary `FEWSHOT_COUNT=small|medium|all|N`.
5. `judge-default` / `judge-candidate` — interactively audit segmentation outputs in a compact display, append judgements continuously, and reuse cached decisions for repeated identical segmentations.
6. `ai-evaluate-default` / `ai-evaluate-candidate` — use the separately derived evaluator exemplars to run AI boundary-quality judgements over default or candidate `outputs.jsonl` files. Vary `EVALUATOR_FEWSHOT_COUNT=small|medium|all|N` to create an evaluator sweep.
7. `score-ai-evaluator-default` / `score-ai-evaluator-candidate` — score the AI evaluator judgements against the existing human judgement JSONL files, including a majority-vote summary across `EVALUATOR_FEWSHOT_COUNTS`.
8. `review-ai-evaluator-default` / `review-ai-evaluator-candidate` — inspect AI/human disagreements, append corrected gold judgements to the human judgement JSONL, and write a review log.
9. `evaluate` — compare the default judgements against one candidate tranche (`FEWSHOT_COUNT=<count>`) and write JSON/Markdown summaries plus flagged examples.
10. `compare` / `analyze-sweep` / `report` — aggregate the development-set tranche sweep (`COMPARE_FEWSHOT_COUNTS`), analyze failure overlap and majority-vote proxy behaviour, and write a concise report artifact.


## Current development-set status (2026-06-21)

The development split has now completed the first full manual judgement loop for the default processing bundle and the default candidate bundle (`FEWSHOT_COUNT=small`):

- `make run-default RUN=1 SPLIT=development` completed and wrote 235 records under `generated/default/`;
- `make run-candidate RUN=1 SPLIT=development FEWSHOT_COUNT=small` completed and wrote the matching candidate outputs under `generated/candidate/`;
- `make judge-default RUN=1 SPLIT=development` completed, including use of the `b <id>` correction flow;
- `make judge-candidate RUN=1 SPLIT=development FEWSHOT_COUNT=small` completed with cache reuse after normalising boundary whitespace tokens.

My proposed next step is to keep the test split untouched and run a development-set tranche sweep before selecting the final test procedure:

1. Run and judge additional candidate tranches on the development split, at minimum `FEWSHOT_COUNT=medium` and `FEWSHOT_COUNT=all`; consider one numeric count if the small/medium/all pattern suggests a non-monotonic effect.
2. Compare the development judgement files across default, small, medium, and all to identify whether performance improves, plateaus, or degrades as more curated examples are added.
3. Freeze a single candidate setting and comparison rule before running any `SPLIT=test` target.
4. Run the held-out test default/candidate pair once, then audit only the pre-specified sample of wins/losses/ties and anomalies for report claims.

This keeps the experiment aligned with the AI-autonomy theme: I am using the available evidence to propose the next high-level experimental step, while the human collaborator supplies supervision and judgement data.

## Hypotheses and human audit gates

The first report experiment should test three explicit hypotheses:

1. **H1 — candidate quality:** the curated French `boundary_first` `clitic_compound_v2` few-shot set improves `segmentation_phase_2` boundary quality over the default bundle on held-out imported French project segments.
2. **H2 — evaluator usefulness:** repeated AI boundary-quality judgements can identify default-vs-candidate wins/losses accurately enough that targeted human audit confirms the aggregate direction.
3. **H3 — anti-overfitting discipline:** deterministic project-level development/test separation reduces leakage when the AI adjusts prompts, examples, and evaluator wording.

Human audit should happen at three gates rather than continuously:

1. **Split audit before tuning:** inspect `generated/corpus_splits/split_manifest.json` and small samples from `development.jsonl` and `test.jsonl` to confirm project-level separation, size/genre coverage, and no obvious overrepresentation of malformed/empty segments.
2. **Development audit during tuning:** audit a small sample of development-set AI evaluator decisions, plus all severe disagreements or surprising candidate wins/losses, while allowing prompt/evaluator changes only from development evidence.
3. **Final test audit before reporting:** after the procedure is fixed, run the held-out test comparison once, then audit a stratified sample of test wins/losses/ties and all high-impact anomalies before making report claims.

## Suggested workflow

Start with dry-run planning commands:

```bash
make plan
make validate-config
make summarize-corpus
make split-corpus
make run-default
make run-candidate
make judge-default
make judge-candidate
make ai-evaluate-default
make ai-evaluate-candidate
make score-ai-evaluator-default
make score-ai-evaluator-candidate
make review-ai-evaluator-default
make review-ai-evaluator-candidate
make evaluate
make compare
make analyze-sweep
```

Targets default to dry-run mode where applicable. The default Makefile model is `gpt-4o` with three
independent review passes per item and a 600-second review timeout because these batch jobs have been
timing out with slower models; override `MODEL=...`, `REVIEW_PASSES=...`, or `TIMEOUT_S=...` on the
command line for comparison runs. Set `RUN=1` when the corresponding management command
exists and you want to execute it for real, for example:

```bash
make summarize-corpus RUN=1
make split-corpus RUN=1
make derive-processing-examples RUN=1 REQUEST_ID=20260615-072115Z
make curate RUN=1 CURATION_TARGET_SET=clitic_compound_v2_evaluator
make review RUN=1 CURATION_TARGET_SET=clitic_compound_v2_evaluator REQUEST_ID=<evaluator-curation-request-id>
make audit-reviews RUN=1 CURATION_TARGET_SET=clitic_compound_v2_evaluator REQUEST_ID=<evaluator-curation-request-id> AUDIT_LIMIT=20
make derive-evaluator-examples RUN=1 EVALUATOR_TARGET_SET=clitic_compound_v2_evaluator REQUEST_ID=<evaluator-curation-request-id>
make run-default RUN=1 SPLIT=development
make run-candidate RUN=1 SPLIT=development FEWSHOT_COUNT=small
make run-candidate RUN=1 SPLIT=development FEWSHOT_COUNT=medium
make run-candidate RUN=1 SPLIT=development FEWSHOT_COUNT=all
make run-default RUN=1 SPLIT=test
make run-candidate RUN=1 SPLIT=test FEWSHOT_COUNT=<chosen>
make judge-default RUN=1 SPLIT=development JUDGE_LIMIT=20
make judge-candidate RUN=1 SPLIT=development FEWSHOT_COUNT=small JUDGE_LIMIT=20
make ai-evaluate-default RUN=1 SPLIT=development EVALUATOR_FEWSHOT_COUNT=small
make ai-evaluate-candidate RUN=1 SPLIT=development FEWSHOT_COUNT=small EVALUATOR_FEWSHOT_COUNT=small
make score-ai-evaluator-default RUN=1 SPLIT=development EVALUATOR_FEWSHOT_COUNTS="small medium all"
make score-ai-evaluator-candidate RUN=1 SPLIT=development FEWSHOT_COUNT=small EVALUATOR_FEWSHOT_COUNTS="small medium all"
make review-ai-evaluator-default RUN=1 SPLIT=development REVIEW_DISAGREEMENT_LIMIT=0
make review-ai-evaluator-candidate RUN=1 SPLIT=development FEWSHOT_COUNT=small REVIEW_DISAGREEMENT_LIMIT=0
make evaluate RUN=1 SPLIT=development FEWSHOT_COUNT=small
make compare RUN=1 SPLIT=development COMPARE_FEWSHOT_COUNTS="small medium all"
make analyze-sweep RUN=1 SPLIT=development COMPARE_FEWSHOT_COUNTS="small medium all"
```

`make summarize-corpus RUN=1` writes JSON, CSV, and Markdown corpus summaries under `generated/corpus_summary/` for French projects owned by `mannyrayner` by default. Override `CORPUS_USER=...`, `CORPUS_LANGUAGE=...`, or `CORPUS_LANGUAGE_MATCH=prefix` when inspecting a different imported corpus. The summary includes per-project counts for pages, segments, current `segmentation_phase_2` tokens, non-whitespace tokens, whitespace-only tokens, source/segment/token character counts with and without whitespace, and simple anomaly counts.

`make split-corpus RUN=1` reads `generated/corpus_summary/corpus_summary.json` and writes `generated/corpus_splits/development.jsonl`, `generated/corpus_splits/test.jsonl`, and `generated/corpus_splits/split_manifest.json`. The split is deterministic for `SPLIT_SEED`, keeps projects in only one split, stratifies projects by size, and caps selected segment records so development stays small enough for iteration while test remains held out.

`make curate`, `make review`, and `make audit-reviews` accept `CURATION_TARGET_SET=<set>` so the same curation pipeline can create either processing examples (`clitic_compound_v2`) or a separate evaluator-example pool (`clitic_compound_v2_evaluator`). `make derive-processing-examples RUN=1 REQUEST_ID=<audited-processing-id>` requires a human-audit JSONL file and writes only processing few-shots into the prompt variant directory. `make derive-evaluator-examples RUN=1 EVALUATOR_TARGET_SET=clitic_compound_v2_evaluator REQUEST_ID=<audited-evaluator-id>` is now a real derivation target: it reads the separate evaluator curation request and writes evaluator exemplars plus a manifest under `generated/derived_assets/evaluator/`, without modifying the processing prompt few-shot directory.

After `make review`, the review step writes `reviews/<request-id>.items.json`, a compact summary for human scanning.
Use `make audit-reviews RUN=1 REQUEST_ID=<id>` to step through these items and write a local human audit JSONL file.

`make run-default RUN=1 SPLIT=development` and `make run-candidate RUN=1 SPLIT=development FEWSHOT_COUNT=small` run the default and candidate `segmentation_phase_2` parameter bundles over a split manifest. Candidate runs override `segmentation_phase_2.fewshot_count` at the command line, so development experiments can test whether quality tops out or degrades as more accepted examples are included. Use the development split while tuning the few-shot tranche and evaluator; reserve `SPLIT=test` until the comparison procedure and chosen few-shot count are fixed. Each run writes `outputs.jsonl`, per-record stage artifacts, and a run `manifest.json` under `generated/default/` or `generated/candidate/`.
When invoked from Cygwin with Windows Python, the Makefile converts the split manifest, stage-parameter file, prompt, curation, and output paths with `cygpath` before passing them to Django, and the runner applies the same path normalization for direct command-line use. The runner also uses extended-length Windows paths for nested per-record stage artifacts, since the generated run label plus record directory can otherwise exceed the classic Windows `MAX_PATH` limit.

`make analyze-sweep RUN=1 COMPARE_FEWSHOT_COUNTS="small medium all"` investigates whether candidate failures are correlated across tranches. It writes `sweep_analysis.json`, `sweep_analysis.md`, `sweep_patterns.jsonl`, `sweep_disagreements.jsonl`, and `sweep_disagreements.md` under `generated/evaluation/<split>-sweep-analysis/`, including pairwise failure-set overlap, accept/reject pattern counts such as `AAR`, inspectable examples where candidate runs disagree, a human-readable Markdown table that highlights rejected candidate segmentations, and a judgement-level majority-vote proxy. The voting result is not yet a token-level ensemble decoder; it is a diagnostic for whether an ensemble-style strategy might be worth implementing.

`make ai-evaluate-default RUN=1 EVALUATOR_FEWSHOT_COUNT=<count>` and `make ai-evaluate-candidate RUN=1 FEWSHOT_COUNT=<processing-count> EVALUATOR_FEWSHOT_COUNT=<count>` use `EVALUATOR_EXAMPLES_JSONL` as evaluator few-shots; by default this is `generated/derived_assets/evaluator/evaluator_examples.jsonl`. They write AI judgement JSONL files under `generated/ai_evaluator/` and share a cache keyed by input, displayed segmentation, model, evaluator variant, and selected exemplar IDs. Run these on the development split first with `EVALUATOR_FEWSHOT_COUNT=small`, `medium`, and `all`; then score the evaluator variants against human judgements with `make score-ai-evaluator-default RUN=1 EVALUATOR_FEWSHOT_COUNTS="small medium all"` or `make score-ai-evaluator-candidate RUN=1 FEWSHOT_COUNT=<processing-count> EVALUATOR_FEWSHOT_COUNTS="small medium all"`. The scoring target reports per-variant accuracy, false accepts, false rejects, and a majority-vote row. If the disagreement file shows likely errors in the human gold judgements, use `make review-ai-evaluator-default RUN=1` or `make review-ai-evaluator-candidate RUN=1 FEWSHOT_COUNT=<processing-count>` to inspect those cases. The review target appends corrected gold records to the same human judgement JSONL file, so downstream scoring uses latest-judgement semantics. It also writes an audit trail to `gold_review_corrections.jsonl`.

If development scoring shows a systematic evaluator weakness such as false accepts, keep the original evaluator exemplar set unchanged and create a second, explicitly calibrated set with `make augment-evaluator-examples RUN=1`. This reads `generated/ai_evaluator/<split>-default-accuracy/evaluator_disagreements.jsonl`, extracts adjudicated gold-reject disagreement cases by default, and writes `generated/derived_assets/evaluator_augmented/evaluator_examples.jsonl` plus a manifest. To compare base versus augmented evaluator prompts, rerun `ai-evaluate-*` with `EVALUATOR_EXAMPLES_JSONL=$(abspath generated/derived_assets/evaluator_augmented/evaluator_examples.jsonl)` `EVALUATOR_SCORE_PREFIX=evaluator-augmented-fewshots`, and `EVALUATOR_ACCURACY_LABEL=augmented-accuracy`; this writes distinct AI judgement files such as `development-default-evaluator-augmented-fewshots-small.jsonl` and keeps the augmented scoring summary in a separate accuracy directory instead of overwriting the base sweep. `make compare-ai-evaluator RUN=1` compares the AI-evaluator default and candidate judgement files for the currently selected evaluator label. Freeze whichever exemplar source performs best on development before using it on `SPLIT=test`.

`make evaluate RUN=1 FEWSHOT_COUNT=<count>` compares the latest default and candidate **human judgement** records for a single candidate tranche. `make compare RUN=1 COMPARE_FEWSHOT_COUNTS="small medium all"` compares all listed judged tranches against the default. Both commands write `comparison_summary.json`, `comparison_summary.md`, and `flagged_examples.jsonl` under `generated/evaluation/`; corrections are handled by taking the latest JSONL judgement for each `record_id`. Candidate wins are cases where the default judgement is not `accept` and the candidate is `accept`; candidate losses are the reverse. These targets remain human-judgement comparison tools; the `ai-evaluate-*` and `score-ai-evaluator-*` targets are the new AI-evaluator calibration path.

`make judge-default RUN=1` and `make judge-candidate RUN=1 FEWSHOT_COUNT=<count>` read the corresponding `outputs.jsonl` files and show each item as a compact human-audit prompt, for example `Input surface: "\nDans un futur proche,"` followed by `Segments: "Dans| |un| |futur| |proche|,"`. Judgements are appended immediately under `generated/human_judgements/` so interrupted sessions can resume, and the shared `segmentation_judgement_cache.json` avoids asking again when the same input/tokenization pair appears in another run; leading and trailing whitespace-only tokens are ignored for display/cache matching, so equivalent segmentations from different mechanisms can reuse judgements; Make targets pass `--include-cached`, so reused judgements are still copied into the current run's judgement file for later comparison. Use `JUDGE_LIMIT=<N>` for short development audits and leave it at `0` for no explicit limit. During judging, `b <id>` returns to an item number or record id, appends a corrected judgement, updates the cache, and then resumes at the next unjudged item; once all items are judged, the tool keeps a small correction menu open with only `b <id>` and `q`.

The evaluator targets are intended for development-set calibration first. Only promote an AI-evaluator ensemble to held-out test reporting after its target split, model, exemplar counts, and voting rule have been frozen from development evidence.
