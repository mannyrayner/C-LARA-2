# Installing dictionary visibility controls

8 October 2026. Incremental patch after the accepted picture-description allowance
release, observed on GitHub main at `fc7efff5a4959030f8b16e0101a019263ec1f12f`.
Apply this after that earlier patch, not instead of it.

The owner gets **Settings → Dictionary visibility → Hide dictionary / Make
dictionary visible**. Hidden dictionaries leave the normal list for all members
and remain accessible under the collapsed **Hidden dictionaries** section.
Saved links and contribution rights remain intact. This lets you hide the original
Swedish dictionary while keeping the newer version easy to find.

There is one additive migration, **0017_dictionary_visibility**, defaulting every
dictionary to visible. No dependency, settings.py, media rewrite, nginx or service
unit change is needed. Back up the database; no new bulk media archive is needed.

## 1. Laptop backup and installation

Stop runserver. Save `community_dictionary_visibility.patch` in `/home/github/`.
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
backup = destination / ('before-dictionary-visibility-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '.sqlite3')
with sqlite3.connect(str(source)) as src, sqlite3.connect(str(backup)) as dst:
    src.backup(dst)
    assert dst.execute('PRAGMA quick_check').fetchall() == [('ok',)], 'Backup verification failed'
print('Database backup verified:', backup)
PY
```

Only after that succeeds:

```bash
cd /home/github/c-lara-2
git apply --check ../community_dictionary_visibility.patch &&
git apply --index ../community_dictionary_visibility.patch &&
git diff --cached --check
cd platform_server
../.venv/Scripts/python.exe -E manage.py check &&
../.venv/Scripts/python.exe -E manage.py test community_dictionary &&
../.venv/Scripts/python.exe -E manage.py migrate &&
../.venv/Scripts/python.exe -E manage.py showmigrations community_dictionary
```

Expect **356 tests**, ending `OK`, and migration 0017 checked `[X]`. Simulated
provider failures printed during successful tests are expected. Stop on any error.
Restart normally:

```bash
../.venv/Scripts/python.exe -E manage.py runserver --insecure
```

## 2. Quick acceptance check

As owner of the original Swedish dictionary, choose **Settings → Dictionary
visibility → Hide dictionary**. Go back to My dictionaries: only the new version
should remain in the ordinary list. Ask Cathy to check her list as well.

Open **Hidden dictionaries** to find the original. It should be clearly labelled
Hidden when opened. The owner can use **Visibility settings → Make dictionary
visible** to put it back, with immediate effect. Try that once, then hide it again
if desired. Content and contribution rights remain unchanged; this does not
withdraw the original images or their copies in the new dictionary.

No AI call or charge is involved. Saved links still work for authorized members;
Hidden is a display setting rather than an access restriction.

## 3. Check in after acceptance

```bash
cd /home/github/c-lara-2
git diff --cached --stat
git diff --cached --check
git diff --name-only
git status --short
```

Everything in the patch is already staged. Expect Community Dictionary
code/templates/tests, migration 0017, documentation and workspace records.
There is no settings.py change in this patch. Keep databases, backups and
credentials out of Git. If those are the expected changes and the unstaged diff
is empty:

```bash
git commit -m "Add reversible dictionary visibility controls" &&
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
export CLARA_VISIBILITY_BACKUP="$HOME/clara2-backups/dictionary-visibility-$(date -u +%Y%m%d-%H%M%S)"
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
backup = Path(os.environ['CLARA_VISIBILITY_BACKUP'])
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

Expect only `community_dictionary.0017_dictionary_visibility`, adding one field.
If any other migration is pending, stop and review the deployment state. Otherwise:

```bash
python manage.py migrate &&
python manage.py collectstatic --noinput &&
sudo systemctl restart gunicorn-clara2 djangoq-clara2 project-understanding-worker
sudo systemctl status --no-pager gunicorn-clara2 djangoq-clara2 project-understanding-worker
```

All three services should stay active. Keep DEBUG=False. No nginx restart or
daemon-reload is needed. Open the dictionary's Settings and repeat the
hide/show check with the original dictionary. Visibility settings chosen on the
laptop are not copied to AWS.

If application startup fails, preserve the error and inspect the service logs.
This migration only adds a field, so the preceding code can run with it still
present; do not restore the whole database over new user contributions merely
to undo this code update.
