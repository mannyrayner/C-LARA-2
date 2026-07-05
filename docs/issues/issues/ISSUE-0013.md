# ISSUE-0013: Improve stage artifact persistence performance and timeout resilience

- **Status:** reported
- **Priority:** P1
- **Created:** 2026-05-13T01:12:11Z
- **Updated:** 2026-07-01T13:36:21Z
- **Origin:** human-suggestion
- **Deadline:** None
- **Dependencies:** None
- **Canonical JSON:** [ISSUE-0013.json](ISSUE-0013.json)

## Notes

Suggestion #1 from admin export (submitted by mannyrayner on 2026-05-13), split out from the
ISSUE-0010 follow-up. Imported legacy C-LARA projects can now be created on the AWS server, but
pipeline compilation there is much slower than expected and sometimes fails with `Read timeout` or
`Internal error`, especially for large imported projects with large intermediate stage artifacts.
Investigate whether repeated reading, writing, and parsing of large JSON stage files is a bottleneck
or timeout trigger. Design a generic stage-artifact persistence layer with central read/write
operations so the on-disk representation can be changed or optimized without rewriting pipeline
logic. Evaluate options such as more efficient JSON handling, compression, caching, SQLite,
MessagePack, or pickle-like internal caches. Be cautious with pickle: it must not be used to load
untrusted user-uploaded files unless there is a clear trust boundary and safety story. Preserve
human-inspectable/exportable JSON where needed for source-bundle interchange, manual debugging, and
legacy migration provenance, possibly by keeping JSON as the interchange format while using a faster
internal representation/cache for server-side pipeline reruns. Include benchmarks on large imported
legacy projects, timeout instrumentation, and regression tests ensuring existing JSON source-bundle
import/export remains compatible. Follow-up suggestion #4 from admin export (submitted by
mannyrayner on 2026-05-13): for the one-off Adelaide legacy migration, a pickle-like or otherwise
binary interchange/cache format may be acceptable because the source corpus is trusted and the
operation is unlikely to be repeated as a general user-facing upload path. Treat this as a scoped
migration optimization rather than a blanket replacement of JSON. The implementation should
explicitly separate trusted admin-only migration artifacts from ordinary user uploads and public
source-bundle interchange. It is reasonable to prototype a pickle or similar representation for the
C-LARA-to-C-LARA-2 migration handoff if this materially improves import/compile speed, but keep JSON
export/import available for auditability, debugging, long-term portability, and any
untrusted/user-supplied bundles. The implementation plan is elaborated in
`docs/roadmap/efficiency-and-stage-artifacts.md`, which proposes central stage-artifact read/write
helpers, backward-compatible JSON reads, selectable formats for benchmarking, read/write timing
capture, and a trusted admin-only binary migration experiment.

Follow-up from human suggestion #30 (submitted by mannyrayner on 2026-07-01): large batch annotation
refreshes for the MWE experiments exposed a more specific timeout-resilience problem. The current
project-level retry/restart behaviour is better than aborting the entire batch, but it is still
wasteful for large projects: if a single API call times out during annotation, the implementation
may repeat the whole project refresh rather than resuming from the completed phase or retrying only
the failed call. Treat this as a P1 refinement under this existing persistence/resilience issue
rather than a separate issue. The next design should add phase-level and, where feasible, call-level
checkpointing/retry semantics for segmentation_phase_2, translation, MWE, lemma, and gloss
refreshes; preserve already-written valid stage artifacts; record enough per-call trace data to
diagnose repeated offenders; and ensure batch runners can continue while isolating unrecoverable
projects for analysis.
