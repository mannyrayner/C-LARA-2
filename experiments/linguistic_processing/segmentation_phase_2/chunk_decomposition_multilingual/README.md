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
