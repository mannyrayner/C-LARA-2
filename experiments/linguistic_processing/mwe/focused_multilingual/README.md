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

## Manual gold workflow

Use the project JSONL files to open the selected projects in the existing manual
annotation editor. Correct MWE annotations there, then rerun `extract-split-corpus`
to export gold-standard segment records from the latest MWE artifacts. Keep test
projects untouched while iterating prompts on development and validation.

`refresh-upstream` remains as a compatibility alias for `refresh-annotations`, but new runs should use `refresh-annotations`.
