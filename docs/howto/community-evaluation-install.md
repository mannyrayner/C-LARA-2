# Install dictionary evaluation

Patch: `community_dictionary_evaluation.patch`.
Base: `7f345d36bcd1d4f1e1638f11d90a340556980828` (published report/About links).

This adds migration **0024_evaluation**, new evaluation views/templates, Profile
navigation and **evaluation.js**. It does not modify existing dictionary records,
media, AI providers, credits or queue configuration. No new Python dependencies.
The first version collects human judgements; it does not call AI evaluators.

## 1. Laptop: back up, apply and test

Stop the local server and let any existing AI jobs finish. Download the patch to
`/home/github/`, beside the checkout. Check that the tree is clean; preserve any
unexpected changes rather than resetting them.

```bash
cd /home/github/c-lara-2
git status --short
git log -1 --oneline
```

Make a verified SQLite backup outside the repository. The explicit `-c` avoids
Cygwin treating the here-document as an interactive Python session.

```bash
cd /home/github/c-lara-2/platform_server
../.venv/Scripts/python.exe -E manage.py shell -v 0 -c "exec(__import__('sys').stdin.read())" <<'PY'
import sqlite3
from pathlib import Path
from datetime import datetime
from django.conf import settings
config = settings.DATABASES['default']
assert config['ENGINE'] == 'django.db.backends.sqlite3', 'Stop: expected laptop SQLite'
source = Path(config['NAME']).resolve()
assert source.is_file(), f'Missing database: {source}'
destination = Path.cwd().parent.parent / 'clara2-backups'
destination.mkdir(parents=True, exist_ok=True)
backup = destination / ('before-evaluation-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '.sqlite3')
with sqlite3.connect(str(source)) as src, sqlite3.connect(str(backup)) as dst:
    src.backup(dst)
    assert dst.execute('PRAGMA quick_check').fetchall() == [('ok',)], 'Backup verification failed'
print('Database backup verified:', backup)
PY
```

Proceed only after the verification message:

```bash
cd /home/github/c-lara-2
git apply --check ../community_dictionary_evaluation.patch &&
git apply --index ../community_dictionary_evaluation.patch &&
git diff --cached --check
```

```bash
cd /home/github/c-lara-2/platform_server
../.venv/Scripts/python.exe -E manage.py check &&
../.venv/Scripts/python.exe -E manage.py test community_dictionary projects.tests.test_admin_tools projects.tests.test_email_reset projects.tests.test_profile &&
../.venv/Scripts/python.exe -E manage.py migrate &&
../.venv/Scripts/python.exe -E manage.py migrate --check
```

The suite includes deliberately simulated provider failures, rollback exceptions
and mail errors; the final `OK` is what matters. If any command fails, stop before
the next block. Migration 0024 only creates new tables and constraints.

```bash
../.venv/Scripts/python.exe -E manage.py runserver --insecure
```

## 2. Try a tiny evaluation

1. **Profile → Add or update language competences**: save Swedish and English,
   with confident reading/listening as appropriate.
2. In a test dictionary, open **Evaluate**. Create a random sample of two pages.
3. Start a session, choose aspects and rate the pages. Verify Save and next,
   skipping, returning to a saved page and resuming after logging out/in.
4. If practical, use a second account on the same set and enter at least one
   deliberately different score. Do this only on a clearly named test set, not
   a set intended to supply research results.
5. As owner, **Finish collection and view results**, then confirm. Check counts,
   agreement and CSV. Before closing, neither owner nor evaluators can see each
   other's judgements. Closing is final; new rounds use a new set.
6. Optionally test a real visitor account: enable public browsing and explicitly
   allow signed-in visitors on the set. This grants evaluation access, not editing.

See `docs/howto/community-evaluation.md` for the scoring and privacy rules.
No AI credits are used. First do the small laptop trial; we can refine wording
before collecting the real 30–50-page sample.

## 3. Check in after acceptance

The patch is already staged. Keep databases and backups out of Git.

```bash
cd /home/github/c-lara-2
git diff --cached --check &&
git diff --cached --stat
git status --short
git commit -m "Add versioned dictionary evaluation and inter-rater reports" &&
git push origin main &&
git rev-parse HEAD
```

