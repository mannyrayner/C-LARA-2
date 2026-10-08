# Installing the picture-description allowance

8 October 2026. Incremental patch after the audio-recovery release, observed on
GitHub main at `3b7bcedd76b2e7fe7cf928e3b0be8a08264aa8a1`.

The owner gets **Settings → Picture-description allowance → Preview daily cost →
Confirm**. Default ten; shared rolling 24-hour usage survives a change. Associated
audio is included approximately, and the estimate is not a spending cap. Each
member retains their own payment settings. Other AI tools keep their own limits.

There is one additive migration, **0016_capture_daily_limit**. No dependency,
media rewrite, nginx or service-unit change is needed. A fresh database backup is
appropriate; no new bulk media archive is needed for this change.

## 1. Laptop backup and installation

Stop runserver. Save `community_dictionary_capture_limits.patch` in `/home/github/`.
Check that main is clean and the preceding audio-recovery change is committed:

```bash
cd /home/github/c-lara-2
git branch --show-current
git status --short
```

Back up SQLite. Keep the explicit `-c` below: it avoids the interactive-shell
problem with native Windows Python launched from Cygwin.

```bash
cd /home/github/c-lara-2/platform_server
../.venv/Scripts/python.exe -E manage.py shell -v 0 -c "exec(__import__('sys').stdin.read())" <<'PY'
import sqlite3
from datetime import datetime
from pathlib import Path
from django.conf import settings

config = settings.DATABASES['default']
assert config['ENGINE'] == 'django.db.backends.sqlite3', 'Stop: not the laptop SQLite database'
source = Path(config['NAME']).resolve()
assert source.is_file(), f'Missing database: {source}'
destination = Path.cwd().parent.parent / 'clara2-backups'
destination.mkdir(exist_ok=True)
backup = destination / ('before-capture-limits-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '.sqlite3')
with sqlite3.connect(str(source)) as src, sqlite3.connect(str(backup)) as dst:
    src.backup(dst)
    assert dst.execute('PRAGMA quick_check').fetchall() == [('ok',)], 'Backup verification failed'
print('Database backup verified:', backup)
PY
```

Only after that succeeds:

```bash
cd /home/github/c-lara-2
git apply --check ../community_dictionary_capture_limits.patch &&
git apply --index ../community_dictionary_capture_limits.patch &&
git diff --cached --check
cd platform_server
../.venv/Scripts/python.exe -E manage.py check &&
../.venv/Scripts/python.exe -E manage.py test community_dictionary &&
../.venv/Scripts/python.exe -E manage.py migrate &&
../.venv/Scripts/python.exe -E manage.py showmigrations community_dictionary
```

Expect **349 tests**, ending `OK`, and migration 0016 checked `[X]`. Simulated
provider failures printed during successful tests are expected. Stop on any error.
Restart normally:

```bash
../.venv/Scripts/python.exe -E manage.py runserver --insecure
```

## 2. Quick acceptance check

As dictionary owner, open Settings and find **Picture-description allowance**.
Enter 50 and choose **Preview daily cost**. Check the total and its assumptions;
the preview is free and changing a limit starts no generation. Going back leaves
the old allowance unchanged. Preview again, tick approval and confirm.

Existing usage must stay the same: if ten were used, forty should remain. A member
can see this count when starting a Picture description. Try one more description
if ready to make an ordinary paid request. Reducing the allowance later does not
hide previous work or reset the count.

The default server ceiling is 1000. An existing operator override of
`C_LARA_COMMUNITY_CAPTURE_DAILY_LIMIT` can lower that maximum. No environment change
is needed on the normal setup. Preview prices come from server configuration;
this update does not change provider tariffs or account funding.

## 3. Check in after acceptance

```bash
cd /home/github/c-lara-2
git diff --cached --stat
git diff --cached --check
git diff --name-only
git status --short
```

