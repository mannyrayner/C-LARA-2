# Focused multilingual MWE workbench

This workbench mirrors the organisation of
`segmentation_phase_2/chunk_decomposition_multilingual`, but extracts segment
records rather than whitespace chunks. Splits are project-separated, so all
segments from a project stay in the same development, validation, or test split.

## Goals

1. Start with `extract-split-corpus` to assign English/French/German projects to
   deterministic development/validation/test splits.
2. Refresh the selected projects through `segmentation_phase_2`, `translation`,
   `mwe`, `lemma`, and `gloss`, so manual judging starts from current annotations
   and the page-oriented editor has useful lemma/gloss context.
3. Rerun `extract-split-corpus` after refresh or manual correction to export
   segment-level JSONL records with the current MWE annotations for prompt
   scoring and diagnostics.

The split assignment is deterministic from project metadata and the seed, and it
can be run before MWE artifacts exist. If MWE artifacts are not present yet, the
project JSONL/manifests are still written and segment JSONL files are empty until
the refresh pass creates current `mwe` stage artifacts.

## Commands

```bash
make help
make validate-config
```

Create project-separated splits first:

```bash
make extract-split-corpus CORPUS_USER=mannyrayner LANGUAGES=en,fr,de
```

Refresh the project annotations from the generated split manifest:

```bash
make refresh-annotations RUN=1
```

`refresh-annotations` uses `config/stage_parameters.json` by default. It starts
from each project's latest `segmentation_phase_1` artifact, preserving the
existing page and segment structure, then runs `segmentation_phase_2`,
`translation`, `mwe`, `lemma`, and `gloss`. The config sets `segmentation_phase_2.mechanism` to
`chunk_decomposition`, with the promoted `chunk_decomposition_multilingual_v1`
prompts, `max_concurrency=20`, and `chunk_consistency=true`, so the refresh pass
runs the new chunk-based segmentation before the downstream annotation steps. If
`PROJECT_IDS` is supplied, those explicit ids are used and the split manifest is
ignored; otherwise the generated split manifest supplies the project ids.

You can also refresh a small explicit smoke set:

```bash
make refresh-annotations PROJECT_IDS="101,102,103" RUN=1
```

Large refreshes run projects in increasing project-id order, so a crashed run can
be resumed without reattempting earlier ids:

```bash
make refresh-annotations RUN=1 RESUME_FROM_PROJECT_ID=245
```

Each project is retried by default (`MAX_PROJECT_RETRIES=2`, i.e. up to three
attempts total). On retry, the command inspects the run's completed stage
artifacts and resumes from the processing phase after the newest valid artifact,
so a timeout in `translation`, `mwe`, `lemma`, or `gloss` does not repeat earlier
phases. Projects that still fail are skipped so later projects can continue;
their diagnostics, including attempted start stage, input artifact, exception
type, and traceback, are written to `generated/refresh_failures.jsonl` by
default. Use `FAIL_FAST=1` if you want the first exhausted project failure to
abort the whole run instead.

After refresh, export current segment records from the latest MWE artifacts:

```bash
make extract-split-corpus CORPUS_USER=mannyrayner LANGUAGES=en,fr,de
```

If the split membership is already fixed and you only need to refresh project-level metadata after manual annotation, use:

```bash
make refresh-project-metadata CORPUS_USER=mannyrayner LANGUAGES=en,fr,de
```

This keeps the existing `development`/`validation`/`test` project lists but recalculates `mwe_count`, token/segment counts, and latest MWE artifact paths from each project's newest saved `mwe.json` artifact, including artifacts updated by the manual page-oriented editor.

The corpus target writes `generated/corpus_splits/<language>/development_projects.jsonl`,
`validation_projects.jsonl`, `test_projects.jsonl`, matching `*_segments.jsonl`
files, a `segments_with_mwes.md` review file with only MWE-bearing segments
and the total MWE count, per-language `split_manifest.json`, and a top-level
`multilingual_split_manifest.json`.

## Snapshot and prompt-scoring workflow

Before running prompt experiments over manually corrected projects, save project
snapshots that explicitly mark the current MWE, lemma, and gloss annotations as
gold-standard data:

```bash
make snapshot-gold-projects RUN=1
```

By default this reads `generated/corpus_splits/multilingual_split_manifest.json`
and covers all configured splits. Use `PROJECT_IDS="239,245,254"` to snapshot an
explicit smoke set, or `SPLITS=development` to restrict the manifest-driven
selection. The target calls the same file-backed snapshot implementation used by
the platform UI.

### Initial seven-project development experiment

For the initial manually corrected English development set, use exactly these
seven project ids:

```bash
MWE_PROJECT_IDS="239,245,254,255,257,261,263"
MWE_RUN_LABEL="mwe-current-prompt-en-development-20260707"
```

