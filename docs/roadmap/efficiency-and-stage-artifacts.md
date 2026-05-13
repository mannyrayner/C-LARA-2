# Efficiency and stage-artifact persistence roadmap

## Purpose

C-LARA-2 now imports large legacy C-LARA projects into normal C-LARA-2 projects, but large imported projects have exposed a practical efficiency problem: pipeline compilation on the AWS server can be much slower than expected and can sometimes fail with `Read timeout` or `Internal error`.

This roadmap tracks a focused response to [ISSUE-0013](../issues/issues/ISSUE-0013.json): make pipeline stage-artifact persistence faster, more measurable, and more flexible without losing the advantages of the current JSON artifacts.

The immediate trigger is the Adelaide legacy migration, but the design should also benefit normal large C-LARA-2 projects, batch testing, and future hosted-corpus work.

## Requested starting plan from ISSUE-0013

ISSUE-0013 should start with the following concrete work items, before any broad rewrite of the pipeline:

1. **Make stage-output reads and writes generic.** Replace ad hoc stage-file JSON handling with a narrow persistence boundary whose callers only name the project, run, stage, payload, and optional format override. The lower-level implementation chooses the concrete encoder/decoder, file extension, metadata sidecar, and timing instrumentation.
2. **Keep old JSON artifacts readable.** The new boundary must detect and read existing `<stage>.json` files exactly as they are today, so previously compiled/imported projects, source bundles, tests, and manually inspected artifacts remain usable without a migration step.
3. **Choose and benchmark a faster default write format.** Start with safe alternatives such as compact JSON or compressed JSON, then compare data-only binary formats and a strictly trusted pickle-like cache. The eventual default for newly written internal stage outputs should be based on measured read/write time, size, memory use, portability, and safety.
4. **Expose a project/run format setting for testing.** Add an advanced project Settings option, or equivalent admin-only test control, so developers can compile the same project with different stage-output formats. Persist the selected format in run metadata and store read/write timings for every artifact operation.

This means the first implementation milestone is not “switch everything to pickle”; it is “make the format switchable and measurable without breaking JSON compatibility.”

## Current working hypothesis

The current pipeline stores stage outputs as JSON files. JSON is valuable because it is:

- human-inspectable;
- easy to include in source-bundle exports;
- robust across versions and languages;
- safe to load from untrusted uploads;
- useful for debugging, manual inspection, and migration provenance.

However, JSON may be inefficient for very large stage outputs. Large JSON artifacts can be expensive to serialize, parse, pretty-print, transfer through web responses, and repeatedly load during pipeline reruns. The first task is to measure this rather than assume it.

A likely solution is not “replace JSON everywhere”, but rather:

> Add a generic stage-artifact read/write layer, then support multiple storage formats behind that layer.

## Design goals

1. **Generic artifact operations**
   - All code that reads or writes pipeline stage outputs should go through central helper functions/classes.
   - Pipeline stages should ask for “read stage artifact” or “write stage artifact”, not directly call `json.loads`, `json.dumps`, `Path.read_text`, or `Path.write_text` for stage payloads.
   - The concrete format should be selected at a lower level.

2. **Backward compatibility**
   - Existing JSON stage artifacts must remain readable.
   - Existing source-bundle exports/imports must remain compatible.
   - Manual annotation/editor workflows that depend on JSON-like structures must continue to work.
   - Compiled or imported projects already on disk should not need wholesale migration before they can be opened.

3. **More efficient default for heavy internal workflows**
   - Evaluate a faster internal representation for newly written stage outputs.
   - Candidate formats include compact JSON, compressed JSON, MessagePack, SQLite-backed artifacts, or pickle-like trusted caches.
   - For the one-off Adelaide migration, pickle-like artifacts may be acceptable because the source corpus and operation are trusted/admin-only.

4. **Explicit trust boundary**
   - JSON should remain the safe interchange format for ordinary user uploads and public source bundles.
   - Pickle or similar code-executing formats must not be accepted from untrusted user-uploaded bundles.
   - If pickle-like formats are used, they should be limited to trusted admin-only migration/cache paths with clear naming and diagnostics.

5. **Measurability**
   - Store read/write timings for stage artifact operations.
   - Capture artifact size, format, stage name, project id, run id, and operation type.
   - Make it possible to compare JSON and alternative formats on the same representative projects.

