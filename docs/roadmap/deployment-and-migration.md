# Deployment and migration roadmap

This roadmap covers production deployment strategy for C-LARA-2, with special emphasis on:

1. Immediate deployment on a dedicated AWS host.
2. Controlled transition away from Adelaide infrastructure before access ends.
3. Migration of C-LARA project data into C-LARA-2.
4. Repeatable backup/export/import for future relocations.

## Why this roadmap changed (date-specific)

- As of **April 23, 2026**, we are assuming Adelaide server access may end on **May 8, 2026**.
- Therefore, the previous Adelaide-first sequence is replaced by an **AWS-first** sequence.
- Adelaide work is now limited to safe transition support and extraction of anything we still need before access ends.

Design requirement: short-term actions must remain compatible with long-term portability and migration.

Decision rule: if a transition shortcut conflicts with portability/recovery/migration quality, choose the portable option.

---

## 1) Immediate priority: AWS production-capable deployment

### Goals
- Stand up C-LARA-2 on dedicated AWS infrastructure as the primary path forward.
- Reach operational readiness quickly without sacrificing reproducibility and rollback.
- Keep the deployment model simple enough for a small team to run.

### Recommended baseline architecture (AWS)

#### Region and network
- Region: **ap-southeast-2 (Sydney)** by default.
- VPC with:
  - 1 public subnet (for reverse proxy / ingress),
  - 1 private subnet (for app/worker and DB access patterns where possible).
- Security groups:
  - inbound 80/443 to web tier,
  - SSH restricted to trusted admin IPs or SSM-only management,
  - DB port only from app/worker security group.

#### Compute and storage
- Start with one EC2 instance for app + worker (cost/simplicity), with a clear path to split later.
- Use EBS gp3 volumes with snapshot policy enabled.
- Host-level separation of app, worker, and data directories.

#### Data layer
- Prefer managed PostgreSQL (RDS) for operational safety (backups, patching, snapshots).
- If RDS cannot be provisioned immediately, use local PostgreSQL as temporary fallback and schedule migration to RDS.

#### Edge and TLS
- DNS in Route 53.
- TLS via AWS Certificate Manager (if fronted by ALB) or certbot on host (if Nginx terminates TLS directly).
- Keep hostname stable for users once cutover occurs.

#### Runtime model
- Nginx + gunicorn + django-q (systemd units), separate service identities and logs.
- Dedicated Python venv for C-LARA-2.
- Environment values in `.env` file or parameter store/secret manager (preferred for secrets).

---

## 2) Concrete AWS provisioning plan (next step after this document)

This is the immediate planning/execution track.

### Phase P0 — decisions to lock (same day)
1. Confirm AWS account and IAM access model.
2. Confirm region (`ap-southeast-2`) and target hostname.
3. Choose DB mode: RDS now (preferred) vs temporary local PostgreSQL.
4. Choose access model: bastion SSH vs AWS SSM Session Manager.

### Phase P1 — infrastructure bootstrap (day 1)
1. Create VPC/subnets/security groups.
2. Provision EC2 instance with fixed Elastic IP (or ALB if used).
3. Attach EBS volumes and enable scheduled snapshots.
4. Provision DB (RDS PostgreSQL preferred) and secure network path.
5. Configure DNS records for target hostname.

### Phase P2 — host hardening and base software (day 1–2)
1. Patch OS packages.
2. Install and configure: Nginx, Python runtime, systemd units, PostgreSQL client tools.
3. Configure firewall and fail2ban (if host-exposed SSH is used).
4. Set up CloudWatch agent (or equivalent) for logs/metrics.

### Phase P3 — application deploy (day 2)
1. Clone C-LARA-2 into `/srv/C-LARA-2` (or equivalent stable path).
2. Build dedicated venv from pinned dependencies.
3. Configure `.env` with dedicated secrets, DB settings, storage paths.
4. Run Django migrations.
5. Collect static assets (if required).
6. Start and enable systemd services:
   - `gunicorn-clara2.service`
   - `djangoq-clara2.service`
   - `nginx.service`

### Phase P4 — production readiness checks (day 2–3)
1. Smoke test critical flows:
   - login,
   - project list/load,
   - compile/worker execution,
   - media/artifact read-write.
2. Verify backups:
   - DB snapshot + restore test,
   - media backup + restore test.