First, preview the snapshot operation. This should print a JSON dry-run manifest
and should not write snapshots:

```bash
make snapshot-gold-projects \
  PROJECT_IDS="$MWE_PROJECT_IDS" \
  SPLITS=development \
  SNAPSHOT_NAME_PREFIX="MWE development gold checkpoint"
```

Then save the snapshots for the same projects. These snapshots mark **MWE
annotations**, **gloss annotations**, and **lemma annotations** as gold-standard
components:

```bash
make snapshot-gold-projects RUN=1 \
  PROJECT_IDS="$MWE_PROJECT_IDS" \
  SPLITS=development \
  SNAPSHOT_NAME_PREFIX="MWE development gold checkpoint"
```

Next, run the current MWE prompt over the extracted English development segment
records, score it, and write conservative prompt-improvement guidance:

```bash
make run-current-mwe RUN=1 \
  PROJECT_IDS="$MWE_PROJECT_IDS" \
  MWE_LANGUAGE=en \
  SPLIT=development \
  MWE_RUN_LABEL="$MWE_RUN_LABEL"

make score-current-mwe RUN=1 \
  PROJECT_IDS="$MWE_PROJECT_IDS" \
  MWE_LANGUAGE=en \
  SPLIT=development \
  MWE_RUN_LABEL="$MWE_RUN_LABEL"

make propose-mwe-prompt-improvement RUN=1 \
  PROJECT_IDS="$MWE_PROJECT_IDS" \
  MWE_LANGUAGE=en \
  SPLIT=development \
  MWE_RUN_LABEL="$MWE_RUN_LABEL"
```

Expected outputs are:

- `generated/mwe_prompt_runs/$MWE_RUN_LABEL/outputs.jsonl`
- `generated/mwe_prompt_runs/$MWE_RUN_LABEL/progress.jsonl`
- `generated/mwe_prompt_scores/$MWE_RUN_LABEL/summary.json`
- `generated/mwe_prompt_scores/$MWE_RUN_LABEL/summary.md`
- `generated/mwe_prompt_improvements/$MWE_RUN_LABEL/prompt_improvement.md`
- `generated/mwe_prompt_improvements/$MWE_RUN_LABEL/candidate_prompt_guidance.txt`

### How `PROJECT_IDS`, `SPLITS`, and `SPLIT` interact

- `PROJECT_IDS` is an explicit comma-separated override. For project-selection
  commands such as `snapshot-gold-projects`, it chooses projects directly and the
  split manifest is not used to choose projects. For `run-current-mwe`,
  `score-current-mwe`, and `propose-mwe-prompt-improvement`, it filters the
  selected segment/output/score records to those projects, which is the safest
  way to run a small hand-curated subset.
- `SPLITS` is plural and only matters for manifest-driven project-selection
  commands. It says which manifest splits to read when `PROJECT_IDS` is empty.
  Passing `SPLITS=development` together with explicit `PROJECT_IDS` is harmless
  documentation of intent, but the explicit ids are what control the snapshot
  target above.
- `SPLIT` is singular and controls prompt-run/scoring paths. For
  `run-current-mwe`, it selects the input records file through
  `MWE_SPLIT_RECORDS`, which defaults to
  `generated/corpus_splits/$(MWE_LANGUAGE)/$(SPLIT)_segments.jsonl`. If
  `PROJECT_IDS` is also supplied, only records from those projects are run or
  scored.
- To run exactly the seven projects above, pass
  `PROJECT_IDS="$MWE_PROJECT_IDS"` to `run-current-mwe`, `score-current-mwe`, and
  `propose-mwe-prompt-improvement`. The development segment file may contain other projects;
  the explicit `PROJECT_IDS` filter keeps them out of this small experiment.

`run-current-mwe` processes each selected extracted segment through the current MWE prompt. It prints per-record progress and appends `progress.jsonl` and `outputs.jsonl` incrementally, so a long run should no longer look idle. `score-current-mwe` compares predicted MWE spans with the extracted gold spans, and `propose-mwe-prompt-improvement` writes conservative guidance under
`generated/mwe_prompt_improvements/`. The proposal step is intentionally general:
it highlights false positives/false negatives and suggests simple language-neutral
prompt principles rather than hard-coding project-specific examples.

## Manual gold workflow

Use the project JSONL files to open the selected projects in the existing manual
annotation editor. Correct MWE annotations there, then rerun `extract-split-corpus`
to export gold-standard segment records from the latest MWE artifacts. Keep test
projects untouched while iterating prompts on development and validation.

`refresh-upstream` remains as a compatibility alias for `refresh-annotations`, but new runs should use `refresh-annotations`.
