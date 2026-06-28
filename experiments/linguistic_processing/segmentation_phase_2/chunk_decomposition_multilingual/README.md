# Multilingual chunk-decomposition segmentation experiments

This workspace is for the redesigned `segmentation_phase_2` experiments where the
operation is constrained to decompose each whitespace-delimited chunk independently.
Later MWE processing remains responsible for joining material across whitespace.

The first target extracts gold chunk-level decomposition records from existing
`segmentation_phase_2` project artifacts and creates project-separated
`development`, `validation`, and `test` splits for French, German, and English by
default.

```bash
make extract-split-corpus RUN=1
```

Useful overrides:

```bash
make extract-split-corpus RUN=1 \
  CORPUS_USER=mannyrayner \
  LANGUAGES=fr,de,en \
  DEVELOPMENT_PROJECT_FRACTION=0.50 \
  VALIDATION_PROJECT_FRACTION=0.25 \
  MAX_DEVELOPMENT_CHUNKS=800 \
  MAX_VALIDATION_CHUNKS=400 \
  MAX_TEST_CHUNKS=800
```

Outputs are written under `generated/corpus_splits/`:

- `multilingual_split_manifest.json` — top-level run manifest;
- `<language>/development.jsonl` — tuning records;
- `<language>/validation.jsonl` — inner-loop validation records;
- `<language>/test.jsonl` — held-out records;
- `<language>/split_manifest.json` — per-language split manifest.

## Human gold judging

The extracted records are a starting point, not yet a gold standard. Use
`judge-corpus` to accept the current decomposition or replace it with a corrected
`|`-delimited decomposition. The correction must concatenate exactly to the
displayed chunk, which catches accidental edits to the surface form.

```bash
make judge-corpus RUN=1 JUDGE_LANGUAGE=fr SPLIT=development
```

Useful controls:

```bash
make judge-corpus RUN=1 \
  JUDGE_LANGUAGE=de \
  SPLIT=validation \
  JUDGE_LIMIT=50
```

The command writes append-only, resumable records to
`generated/gold/<language>-<split>.jsonl`. Prompt commands are:

- `a` — accept the displayed decomposition;
- `c PART|PART` — replace it with a corrected decomposition;
- `s` — skip the record for now;
- `b <number-or-record-id>` — go back and rejudge a previous record;
- `q` — quit, preserving judgements already written.


## Deleting an incorrectly imported project from generated artifacts

If an imported project has the wrong language metadata, prune it from the
generated chunk-experiment artifacts before rerunning splits or prompt cycles.
The target scans JSONL files under `DELETE_PROJECT_SUBDIR` and removes records
matching either `DELETE_PROJECT_ID` or the exact `DELETE_PROJECT_TITLE`. It is a
dry run unless `RUN=1` is supplied:

```bash
make delete-project-data RUN=1 \
  DELETE_PROJECT_SUBDIR=generated \
  DELETE_PROJECT_TITLE="Kok Kaper"
```

Prefer `DELETE_PROJECT_ID=<id>` when it is known, since titles are only matched
exactly. The command rewrites JSONL files in place under the chosen subtree; if
you prune corpus split or gold files, rerun the downstream prompt cycles that
depended on those records.

## Prompt-improvement cycles

Starter prompts live under `prompts/chunk_segmentation/` and
`prompts/chunk_rating/`, but iterative runs are kept in cycle-specific generated
folders. Set `PROMPT_IMPROVEMENT_CYCLE_NUMBER` to choose the cycle. Cycle 1 copies
`CURRENT_PROMPT` into `prompt.md`; cycle N>1 copies `prompt_revision.md` from
cycle N-1 into the new cycle's `prompt.md`.

First run the prompt for the current cycle:

```bash
make run-prompt RUN=1 \
  JUDGE_LANGUAGE=fr \
  SPLIT=development \
  PROMPT_KIND=segmentation \
  PROMPT_IMPROVEMENT_CYCLE_NUMBER=1 \
  PROMPT_LIMIT=0 \
  MAX_CONCURRENCY=4 \
  PROGRESS_EVERY=25
```

This creates or reuses
`generated/prompt_improvement/<language>-<prompt-kind>-<split>/cycle_<n>/prompt.md`
and writes predictions to the same cycle directory as `predictions.jsonl`.
`run-prompt` uses fan-out/fan-in: it sends up to `MAX_CONCURRENCY` chunk requests
at a time and writes the final JSONL in the original record order. Progress is
reported every `PROGRESS_EVERY` completed records; set `PROGRESS_EVERY=0` to
suppress progress updates.

Then use `prepare-prompt-improvement` to compare the cycle predictions with the
human-gold file, produce a compact revision brief, and by default ask the model
to draft the next prompt revision.

```bash
make prepare-prompt-improvement RUN=1 \
  JUDGE_LANGUAGE=fr \
  SPLIT=development \
  PROMPT_KIND=segmentation \
  PROMPT_IMPROVEMENT_CYCLE_NUMBER=1
```

Each cycle directory contains the full state needed to inspect or reproduce that
pass:

- `prompt.md` — the prompt evaluated during this cycle;
- `predictions.jsonl` — model outputs for this prompt over the selected split;
- `prompt_improvement_brief.json` and `prompt_improvement_brief.md` — error
  summaries and selected examples;
