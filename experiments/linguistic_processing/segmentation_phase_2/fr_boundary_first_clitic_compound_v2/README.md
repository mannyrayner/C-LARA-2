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

## Suggested workflow

Start with dry-run planning commands:

```bash
make plan
make validate-config
make run-default
make run-candidate
make evaluate
```

Targets default to dry-run mode where applicable. The default Makefile model is `gpt-4o` with a 600-second
review timeout because these batch jobs have been timing out with slower models; override `MODEL=...` or
`TIMEOUT_S=...` on the command line for comparison runs. Set `RUN=1` when the corresponding management command
exists and you want to execute it for real, for example:

```bash
make curate RUN=1
make review RUN=1 REQUEST_ID=<curation-request-id>
make run-candidate RUN=1
```

Some targets intentionally document future commands that still need implementation, especially
`run_linguistic_pipeline_experiment` and the derivation/evaluator helpers.
