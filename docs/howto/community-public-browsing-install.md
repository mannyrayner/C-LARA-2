# Install optional public dictionary browsing

Prepared against main `067cfc7938822858f34782fe2f28f0a532e28a7c`
(the email-password-recovery release). This adds only migration
`community_dictionary.0020_public_browsing`. Existing dictionaries remain private.
There are no dependency, static-file, email or environment-setting changes.

## 1. Laptop: back up and apply

Stop the development server. Save the patch as
`/home/github/community_dictionary_public_browsing.patch`, then check:

```bash
cd /home/github/c-lara-2
git status --short
git log -1 --oneline
```

Expect a clean working tree and the email-recovery commit. Stop for unexpected
local changes. Back up SQLite outside the repository:

```bash
cd /home/github/c-lara-2/platform_server
../.venv/Scripts/python.exe -E manage.py shell -v 0 -c "exec(__import__('sys').stdin.read())" <<'PY'
import sqlite3
from pathlib import Path
from datetime import datetime
from django.conf import settings
config = settings.DATABASES['default']
assert config['ENGINE'] == 'django.db.backends.sqlite3', 'Stop: not the laptop SQLite setup'
source = Path(config['NAME']).resolve()
assert source.is_file(), f'Missing database: {source}'
destination = Path.cwd().parent.parent / 'clara2-backups'
destination.mkdir(exist_ok=True)
backup = destination / ('before-public-browsing-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.sqlite3')
with sqlite3.connect(str(source)) as src, sqlite3.connect(str(backup)) as dst:
    src.backup(dst)
    assert dst.execute('PRAGMA quick_check').fetchall() == [('ok',)], 'Backup verification failed'
print('Database backup verified:', backup)
PY
```

The explicit `-c` and `-E` retain the working Cygwin/Windows setup. Then:

```bash
cd /home/github/c-lara-2
git apply --check ../community_dictionary_public_browsing.patch &&
git apply --index ../community_dictionary_public_browsing.patch &&
git diff --cached --check

cd platform_server
../.venv/Scripts/python.exe -E manage.py check &&
../.venv/Scripts/python.exe -E manage.py test community_dictionary projects.tests.test_email_reset projects.tests.test_admin_tools projects.tests.test_profile &&
../.venv/Scripts/python.exe -E manage.py migrate &&
../.venv/Scripts/python.exe -E manage.py showmigrations community_dictionary
```

Expected: **536 tests, OK**, and `[X] 0020_public_browsing`. Failure-simulation tests
deliberately log exceptions. Stop if the final result is not OK.

## 2. Laptop: try the visitor experience

```bash
cd /home/github/c-lara-2/platform_server
../.venv/Scripts/python.exe -E manage.py runserver --insecure
```

1. Log in as owner. Choose a suitable test dictionary, then **Settings → Public
   browsing**. Confirm contributor permission and enable it.
2. Open **View as a visitor**. Check Pictures, Words, Sentences, translations and audio.
3. In an Incognito/private window, open
   `http://127.0.0.1:8000/community-dictionaries/login/` and choose **Browse without
   logging in**. The enabled dictionary should appear; your private dictionaries
   should not. Check that editing/discussion/member controls are absent.
4. Turn public browsing off in the owner window. Reload the visitor page: it should
   say the dictionary/content is unavailable. Previously loaded material can remain
   on screen until reloaded.
5. If useful, re-enable and check that hiding the dictionary turns public browsing
   off, and unhiding leaves it off. Leave it in your preferred state afterwards.

Enabling a laptop copy does not enable its AWS counterpart. Existing password-reset
configuration is unchanged; no Google credentials are needed for this feature.

## 3. Check in after laptop acceptance

The patch stages its files. Check that the commit contains no database backups or secrets:

```bash
cd /home/github/c-lara-2
git diff --cached --check &&
git diff --cached --stat
git status --short
git commit -m "Add owner-controlled public dictionary browsing"
git push
git rev-parse HEAD
```

Retain the SHA for comparison with AWS.

## 4. AWS: prepare while the app is online

Finish running AI jobs first. Use the same shell throughout these blocks:

