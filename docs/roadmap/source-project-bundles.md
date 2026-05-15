# Roadmap: source project export/import bundles

This roadmap defines support for exporting and importing **source project bundles** (ZIP files) for C-LARA-2 projects, including direct import of supported legacy C-LARA JSON export bundles.

## Goal

Enable a project to be moved between environments (server ↔ laptop) in a form that preserves editable source artifacts, not only compiled output. Also provide a practical migration path for legacy C-LARA projects by importing supported legacy JSON exports into the same C-LARA-2 project model.

## Why this matters

This workflow is already proven useful in C-LARA. Typical use cases include:

- export from server and import locally for debugging/re-running,
- export from local machine and import to server for publishing/collaboration,
- backup/transfer of in-progress annotation work,
- reproducibility of pipeline runs,
- migration of legacy C-LARA content into C-LARA-2 for inspection, reruns, and continued editing.

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

### Import: legacy C-LARA JSON export bundle (ZIP)

Status: **Implemented.** The same source-bundle import entry point now detects legacy C-LARA JSON export bundles and imports them directly as new C-LARA-2 projects.

Supported legacy ZIP layouts:

- flat archives containing `annotated_text.json` and `metadata.json`, with optional `audio/` and `images/` folders;
- archives rooted at a single top-level directory containing the same files.

The importer:

- creates a normal C-LARA-2 `Project` owned by the importing user;
- stores the original legacy files under `legacy_clara/` in the project artifact root for provenance and auditing;
- converts legacy pages, segments, annotations, pinyin, lemma/gloss data, and audio references into C-LARA-2 stage JSON artifacts;
- restores page-image and style records from legacy image metadata when present;
- preserves unsupported content elements in diagnostic/provenance annotations rather than silently dropping them;
- normalizes the temporary legacy import processing marker to valid runtime choices (`auto`) so imported projects can be rerun with current C-LARA-2 validation.

The previous proposal to require an intermediate C-LARA-2-oriented migration bundle is no longer necessary for this supported legacy JSON export format. Future migration work should focus on narrower gaps, such as additional legacy export variants or unsupported fields discovered in real archives.

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
- Detect both native C-LARA-2 source bundles and supported legacy C-LARA JSON export bundles.
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

Status: **Delivered.**

- Export latest run source artifacts.
- Import as new project with validation.
- Minimal manifest and checksum support.
- Validate required stage artifacts during import and regenerate missing export stages automatically when possible.

### Phase B — media + image completeness

Status: **Partly delivered.**

- Include image artifacts/prompts and optional media payloads.
- Better import preflight reporting and environment-compatibility checks.
- Legacy C-LARA JSON export import now preserves legacy media files, imports audio references, and restores page-image/style metadata where present.

### Phase C — reproducibility hardening

- Stronger provenance mapping and deterministic packaging.
- Consistency checks for cross-environment reruns (server vs laptop).

### Phase D — automation and ops support

- CLI/admin automation for batch export/import.
- Nightly backup/export pipelines and restore drills.
- Document and preserve deployment-transfer runbooks for large legacy corpora, including AWS security-group inbound SSH rules, explicit EC2 `.pem` key usage, and resumable `rsync` options such as `--partial --append-verify`.

### Phase E — legacy migration follow-ups

Status: **Core legacy JSON import delivered; follow-ups only as needed.**

- Add regression fixtures for additional real legacy C-LARA archives when they become available.
- Track unsupported legacy fields as specific issues with examples rather than reopening the broad migration task.
- Consider batch/admin tooling for importing many legacy JSON export bundles.

## Success criteria

- Users can reliably move editable projects between server and local environments.
- Imported bundles can be rerun in debug mode with minimal manual repair.
- Supported legacy C-LARA JSON exports can be imported directly into usable C-LARA-2 projects.
- Bundle format remains stable and versioned across releases.
- Teams can use bundles for backup, handover, and migration workflows.