Everything in the patch is already staged. **settings.py is intentionally changed**
this time: it defines the server ceiling from the environment. Expect Community
Dictionary code/tests/migration, that setting, documentation and workspace records.
Keep databases, backups and credentials out of Git. If those are the expected
changes and the unstaged diff is empty:

```bash
git commit -m "Configure picture-description allowances with cost approval" &&
git push origin main &&
git rev-parse HEAD &&
git status --short
```

## 4. AWS

Let current AI jobs finish, then allow a short shared-site interruption. Start
with clean main and load the same environment as the services:

```bash
sudo -iu ssm-user
cd /srv/C-LARA-2
umask 022
git branch --show-current
git status --short
. .venv/bin/activate
set -a && . /etc/clara2.env && set +a
export CLARA_CAPTURE_BACKUP="$HOME/clara2-backups/capture-limits-$(date -u +%Y%m%d-%H%M%S)"
sudo systemctl stop gunicorn-clara2 djangoq-clara2 project-understanding-worker
```

Take a database-only backup using the installed PostgreSQL 18 utilities. This
reads the actual Django connection settings and does not print credentials:

```bash
cd /srv/C-LARA-2/platform_server
python manage.py shell -v 0 -c "exec(__import__('sys').stdin.read())" <<'PY'
import os
import subprocess
from pathlib import Path
from django.conf import settings

os.umask(0o077)
config = settings.DATABASES['default']
assert config['ENGINE'] == 'django.db.backends.postgresql', 'Stop: unexpected database engine'
backup = Path(os.environ['CLARA_CAPTURE_BACKUP'])
backup.mkdir(parents=True, exist_ok=False)
backup.joinpath('previous-commit.txt').write_text(subprocess.check_output(
    ['git', 'rev-parse', 'HEAD'], text=True))
environment = dict(os.environ, PGPASSWORD=config.get('PASSWORD') or '')
dump = backup / 'database.dump'
subprocess.run(['/usr/lib/postgresql/18/bin/pg_dump', '--no-password',
    '--host=' + str(config.get('HOST') or ''),
    '--port=' + str(config.get('PORT') or 5432),
    '--username=' + str(config.get('USER') or 'postgres'),
    '--dbname=' + str(config['NAME']), '--format=custom', '--file=' + str(dump)],
    env=environment, check=True)
assert dump.stat().st_size > 0, 'Empty backup'
with (backup / 'archive-list.txt').open('w') as listing:
    subprocess.run(['/usr/lib/postgresql/18/bin/pg_restore', '--list', str(dump)],
        stdout=listing, check=True)
print('Database backup created; archive catalogue readable:', backup)
PY
```

Only continue after success. If backup fails, leave the old code installed and
bring the services back with `sudo systemctl start gunicorn-clara2 djangoq-clara2
project-understanding-worker`; resolve the backup error before updating.

```bash
cd /srv/C-LARA-2
git pull --ff-only origin main &&
git rev-parse HEAD
```

Compare that SHA with the laptop's commit. Stop on a mismatch. Then inspect the
migration plan before applying it:

```bash
cd /srv/C-LARA-2/platform_server
python manage.py check &&
python manage.py migrate --plan
```

Expect only `community_dictionary.0016_capture_daily_limit`, adding one field.
If any other migration is pending, stop and review the deployment state. Otherwise:

```bash
python manage.py migrate &&
python manage.py collectstatic --noinput &&
sudo systemctl restart gunicorn-clara2 djangoq-clara2 project-understanding-worker
sudo systemctl status --no-pager gunicorn-clara2 djangoq-clara2 project-understanding-worker
```

All three services should stay active. Keep DEBUG=False. No nginx restart or
daemon-reload is needed. Open the dictionary's Settings and repeat the free
preview/confirmation check; laptop quota changes are not copied to AWS.

If application startup fails, preserve the error and inspect the service logs.
This migration only adds a field, so the preceding code can run with it still
present; do not restore the whole database over new user contributions merely
to undo this code update.
