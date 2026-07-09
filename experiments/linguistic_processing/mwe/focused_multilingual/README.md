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

Then declare the gold data for the same projects. This target does two things:
first it saves gold-standard project snapshots, then it exports an explicit
seven-project gold JSONL from the projects' latest MWE artifacts. This explicit
JSONL is what the iterative prompt-cycle targets use; the snapshots are the
rollback/provenance checkpoint.

```bash
make declare-mwe-gold RUN=1 \
  PROJECT_IDS="$MWE_PROJECT_IDS" \
  MWE_LANGUAGE=en \
  SPLIT=development \
  SNAPSHOT_NAME_PREFIX="MWE development gold checkpoint"
```

Now check that the exported gold data is really present. This target rewrites the
same explicit gold JSONL and fails if no gold MWEs are found:

```bash
make check-mwe-gold RUN=1 \
  PROJECT_IDS="$MWE_PROJECT_IDS" \
  MWE_LANGUAGE=en \
  SPLIT=development
```

Inspect the high-level gold-data files if anything looks wrong:

- `generated/mwe_gold/en-development/summary.json`
- `generated/mwe_gold/en-development/review.md`
- `generated/mwe_gold/en-development/selected_segments.jsonl`

Next, run the current MWE prompt over the explicit gold records exported by
`declare-mwe-gold`, score it, and write conservative prompt-improvement guidance:

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

- `generated/mwe_gold/en-development/selected_segments.jsonl`
- `generated/mwe_gold/en-development/summary.json`
- `generated/mwe_gold/en-development/review.md`
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
- `SPLIT` is singular and controls output paths and the default gold-record path.
  For `run-current-mwe`, the input is `MWE_RUN_RECORDS`, which defaults to
  `MWE_GOLD_RECORDS` (`generated/mwe_gold/$(MWE_LANGUAGE)-$(SPLIT)/selected_segments.jsonl`).
  `PROJECT_IDS` is still passed as a safety filter, but after `declare-mwe-gold`
  the file should already contain only the selected projects.
- To run exactly the seven projects above, first run `declare-mwe-gold` with
  `PROJECT_IDS="$MWE_PROJECT_IDS"`, then pass the same `PROJECT_IDS` to
  `run-current-mwe`, `score-current-mwe`, and `propose-mwe-prompt-improvement`.
  The explicit gold file should already contain only those projects; the repeated
  `PROJECT_IDS` arguments are a safety filter.

`run-current-mwe` processes `MWE_RUN_RECORDS`, which defaults to the explicit `MWE_GOLD_RECORDS` file written by `declare-mwe-gold`. It prints per-record progress and appends `progress.jsonl` and `outputs.jsonl` incrementally, so a long run should no longer look idle. `score-current-mwe` compares predicted MWE spans with the extracted gold spans, and `propose-mwe-prompt-improvement` writes conservative guidance under
`generated/mwe_prompt_improvements/`. The proposal step is intentionally general:
it highlights false positives/false negatives and suggests simple language-neutral
prompt principles rather than hard-coding project-specific examples.


## Iterative prompt-improvement cycles

The baseline `run-current-mwe` / `score-current-mwe` /
`propose-mwe-prompt-improvement` targets are useful for sanity checks against the
production prompt. For iterative prompt development, use cycle-specific prompt
files under `generated/mwe_prompt_cycles/<language>-<split>/cycle_<n>/` so that
production prompts under `prompts/mwe/` are not edited during development. Set
`MWE_PROMPT_CYCLE_SERIES=<name>` to put an alternative series under
`generated/mwe_prompt_cycles/<language>-<split>/<name>/cycle_<n>/` and keep
methodologically distinct variants separate.

Cycle 1 copies `prompts/mwe/$(MWE_LANGUAGE)/template.txt` when it exists, falling
back to `prompts/mwe/default/template.txt`. Cycle N>1 copies
`generated/mwe_prompt_cycles/<language>-<split>/cycle_<N-1>/improvement/template_revision.txt`.
The proposal target seeds that `template_revision.txt` from the just-run cycle
prompt. You can either edit it manually using `candidate_prompt_guidance.txt` and
`prompt_improvement.md`, or run the AI revision target described below to produce a
first next-cycle draft while still keeping the revision auditable and development-only.

