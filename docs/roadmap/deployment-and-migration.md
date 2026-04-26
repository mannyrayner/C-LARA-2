# Deployment and migration roadmap

This roadmap covers production deployment strategy for C-LARA-2, with special emphasis on:

1. Immediate deployment on a dedicated AWS host.
2. Controlled transition away from Adelaide infrastructure before access ends.
3. Temporary side-by-side hosting of C-LARA and C-LARA-2 on AWS.
4. Preservation of legacy published materials from LARA and C-LARA.
5. Migration of C-LARA project data into C-LARA-2.
6. Repeatable backup/export/import for future relocations.

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
- Support a crossover period where **C-LARA and C-LARA-2 both run on AWS**.
- Host read-only legacy compiled content from the original LARA project.
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
- Plan storage layout to include:
  - active C-LARA-2 media/artifacts,
  - temporary C-LARA crossover data,
  - read-only legacy compiled HTML content (~9 GB baseline, plus growth headroom).

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
- Dedicated Python venv and systemd services for C-LARA during crossover period.
- Environment values in `.env` file or parameter store/secret manager (preferred for secrets).

#### Legacy content hosting model (explicit requirement)
- Host original LARA compiled HTML directories as **read-only static content**.
- Keep legacy content operationally separate from active app write paths.
- Serve legacy content under a stable URL prefix (for example `/lara-legacy/`) so links can be documented and tested.
- Source material status:
  - legacy compiled HTML/audio/image directories are already downloaded to a local laptop,
  - current known size is approximately **9 GB**,
  - content is non-editable but must remain publicly accessible.

---

## 2) Concrete AWS provisioning plan (next step after this document)

This is the immediate planning/execution track.

### Phase P0 — decisions to lock (same day)
1. Confirm AWS account and IAM access model.
2. Confirm region (`ap-southeast-2`) and target hostname.
3. Choose DB mode: RDS now (preferred) vs temporary local PostgreSQL.
4. Choose access model: bastion SSH vs AWS SSM Session Manager.
5. Confirm crossover hosting scope: C-LARA + C-LARA-2 + legacy LARA static content.

### Phase P0 decision log (updated Friday, April 24, 2026)

Status summary:
- ✅ AWS account access confirmed.
- ✅ IAM admin model established for day-to-day use:
  - account alias sign-in URL set and tested,
  - dedicated IAM user in `Admin` group,
  - MFA enabled,
  - root retained for emergency-only use.
- ✅ Region confirmed as `ap-southeast-2`.
- ✅ DB direction agreed: PostgreSQL on AWS via RDS (preferred path), consistent with prior stable PostgreSQL operations on Adelaide.
- ✅ Access direction agreed: AWS SSM Session Manager (preferred over bastion SSH for routine administration).
- ✅ Crossover scope confirmed: C-LARA + C-LARA-2 + legacy read-only LARA static content.

Execution note:
- P1 provisioning work intentionally deferred to Saturday, April 25, 2026 due to end-of-day timing.

### Phase P1 — infrastructure bootstrap (day 1)
1. Create VPC/subnets/security groups.
2. Provision EC2 instance with fixed Elastic IP (or ALB if used).
3. Attach EBS volumes and enable scheduled snapshots.
4. Provision DB (RDS PostgreSQL preferred) and secure network path.
5. Configure DNS records for target hostname.

### Phase P1 progress log (updated Sunday, April 26, 2026)

Status summary:
- ✅ VPC/subnets/security groups created.
  - Dedicated private subnets prepared for DB placement.
  - Security groups split by role (`clara2-web-sg` and `clara2-db-sg`) with DB ingress restricted to app SG.
- ✅ EC2 app host provisioned with fixed Elastic IP.
  - Instance: `clara2-app-01`
  - Elastic IP associated and DNS-resolvable.
- ✅ EBS baseline in place.
  - Root gp3 volume configured and encrypted.
  - Snapshot policy setup remains part of immediate hardening follow-up in P2.
