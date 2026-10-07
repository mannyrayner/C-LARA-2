# Check in and deploy picture descriptions

7 October 2026. Manny reports that the new functionality works on the small Swedish
laptop dictionary and requests check-in and AWS deployment. Further MWE work is
**deferred until after the larger Community Dictionaries trial**. This runbook
releases the tested picture-description and vocabulary/copy patches together.

AWS is expected to have migrations through **0014**. This release adds
**0015_picture_descriptions**; the vocabulary follow-up has no further migration.
The new Picture descriptions setting initially remains off on existing dictionaries.
No new Python packages, service units, nginx settings or API credentials are required.

Run each block in order and stop if any command fails. Keep the same AWS shell
through the backup and deployment steps.

## 1. Check in on the laptop

Download `community_dictionary_picture_release_notes.patch` to `/home/github/`.
It records this laptop acceptance, the MWE deferral and this runbook; it changes
no runtime code. Apply it on top of the two patches you have just tested:

```bash
cd /home/github/c-lara-2
git apply --check ../community_dictionary_picture_release_notes.patch &&
git apply --index ../community_dictionary_picture_release_notes.patch &&
git diff --cached --check
```

Then inspect:

```bash
git branch --show-current
git status --short
git diff --name-only
git diff --cached --stat
```

Expect branch **main**. Patches applied with `--index` are already staged; no
`git add .` is needed. The staged changes should be the Community Dictionary code,
migration 0015, tests and accompanying documentation/global-state records.
`git diff --name-only` should be empty if there are no unrelated unstaged changes.
Keep database/media files, credentials and backups out of the commit. Investigate
unexpected changes before proceeding.

The implementation has 324 passing tests and your laptop acceptance. No repeat
application test run is needed solely for these release notes.

```bash
git commit -m "Add picture descriptions, editable vocabulary and image-only dictionary copies" &&
git push origin main &&
git rev-parse HEAD &&
git status --short
```

Keep the printed commit ID for comparison on AWS. The final status should be
empty. If you already committed the implementation, this commit contains only
the remaining release notes; pushing main still includes the earlier commits.

## 2. Prepare AWS while the site is still running

Choose a quiet interval and allow saves/AI jobs to finish. Both Community
Dictionaries and ordinary C-LARA-2 share the services and will be unavailable
during the backup/install interval.

```bash
sudo -iu ssm-user
cd /srv/C-LARA-2
umask 022
git branch --show-current
git status --short
. .venv/bin/activate
cd platform_server
set -a && . /etc/clara2.env && set +a
python manage.py shell -v 0 -c "from django.conf import settings; assert settings.DATABASES['default']['ENGINE'] == 'django.db.backends.postgresql', 'Stop: expected AWS PostgreSQL'; print('PostgreSQL configured; DEBUG =', settings.DEBUG)" &&
/usr/lib/postgresql/18/bin/pg_dump --version &&
/usr/lib/postgresql/18/bin/pg_restore --version
df -h /srv/C-LARA-2 "$HOME"
sudo du -sh /srv/C-LARA-2/platform_server/private_uploads/community_dictionary
```

Expect clean **main**, `DEBUG = False`, PostgreSQL 18 client tools and enough disk
space for a database dump plus an uncompressed private-media copy. Keep the
contents of `/etc/clara2.env` private. Do not use the unversioned PostgreSQL 16
`pg_dump` that failed during the earlier deployment.

## 3. Stop writers and back up

Take a fresh database/private-media backup. Migration 0015 adds tables/fields; it
does not move/delete existing media. We do not need another 22 GB public-media
archive for this release. Normal whole-site backups remain a separate requirement.

```bash
export CLARA_CAPTURE_BACKUP="$HOME/clara2-backups/before-picture-descriptions-$(date +%Y%m%d-%H%M%S)"
(
  set -e
  umask 077
  mkdir -p "$HOME/clara2-backups"
  mkdir -m 700 "$CLARA_CAPTURE_BACKUP"
  git rev-parse HEAD > "$CLARA_CAPTURE_BACKUP/deployed-commit.txt"
  sudo systemctl stop gunicorn-clara2 djangoq-clara2 project-understanding-worker
  echo "Backing up PostgreSQL ..."
  PGPASSWORD="${POSTGRES_PASSWORD:-}" /usr/lib/postgresql/18/bin/pg_dump \
    --no-password --format=custom \
    --host="${POSTGRES_HOST:-}" --port="${POSTGRES_PORT:-5432}" \
    --username="${POSTGRES_USER:-postgres}" --dbname="${POSTGRES_DB:-clara2}" \
    --file="$CLARA_CAPTURE_BACKUP/database.dump"
  test -s "$CLARA_CAPTURE_BACKUP/database.dump"
  /usr/lib/postgresql/18/bin/pg_restore --list \
    "$CLARA_CAPTURE_BACKUP/database.dump" > "$CLARA_CAPTURE_BACKUP/database-contents.txt"
  python manage.py shell -v 0 -c "exec(__import__('sys').stdin.read())" <<'PY'
import os
import subprocess
from pathlib import Path
from django.conf import settings

backup = Path(os.environ['CLARA_CAPTURE_BACKUP'])
root = Path(settings.COMMUNITY_DICTIONARY_MEDIA_ROOT).resolve()
if not root.is_dir():
    raise RuntimeError(f'Expected private-media directory is missing: {root}')
archive = backup / 'community-private-media.tar'
print(f'Archiving private media from {root} ...', flush=True)
subprocess.run(['sudo', 'tar', '--create', '--totals', '--checkpoint=10000',
                '--file', str(archive), '--directory', str(root), '.'], check=True)
subprocess.run(['sudo', 'chmod', '600', str(archive)], check=True)
print('Comparing private-media archive with its source ...', flush=True)
subprocess.run(['sudo', 'tar', '--compare', '--checkpoint=10000',
                '--file', str(archive), '--directory', str(root)], check=True)
(backup / 'community-private-media-path.txt').write_text(str(root) + '\n')
print(f'Backup checks passed: {backup}', flush=True)
PY
)
```

