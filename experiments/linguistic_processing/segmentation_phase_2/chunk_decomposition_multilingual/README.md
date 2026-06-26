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

## Prompt-improvement briefs

Starter prompts live under `prompts/chunk_segmentation/` and
`prompts/chunk_rating/`. After judging a split, first run the current prompt to
create prediction records:

```bash
make run-prompt RUN=1 \
  JUDGE_LANGUAGE=fr \
  SPLIT=development \
  PROMPT_KIND=segmentation \
  PROMPT_LIMIT=0 \
  MAX_CONCURRENCY=4 \
  PROGRESS_EVERY=25
```

This writes `generated/predictions/<language>-<prompt-kind>-<split>.jsonl`.
`run-prompt` uses fan-out/fan-in: it sends up to `MAX_CONCURRENCY` chunk requests
at a time and writes the final JSONL in the original record order. Progress is
reported every `PROGRESS_EVERY` completed records; set `PROGRESS_EVERY=0` to
suppress progress updates.

Then use `prepare-prompt-improvement` to compare the predictions with the
human-gold file, produce a compact revision brief, and by default ask the model
to draft a revised prompt.

```bash
make prepare-prompt-improvement RUN=1 \
  JUDGE_LANGUAGE=fr \
  SPLIT=development \
  PROMPT_KIND=segmentation \
  PREDICTION_RECORDS=generated/predictions/fr-segmentation-development.jsonl
```

For the independent rating-prompt track, switch `PROMPT_KIND=rating` and point
`PREDICTION_RECORDS` at rating judgements for the same gold records.

### Where prompts come from and where revisions go

- `CURRENT_PROMPT` is the prompt being evaluated and improved. By default it is
  selected from `PROMPT_KIND` and `JUDGE_LANGUAGE`: segmentation uses
  `prompts/chunk_segmentation/<language>.md`, and rating uses
  `prompts/chunk_rating/<language>.md`.
- `run-prompt` reads `CURRENT_PROMPT` and writes predictions only. It does not
  edit prompt files.
- `prepare-prompt-improvement` reads `CURRENT_PROMPT`, the gold records, and the
  prediction records, then writes a JSON/Markdown brief under
  `generated/prompt_improvement/<language>-<prompt-kind>-<split>/`.
- With the default `GENERATE_REVISED_PROMPT=1`, `prepare-prompt-improvement`
  also writes `revised_prompt.md` and `prompt_revision.json` in that same
  directory. These are generated artifacts; the command still does not edit the
  checked-in prompt files under `prompts/`.
- To iterate, inspect `revised_prompt.md`, copy or adapt it into a new prompt
  file manually, for example `prompts/chunk_segmentation/fr_v2.md`, then rerun
  `run-prompt` with
  `CURRENT_PROMPT=prompts/chunk_segmentation/fr_v2.md` and a distinct
  `PREDICTION_RECORDS=...fr-segmentation-development-v2.jsonl`.
- Set `GENERATE_REVISED_PROMPT=0` if you only want the diagnostic brief and do
  not want to spend an extra model call drafting a revised prompt.

### Diagnostics

The generated brief deliberately stresses anti-overfitting constraints:

- keep the revised prompt small and principle-based;
- use only a minimal number of examples;
- avoid memorising rare development-set chunks;
- revise from development evidence, then check whether the change generalises on
  validation before touching the held-out test split.

This gives us parallel, comparable improvement loops for (1) producing chunk
segmentations directly and (2) judging whether a proposed chunk segmentation is
correct.

Use the development split for revision decisions. To check whether a revised
prompt generalises, rerun `run-prompt` and `prepare-prompt-improvement` with
`SPLIT=validation` and the same `CURRENT_PROMPT`; treat the validation brief as a
diagnostic, not as another source of prompt edits. The held-out test split should
remain untouched until the workflow and prompt choice are fixed.