## 4. AWS: preparation and database backup

Choose a quiet interval and let active AI jobs finish. Do not change the tested
queue implementation or `USE_REAL_DJANGO_Q`. There are no environment or nginx changes.

```bash
sudo -iu ssm-user
umask 022
cd /srv/C-LARA-2
git branch --show-current
git status --short
git fetch origin
git log --oneline HEAD..origin/main
CLARA_EVALUATION_OLD_SHA=$(git rev-parse HEAD)
echo "$CLARA_EVALUATION_OLD_SHA"
```

Expect `main`, a clean tree and your tested commit in the incoming log. Define the
usual helper; systemd reads the protected environment file without printing it:

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
```

Make a fresh custom-format database backup using the already installed PostgreSQL
18 client. No full media archive is needed for this additive migration: it neither
rewrites nor deletes media. Continue the existing routine database/media backup policy.
The following private backup directory is outside the checkout and web-served paths.

```bash
sudo install -d -o ubuntu -g www-data -m 700 /var/backups/clara2
clara_manage shell -v 0 -c '
import os, subprocess
from datetime import datetime, timezone
from pathlib import Path
from django.conf import settings
cfg = settings.DATABASES["default"]
assert cfg["ENGINE"] == "django.db.backends.postgresql", "Stop: expected PostgreSQL"
os.umask(0o077)
root = Path("/var/backups/clara2")
stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
backup = root / ("before-evaluation-" + stamp + ".dump")
env = os.environ.copy()
for key, name in [("HOST", "PGHOST"), ("PORT", "PGPORT"), ("USER", "PGUSER"), ("PASSWORD", "PGPASSWORD"), ("NAME", "PGDATABASE")]:
    env[name] = str(cfg.get(key) or "")
if cfg.get("OPTIONS", {}).get("sslmode"):
    env["PGSSLMODE"] = cfg["OPTIONS"]["sslmode"]
subprocess.run(["/usr/lib/postgresql/18/bin/pg_dump", "--no-password", "--format=custom", "--file=" + str(backup)], env=env, check=True)
subprocess.run(["/usr/lib/postgresql/18/bin/pg_restore", "--list", str(backup)], stdout=subprocess.DEVNULL, check=True)
print("Database archive created and readable:", backup)
'
```

This checks archive readability, not a full restore rehearsal. If it fails, stop;
the old site is still running. Do not dump environment variables or credentials.

Check static-directory write access before taking the site down:

```bash
sudo -u ubuntu test -w /srv/C-LARA-2/platform_server/staticfiles &&
sudo -u ubuntu test -w /srv/C-LARA-2/platform_server/staticfiles/community_dictionary &&
echo 'Static directories are writable by the service account.'
```

If the success message does not appear, stop and report the directory ownership;
do not apply a recursive permission change to the whole checkout or private media.

## 5. AWS: short deployment interval

```bash
sudo systemctl stop gunicorn-clara2 djangoq-clara2 project-understanding-worker &&
git merge --ff-only origin/main &&
clara_manage check &&
clara_manage migrate &&
clara_manage migrate --check &&
clara_manage collectstatic --noinput &&
sudo systemctl start gunicorn-clara2 djangoq-clara2 project-understanding-worker
```

```bash
sudo systemctl status --no-pager gunicorn-clara2 djangoq-clara2 project-understanding-worker
git rev-parse HEAD
```

Compare the SHA with the laptop commit. Keep DEBUG=False. Test public browsing,
a normal member entry, Profile and the new Evaluate tab; then use a two-page test
set. Phone usability remains a human acceptance check. Existing AI work should
behave as before; evaluation does not schedule background tasks.

If a step fails, keep the output and stop. Check service logs without enabling DEBUG:

```bash
sudo journalctl -u gunicorn-clara2 -u djangoq-clara2 --since '10 minutes ago' -n 160 --no-pager
```

The migration is additive. If reverting application code becomes necessary, the
previous code can run with the extra evaluation tables left in place. Do not
unapply migration 0024 after collecting ratings, and do not restore an old whole
database over newer contributions merely to roll back this UI. Preserve the saved
old SHA and error output so we can choose a forward fix or a safe code rollback.
