# Install dictionary discovery, profiles and About

Prepared against main `4d90cf8efaa1ef31f0c79163be85dea619f76d87`
(the public-browsing release). This adds only migration
`community_dictionary.0021_discovery_profiles`: two default-off discovery fields
and tables for private membership requests and opt-in contributor profiles.

**Existing public URLs keep working. Dictionaries will no longer appear in the
directory until their owners enable Settings → Discoverability.** This does not
alter public-content access or existing memberships.
There are no dependency, static-file, email or environment-setting changes.

## 1. Laptop: back up and apply

Stop the development server. Save the patch as
`/home/github/community_dictionary_discovery_profiles.patch`, then check:

```bash
cd /home/github/c-lara-2
git status --short
git log -1 --oneline
```

Expect a clean working tree and the public-browsing commit. Stop for unexpected
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
backup = destination / ('before-discovery-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.sqlite3')
with sqlite3.connect(str(source)) as src, sqlite3.connect(str(backup)) as dst:
    src.backup(dst)
    assert dst.execute('PRAGMA quick_check').fetchall() == [('ok',)], 'Backup verification failed'
print('Database backup verified:', backup)
PY
```

The explicit `-c` and `-E` retain the working Cygwin/Windows setup. Then:

```bash
cd /home/github/c-lara-2
git apply --check ../community_dictionary_discovery_profiles.patch &&
git apply --index ../community_dictionary_discovery_profiles.patch &&
git diff --cached --check

cd platform_server
../.venv/Scripts/python.exe -E manage.py check &&
../.venv/Scripts/python.exe -E manage.py test community_dictionary projects.tests.test_email_reset projects.tests.test_admin_tools projects.tests.test_profile &&
../.venv/Scripts/python.exe -E manage.py migrate &&
../.venv/Scripts/python.exe -E manage.py showmigrations community_dictionary
```

Expected: **564 tests, OK**, and `[X] 0021_discovery_profiles`. Failure-simulation tests
deliberately log exceptions. Stop if the final result is not OK.

## 2. Laptop: try with two accounts

```bash
cd /home/github/c-lara-2/platform_server
../.venv/Scripts/python.exe -E manage.py runserver --insecure
```

1. As owner, choose a test dictionary. Leave Public browsing off, then enable
   **Settings → Discoverability → Make dictionary discoverable**.
2. Open `http://127.0.0.1:8000/community-dictionaries/browse/` in a private window.
   The dictionary should show its name, languages and counts, without pictures,
   words or recordings. Open its membership details.
3. Log in as a second account which is not already a member. Send **Request
   membership** with a short message. It should become pending, without email.
4. Return to the owner window: **My dictionaries → Pending membership requests**.
   Approve. The second account should now see the dictionary in My dictionaries
   and be able to contribute, with no editor/owner powers.
5. In **Profile**, choose a public name and select **List me as a contributor**.
   Visit **About** in the private window. The name should link to a contributor
   page showing the discoverable dictionary, without account email or private
   dictionaries. Uncheck the box and save; reload the public pages to verify removal.
6. Turn off discoverability. Its directory card and request page disappear, while
   existing members retain access. An existing public browsing link should still
   work if Public browsing is on. Hiding a dictionary turns both settings off.
7. Check **About** and **Profile** on your phone when convenient. Optionally change
   the second account's password through Profile and confirm it stays logged in.

No Google credentials or AI calls are needed. Laptop settings do not change AWS.
The new Profile shares the existing account, password and credit balance.

## 3. Check in after laptop acceptance

The patch stages its files. Check that the commit contains no database backups or secrets:

```bash
cd /home/github/c-lara-2
git diff --cached --check &&
git diff --cached --stat
git status --short
git commit -m "Add dictionary discovery, membership requests, profiles and About"
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

Both applications will be unavailable while their services are stopped. These additive tables and fields do not change media; no new 22 GB media archive is needed
for this update. Existing regular media backups should continue separately.

```bash
mkdir -p -m 700 "$HOME/clara2-backups"
CLARA_DISCOVERY_BACKUP="$(mktemp -d "$HOME/clara2-backups/discovery-$(date +%Y%m%d-%H%M%S)-XXXXXX")"
git rev-parse HEAD > "$CLARA_DISCOVERY_BACKUP/deployed-commit.txt"
printf 'Backup directory: %s\n' "$CLARA_DISCOVERY_BACKUP"
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
  ' bash "$CLARA_DISCOVERY_BACKUP/database.dump.partial" &&
/usr/lib/postgresql/18/bin/pg_restore --list "$CLARA_DISCOVERY_BACKUP/database.dump.partial" >/dev/null &&
mv "$CLARA_DISCOVERY_BACKUP/database.dump.partial" "$CLARA_DISCOVERY_BACKUP/database.dump" &&
printf 'Database dump completed and archive index checked: %s\n' "$CLARA_DISCOVERY_BACKUP"
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

The migration plan should contain only `community_dictionary.0021_discovery_profiles`.
If it contains something unexpected, stop and inspect before proceeding.

```bash
clara_manage migrate community_dictionary 0021_discovery_profiles &&
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

First verify normal login, member browsing, Profile and About. Repeat the short
laptop sequence using a suitable test dictionary and two accounts. No dictionary
or contributor profile is automatically advertised. Public links already shared
with visitors keep working; explicitly enable discoverability for dictionaries
that should appear in Find dictionaries.

The discoverability toggle makes name/languages/counts public, not the dictionary
contents. Enabling Public browsing is a separate decision requiring contributor
permission. Unlisting stops new requests but retains pending ones for the owner to
resolve. Request messages and account details are private. No membership email is
sent; owners check the pending list.

If a problem is confined to a listing, switch discoverability off in Settings;
normal member access and any independently enabled public browsing remain intact.
There is no need to reverse the additive migration or restore the database for
that action. Keep the database backup and pre-update commit until acceptance.
