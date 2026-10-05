# Check in and deploy language porting after laptop acceptance

Manny reports that the integrated small-dictionary laptop test works, including
successful French **chat** and **lit** generation. This is the next deployment
step. Manny subsequently reports a 61-entry Swedish/English to French/English AWS
conversion and review; see the [trial record](../../experiments/community_dictionary/porting-aws-2026-10-05.md). Human recording remains central;
generated pronunciation still needs listening review.

## 1. Check in on the laptop

Save `community_dictionary_porting_release_notes.patch` in `/home/github/`.
It only updates documentation, including the corrected local startup command.
Apply it after the installed TTS-guidance patch:

```bash
cd /home/github/c-lara-2
git apply --check ../community_dictionary_porting_release_notes.patch &&
git apply --index ../community_dictionary_porting_release_notes.patch &&
git diff --cached --check
git branch --show-current
git status --short
git diff --cached --stat
```

Expect branch `main`. Earlier patches applied with `--index` are already staged.
Check that the staged changes are the intended porting/TTS implementation and
documentation. Do not add databases, uploaded media, credentials or backups. If
there are unexpected or unstaged changes, inspect them before committing.

```bash
git commit -m "Add community dictionary language porting and pronunciation guidance" &&
git push origin main &&
git rev-parse HEAD
```

Keep that commit ID for comparison on AWS. No repeat application tests are needed
just for this documentation follow-up. The implementation has 275 passing app
tests and the reported laptop acceptance. Local startup remains:

```bash
cd /home/github/c-lara-2/platform_server
../.venv/Scripts/python.exe -E manage.py runserver --insecure
```

`--insecure` serves development static files with `DEBUG=False`. It is only for
the laptop; AWS uses nginx for static files.

## 2. Prepare AWS

Choose a quiet interval, let users finish saves and AI jobs, and warn them that
both Community Dictionaries and ordinary C-LARA-2 will briefly be unavailable.
Run these blocks in order; stop at any error.

```bash
sudo -iu ssm-user
cd /srv/C-LARA-2
umask 022
git branch --show-current
git status --short
. .venv/bin/activate
cd platform_server
set -a && . /etc/clara2.env && set +a
python manage.py shell -c "from django.conf import settings; assert settings.DATABASES['default']['ENGINE'] == 'django.db.backends.postgresql', 'Stop: expected AWS PostgreSQL'; print('PostgreSQL configured')" &&
/usr/lib/postgresql/18/bin/pg_dump --version &&
/usr/lib/postgresql/18/bin/pg_restore --version
df -h /srv/C-LARA-2 "$HOME"
sudo du -sh /srv/C-LARA-2/platform_server/private_uploads/community_dictionary
```

Expect clean `main`, working PostgreSQL 18 client tools, and enough space for a
database dump and a private-media copy. Use the versioned tools: the unversioned
`pg_dump` previously selected version 16. Keep environment-file contents private.
The mask `022` keeps checked-out code/static files readable by the service account;
the more restrictive backup mask below is confined to its subshell.

## 3. Back up before pulling or migrating

Migrations 0011–0014 add tables/fields; they do not move or delete existing media.
For this release, take a fresh full database dump and Community Dictionary private
media archive. There is no need to repeat the 22 GB public-media archive solely for
these migrations. This scoped backup does not replace normal whole-site backups.

