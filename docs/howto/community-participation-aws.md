# Deploy dictionary-wide participation after laptop acceptance

2 October 2026. Manny reports that the new version appears fully working and much
better than the previous model. He considers the conceptual structure essentially
ready, subject to possible cosmetic feedback from Sophie. The next step is a
controlled AWS trial with the larger dictionary. This is human-reported laptop
acceptance, not a claim that every checklist item or physical device was tested.
Manny also specifically reports that laptop ownership handover appeared to work
correctly.

The accompanying acceptance patch changes documentation only. Apply it after the
installed `community_dictionary_participation.patch`. The application still has
156 passing controlled tests; no additional app change or migration is introduced.

## 1. Check in on the laptop

Save `community_dictionary_participation_acceptance.patch` above the checkout:

```bash
cd /home/github/c-lara-2
git apply --check ../community_dictionary_participation_acceptance.patch &&
git apply --index ../community_dictionary_participation_acceptance.patch
git branch --show-current
git status --short
git diff --cached --check && git diff --cached --stat
```

The intended branch is `main`. If it is another branch, or there are unexpected
files, inspect before committing. The earlier patch applications used `--index`,
so the implementation and documentation should already be staged. Do not add the
database, backups or uploaded media. When the staged changes are as expected:

```bash
git commit -m "Simplify community dictionary withdrawal and restoration" &&
git push origin main &&
git rev-parse HEAD
```

Keep that commit ID to compare with the server after pulling.

## 2. Prepare AWS and pause writes

Choose a quiet interval: both Community Dictionaries and ordinary C-LARA-2 will
briefly be unavailable. Let users finish their current saves and background jobs.

```bash
sudo -iu ssm-user
cd /srv/C-LARA-2
git branch --show-current
git status --short
. .venv/bin/activate
cd platform_server
set -a && . /etc/clara2.env && set +a
python manage.py shell -c "from django.conf import settings; assert settings.DATABASES['default']['ENGINE'] == 'django.db.backends.postgresql', 'This backup sequence expects the AWS PostgreSQL database'; print('PostgreSQL configured')" &&
command -v pg_dump && command -v pg_restore
```

The checkout should be clean and on `main`. If the database assertion fails, a
backup tool is missing, or the status is unexpected, stop before taking the site
offline. This sequence uses the `POSTGRES_*` environment variables used by the
repository's Django settings. Do not paste their values into a conversation.

## 3. Make a fresh backup before pulling or migrating

These commands keep backups outside the repository and web-served directories.
They copy the complete database and the configured public/private media roots.

```bash
umask 077
export CLARA_PARTICIPATION_BACKUP="$HOME/clara2-backups/participation-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$CLARA_PARTICIPATION_BACKUP" &&
git rev-parse HEAD > "$CLARA_PARTICIPATION_BACKUP/deployed-commit.txt" &&
sudo systemctl stop gunicorn-clara2 djangoq-clara2 project-understanding-worker &&
PGPASSWORD="${POSTGRES_PASSWORD:-}" pg_dump --no-password \
  --host="${POSTGRES_HOST:-}" --port="${POSTGRES_PORT:-5432}" \
  --username="${POSTGRES_USER:-postgres}" --dbname="${POSTGRES_DB:-clara2}" \
  --format=custom --file="$CLARA_PARTICIPATION_BACKUP/database.dump" &&
pg_restore --list "$CLARA_PARTICIPATION_BACKUP/database.dump" >/dev/null
```

Only continue if the dump and archive listing succeeded. The listing is a basic
archive check, not a full restore rehearsal. Keep any existing off-server/RDS
backup policy as well; this local copy is an immediate upgrade recovery point.

```bash
python manage.py shell -v 0 <<'PY'
import os
import subprocess
from pathlib import Path
from django.conf import settings

backup = Path(os.environ['CLARA_PARTICIPATION_BACKUP'])
roots = [('public-media', settings.MEDIA_ROOT),
         ('community-private-media', settings.COMMUNITY_DICTIONARY_MEDIA_ROOT)]
for name, configured in roots:
    root = Path(configured).resolve()
    if not root.is_dir():
        raise RuntimeError(f'Expected media directory is missing: {root}')
    subprocess.run(['sudo', 'tar', '-czf', str(backup / (name + '.tar.gz')),
                    '-C', str(root), '.'], check=True)
    subprocess.run(['sudo', 'tar', '-tzf', str(backup / (name + '.tar.gz'))],
                   stdout=subprocess.DEVNULL, check=True)
    subprocess.run(['sudo', 'chmod', '600', str(backup / (name + '.tar.gz'))], check=True)
    (backup / (name + '-path.txt')).write_text(str(root) + '\n')
print(f'Backup complete: {backup}')
PY
```

If a backup fails, stop. Since the code has not yet been pulled or migrated, the
old site can be brought back with `sudo systemctl start gunicorn-clara2
djangoq-clara2 project-understanding-worker` while the backup issue is resolved.

## 4. Update and check the one-time migration

```bash
cd /srv/C-LARA-2
git pull --ff-only && git rev-parse HEAD
```

Check that the printed commit matches the laptop. Then:

```bash
python -m pip install -r requirements.txt &&
cd platform_server &&
python manage.py check &&
python manage.py showmigrations community_dictionary
```

For this **first deployment**, migration 0009 should be unchecked. If it is already
`[X]`, do not run the command targeting 0008 below: that would request a downgrade.
Use the normal forward `migrate` sequence instead and preserve any later withdrawals.

AWS may still precede the personal-collection schema, so first migrate to 0008.
This applies any missing earlier migrations, but stops before the experimental
private-content reset. Then run the audit:

```bash
python manage.py migrate community_dictionary 0008_dictionary_participation &&
python manage.py community_withdrawal_audit --expect-empty
```

Expected: `Private contributions: 0`, `Private entries: 0`. **If the audit fails,
stop and retain the output. Do not run migration 0009.** This detects private
material that would otherwise be restored to shared dictionaries by the reset.
The site is still stopped; resolve the discrepancy before reopening it.

If the audit passes:

```bash
python manage.py migrate &&
python manage.py collectstatic --noinput &&
python manage.py check &&
sudo systemctl start gunicorn-clara2 djangoq-clara2 project-understanding-worker &&
sudo systemctl status --no-pager gunicorn-clara2 djangoq-clara2 project-understanding-worker
```

There are no nginx or systemd unit changes in this revision, so no nginx restart
or `daemon-reload` is needed. Do not run the Django test suite against production;
the existing 156-test result used disposable test databases and media.

If a migration or startup fails, stop and keep the error output. Do not blindly
reverse migrations or switch to older code against the changed database. Recovery
may require the pre-upgrade database and matching code/media; account for any
subsequent withdrawals before restoring an older snapshot.

## 5. Test on the server

- Refresh the browser. Check ordinary C-LARA-2 login/project access, then browse
  the Swedish dictionary's images, words, translations and audio.
- Use a small temporary dictionary and two accounts for one withdraw/restore cycle;
  verify the other account's view and previously accepted content's immediate return.
- Then test with the substantial dictionary. **Do not casually withdraw as its
  owner:** that transfers ownership, and restoring does not transfer it back.
  Test owner handover in the temporary dictionary.
- Repeat the basic cycle on a phone and note any cosmetic feedback for Sophie.

Server deployment and these tests remain pending until Manny reports their results.
