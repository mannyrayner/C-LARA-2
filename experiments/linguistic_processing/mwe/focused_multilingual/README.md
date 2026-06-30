# Focused multilingual MWE workbench

This workbench prepares the English/French/German data needed before prompt-cycle
experiments for focused MWE identification.

## Goals

1. Refresh each selected project through `segmentation_phase_2`, `translation`, and
   `mwe`, so manual judging starts from current upstream annotations.
2. Extract deterministic, project-level development/validation/test splits that can
   be corrected in the existing manual annotation editor.
3. Preserve segment-level JSONL records with current MWE annotations as a convenient
   export for later prompt scoring and diagnostics.

## Commands

```bash
make plan
make validate-config
```

Refresh selected projects by explicit ids:

```bash
make refresh-upstream PROJECT_IDS="101,102,103" RUN=1
```

Or refresh the project ids from an existing split manifest:

```bash
make refresh-upstream SPLIT_MANIFEST=experiments/linguistic_processing/mwe/focused_multilingual/artifacts/corpus/multilingual_split_manifest.json RUN=1
```

After refresh, create the split manifests and segment exports:

```bash
make extract-corpus USERNAME=mannyrayner LANGUAGES=en,fr,de
```

The corpus target writes `artifacts/corpus/<language>/development_projects.jsonl`,
`validation_projects.jsonl`, `test_projects.jsonl`, matching `*_segments.jsonl`
files, per-language `split_manifest.json`, and a top-level
`multilingual_split_manifest.json`.

## Manual gold workflow

Use the project JSONL files to open the selected projects in the existing manual
annotation editor. Correct MWE annotations there, then rerun `extract-corpus` to
export gold-standard segment records from the latest MWE artifacts. Keep test
projects untouched while iterating prompts on development and validation.
