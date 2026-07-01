# Focused multilingual MWE workbench

This workbench mirrors the organisation of
`segmentation_phase_2/chunk_decomposition_multilingual`, but extracts segment
records rather than whitespace chunks. Splits are project-separated, so all
segments from a project stay in the same development, validation, or test split.

## Goals

1. Start with `extract-split-corpus` to assign English/French/German projects to
   deterministic development/validation/test splits.
2. Refresh the selected projects through `segmentation_phase_2`, `translation`,
   and `mwe`, so manual judging starts from current upstream annotations.
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

Refresh the projects from the generated split manifest:

```bash
make refresh-upstream RUN=1
```

You can also refresh a small explicit smoke set:

```bash
make refresh-upstream PROJECT_IDS="101,102,103" RUN=1
```

After refresh, export current segment records from the latest MWE artifacts:

```bash
make extract-split-corpus CORPUS_USER=mannyrayner LANGUAGES=en,fr,de
```

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