For the current seven-project sanity-check set, first run `declare-mwe-gold` and
`check-mwe-gold` as above. Then a full high-level cycle 1 run is:

```bash
MWE_PROJECT_IDS="239,245,254,255,257,261,263"
MWE_PROMPT_CYCLE_NUMBER=1

make mwe-prompt-cycle RUN=1 \
  PROJECT_IDS="$MWE_PROJECT_IDS" \
  MWE_LANGUAGE=en \
  SPLIT=development \
  MWE_PROMPT_CYCLE_NUMBER="$MWE_PROMPT_CYCLE_NUMBER"

make show-mwe-prompt-cycle-results \
  MWE_LANGUAGE=en \
  SPLIT=development \
  MWE_PROMPT_CYCLE_NUMBER="$MWE_PROMPT_CYCLE_NUMBER"

make compare-mwe-prompt-cycles RUN=1 \
  MWE_LANGUAGE=en \
  SPLIT=development
```


`compare-mwe-prompt-cycles` writes one cross-cycle review page at
`generated/mwe_prompt_cycles/en-development/cycle_comparison.md` plus a JSON copy.
It lists precision, recall, F1, exact-match rate, TP/FP/FN counts, prompt length,
and revision length for each completed cycle. This is intended to make regressions
like "cycle 5 got worse than cycle 4" easy to spot and to show whether prompt
growth is correlating with a plateau or decline.

Current hypothesis to investigate next: if recall remains poor after prompt-only
iterations, add whole-segment translation context to the MWE-location prompt. Start
with the gloss-language translation because it is cheap and already aligned with
the task; if helpful, compare one translation against multiple translations before
using validation/test projects. Keep this as a controlled cycle variant rather than
mixing it silently into the existing prompt-only run.

### Translation-context cycle variant

To test the simple segment-translation hypothesis cleanly, start a new named
series instead of continuing the prompt-only `cycle_1` ... `cycle_5` series. The
`MWE_PROMPT_CYCLE_SERIES` variable appends a subdirectory under
`generated/mwe_prompt_cycles/<language>-<split>/`, so these results do not mix
with the original prompt-only cycles.

```bash
MWE_PROJECT_IDS="239,245,254,255,257,261,263"

make declare-mwe-gold RUN=1 \
  PROJECT_IDS="$MWE_PROJECT_IDS" \
  MWE_LANGUAGE=en \
  SPLIT=development \
  SNAPSHOT_NAME_PREFIX="MWE development translation-context gold checkpoint"

python - <<'PY'
import json
from pathlib import Path
path = Path("generated/mwe_gold/en-development/selected_segments.jsonl")
records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
with_translation = [record for record in records if record.get("translation_context")]
print(f"records={len(records)} records_with_translation_context={len(with_translation)}")
if with_translation:
    sample = with_translation[0]
    print(sample["record_id"], sample["translation_context"][0])
PY

MWE_PROMPT_CYCLE_SERIES=translation_context
MWE_PROMPT_CYCLE_NUMBER=1

make mwe-prompt-cycle RUN=1 \
  PROJECT_IDS="$MWE_PROJECT_IDS" \
  MWE_LANGUAGE=en \
  SPLIT=development \
  MWE_PROMPT_CYCLE_SERIES="$MWE_PROMPT_CYCLE_SERIES" \
  MWE_PROMPT_CYCLE_NUMBER="$MWE_PROMPT_CYCLE_NUMBER" \
  MWE_USE_TRANSLATION_CONTEXT=1

make revise-mwe-prompt-cycle-template RUN=1 \
  PROJECT_IDS="$MWE_PROJECT_IDS" \
  MWE_LANGUAGE=en \
  SPLIT=development \
  MWE_PROMPT_CYCLE_SERIES="$MWE_PROMPT_CYCLE_SERIES" \
  MWE_PROMPT_CYCLE_NUMBER="$MWE_PROMPT_CYCLE_NUMBER"

make compare-mwe-prompt-cycles RUN=1 \
  MWE_LANGUAGE=en \
  SPLIT=development \
  MWE_PROMPT_CYCLE_SERIES="$MWE_PROMPT_CYCLE_SERIES"
```