- ✅ RDS PostgreSQL provisioned on private subnets with secure network path.
  - DB subnet group uses private subnets only.
  - Public access disabled and connectivity from EC2 validated on port 5432.
- ✅ DNS record created for AWS host target.
  - `c-lara-2.c-lara.org` A record points to AWS Elastic IP.
  - Operational DNS currently managed at authoritative WordPress nameservers.

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
7. Deploy C-LARA in parallel (temporary crossover track) with separate services and env:
   - `gunicorn-clara.service`
   - `djangoq-clara.service`
8. Import legacy LARA compiled directories to dedicated read-only path, then wire Nginx static route.

### Phase P4 — production readiness checks (day 2–3)
1. Smoke test critical flows:
   - login,
   - project list/load,
   - compile/worker execution,
   - media/artifact read-write.
2. Smoke test crossover scope:
   - C-LARA login/basic project access,
   - C-LARA-2 login/basic project access,
   - legacy LARA static content URLs and media playback.
3. Verify backups:
   - DB snapshot + restore test,
   - media backup + restore test.
4. Verify observability:
   - app and worker logs,
   - uptime/latency/error alerting.
5. Run rollback drill to previous known-good deploy artifact.

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
5. Inventory resource usage from Adelaide to seed AWS sizing estimates:
   - CPU and memory utilization patterns,
   - disk occupancy and growth,
   - request/traffic pattern snapshots,
   - queue/job throughput for compile workloads.

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

### Additional migration inventory already available
- Hundreds of C-LARA projects have already been downloaded locally as source packages.
- These local exports should be treated as a migration seed set for dry runs and validation before any production import.
- Keep a manifest (project identifier, export timestamp, checksum) for traceability.

---

## 5) Legacy and crossover hosting requirements

### Legacy LARA compiled content
- Preserve and host legacy compiled HTML content from original LARA as read-only.
- Maintain audio/image asset integrity and path stability.
- Create a published index page so users can discover available legacy materials.

### C-LARA + C-LARA-2 crossover period
- Plan for a substantial period where both systems are publicly accessible on the same AWS host or AWS environment.
- Keep clear URL separation and service isolation to reduce regression risk.
- Define explicit retirement criteria for C-LARA once C-LARA-2 adoption and migration reach agreed thresholds.

---

## 6) Cost planning and estimation (initial placeholder, to refine)

### Why this is included now
- Cost questions are immediate and unavoidable for AWS provisioning decisions.
- Estimates should be iterative: start with coarse ranges, then tighten using Adelaide measurements and AWS telemetry.

### Cost components to estimate
1. Compute (EC2 instance hours, optional ALB).
2. Database (RDS instance/storage/backup, or temporary self-managed DB cost).
3. Storage (EBS volumes + snapshots; S3 if used for backup bundles).
4. Data transfer (egress to users, inter-service transfer where relevant).
5. Monitoring/logging (CloudWatch metrics/log ingestion/retention).
6. DNS/TLS supporting services (Route 53, certificate operations where applicable).

### Practical estimation method
1. **Baseline from Adelaide (immediate):**
   - collect current CPU/RAM/disk usage, traffic shape, and queue/job volumes;
   - use this as lower-bound sizing for crossover AWS workloads.
2. **Adjust for crossover scope:**
   - include simultaneous C-LARA + C-LARA-2 runtime overhead;
   - include legacy static content hosting and transfer demand.
3. **Build three scenarios:**
   - conservative (low traffic),
   - expected,
   - peak/headroom.
4. **Use AWS Pricing Calculator** for each scenario and record assumptions in-repo.
5. **Run 2-week measurement loop post-deploy:**
   - compare estimated vs observed cost and resize where needed.

### Immediate data to collect for first-pass estimate
- From Adelaide: 30-day CPU/RAM peaks, average/peak request rates, queue throughput, and disk growth.
- From local archives: exact size of legacy LARA static package (currently ~9 GB), plus size of C-LARA source exports.
- From product owners: expected user concurrency and growth assumptions for next 6–12 months.