Wait for **Backup checks passed** before continuing. Archive listing and media
comparison are basic backup checks, not a database restore rehearsal. The restrictive
`umask 077` is confined to the subshell so code remains readable by the service user.

If this backup fails, **do not pull or migrate**. The deployed code/database are
still unchanged; restart the existing site while we resolve it:

```bash
sudo systemctl start gunicorn-clara2 djangoq-clara2 project-understanding-worker
sudo systemctl status --no-pager gunicorn-clara2 djangoq-clara2 project-understanding-worker
```

That is a recovery block only. After a successful backup, leave services stopped
and continue below.

## 4. Pull, migrate and collect static files

```bash
cd /srv/C-LARA-2
umask 022
git pull --ff-only origin main &&
git rev-parse HEAD
```

The printed SHA must match the laptop SHA. Stop on a mismatch or pull error.
No dependency installation is needed for these patches.

```bash
cd /srv/C-LARA-2/platform_server
python manage.py check &&
python manage.py showmigrations community_dictionary &&
python manage.py migrate --plan
```

Expected: 0001–0014 applied and only **0015_picture_descriptions** pending for this
release. If it is already `[X]`, leave it applied. If older or unrelated migrations
are unexpectedly pending, inspect that before proceeding. Do not run the old
0008/0009 withdrawal-reset procedure.

```bash
python manage.py migrate &&
python manage.py collectstatic --noinput &&
python manage.py check &&
python manage.py showmigrations community_dictionary &&
sudo systemctl restart gunicorn-clara2 djangoq-clara2 project-understanding-worker
```

Expect `[X] 0015_picture_descriptions`. Keep `DEBUG=False`. `collectstatic` is needed
for the updated forms/JavaScript/CSS. Restart reloads all workers even if a service
was inadvertently left running. No systemd daemon-reload or nginx restart is needed
because their configurations have not changed.

## 5. Verify service health and browser behaviour

```bash
sudo systemctl status --no-pager gunicorn-clara2 djangoq-clara2 project-understanding-worker
```

All three should be **active (running)** and remain so after a short interval.
If a service fails, inspect server-side logs instead of enabling DEBUG:

```bash
sudo journalctl -u gunicorn-clara2 -u djangoq-clara2 \
  -u project-understanding-worker -n 80 --no-pager
```

Do not automatically reverse migrations or restore the database after an error.
Keep the backup and share the relevant exception with secrets/private content removed.

At https://c-lara-2.c-lara.org/community-dictionaries/:

1. Check login, an existing entry image and an existing human recording.
2. As owner, use the Swedish dictionary's **Settings → Create an image-only copy**.
   Give it an unmistakable test name. The original should remain unchanged.
3. In the **new copy's Settings**, enable **Picture descriptions (OpenAI)** and keep
   saved spoken audio enabled. It will otherwise inherit the original's off setting.
4. Open an image and choose **Describe this picture**. Test one typed description,
   edit its vocabulary, save, and check sentence/word links and audio. Then test a
   spoken description and spoken confirmation. Allow background audio to finish;
   Django-Q should be running.
5. Continue with a handful of varied images and try the same workflow on the phone.
   Note problems with capture, confirmation, saving, links, audio or navigation.
   Record MWE mistakes as examples, but defer redesigning MWE analysis until this
   functionality trial is complete.

The default cap is 10 picture-description attempts per user and per dictionary
in a rolling 24 hours. Start with a small varied batch. Each preparation requests
paid AI processing after the displayed consent; image-only copying itself does not.
The `expire_photo_studies` maintenance command also clears expired private
picture-description previews. It should run daily; its actual AWS schedule has
not been verified here.

Record the deployed commit, trial size and any concrete failures. This runbook does
not itself establish AWS deployment or phone acceptance; those await Manny's report.