3. Verify observability:
   - app and worker logs,
   - uptime/latency/error alerting.
4. Run rollback drill to previous known-good deploy artifact.

### Phase P5 — DNS cutover and stabilization
1. Lower DNS TTL before cutover.
2. Switch production hostname to AWS target.
3. Monitor error rates and job queue behavior for 24–48 hours.
4. Keep rollback option ready until stabilization criteria are met.

---

## 3) Adelaide transition plan (time-boxed until May 8, 2026)

### Goals
- Extract configuration and operational knowledge from Adelaide.
- Avoid significant new investment in Adelaide-specific architecture.
- Preserve ability to operate C-LARA while C-LARA-2 AWS cutover completes.

### Actions to complete before access ends
1. Capture current C-LARA operational baseline:
   - Nginx config,
   - systemd units,
   - Python/venv details,
   - DB backup scripts and schedules,
   - TLS management details.
2. Take final verified backups and record restore procedure.
3. Export any deployment scripts/runbooks that only exist on server.
4. Record ownership/permissions and service users for reference.

### Explicit non-goals
- Do not build complex new dual-run architecture on Adelaide unless absolutely required for short-term continuity.
- Do not introduce ad-hoc package installs that are not reflected in reproducible deployment definitions.

---

## 4) Data migration from C-LARA to C-LARA-2

### Strategy
- Implement explicit migration pipeline: **extract → transform → validate → import**.
- Preserve provenance and traceability for each migrated record.
- Make migration rerunnable and idempotent.

### Migration phases
1. **Schema mapping spec**
   - map legacy entities to C-LARA-2 models,
   - define lossless/lossy mappings,
   - define defaults for missing legacy fields.
2. **Read-only extractor** from C-LARA.
3. **Transform + validator**
   - structural checks,
   - referential integrity,
   - media path checks,
   - language/annotation consistency.
4. **Importer** into C-LARA-2 (idempotent, resumable).
5. **Reconciliation report**
   - counts, mismatches, warnings, manual-fix queue.

---

## 5) Backup/export/import portability

### Goals
- Make relocation routine and testable.
- Ensure disaster recovery is practical under time pressure.

### Backup bundle definition
Each backup bundle should contain:
- DB dump/snapshot metadata,
- media/artifact archive,
- non-secret config snapshot,
- app version + migration metadata,
- restore instructions and checksum manifest.

### Restore/import process
1. Restore DB/media.
2. Apply migrations.
3. Verify checksums and referential integrity.
4. Run smoke tests automatically.
5. Emit signed run report (timestamp, operator, outcome).

---

## 6) Operational standards (cross-cutting)

- **Security:** least-privilege IAM and DB users, secret rotation policy, audited admin actions.
- **Observability:** logs + metrics for app/worker/DB/host, with alert thresholds.
- **Durability:** automated backups with retention policy and periodic restore drills.
- **Reproducibility:** pinned Python dependencies; no unlogged production hotfix installs.
- **Compatibility:** stable URL/artifact strategy to avoid breaking published links.

---

## 7) Rescheduled milestones (AWS-first)

### Milestone A — AWS foundation (target: by April 30, 2026)
- AWS infra baseline provisioned (network, compute, DB, DNS plan).
- Base security/monitoring controls enabled.

### Milestone B — AWS app readiness (target: by May 3, 2026)
- C-LARA-2 deployed on AWS with services running.
- Smoke tests passing; backup and restore drills executed.

### Milestone C — Production cutover (target: by May 6, 2026)
- DNS cutover completed.
- 24–48h stabilization with rollback readiness.

### Milestone D — Adelaide wrap-up (no later than May 8, 2026)
- Final Adelaide backups and runbook capture complete.
- Decommission/hand-off checklist completed.

### Milestone E — Migration tooling progress (following cutover)
- C-LARA → C-LARA-2 mapping spec and first dry-run on sample data.

---

## 8) Immediate inputs needed to execute provisioning plan

To start Phase P0/P1 immediately, confirm:
1. AWS account/project owner and who can approve cost/security settings.
2. Preferred hostname for C-LARA-2 production on AWS.
3. Whether RDS PostgreSQL is approved for day-1 use.
4. Preferred operations access model (SSM-only recommended).
5. Budget envelope (monthly target + hard cap).

Once these five items are confirmed, we can produce a concrete, command-level provisioning runbook.
