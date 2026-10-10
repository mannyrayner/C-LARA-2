# Install email password recovery

Prepared against main `9947c9667e2086b96faddf49bf2d86d74d94b68a`
(the batch-description update now reported working on laptop and AWS).
This adds `projects.0044_passwordresetlimit`; no package or static-file changes.
Keep the Google app password out of chat, Git, screenshots and command output.
Anonymous browsing is not included in this increment.

## 1. Laptop: back up and apply

Stop the laptop development server, then check the working tree is clean:

```bash
cd /home/github/c-lara-2
git status --short
git log -1 --oneline
```

If there are unexpected changes, stop rather than overwriting them. Save the patch
as `/home/github/clara2_email_password_reset.patch`.

Back up SQLite (the explicit `-c` avoids the Cygwin/Windows interactive-shell issue):

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
backup = destination / ('before-email-reset-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.sqlite3')
with sqlite3.connect(str(source)) as src, sqlite3.connect(str(backup)) as dst:
    src.backup(dst)
    assert dst.execute('PRAGMA quick_check').fetchall() == [('ok',)], 'Backup verification failed'
print('Database backup verified:', backup)
PY
```

Apply, check and test:

```bash
cd /home/github/c-lara-2
git apply --check ../clara2_email_password_reset.patch &&
git apply --index ../clara2_email_password_reset.patch &&
git diff --cached --check

cd platform_server
../.venv/Scripts/python.exe -E manage.py check &&
../.venv/Scripts/python.exe -E manage.py test projects.tests.test_email_reset projects.tests.test_admin_tools projects.tests.test_profile community_dictionary &&
../.venv/Scripts/python.exe -E manage.py migrate &&
../.venv/Scripts/python.exe -E manage.py showmigrations projects
```

Expected: tests end `OK`; migration `0044_passwordresetlimit` is marked `[X]`.
Failure-simulation tests deliberately log errors. Stop if the final result is not OK.

## 2. Laptop: test the workflow without Google credentials

This command enables recovery only for this server process. Email is printed in
the local terminal instead of being sent. No app password is needed on the laptop.

```bash
cd /home/github/c-lara-2/platform_server
CLARA_PASSWORD_RESET_ENABLED=1 \
CLARA_PUBLIC_BASE_URL=http://127.0.0.1:8000 \
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend \
DEFAULT_FROM_EMAIL=mannyrayner@c-lara.org \
../.venv/Scripts/python.exe -E manage.py runserver --insecure
```

Visit `http://127.0.0.1:8000/community-dictionaries/login/`.
Choose **Forgotten password?**, enter an email belonging to an existing laptop
account, and copy the printed reset link into the browser. Choose a new password,
then log in. This changes only that laptop account's password. Profile displays
its registered email. Keep the terminal output private because it contains the
working link. An unknown email gives the same check-your-email page but no link.

The link works once and expires after an hour. There are three requests per
address per 15 minutes. Existing admin password reset remains available.

When finished, Ctrl+C. Your normal `runserver --insecure` command has email recovery
disabled unless you separately exported the feature's environment variables.

## 3. Check in after laptop acceptance

The patch already stages its files. Review before committing:

```bash
cd /home/github/c-lara-2
git diff --cached --check &&
git diff --cached --stat
git status --short
git commit -m "Add email password recovery for C-LARA and Community Dictionaries"
git push
git rev-parse HEAD
```

Retain the resulting SHA for comparison with AWS. There should be no credential
files or database backups in the commit.

## 4. AWS preparation while the app is online

Finish any running AI jobs first. Use the same shell for the following blocks.

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

Expect branch `main`, a clean working tree, your newly pushed commit, and version
18.x PostgreSQL clients. Stop for unexpected commits or local changes.

Define the existing service-identity helper. It does not require ubuntu to read
`/etc/clara2.env` and does not run Django as root:

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

## 5. Brief maintenance: database backup and migration

Both apps will be unavailable during this block. No media archive is needed for
this new counter table; existing media is not changed.

