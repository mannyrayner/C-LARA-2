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
2. `derive-processing-examples` — convert accepted records from the audited `clitic_compound_v2` curation request into compact prompt-facing few-shot assets under `prompts/segmentation_phase_2/variants/clitic_compound_v2/fewshots/`.
3. `derive-evaluator-examples` — convert the same accepted records into evaluator exemplars/rubric material under `generated/derived_assets/evaluator_examples.jsonl`.
4. `run-default` / `run-candidate` — run fixed split manifests through default and candidate `segmentation_phase_2` processing with `run_linguistic_pipeline_experiment`; candidate runs can vary `FEWSHOT_COUNT=small|medium|all|N`.
5. `evaluate` / `compare` / `report` — produce paired judgements, aggregate results, and write a concise report artifact.

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
make evaluate
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
make derive-evaluator-examples RUN=1 REQUEST_ID=20260615-072115Z
make curate RUN=1
make review RUN=1 REQUEST_ID=<curation-request-id>
make audit-reviews RUN=1 REQUEST_ID=<curation-request-id> AUDIT_LIMIT=20
make run-default RUN=1 SPLIT=development
make run-candidate RUN=1 SPLIT=development FEWSHOT_COUNT=small
make run-candidate RUN=1 SPLIT=development FEWSHOT_COUNT=medium
make run-candidate RUN=1 SPLIT=development FEWSHOT_COUNT=all
make run-default RUN=1 SPLIT=test
make run-candidate RUN=1 SPLIT=test FEWSHOT_COUNT=<chosen>
```

`make summarize-corpus RUN=1` writes JSON, CSV, and Markdown corpus summaries under `generated/corpus_summary/` for French projects owned by `mannyrayner` by default. Override `CORPUS_USER=...`, `CORPUS_LANGUAGE=...`, or `CORPUS_LANGUAGE_MATCH=prefix` when inspecting a different imported corpus. The summary includes per-project counts for pages, segments, current `segmentation_phase_2` tokens, non-whitespace tokens, whitespace-only tokens, source/segment/token character counts with and without whitespace, and simple anomaly counts.

`make split-corpus RUN=1` reads `generated/corpus_summary/corpus_summary.json` and writes `generated/corpus_splits/development.jsonl`, `generated/corpus_splits/test.jsonl`, and `generated/corpus_splits/split_manifest.json`. The split is deterministic for `SPLIT_SEED`, keeps projects in only one split, stratifies projects by size, and caps selected segment records so development stays small enough for iteration while test remains held out.

`make derive-processing-examples RUN=1 REQUEST_ID=<audited-id>` requires a human-audit JSONL file unless the management command is explicitly run with `--allow-unaudited`. The target writes processing few-shots into the prompt variant directory and derives evaluator examples at the same time; `derive-evaluator-examples` is an alias/dependency target that documents the shared derivation step.

After `make review`, the review step writes `reviews/<request-id>.items.json`, a compact summary for human scanning.
Use `make audit-reviews RUN=1 REQUEST_ID=<id>` to step through these items and write a local human audit JSONL file.

`make run-default RUN=1 SPLIT=development` and `make run-candidate RUN=1 SPLIT=development FEWSHOT_COUNT=small` run the default and candidate `segmentation_phase_2` parameter bundles over a split manifest. Candidate runs override `segmentation_phase_2.fewshot_count` at the command line, so development experiments can test whether quality tops out or degrades as more accepted examples are included. Use the development split while tuning the few-shot tranche and evaluator; reserve `SPLIT=test` until the comparison procedure and chosen few-shot count are fixed. Each run writes `outputs.jsonl`, per-record stage artifacts, and a run `manifest.json` under `generated/default/` or `generated/candidate/`.
When invoked from Cygwin with Windows Python, the Makefile converts the split manifest, stage-parameter file, prompt, curation, and output paths with `cygpath` before passing them to Django, and the runner applies the same path normalization for direct command-line use. The runner also uses extended-length Windows paths for nested per-record stage artifacts, since the generated run label plus record directory can otherwise exceed the classic Windows `MAX_PATH` limit.

Some targets intentionally document future commands that still need implementation, especially
the evaluator/comparison/report helpers.