---

## 7) Backup/export/import portability

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

## 8) Operational standards (cross-cutting)

- **Security:** least-privilege IAM and DB users, secret rotation policy, audited admin actions.
- **Observability:** logs + metrics for app/worker/DB/host, with alert thresholds.
- **Durability:** automated backups with retention policy and periodic restore drills.
- **Reproducibility:** pinned Python dependencies; no unlogged production hotfix installs.
- **Compatibility:** stable URL/artifact strategy to avoid breaking published links.

---

## 9) Rescheduled milestones (AWS-first)

### Milestone A — AWS foundation (target: by April 30, 2026)
- AWS infra baseline provisioned (network, compute, DB, DNS plan).
- Base security/monitoring controls enabled.

### Milestone B — AWS app readiness (target: by May 3, 2026)
- C-LARA-2 and C-LARA deployed on AWS with services running.
- Smoke tests passing; backup and restore drills executed.
- Legacy LARA static content hosted read-only and verified.

### Milestone C — Production cutover (target: by May 6, 2026)
- DNS cutover completed.
- 24–48h stabilization with rollback readiness.

### Milestone D — Adelaide wrap-up (no later than May 8, 2026)
- Final Adelaide backups and runbook capture complete.
- Decommission/hand-off checklist completed.

### Milestone E — Migration tooling progress (following cutover)
- C-LARA → C-LARA-2 mapping spec and first dry-run on sample data.

---

## 10) Immediate inputs needed to execute provisioning plan

To start Phase P0/P1 immediately, confirm:
1. AWS account/project owner and who can approve cost/security settings.
2. Preferred hostname for C-LARA-2 production on AWS.
3. Whether RDS PostgreSQL is approved for day-1 use.
4. Preferred operations access model (SSM-only recommended).
5. Budget envelope (monthly target + hard cap).
6. Crossover policy for C-LARA duration and retirement criteria.
7. URL strategy for legacy read-only LARA hosting.

Once these items are confirmed, we can produce a concrete, command-level provisioning runbook and a first-pass cost estimate.

## 11) Current status snapshot (as of Sunday, April 26, 2026)

### What is complete
- **P0:** complete (IAM/admin model, MFA, region, DB direction, access model, and crossover scope all confirmed).
- **P1 core infrastructure bootstrap:** complete.
  - VPC networking prepared with dedicated private subnets and private DB subnet group.
  - EC2 application host launched and bound to fixed Elastic IP.
  - RDS PostgreSQL instance (`database-1`) created in private subnets.
  - EC2 → RDS connectivity validated on port 5432.
  - DNS for `c-lara-2.c-lara.org` created at current authoritative DNS provider and resolving to AWS Elastic IP.
- **Initial database bootstrap:** complete.
  - `clara2` database created.
  - `clara2_app` role created and granted database-level privileges.

### Important implementation notes from the last two days
- First AWS account attempt ran into permissions-boundary lock issues; we restarted with a fresh AWS account and documented root/IAM access setup more carefully.
- Route 53 hosted zone was created in AWS, but `c-lara.org` remains delegated to WordPress nameservers for now; operational DNS changes are being performed at the current authoritative provider to avoid disruption.

### Next actions (in order)
1. Start **P2** host hardening/base software setup on EC2 (Nginx, Python runtime, system packages, logging/monitoring baseline).
2. Begin **P3** application deployment:
   - clone repo,
   - create venv and install dependencies,
   - configure `.env` for RDS and runtime settings,
   - run migrations/static setup,
   - stand up `gunicorn-clara2.service` and `djangoq-clara2.service`.
3. Configure TLS for `c-lara-2.c-lara.org` and validate end-to-end HTTPS access.
4. Proceed to crossover tracks (C-LARA side-by-side deployment and legacy read-only content hosting) once C-LARA-2 baseline is healthy.