```bash
mkdir -p -m 700 "$HOME/clara2-backups"
CLARA_EMAIL_BACKUP="$(mktemp -d "$HOME/clara2-backups/email-$(date +%Y%m%d-%H%M%S)-XXXXXX")"
git rev-parse HEAD > "$CLARA_EMAIL_BACKUP/deployed-commit.txt"
printf 'Backup directory: %s\n' "$CLARA_EMAIL_BACKUP"
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
  ' bash "$CLARA_EMAIL_BACKUP/database.dump.partial" &&
/usr/lib/postgresql/18/bin/pg_restore --list "$CLARA_EMAIL_BACKUP/database.dump.partial" >/dev/null &&
mv "$CLARA_EMAIL_BACKUP/database.dump.partial" "$CLARA_EMAIL_BACKUP/database.dump" &&
printf 'Database dump completed and archive index checked: %s\n' "$CLARA_EMAIL_BACKUP"
```

The archive-index check is not a full restore rehearsal. If backup fails before
any update, restart the three unchanged services and report the error. Do not
continue to migration with a failed backup.

```bash
cd /srv/C-LARA-2
git merge --ff-only origin/main &&
git log -1 --oneline &&
clara_manage check &&
clara_manage migrate --plan
```

Expect only `projects.0044_passwordresetlimit`. For anything else, stop and show
the plan. Then:

```bash
clara_manage migrate projects 0044_passwordresetlimit &&
clara_manage migrate --check &&
clara_manage check &&
sudo systemctl start gunicorn-clara2 djangoq-clara2 project-understanding-worker
sudo systemctl status --no-pager gunicorn-clara2 djangoq-clara2 project-understanding-worker
```

The site is back online with email recovery still disabled by default. Check an
ordinary dictionary page before continuing. No pip install, collectstatic,
nginx restart or systemd daemon-reload is needed.

## 6. Configure Google Workspace privately

First preserve the existing protected environment file:

```bash
sudo install -m 600 -o root -g root /etc/clara2.env "$CLARA_EMAIL_BACKUP/clara2.env"
sudoedit /etc/clara2.env
```

Add/update these settings once each. Replace the placeholder locally with your
Google app password, removing the display spaces between its groups. Do not use
your ordinary Google login password. Keep every existing unrelated setting,
especially `DJANGO_SECRET_KEY`, unchanged.

```text
CLARA_PASSWORD_RESET_ENABLED=1
CLARA_PUBLIC_BASE_URL=https://c-lara-2.c-lara.org
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=true
EMAIL_USE_SSL=false
EMAIL_HOST_USER=mannyrayner@c-lara.org
DEFAULT_FROM_EMAIL=mannyrayner@c-lara.org
EMAIL_HOST_PASSWORD='PASTE_THE_APP_PASSWORD_HERE'
```

Do not loosen the environment file's permissions. Nothing from this block belongs
in Git. The currently running services retain their old environment until restart.

## 7. Check configuration, then send one test email

```bash
clara_manage account_email_check
```

This sends nothing. If it reports the default development `DJANGO_SECRET_KEY`,
stop and ask rather than casually replacing a production key.

Then explicitly send one harmless message to your own address:

```bash
clara_manage account_email_check --send-to mannyrayner@c-lara.org
```

Check the inbox and spam folder. Success at the command line means the mail
backend accepted the message, not proof of delivery. If it fails, retain the
exception class but do not post credentials or a complete environment dump.
The existing site stays online with its old environment while we investigate.

## 8. Activate and try a real reset

After the diagnostic email arrives, make sure AI jobs have finished again, then:

```bash
sudo systemctl restart gunicorn-clara2 djangoq-clara2 project-understanding-worker
sudo systemctl status --no-pager gunicorn-clara2 djangoq-clara2 project-understanding-worker
```

Use a private browser window to open the Community Dictionaries login page. Choose
**Forgotten password?** and use your own account's registered address. Follow the
email link, choose a new password and log in. Verify you return to Community
Dictionaries. This really changes that account's password and ends its other
sessions. Once that succeeds, Cathy can try her account. An account lacking a usable
email address still needs the existing admin recovery route.

If needed, disabling `CLARA_PASSWORD_RESET_ENABLED` and restarting the services
turns off both issuing and redeeming reset links. Keep migration 0044 applied.
Do not restore the whole database to undo a mail-configuration problem.

For service errors, keep DEBUG=False:

```bash
sudo journalctl -u gunicorn-clara2 -u djangoq-clara2 \
  --since "10 minutes ago" -n 120 --no-pager
```

Before sharing output, remove any actual reset-link URLs from access-log lines.