This writes translation-context outputs under
`generated/mwe_prompt_cycles/en-development/translation_context/`, including
`translation_context/cycle_comparison.md`. The earlier prompt-only comparison
remains at `generated/mwe_prompt_cycles/en-development/cycle_comparison.md`; compare
those two reports to decide whether translation context is helping.

`declare-mwe-gold` now exports `translation_context` records from the latest
translation stage when available. `MWE_USE_TRANSLATION_CONTEXT=1` passes those
records into the MWE prompt as `translation_context`, currently a list so later
experiments can add more than one translation without changing the run format.
The prompt-revision step is also instructed to use translations as optional
evidence for expressions that translate as phrases, while keeping the prompt short
and avoiding over-elaborate instructions.

When `MWE_USE_TRANSLATION_CONTEXT=1`, `run_mwe_prompt_experiment` prints a trace
line like `Translation context enabled: N/M records have translation_context` and
records the same count in the run `manifest.json`, so you can confirm that the
cycle is actually using the exported translations.

If you want to run the steps separately for debugging, use
`prepare-mwe-prompt-cycle`, `run-mwe-prompt-cycle`, `score-mwe-prompt-cycle`, and
`propose-mwe-prompt-cycle-improvement` with the same variables.

To ask AI to draft a non-trivial but conservative next-cycle prompt from the cycle
report, run this after `mwe-prompt-cycle` has produced the score and improvement
files:

```bash
make revise-mwe-prompt-cycle-template RUN=1 \
  PROJECT_IDS="$MWE_PROJECT_IDS" \
  MWE_LANGUAGE=en \
  SPLIT=development \
  MWE_PROMPT_CYCLE_NUMBER="$MWE_PROMPT_CYCLE_NUMBER"
```

This overwrites
`generated/mwe_prompt_cycles/en-development/cycle_1/improvement/template_revision.txt`
with a complete prompt generated from the current cycle prompt plus
`prompt_improvement.md` and `candidate_prompt_guidance.txt`. It also writes
`template_revision.json` with the model rationale, listed changes, and risks. The
revision prompt explicitly asks for simple, general changes and forbids memorising
project-specific answers, so the output should still be reviewed before use.

By default, this target uses `MWE_REVISION_MODEL=gpt-5.5`, since prompt revision
is only run once per cycle and is the highest-leverage step. Override
`MWE_REVISION_MODEL=...` on the command line if you need a cheaper smoke test.

After the proposal target finishes, inspect:

- `generated/mwe_prompt_cycles/en-development/cycle_1/template.txt` — the prompt
  actually evaluated;
- `generated/mwe_prompt_cycles/en-development/cycle_1/run/outputs.jsonl` and
  `progress.jsonl` — the MWE run output and trace;
- `generated/mwe_prompt_cycles/en-development/cycle_1/score/summary.md` — the
  cycle score;
- `generated/mwe_prompt_cycles/en-development/cycle_1/improvement/prompt_improvement.md`
  and `candidate_prompt_guidance.txt` — conservative error-analysis guidance;
- `generated/mwe_prompt_cycles/en-development/cycle_1/improvement/template_revision.txt`
  — an editable copy of the cycle prompt to revise for cycle 2.

For cycle 2, review and optionally edit `cycle_1/improvement/template_revision.txt`
(using only general, language-neutral prompt changes), then rerun `mwe-prompt-cycle`
with `MWE_PROMPT_CYCLE_NUMBER=2`. Keep development cycles separate from future
validation/test runs; once the machinery is stable, use larger annotated
English/French/German development sets for prompt iteration and reserve held-out
validation/test projects for final checks.

## Manual gold workflow

Use the project JSONL files to open the selected projects in the existing manual
annotation editor. Correct MWE annotations there, then rerun `extract-split-corpus`
to export gold-standard segment records from the latest MWE artifacts. Keep test
projects untouched while iterating prompts on development and validation.

`refresh-upstream` remains as a compatibility alias for `refresh-annotations`, but new runs should use `refresh-annotations`.