6. **User/admin configurability for testing**
   - Allow the stage-output format to be selected for a project or run during testing.
   - This probably belongs in a project-level **Settings** or **Advanced settings** UI, with safe defaults.
   - For production, only admins should be able to enable experimental/trusted formats unless the format is safe for normal users.

## Proposed architecture

### Stage artifact API

Introduce a small API, for example conceptually:

```python
read_stage_artifact(project, run_id, stage_name, *, expected_schema=None)
write_stage_artifact(project, run_id, stage_name, payload, *, format=None)
artifact_exists(project, run_id, stage_name)
artifact_metadata(project, run_id, stage_name)
```

The exact module and names can be chosen during implementation, but the API should centralize:

- path resolution;
- format selection;
- serialization/deserialization;
- schema/version metadata;
- timing collection;
- error reporting;
- backward-compatible JSON fallback.

### Format selection

Format selection should be explicit and inspectable. Possible levels:

1. **System default** — configured in settings/environment.
2. **Project setting** — used for experiments or known large imported projects.
3. **Run override** — useful for benchmarks and one-off tests.
4. **Bundle/import override** — used for trusted migration material.

Suggested initial values:

- `json_pretty` — current human-readable JSON, kept for compatibility.
- `json_compact` — JSON without indentation, likely smaller/faster but still inspectable with tools.
- `json_gzip` — compressed JSON for large artifacts.
- `msgpack` or similar — binary but data-only.
- `pickle_trusted` — only for trusted admin-only migration/cache experiments.

### File layout

Keep stage names stable, but allow extensions or sidecar metadata to identify the format:

```text
runs/<run_id>/stages/
  segmentation_phase_1.json
  segmentation_phase_2.stage
  segmentation_phase_2.stage.meta.json
```

or:

```text
runs/<run_id>/stages/
  segmentation_phase_2.msgpack
  segmentation_phase_2.meta.json
```

The implementation should choose one convention and document it. The key point is that stage discovery must no longer assume every stage is exactly `<stage>.json` once the new layer is enabled.

### Concrete read/write contract

The first implementation should keep the persistence layer deliberately small. A stage write should:

1. resolve the canonical stage directory for the project/run;
2. select a requested format in this precedence order: explicit run override, project setting, system default, safe JSON fallback;
3. serialize the payload through a registered format adapter;
4. write atomically using a temporary file and rename where possible;
5. write or update a metadata sidecar with format, schema version, writer version, byte size, wall-clock write time, and source trust level;
6. emit the same timing/size data to logs or a diagnostics table.

A stage read should:

1. prefer explicit metadata when present;
2. fall back to extension-based detection for legacy or partially migrated artifacts;
3. always try the existing JSON `<stage>.json` convention before reporting a missing artifact;
4. refuse unsafe formats, such as `pickle_trusted`, unless the call site is inside a trusted admin/migration/cache context;
5. return ordinary Python objects to pipeline and editor code, independent of the backing format;
6. record read timing, byte size, selected format, and whether fallback logic was used.

## Backward compatibility strategy

1. **Read old JSON first**
   - If only `<stage>.json` exists, read it as current JSON.
   - This keeps all existing projects and tests usable.

2. **Prefer explicit metadata for new artifacts**
   - New non-JSON artifacts should include sidecar metadata recording format, schema version, write time, payload size, and C-LARA-2 version if available.

3. **Export JSON for interchange**
   - Source-bundle export should either export JSON artifacts or include a compatibility conversion step.
   - A project using a binary internal cache should still be exportable to a standard JSON-based source bundle unless we explicitly define a trusted binary bundle type.

4. **Manual editor compatibility**
   - The manual annotation editor should receive normal Python/JSON-like objects through the artifact API.
   - It should not need to know whether the backing store was JSON, compressed JSON, or another format.

## Measurement plan

Before changing defaults, benchmark on representative projects:

- small normal project;
- medium generated text with images/audio;
- large imported legacy project;
- known problematic project such as `The Dragon and the Cube`;
- one or more CJK/romanization-heavy projects.

For each stage and format, record:

- serialized artifact size;
- write time;
- read time;
- parse/deserialization time if separable;
- total compile time;
- failures/timeouts;
- memory use if easy to capture.

