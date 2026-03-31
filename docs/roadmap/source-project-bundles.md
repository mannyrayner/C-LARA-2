# Roadmap: source project export/import bundles

This roadmap defines support for exporting and importing **source project bundles** (ZIP files) for C-LARA-2 projects.

## Goal

Enable a project to be moved between environments (server ↔ laptop) in a form that preserves editable source artifacts, not only compiled output.

## Why this matters

This workflow is already proven useful in C-LARA. Typical use cases include:

- export from server and import locally for debugging/re-running,
- export from local machine and import to server for publishing/collaboration,
- backup/transfer of in-progress annotation work,
- reproducibility of pipeline runs.

## Scope

### Export: source bundle (ZIP)

Export the latest run’s source-side artifacts, including where available:

- original and segmented text,
- translation outputs,
- MWE annotations,
- lemma/gloss/romanization layers,
- image pipeline artifacts:
  - style definitions,
  - recurring element records,
  - page-image metadata,
  - prompts and provenance,
  - generated image files (optionally).

### Import: source bundle (ZIP)

Import a compatible bundle and reconstruct a project with:

- source artifacts restored,
- metadata/provenance preserved,
- option to rerun selected phases,
- conflict handling when project IDs/names collide.

## Bundle format proposal

```text
project_source_bundle.zip
  manifest.json
  project/
    metadata.json
    pipeline_config.json
  text/
    source.txt
    segmented.txt
    translation.json
    mwe.json
    lemma.json
    gloss.json
    romanization.json
  images/
    style.json
    elements.json
    pages.json
    prompts.json
    files/
      ...
  runs/
    latest_run_summary.json
```

## Manifest requirements

`manifest.json` should include:

- bundle schema version,
- export timestamp,
- C-LARA-2 version/commit,
- source project identifier,
- checksum table for integrity,
- optional privacy flags (e.g., excludes certain media).

## Export requirements

- UI action from project page: **Export Source Bundle**.
- API endpoint for scripted export.
- Option toggles:
  - include only latest run vs selected run,
  - include/exclude judge/evaluation artifacts.
- Deterministic file naming for reproducible diffs.

## Import requirements

- UI action: **Import Source Bundle** (always creates a new project).
- Preflight validation before write:
  - schema compatibility,
  - required files present,
  - checksum/integrity validation,
  - safe path handling (zip-slip protection).
- Import modes:
  1. create new project,
  2. dry-run validation only.

## Project identity handling

- Import always creates a new project record.
- Original project identifiers are stored as provenance metadata.
- Internal artifact IDs are remapped as needed to avoid collisions in the target environment.

## Security and privacy

- sanitize extracted filenames/paths,
- enforce max archive size and file-count limits,
- scan MIME/type consistency for included files,
- allow redaction of sensitive content before export.

## Integration points

- Complements existing compiled bundle download by adding source-level portability.
- Works with manual annotation editor roadmap to support offline correction workflows.
- Supports deployment/migration roadmap by simplifying cross-host transfer and backup.

## Delivery phases

### Phase A — MVP export/import

- Export latest run source artifacts.
- Import as new project with validation.
- Minimal manifest and checksum support.

### Phase B — media + image completeness

- Include image artifacts/prompts and optional media payloads.
- Better import preflight reporting and environment-compatibility checks.

### Phase C — reproducibility hardening

- Stronger provenance mapping and deterministic packaging.
- Consistency checks for cross-environment reruns (server vs laptop).

### Phase D — automation and ops support

- CLI/admin automation for batch export/import.
- Nightly backup/export pipelines and restore drills.

## Success criteria

- Users can reliably move editable projects between server and local environments.
- Imported bundles can be rerun in debug mode with minimal manual repair.
- Bundle format remains stable and versioned across releases.
- Teams can use bundles for backup, handover, and migration workflows.
