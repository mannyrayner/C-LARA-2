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

Decision rule: if a short-term Adelaide workaround conflicts with migration/relocation portability, choose the portable option or document an explicit deprecation path.

---

## 1) Adelaide dual-run deployment (urgent)

### Goals
- Deploy C-LARA-2 without disrupting the existing C-LARA service.
- Keep operational separation while allowing shared infrastructure where safe.
- Enable rollback with minimal risk.

### Known current baseline (from existing C-LARA ops)
- Current production URL: `https://c-lara.unisa.edu.au/`.
- Reverse proxy: **Nginx**.
- C-LARA code root: `<root>/C-LARA`, exposed as `$CLARA`.
- Typical restart sequence:
  - `sudo systemctl restart gunicorn`
  - `sudo systemctl restart djangoq.service`
  - `sudo systemctl restart nginx`
- Existing app Makefile includes `migrate`, `runserver`, `qcluster`.

### Recommended C-LARA-2 target shape on Adelaide

#### Hostname and routing
- Keep C-LARA unchanged at `https://c-lara.unisa.edu.au/`.
- Deploy C-LARA-2 at `https://c-lara-2.unisa.edu.au/` (preferred, clear separation).
- Nginx should use separate server blocks and upstreams for C-LARA and C-LARA-2.

#### Filesystem layout and environment variables
- Keep C-LARA at `<root>/C-LARA` with `$CLARA`.
- Place C-LARA-2 at `<root>/C-LARA-2`.
- Use an env var name without hyphens, e.g.:
  - `$CLARA2` (recommended) or `$CLARA_2`.
  - **Do not** use `$C-LARA-2` (invalid shell variable syntax).

#### Process isolation
- Use distinct systemd units:
  - `gunicorn-clara.service` (existing C-LARA),
  - `djangoq-clara.service` (existing C-LARA),
  - `gunicorn-clara2.service` (new),
  - `djangoq-clara2.service` (new).
- Keep separate sockets/pids/log files for each service to simplify debugging.

#### Runtime/data isolation
- Separate DB names (or at minimum separate DB schemas/users) for C-LARA vs C-LARA-2.
- Separate media/artifact roots:
  - C-LARA: existing media root,
  - C-LARA-2: dedicated media root (no shared writes).
- Separate secrets/config files:
  - `<root>/C-LARA/.env` (or equivalent),
  - `<root>/C-LARA-2/.env` (or equivalent).

### Part 1 implementation plan (detailed)

#### Phase 1 — discovery + freeze (very short, high impact)
1. Export and snapshot current C-LARA deployment config:
   - Nginx site config,
   - `gunicorn`/`djangoq` systemd unit files,
   - current venv path and python package lock/freeze,
   - DB connection settings and backup routine.
2. Create rollback bookmarks:
   - git commit/tag currently deployed for C-LARA,
   - copy of active service files,
   - DB backup timestamp recorded in runbook.

#### Phase 2 — install C-LARA-2 side-by-side
1. Provision `<root>/C-LARA-2` and dedicated venv.
2. Install dependencies from pinned lock constraints (see “Python package hygiene” below).
3. Configure C-LARA-2 `.env` with separate DB/media/secret values.
4. Run:
   - migrations,
   - static collection (if applicable),
   - smoke startup via `runserver` and `qcluster`.

#### Phase 3 — wire production services
1. Add `gunicorn-clara2.service` and `djangoq-clara2.service`.
2. Add Nginx `server_name c-lara-2.unisa.edu.au` with TLS and proxy upstream.
3. Start/restart C-LARA-2 services, then Nginx.
4. Validate:
   - health page/login/project list,
   - compile monitor + worker execution,
   - artifact serving and media writes.

#### Phase 4 — post-cutover validation + rollback drill
1. Execute smoke script for critical flows (compile, image generation, exercises, publish/content page).
2. Confirm C-LARA remains unaffected.
3. Run a rollback dry-run:
   - stop clara2 services,
   - disable clara2 server block,
   - verify C-LARA only mode still healthy.

### Python package hygiene (explicit fix for prior “messy installs”)
- Maintain a dedicated venv per app (`C-LARA` and `C-LARA-2` must not share site-packages).
- Pin dependencies using a lock file workflow (`requirements.txt` + lock, or `pip-tools`/`uv` lock).
- Update process:
  1. change dependency file in repo,
  2. rebuild venv from lock,
  3. restart relevant app services,
  4. record package diff in deployment log.
- Avoid manual `pip install` on production except as emergency hotfix, and log any emergency action.

### Operational checklist
- Health endpoints for app and worker.
- Log separation and rotation per app.
- Resource limits/monitoring to avoid one app starving the other.
- Staging dry-run before production cutover.
- One-command rollback procedure.