This should make it clear whether the bottleneck is JSON serialization, disk I/O, web/server timeout policy, stage computation, or something else.


Suggested per-operation timing record fields:

| Field | Purpose |
| --- | --- |
| `project_id` / `run_id` / `stage_name` | Groups timings by project, compile run, and pipeline stage. |
| `operation` | Distinguishes read, write, conversion, fallback read, and export conversion. |
| `format` | Records `json_pretty`, `json_compact`, `json_gzip`, `msgpack`, `pickle_trusted`, etc. |
| `payload_bytes` | Compares serialized sizes across formats. |
| `elapsed_ms` | Main read/write performance measure. |
| `trust_level` | Separates normal user data from trusted admin-only migration/cache artifacts. |
| `fallback_used` | Shows when compatibility behavior, such as old JSON reads, was needed. |
| `error_code` | Makes timeouts, parse failures, and unsafe-format refusals reportable. |

The initial storage target can be run metadata or a simple JSON diagnostics file; if performance analysis becomes routine, promote the records to a database model or append-only event table.

## Project settings / UI implications

The suggestion to expose the stage-output format points toward a more general project **Settings** page or menu.

For an initial testing-oriented implementation:

- add an advanced/admin-visible project setting for stage artifact format;
- show the current format and whether it is experimental;
- record per-run chosen format in run metadata;
- show read/write timing summaries on a diagnostics/admin page;
- default normal user projects to the safe current format until the alternative is proven.

Longer term, project settings may also include other advanced controls, but this roadmap is only concerned with stage artifact persistence.


A minimal settings implementation could expose:

- **Stage artifact format**: `System default`, `Pretty JSON`, `Compact JSON`, `Gzipped JSON`, and any experimental formats enabled by server settings.
- **Trusted binary cache**: hidden unless the current user is staff and the project/run is marked as admin-created or migration-trusted.
- **Diagnostics display**: latest compile total artifact read/write time, largest artifacts, and any compatibility fallback reads.
- **Reset to default**: removes project-level overrides so production projects return to the safe deployment default.

This UI should be treated as an advanced testing control until benchmarks justify changing the production default.

## Phased plan

### Phase A — inventory and wrapper layer

- Find all direct stage artifact JSON reads/writes in platform and pipeline code.
- Add central artifact read/write helpers.
- Convert the main pipeline paths to use them while still writing the current JSON format.
- Add tests proving old JSON artifacts are still readable.

### Phase B — timing and diagnostics

- Record read/write timings and artifact sizes.
- Add lightweight diagnostics to run summaries or admin views.
- Benchmark representative projects, especially large imported legacy projects.

### Phase C — compact JSON and/or compressed JSON

- Add a low-risk first alternative such as compact JSON or gzip-compressed JSON.
- Make it selectable for test projects/runs.
- Confirm source-bundle export can still produce compatible JSON.

### Phase D — trusted binary migration experiment

- Prototype a faster binary format for the one-off trusted Adelaide migration path.
- If using pickle, label it clearly as trusted/admin-only and never load it from ordinary user uploads.
- Compare speed and reliability against JSON on imported large projects.

### Phase E — default decision

- Choose the default based on measured performance, safety, and maintainability.
- Keep JSON read compatibility indefinitely.
- Decide whether the alternative format is internal-cache-only or becomes a supported project setting.

## Open questions

- Are the observed AWS failures caused primarily by stage artifact I/O, by long-running web requests, by worker timeouts, by memory pressure, or by a specific stage computation?
- Should artifact timing be stored in per-run metadata, a database table, log files, or all three?
- Which workflows require pretty JSON on disk, and which only require object-level access through the editor/API?
- Should the one-off Adelaide migration format be implemented in legacy C-LARA, in C-LARA-2, or both?
- How should binary/cache artifacts interact with backups, source-bundle export, and long-term archival reproducibility?

## Success criteria

- Large imported legacy projects compile reliably on AWS without read timeouts/internal errors attributable to artifact persistence.
- Stage artifact reads/writes are centralized behind a tested API.
- Existing JSON artifacts and source bundles remain readable/importable/exportable.
- Timing data can show whether format changes improved performance.
- Any pickle-like path is explicitly trusted/admin-only and cannot be confused with normal user-uploaded bundles.