- `prompt_revision.md` and `prompt_revision.json` — the generated candidate
  prompt for the next cycle when `GENERATE_REVISED_PROMPT=1`; `prompt_revision.md`
  is self-contained and includes any generated examples that will be sent in the
  next cycle.


To inspect exactly what will be sent to the API for one record, write a full
prompt preview:

```bash
make preview-prompt RUN=1 \
  JUDGE_LANGUAGE=en \
  SPLIT=development \
  PROMPT_KIND=segmentation \
  PROMPT_IMPROVEMENT_CYCLE_NUMBER=1 \
  PROMPT_PREVIEW_RECORD_NUMBER=1
```

This writes `full_api_prompt_preview.txt` in the cycle directory. It includes the
cycle-local prompt text, the surface-preservation guard, the JSON schema hint,
and the selected record payload.

For the independent rating-prompt track, switch `PROMPT_KIND=rating`. It uses the
same cycle layout under `<language>-rating-<split>/`.

### Where prompts come from and where revisions go

- `CURRENT_PROMPT` is only the seed prompt for cycle 1. By default it is selected
  from `PROMPT_KIND` and `JUDGE_LANGUAGE`: segmentation uses
  `prompts/chunk_segmentation/<language>.md`, and rating uses
  `prompts/chunk_rating/<language>.md`.
- `run-prompt` evaluates the cycle-local `prompt.md`; it does not edit the
  checked-in starter prompts under `prompts/`.
- `prepare-prompt-improvement` reads the same cycle-local `prompt.md`, the gold
  records, and the cycle's `predictions.jsonl`, then writes the brief and
  `prompt_revision.md` into that cycle directory.
- To start cycle 2, run the same targets with
  `PROMPT_IMPROVEMENT_CYCLE_NUMBER=2`; the Makefile copies
  `cycle_1/prompt_revision.md` to `cycle_2/prompt.md` if the cycle prompt does
  not already exist.
- If you want to discard manual edits in an existing cycle and recopy its source
  prompt, set `RESET_CYCLE_PROMPT=1`.
- Set `GENERATE_REVISED_PROMPT=0` if you only want the diagnostic brief and do
  not want to spend an extra model call drafting a revised prompt.

Summarize progress across cycles with:

```bash
make summarize-prompt-improvement-cycles RUN=1 \
  JUDGE_LANGUAGE=fr \
  SPLIT=development \
  PROMPT_KIND=segmentation
```

This writes `cycles_summary.json` and `cycles_summary.md` under the
`generated/prompt_improvement/<language>-<prompt-kind>-<split>/` base directory.



### Reviewing prompt/gold divergences

After `run-prompt` and `prepare-prompt-improvement`, use the cycle-local
`review-prompt-divergences` target to inspect every non-matching prediction/gold
pair and repair clear gold-standard slips before using the errors to revise the
prompt further:

```bash
make review-prompt-divergences RUN=1 \
  JUDGE_LANGUAGE=de \
  SPLIT=development \
  PROMPT_KIND=segmentation \
  PROMPT_IMPROVEMENT_CYCLE_NUMBER=2 \
  DIVERGENCE_REVIEW_LIMIT=0
```

The reviewer shows the segment, chunk, current gold decomposition, and cycle
prediction. Use `a` when the gold standard is correct, `p` when the prediction
should replace the gold decomposition, `c PART|PART` for a manual correction,
`s` to skip, `b <number-or-record-id>` to go back, and `q` to quit. Corrections
are appended to `generated/gold/<language>-<split>.jsonl`, so subsequent commands
see the latest corrected gold record. Review decisions are logged in the cycle
directory as `gold_divergence_review.jsonl`, which lets the target resume without
showing already-reviewed divergences.

### Surface-preservation guard

`run-prompt` now wraps every cycle prompt with an explicit invariant: segment only
`Record.chunk_surface`, never the surrounding `Record.segment_surface`, and return
parts whose concatenation is exactly the chunk surface. If a model nevertheless
returns sentence-level parts, the runner records the raw response, replaces the
predicted parts with the unsplit chunk for downstream safety, and marks the record
with `invalid_response=true` and `surface_preserved=false`. The improvement brief
then classifies these cases as `invalid_surface`, making prompt-wiring failures
visible instead of silently treating sentence-level segmentations as ordinary
chunk decompositions.

### Diagnostics

The generated brief deliberately stresses anti-overfitting constraints:

- keep the revised prompt compact and principle-based without leaving important rules implicit;
- include a small curated set of examples for distinct general rules and common edge cases;
- avoid memorising rare development-set chunks or adding a large example catalogue;
- revise from development evidence, then check whether the change generalises on
  validation before touching the held-out test split.

This gives us parallel, comparable improvement loops for (1) producing chunk
segmentations directly and (2) judging whether a proposed chunk segmentation is
correct.

Use the development split for revision decisions. To check whether a revised
prompt generalises, run validation with `SPLIT=validation` and seed that
validation cycle from the chosen development `prompt_revision.md` via
`CURRENT_PROMPT=generated/prompt_improvement/<language>-<prompt-kind>-development/cycle_<n>/prompt_revision.md`.
Treat the validation brief as a diagnostic, not as another source of prompt
edits. The held-out test split should remain untouched until the workflow and
prompt choice are fixed.