### Information still needed to complete Part 1 precisely
To turn this from roadmap to exact executable runbook, we still need:
1. Current Nginx site config for `c-lara.unisa.edu.au`.
2. Current systemd unit files for C-LARA (`gunicorn` + `djangoq`).
3. Exact Python/venv path used by current C-LARA.
4. Current DB engine/version and backup command(s).
5. TLS certificate provisioning method (certbot/manual/institutional proxy).
6. File ownership/user model (which Unix user runs app, worker, and nginx).
7. Existing log locations and rotation policy.
8. Any firewall/SELinux/AppArmor/network policy constraints on Adelaide hosts.

### How to collect this information (operator checklist)
If you are not a deployment specialist, use this as a copy/paste checklist for whoever has shell access to the Adelaide host.

> Run these commands on the Adelaide server and save outputs in a dated text file (e.g. `deploy-discovery-2026-04-02.txt`).

#### 1) Nginx config for current site
- Commands:
  - `sudo nginx -T | less`
  - `sudo nginx -T | grep -n "server_name"`
  - `sudo ls -l /etc/nginx/sites-enabled /etc/nginx/conf.d`
- What to capture:
  - `server_name` entries for `c-lara.unisa.edu.au`,
  - `location` and `proxy_pass` blocks,
  - TLS certificate/key file paths,
  - include-file structure.

#### 2) Systemd service definitions (gunicorn + djangoq)
- Commands:
  - `systemctl list-unit-files | grep -E "gunicorn|djangoq|qcluster"`
  - `sudo systemctl cat gunicorn`
  - `sudo systemctl cat djangoq.service`
  - `sudo systemctl status gunicorn djangoq.service --no-pager`
- What to capture:
  - `ExecStart`, `WorkingDirectory`, `User`, `Group`,
  - environment file references,
  - restart policy/timeouts.

#### 3) Python and venv path currently in use
- Commands:
  - `sudo systemctl cat gunicorn | grep -E "ExecStart|Environment|WorkingDirectory"`
  - `ps aux | grep -E "gunicorn|manage.py|qcluster" | grep -v grep`
  - `which python3 && python3 --version`
- What to capture:
  - absolute venv/bin/python path used by services,
  - package environment location,
  - Python version.

#### 4) DB engine/version + backup method
- Commands (adapt to your DB):
  - PostgreSQL: `psql --version`, `sudo -u postgres psql -c "\l"`
  - MariaDB/MySQL: `mysql --version`, `mysql -e "SHOW DATABASES;"`
  - Find backup jobs: `sudo crontab -l`, `sudo ls -l /etc/cron*`, `sudo systemctl list-timers --all`
- What to capture:
  - DB type/version,
  - database name/user for C-LARA,
  - actual backup command/script path and schedule,
  - backup destination + retention policy.

#### 5) TLS certificate provisioning method
- Commands:
  - `sudo nginx -T | grep -E "ssl_certificate|ssl_certificate_key|ssl_trusted_certificate"`
  - `sudo certbot certificates` (if certbot is used)
  - `sudo ls -l /etc/letsencrypt/live 2>/dev/null || true`
- What to capture:
  - whether certs are from certbot, institutional reverse proxy, or manual files,
  - renewal mechanism and owner.

#### 6) File ownership and runtime user model
- Commands:
  - `id`
  - `ps -eo user,group,cmd | grep -E "nginx|gunicorn|qcluster|djangoq" | grep -v grep`
  - `sudo ls -ld <root>/C-LARA <root>/C-LARA-2 2>/dev/null || true`
- What to capture:
  - Unix users/groups running web/app/worker,
  - ownership/permissions on code, media, log directories.

#### 7) Logs and log rotation
- Commands:
  - `sudo find /var/log -maxdepth 2 -type f | grep -E "nginx|gunicorn|django|qcluster|djangoq"`
  - `sudo ls -l /etc/logrotate.d`
  - `sudo sed -n '1,200p' /etc/logrotate.d/nginx`
- What to capture:
  - active log file locations,
  - rotation frequency/retention,
  - whether app logs are journal-only or file-based.

#### 8) Network and host security constraints
- Commands:
  - Firewall: `sudo ufw status verbose` or `sudo firewall-cmd --list-all`
  - SELinux: `getenforce` (if present)
  - AppArmor: `sudo aa-status` (if present)
  - Listening ports: `sudo ss -tulpn | head -n 200`
- What to capture:
  - inbound allowed ports,
  - mandatory access control mode (SELinux/AppArmor),
  - any proxy/network rules that affect new hostnames or services.

### Minimal handover format (recommended)
For each of the 8 items above, record:
1. **Current value** (exact config/service/command output),
2. **Where found** (file path or command),
3. **Owner/contact** (who can approve changes),
4. **Risk if changed** (short note).

This turns the discovery output into a practical deployment runbook input.

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
