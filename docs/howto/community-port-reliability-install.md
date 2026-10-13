# Install the language-port reliability patch

Patch: `community_dictionary_port_reliability.patch`.
Baseline: `3ed343a3b70565c686b836eadb5d0330c5df7f14`
(`Clarify Community Dictionary credit holds and add read-only audit`).

This patch includes **migration 0023_port_budget_release**. It adds bookkeeping
fields, without rewriting existing content or credit records. No requirements,
static assets or environment settings change. Existing approved jobs keep their
original accounting; fresh estimates use the new allowances.

## Laptop first

Let active AI calls finish, then stop runserver and any local qcluster. Save the
patch in `/home/github/`, beside the repository. Back up SQLite using the explicit
`-c` wrapper needed by Windows Python under Cygwin:

```bash
cd /home/github/c-lara-2/platform_server
../.venv/Scripts/python.exe -E manage.py shell -v 0 -c "exec(__import__('sys').stdin.read())" <<'PY'
import sqlite3
from contextlib import closing
from pathlib import Path
from datetime import datetime
from django.conf import settings
config = settings.DATABASES['default']
assert config['ENGINE'] == 'django.db.backends.sqlite3', 'Stop: expected laptop SQLite'
source = Path(config['NAME']).resolve()
assert source.is_file(), f'Missing database: {source}'
directory = Path.cwd().parent.parent / 'clara2-backups'
directory.mkdir(exist_ok=True)
backup = directory / ('before-port-reliability-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '.sqlite3')
with closing(sqlite3.connect(str(source))) as src, closing(sqlite3.connect(str(backup))) as dst:
    src.backup(dst)
    assert dst.execute('PRAGMA quick_check').fetchall() == [('ok',)], 'Backup verification failed'
print('Database backup verified:', backup)
PY
```

After that success message, inspect the working tree. Expect no output from
`git status --short`; stop and preserve unexpected changes rather than resetting them.

```bash
cd /home/github/c-lara-2
git status --short
git apply --check ../community_dictionary_port_reliability.patch &&
git apply --index ../community_dictionary_port_reliability.patch &&
git diff --cached --check
```

Then run the checks. Stop if any command fails:

```bash
cd /home/github/c-lara-2/platform_server
../.venv/Scripts/python.exe -E manage.py check &&
../.venv/Scripts/python.exe -E manage.py test community_dictionary projects.tests.test_admin_tools projects.tests.test_email_reset projects.tests.test_profile &&
../.venv/Scripts/python.exe -E manage.py migrate &&
../.venv/Scripts/python.exe -E manage.py showmigrations community_dictionary
```

The tested suite contains **634 tests**. Mocked failure/timeout logs are expected;
the final result must be **OK**. Expect `[X] 0023_port_budget_release`.
Restart in the normal laptop environment:

```bash
../.venv/Scripts/python.exe -E manage.py runserver --insecure
```

If using the real local queue, restart it in a second terminal with the same
environment using `../.venv/Scripts/python.exe -E manage.py qcluster`. Do not add a
second worker if one is already managed separately. No queue-setting change is
needed for this patch.

## Trial checklist

1. Request a **fresh** vocabulary estimate for a small dictionary. Compare the
   estimate and allowance; nothing is charged until approval. An existing approved
   job will still show its original allowance.
2. Retry vocabulary on accepted Japanese sentences. Check word pages and links,
   including inflected surface forms. This does not repeat sentence translation.
3. Save accepted text from a job with missing audio. On that job's results page,
   choose **Retry missing audio — show estimate** and approve. Successful existing
   recordings should remain; only missing current recordings are requested.
4. New sentence translations are checked independently for the requested language.
   If flagged, review/edit and save them; create missing audio afterwards. Existing
   accepted French-in-Italian text is not automatically corrected: edit it manually.
5. After a credit-funded job finishes, run the read-only audit. Expect zero held
   for that completed job and zero reconciliation warnings. While other items await
   review, completed items can already have returned unused credit. Do not create
   deliberate paid failures just to exercise the top-up path; regression tests do that.

```bash
../.venv/Scripts/python.exe -E manage.py community_credit_audit --username 'mannyrayner'
```

When satisfied, check in the staged patch:

```bash
cd /home/github/c-lara-2
git diff --cached --check
git diff --cached --stat
git status --short
git commit -m "Improve language-port estimates, CJK vocabulary and audio recovery" &&
git push origin main &&
git rev-parse HEAD
```

Keep the printed commit ID for AWS comparison. Do not add databases, media or secrets.

## AWS after laptop acceptance

Choose a quiet interval and let actual queued/running AI requests finish. Review
previews may remain pending. Both applications share the service restart.