```bash
sudo -iu ssm-user
umask 022
cd /srv/C-LARA-2
git branch --show-current
git status --short
git fetch origin
git log --oneline HEAD..origin/main
/usr/lib/postgresql/18/bin/pg_dump --version
/usr/lib/postgresql/18/bin/pg_restore --version
df -h /srv/C-LARA-2 "$HOME"
```

Expect `main`, a clean working tree, your intended commit and PostgreSQL 18.x
clients. Stop for unexpected changes. Keep source files readable by the services;
the restrictive backup mask below runs only inside the backup subprocess.

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

This loads the protected environment through systemd without changing its permissions.

## 5. AWS: brief maintenance, backup and migration

Both applications will be unavailable while their services are stopped. These two
additive database fields do not change media; no new 22 GB media archive is needed
for this update. Existing regular media backups should continue separately.

```bash
mkdir -p -m 700 "$HOME/clara2-backups"
CLARA_PUBLIC_BACKUP="$(mktemp -d "$HOME/clara2-backups/public-$(date +%Y%m%d-%H%M%S)-XXXXXX")"
git rev-parse HEAD > "$CLARA_PUBLIC_BACKUP/deployed-commit.txt"
printf 'Backup directory: %s\n' "$CLARA_PUBLIC_BACKUP"
```

```bash
sudo systemctl stop gunicorn-clara2 djangoq-clara2 project-understanding-worker &&
sudo systemd-run --quiet --wait --pipe --collect \
  --property=User=ssm-user \
  --property=EnvironmentFile=/etc/clara2.env \
  /bin/bash -c '
    umask 077
    export PGPASSWORD="${POSTGRES_PASSWORD:-}"
    exec /usr/lib/postgresql/18/bin/pg_dump \
      --no-password --verbose \
      --host="${POSTGRES_HOST:?POSTGRES_HOST is missing}" \
      --port="${POSTGRES_PORT:-5432}" \
      --username="${POSTGRES_USER:-postgres}" \
      --dbname="${POSTGRES_DB:-clara2}" \
      --format=custom --file="$1"
  ' bash "$CLARA_PUBLIC_BACKUP/database.dump.partial" &&
/usr/lib/postgresql/18/bin/pg_restore --list "$CLARA_PUBLIC_BACKUP/database.dump.partial" >/dev/null &&
mv "$CLARA_PUBLIC_BACKUP/database.dump.partial" "$CLARA_PUBLIC_BACKUP/database.dump" &&
printf 'Database dump completed and archive index checked: %s\n' "$CLARA_PUBLIC_BACKUP"
```

The archive-index check is not a full restore rehearsal. If the backup fails before
the update, restart the unchanged services and stop here. Do not migrate without
a completed backup.

```bash
cd /srv/C-LARA-2
git merge --ff-only origin/main &&
clara_manage check &&
clara_manage migrate --plan
```

The migration plan should contain only `community_dictionary.0020_public_browsing`.
If it contains something unexpected, stop and inspect before proceeding.

```bash
clara_manage migrate community_dictionary 0020_public_browsing &&
clara_manage migrate --check &&
clara_manage check &&
sudo systemctl start gunicorn-clara2 djangoq-clara2 project-understanding-worker

sudo systemctl status --no-pager gunicorn-clara2 djangoq-clara2 project-understanding-worker
git rev-parse HEAD
```

If a command fails, do not skip it or restore the database blindly; retain the error
output. No package installation, collectstatic, nginx restart or daemon-reload is
needed for this particular patch.

## 6. AWS acceptance

Check normal login and member browsing first. Every dictionary is still private.
Only enable public browsing on a dictionary whose contributors agree to publication.
Use its Settings link in a private window and on a phone; try word/sentence links,
translations and audio. Check another private dictionary stays unavailable and
that disabling public browsing revokes the visitor link.

Public browsing means anyone, including signed-in nonmembers and former members.
It gives no account, editing or AI-generation privileges. Turning it off or
withdrawing content stops later requests but cannot recall copies already received.
If a problem is limited to the visitor feature, turn it off in Settings while
retaining normal member access.