```bash
export CLARA_PORTING_BACKUP="$HOME/clara2-backups/before-porting-$(date +%Y%m%d-%H%M%S)"
(
  set -e
  umask 077
  mkdir -p "$HOME/clara2-backups"
  mkdir -m 700 "$CLARA_PORTING_BACKUP"
  git rev-parse HEAD > "$CLARA_PORTING_BACKUP/deployed-commit.txt"
  sudo systemctl stop gunicorn-clara2 djangoq-clara2 project-understanding-worker
  PGPASSWORD="${POSTGRES_PASSWORD:-}" /usr/lib/postgresql/18/bin/pg_dump \
    --no-password --format=custom \
    --host="${POSTGRES_HOST:-}" --port="${POSTGRES_PORT:-5432}" \
    --username="${POSTGRES_USER:-postgres}" --dbname="${POSTGRES_DB:-clara2}" \
    --file="$CLARA_PORTING_BACKUP/database.dump"
  test -s "$CLARA_PORTING_BACKUP/database.dump"
  /usr/lib/postgresql/18/bin/pg_restore --list \
    "$CLARA_PORTING_BACKUP/database.dump" > "$CLARA_PORTING_BACKUP/database-contents.txt"
  python manage.py shell -v 0 -c "exec(__import__('sys').stdin.read())" <<'PY'
import os
import subprocess
from pathlib import Path
from django.conf import settings

backup = Path(os.environ['CLARA_PORTING_BACKUP'])
root = Path(settings.COMMUNITY_DICTIONARY_MEDIA_ROOT).resolve()
if not root.is_dir():
    raise RuntimeError(f'Expected private-media directory is missing: {root}')
archive = backup / 'community-private-media.tar'
print(f'Archiving private media from {root} ...', flush=True)
subprocess.run(['sudo', 'tar', '--create', '--file', str(archive),
                '--directory', str(root), '.'], check=True)
subprocess.run(['sudo', 'chmod', '600', str(archive)], check=True)
subprocess.run(['sudo', 'tar', '--compare', '--file', str(archive),
                '--directory', str(root)], check=True)
(backup / 'community-private-media-path.txt').write_text(str(root) + '\n')
print(f'Database archive listed; private media comparison passed. Backup: {backup}', flush=True)
PY
)
```

Proceed only after that final success message. Listing a database archive is a
basic check, not a restore rehearsal. If backup fails, do not pull or migrate; the
code/database are still unchanged, so bring the existing services back with
`sudo systemctl start gunicorn-clara2 djangoq-clara2 project-understanding-worker`
while resolving the backup problem. A failed backup must not be treated as complete.

## 4. Install and start

Keep the services stopped during installation. In the same shell:

```bash
cd /srv/C-LARA-2
umask 022
git pull --ff-only &&
git rev-parse HEAD &&
python -m pip install -r requirements.txt
```

Check that the printed commit matches the laptop commit and installation succeeded.
Then inspect the migration plan:

```bash
cd /srv/C-LARA-2/platform_server
python manage.py check &&
python manage.py showmigrations community_dictionary &&
python manage.py migrate --plan
```

The first porting deployment applied 0011–0013 over 0010 and has now been reported
working on AWS. For the subsequent review-UX patch, only 0014 should be pending.
If upgrading directly from 0010, apply all four in the normal forward order. Leave
already applied migrations applied; investigate unexpected migrations before continuing.
Do not repeat the old command targeting migration 0008 or rerun the experimental
withdrawal-restoration procedure.

```bash
python manage.py migrate &&
python manage.py collectstatic --noinput &&
python manage.py check &&
sudo systemctl restart gunicorn-clara2 djangoq-clara2 project-understanding-worker
sudo systemctl status --no-pager gunicorn-clara2 djangoq-clara2 project-understanding-worker
```

Use **restart** even if the services may already be running: **start** alone does
not reload old workers. A missed stop caused entry-page errors in the first porting
deployment; Manny reports that stopping/restarting restored access. Keep
`DEBUG=False`; diagnose errors through server-side logs.

All three services should stay active/running. No nginx restart or systemd
daemon-reload is needed because this release changes neither configuration. If a
service fails, inspect its journal before changing anything further:

```bash
sudo journalctl -u gunicorn-clara2 -u djangoq-clara2 \
  -u project-understanding-worker -n 80 --no-pager
```

Share relevant errors with secrets/private content removed. Do not automatically
restore the database or reverse migrations after an installation error.

## 5. Larger-dictionary trial (French now reported)

First check login, images and an existing human recording. Then open the source
Swedish dictionary's **Settings → Create a version in another language** and make
a **French/English** version. Review the estimate and available funds before
approving. Use a fresh estimate; estimates from the older speech method require
renewed approval. Let this job finish before trying Italian.

Review/play results, especially flagged English homographs and category
translations, then save accepted entries. Confirm that the Swedish original is
unchanged. Human corrections remain protected on subsequent approved updates.
If an entry fails, inspect its result before submitting another paid run.

Useful feedback is: entries attempted/completed/failed, estimated and recorded
cost, any mispronounced words with language/voice, and whether review/save feels
manageable at this size. Avoid sharing private dictionary exports just to report
an error. Successful French acceptance can be followed by Italian/English and a
phone playback check. The subsequent French AWS trial is now recorded; Italian
and new phone results remain unreported. The later review-UX increment has additive
migration 0014; follow its [installation notes](community-port-review.md).