```bash
sudo -iu ssm-user
umask 022
cd /srv/C-LARA-2
git branch --show-current
git status --short
git fetch origin
git log --oneline HEAD..origin/main
CLARA_PORT_REPAIR_OLD_SHA=$(git rev-parse HEAD)
git rev-parse HEAD
```

Expect `main`, a clean tree, and the intended tested commit in the incoming log.
Define the protected-environment helper if it is not already available:

```bash
clara_manage() {
  sudo systemd-run --quiet --wait --pipe --collect \
    --property=User=ubuntu \
    --property=Group=www-data \
    --property=WorkingDirectory=/srv/C-LARA-2/platform_server \
    --property=EnvironmentFile=/etc/clara2.env \
    /srv/C-LARA-2/.venv/bin/python manage.py "$@"
}
clara_manage check
clara_manage community_queue_check --tasks 20
```

Stop on a failure. The patched local Django-Q fallback is valid on AWS; check
its concurrency and connection cleanup with the probe, not USE_REAL_DJANGO_Q.
Do not disclose the environment file or relax its permissions.
Use PostgreSQL 18 client tools for the backup, as in the earlier successful deployment.
This additive migration requires a fresh database backup; it does not require
another 22 GB public-media archive. Keep normal media backups independently.

```bash
/usr/lib/postgresql/18/bin/pg_dump --version
/usr/lib/postgresql/18/bin/pg_restore --version
sudo install -d -o ubuntu -g www-data -m 700 /var/backups/clara2-port-reliability
sudo systemctl stop gunicorn-clara2 djangoq-clara2 project-understanding-worker
clara_manage shell -v 0 -c '
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from django.conf import settings

config = settings.DATABASES["default"]
assert config["ENGINE"] == "django.db.backends.postgresql", "Expected AWS PostgreSQL"
os.umask(0o077)
backup = Path("/var/backups/clara2-port-reliability") / datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
backup.mkdir(mode=0o700)
env = {**os.environ, "PGPASSWORD": str(config.get("PASSWORD") or "")}
sslmode = config.get("OPTIONS", {}).get("sslmode")
if sslmode:
    env["PGSSLMODE"] = str(sslmode)
dump = backup / "database.dump"
subprocess.run(["/usr/lib/postgresql/18/bin/pg_dump", "--no-password", "--format=custom",
    "--host=" + str(config.get("HOST") or ""), "--port=" + str(config.get("PORT") or "5432"),
    "--username=" + str(config.get("USER") or "postgres"), "--dbname=" + str(config["NAME"]),
    "--file=" + str(dump)], env=env, check=True)
assert dump.stat().st_size > 0, "Empty database backup"
subprocess.run(["/usr/lib/postgresql/18/bin/pg_restore", "--list", str(dump)],
    stdout=subprocess.DEVNULL, check=True)
print("Database archive created and listed:", backup)
'
```

Proceed only after the final success message. Archive listing is a basic check,
not a full restore rehearsal. If backup fails, do not pull/migrate; restart the
unchanged services while resolving the backup problem.

With services still stopped:

```bash
cd /srv/C-LARA-2
git merge --ff-only origin/main &&
clara_manage check &&
clara_manage migrate &&
clara_manage showmigrations community_dictionary &&
clara_manage migrate --check
```

Expect `[X] 0023_port_budget_release`. Stop and retain output if anything fails.
There is no `collectstatic`, pip install, nginx reload or environment edit for this patch.

```bash
sudo systemctl start gunicorn-clara2 djangoq-clara2 project-understanding-worker
sudo systemctl status --no-pager gunicorn-clara2 djangoq-clara2 project-understanding-worker
clara_manage community_credit_audit --username 'mannyrayner'
```

Check an existing dictionary/entry, then repeat the small trial before a larger
fresh conversion. Run the audit again after the new job finishes. Report any
warnings; do not manually refund or reset balances. Old approved jobs retain their
original holds until their normal review/audio lifecycle finishes.

## Recovery

If startup fails, keep `DEBUG=False` and inspect the service journal:

```bash
sudo journalctl -u gunicorn-clara2 -u djangoq-clara2 \
  --since '10 minutes ago' -n 160 --no-pager
```

Before any new-policy job has been approved, a code rollback to the saved SHA can
leave the additive schema in place. **After new jobs have run, do not deploy the
old accounting code:** it does not understand incremental refunds and top-ups.
Check first with the services stopped:

```bash
clara_manage shell -v 0 -c 'from community_dictionary.models import PortRun; print("New-policy approvals exist:", PortRun.objects.filter(options__budget_version=1, approved_at__isnull=False).exists())'
```

If that prints `True`, prefer a forward repair and preserve the job/ledger evidence.
Do not reverse migration 0023 or restore a whole database over newer contributions
as an automatic rollback. Keep the backup and ask for a targeted recovery sequence.
