# Install public practice and owner workflow suggestions

Prepared against main `7cb9a82fe3cf2e7aa54d383ffd80056fb452dc34`
(the discovery, profiles and About release). Migration
`community_dictionary.0022_workflow_suggestions` adds a default-on guidance
preference and its revision counter. No content or permissions are migrated.

Public practice becomes available only in dictionaries that already permit
public browsing. Owner suggestions never enable AI or start paid work by
visiting a page. No dependency, email or environment changes are required.
**There is a static JavaScript change: run collectstatic on AWS as shown below.**

## 1. Laptop: back up and apply

Stop the development server. Save the patch as
`/home/github/community_dictionary_practice_guidance.patch`, then check:

```bash
cd /home/github/c-lara-2
git status --short
git log -1 --oneline
```

Expect a clean working tree and the discovery/profiles/About commit. Stop for unexpected
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
backup = destination / ('before-practice-guidance-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.sqlite3')
with sqlite3.connect(str(source)) as src, sqlite3.connect(str(backup)) as dst:
    src.backup(dst)
    assert dst.execute('PRAGMA quick_check').fetchall() == [('ok',)], 'Backup verification failed'
print('Database backup verified:', backup)
PY
```

The explicit `-c` and `-E` retain the working Cygwin/Windows setup. Then:

```bash
cd /home/github/c-lara-2
git apply --check ../community_dictionary_practice_guidance.patch &&
git apply --index ../community_dictionary_practice_guidance.patch &&
git diff --cached --check

cd platform_server
../.venv/Scripts/python.exe -E manage.py check &&
../.venv/Scripts/python.exe -E manage.py test community_dictionary projects.tests.test_email_reset projects.tests.test_admin_tools projects.tests.test_profile &&
../.venv/Scripts/python.exe -E manage.py migrate &&
../.venv/Scripts/python.exe -E manage.py showmigrations community_dictionary
```

Expected: **591 tests, OK**, and `[X] 0022_workflow_suggestions`. Failure-simulation tests
deliberately log exceptions. Stop if the final result is not OK.

## 2. Laptop: try the new workflow

```bash
cd /home/github/c-lara-2/platform_server
../.venv/Scripts/python.exe -E manage.py runserver --insecure
```

1. As owner, open an AI-enabled test dictionary with pictures lacking sentences.
   **My dictionaries** should show “N pictures ready for sentences”. Follow it.
   Ordinary contributors should not see this prompt.
2. Read the estimate and payer information, then choose **Approve and create
   sentences** if you want to incur that small test cost. Review/accept the results
   using the existing screen. Refreshing or going back does not approve new work.
3. Return to the dictionary: it should now offer word suggestions from accepted
   sentences. Approve the displayed estimate, then review/accept those suggestions.
   Confirm sentence links, shared word pages and audio as usual.
4. In **Settings → Workflow suggestions**, turn them off. The card/panel prompts
   disappear; the existing batch controls still work. Turn them on again.
5. If a pending membership request exists, the owner's card should link to that
   dictionary's pending requests before offering more generation work.
6. Use a test dictionary whose accepted content you have permission to make public.
   Open its existing visitor link in a private window and choose **Practise**.
   Try multiple-choice/reveal flashcards and the two puzzles. No login or AI cost
   is involved. Small categories may need more distinct answers for multiple choice.
7. Turn public browsing off and reload the visitor practice page: it should be
   unavailable. Enabling discoverability alone must not make practice available.

Public-content settings require the same permission as before. Do not enable them
on private community material merely for this test. Laptop changes do not affect AWS.

## 3. Check in after laptop acceptance

The patch stages its files. Check that the commit contains no database backups or secrets:

```bash
cd /home/github/c-lara-2
git diff --cached --check &&
git diff --cached --stat
git status --short
git commit -m "Add public practice and owner workflow guidance"
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

Both applications will be unavailable while their services are stopped. These additive fields do not change media; no new 22 GB media archive is needed
for this update. Existing regular media backups should continue separately.

```bash
mkdir -p -m 700 "$HOME/clara2-backups"
CLARA_GUIDANCE_BACKUP="$(mktemp -d "$HOME/clara2-backups/practice-guidance-$(date +%Y%m%d-%H%M%S)-XXXXXX")"
git rev-parse HEAD > "$CLARA_GUIDANCE_BACKUP/deployed-commit.txt"
printf 'Backup directory: %s\n' "$CLARA_GUIDANCE_BACKUP"
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
  ' bash "$CLARA_GUIDANCE_BACKUP/database.dump.partial" &&
/usr/lib/postgresql/18/bin/pg_restore --list "$CLARA_GUIDANCE_BACKUP/database.dump.partial" >/dev/null &&
mv "$CLARA_GUIDANCE_BACKUP/database.dump.partial" "$CLARA_GUIDANCE_BACKUP/database.dump" &&
printf 'Database dump completed and archive index checked: %s\n' "$CLARA_GUIDANCE_BACKUP"
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

The migration plan should contain only `community_dictionary.0022_workflow_suggestions`.
If it contains something unexpected, stop and inspect before proceeding.

```bash
clara_manage migrate community_dictionary 0022_workflow_suggestions &&
clara_manage migrate --check &&
clara_manage collectstatic --noinput &&
clara_manage check &&
sudo systemctl start gunicorn-clara2 djangoq-clara2 project-understanding-worker

sudo systemctl status --no-pager gunicorn-clara2 djangoq-clara2 project-understanding-worker
git rev-parse HEAD
```

If a command fails, do not skip it or restore the database blindly; retain the error
output. No package installation, nginx restart or daemon-reload is needed for this patch.
Do not omit collectstatic: it installs the updated practice JavaScript.

## 6. AWS acceptance

Verify normal login, member browsing, Profile and About, then repeat the short
laptop sequence with a suitable test dictionary. Check one owner approval and
both review stages. Try public Practice in a private phone browser, then check
that switching public browsing off blocks the game and media on fresh requests.

The owner card reports one primary action; review and membership requests can take
priority over generating more sentences. For another voice or a restricted image
selection, use the existing Settings controls. An insufficient app balance should
be explained without starting the job. Public browsing and normal manual
contribution do not consume AI credits.

If prompts are unwanted, turn Workflow suggestions off. If visitor access is
unwanted, turn Public browsing off. Neither requires a migration reversal. Keep
the database backup and pre-update commit until acceptance. If rollback is needed,
stop services and inspect the failure first; do not restore an old database over
new contributions. This additive migration can remain during a code rollback to
the recorded baseline, with its matching static files collected again.
