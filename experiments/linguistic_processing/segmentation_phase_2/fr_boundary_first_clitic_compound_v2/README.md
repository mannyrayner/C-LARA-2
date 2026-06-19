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

I am taking the initiative to make the next targets data-oriented rather than immediately running more model calls. The next Makefile additions should be:

1. `split-corpus` — consume `generated/corpus_summary/corpus_summary.json` and write deterministic development/test manifests under `generated/corpus_splits/`, ideally with project-level separation and stratification by project size.
2. `derive-processing-examples` — convert accepted records from the audited `clitic_compound_v2` curation request into compact prompt-facing few-shot assets.
3. `derive-evaluator-examples` — convert the same accepted records into evaluator exemplars/rubric material.
4. `run-default` / `run-candidate` — run fixed split manifests through default and candidate `segmentation_phase_2` processing.
5. `evaluate` / `compare` / `report` — produce paired judgements, aggregate results, and write a concise report artifact.

## Suggested workflow

Start with dry-run planning commands:

```bash
make plan
make validate-config
make summarize-corpus
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
make curate RUN=1
make review RUN=1 REQUEST_ID=<curation-request-id>
make audit-reviews RUN=1 REQUEST_ID=<curation-request-id> AUDIT_LIMIT=20
make run-candidate RUN=1
```

`make summarize-corpus RUN=1` writes JSON, CSV, and Markdown corpus summaries under `generated/corpus_summary/` for French projects owned by `mannyrayner` by default. Override `CORPUS_USER=...`, `CORPUS_LANGUAGE=...`, or `CORPUS_LANGUAGE_MATCH=prefix` when inspecting a different imported corpus. The summary includes per-project counts for pages, segments, current `segmentation_phase_2` tokens, non-whitespace tokens, whitespace-only tokens, source/segment/token character counts with and without whitespace, and simple anomaly counts.

After `make review`, the review step writes `reviews/<request-id>.items.json`, a compact summary for human scanning.
Use `make audit-reviews RUN=1 REQUEST_ID=<id>` to step through these items and write a local human audit JSONL file.

Some targets intentionally document future commands that still need implementation, especially
`run_linguistic_pipeline_experiment` and the derivation/evaluator helpers.
