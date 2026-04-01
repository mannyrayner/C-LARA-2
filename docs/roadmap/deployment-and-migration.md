# Deployment and migration roadmap

This roadmap covers production deployment strategy for C-LARA-2, with special emphasis on:

1. Near-term dual-running with existing C-LARA on the Adelaide Uni server.
2. Future migration of C-LARA project data into C-LARA-2.
3. Portability to a new host (likely AWS Sydney) with export/import support.

## Priorities and timeline

- **Priority A (urgent, target: before end of April 2026):** safe Adelaide deployment with C-LARA and C-LARA-2 running concurrently.
- **Priority B (next):** migration tooling from C-LARA data model to C-LARA-2 data model.
- **Priority C (next):** full backup/export/import path for relocation to a different server (e.g. AWS Sydney).

Design requirement: Priority A decisions must be **upward-compatible** with B and C.

---

## 1) Adelaide dual-run deployment (urgent)

### Goals
- Deploy C-LARA-2 without disrupting the existing C-LARA service.
- Keep operational separation while allowing shared infrastructure where safe.
- Enable rollback with minimal risk.

### Proposed architecture (first cut)
- Reverse proxy (Nginx/Apache) routes by path or subdomain:
  - `c-lara.org/...` → existing C-LARA
  - `c-lara.org/clara2/...` or `clara2.c-lara.org/...` → C-LARA-2
- Separate runtime services:
  - separate app process/systemd unit/container,
  - separate queue worker,
  - separate database schema or database,
  - separate media/artifact root.
- Shared TLS certificate management at proxy layer.

### Operational checklist
- Health endpoints for app and worker.
- Log separation and rotation per app.
- Resource limits/monitoring to avoid one app starving the other.
- Staging dry-run before production cutover.
- One-command rollback procedure.

### Acceptance criteria
- Both apps reachable and stable under expected load.
- Existing C-LARA behavior unchanged.
- C-LARA-2 compile/publish/content flows operational.

---

## 2) Data migration from C-LARA to C-LARA-2

### Reality
Formats are different, but conceptual entities are similar (users, projects, annotations, media).

### Strategy
- Build an explicit **migration pipeline** (extract → transform → validate → import), not ad-hoc scripts.
- Preserve provenance and traceability per migrated record.

### Migration phases
1. **Schema mapping spec**
   - map legacy entities to C-LARA-2 models,
   - define lossless/lossy fields,
   - define defaults where no legacy equivalent exists.
2. **Read-only extractor** from C-LARA.
3. **Transform + validator**
   - structural checks,
   - referential integrity,
   - media path checks,
   - language/annotation consistency checks.
4. **Importer** into C-LARA-2 (idempotent, resumable).
5. **Reconciliation report**
   - counts, mismatches, warnings, manual-fix queue.

### Key requirement
- Migration tooling should be reusable for future host moves (ties into section 3).

---

## 3) Portability to alternate hosting (e.g. AWS Sydney)

### Goals
- Minimize lock-in to Adelaide-specific environment.
- Make full-system relocation routine and testable.

### Export/import capability
Implement platform-level backup bundles containing:
- database dump,
- media/artifacts archive,
- configuration snapshot (non-secret),
- migration/version metadata.

Import process should:
- restore DB/media,
- run migrations,
- verify checksums/referential integrity,
- run smoke tests automatically.

### Environment packaging
- Prefer reproducible deployment (containerized or scripted systemd setup).
- Keep all required env vars documented.
- Maintain infrastructure runbook for:
  - Adelaide deployment,
  - AWS deployment,
  - restore-from-backup.

---

## Cross-cutting constraints

- **Security:** secret handling, least-privilege DB users, audited admin actions.
- **Observability:** unified metrics/logging for app + worker + DB + queue.
- **Data durability:** regular automated backups, retention policy, restore drills.
- **Compatibility:** URLs and artifact paths should remain stable where possible to avoid breaking published content links.

---

## Incremental delivery plan

### Milestone A (before end of April 2026)
- Dual-run deployment live on Adelaide with rollback plan and runbook.
- Smoke tests + monitoring in place.

### Milestone B
- C-LARA → C-LARA-2 migration spec + first migration dry-run on sample dataset.

### Milestone C
- Full export/import tooling validated by moving a staging snapshot to AWS Sydney environment.

### Milestone D
- Production migration + optional cutover from Adelaide to alternate host, with rollback-ready plan.
