# Deploy dictionary-wide participation after laptop acceptance

Updated after the successful AWS deployment and withdrawal/restoration trial on
2 October 2026. See the [dated evidence record](../../experiments/community_dictionary/participation-aws-2026-10-02.md).
The commands below document the **first upgrade from the older schema**. On the
already-upgraded server, do not repeat the command targeting migration 0008.

2 October 2026. Manny reports that the new version appears fully working and much
better than the previous model. He considers the conceptual structure essentially
ready, subject to possible cosmetic feedback from Sophie. The proposed next step
was a controlled AWS trial. That server deployment and a withdrawal/restoration
trial have now succeeded. The initial report was human-reported laptop
acceptance, not a claim that every checklist item or physical device was tested.
Manny also specifically reports that laptop ownership handover appeared to work
correctly.

The original acceptance patch changed documentation only. Apply it after the
installed `community_dictionary_participation.patch`. The application still has
156 passing controlled tests; no additional app change or migration is introduced.

## Save this documentation follow-up after completed deployment

`community_dictionary_aws_trial_record.patch` applies after the installed
`community_dictionary_participation_acceptance.patch`. It records the AWS result
and repairs these instructions. It can be checked in with the next documentation
update; no database migration, application restart or new backup is needed merely
to install this documentation follow-up.

Save the patch above the laptop checkout. The archived console messages retain
original trailing spaces; the commands below preserve them and exclude only those
verbatim copies from the whitespace check.

```bash
cd /home/github/c-lara-2
git apply --check --whitespace=nowarn ../community_dictionary_aws_trial_record.patch &&
git apply --index --whitespace=nowarn ../community_dictionary_aws_trial_record.patch &&
git diff --cached --check -- . ':(exclude)docs/global_workspace/archive/inputs/rev-0038/*'
```

Review the staged documentation and commit/push it through the normal workflow.

The sections below retain the first-deployment workflow for reference. Steps 1–5
have already been completed on Manny's AWS server.

## 1. Original first-deployment check-in

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
be unavailable. The first upgrade's full media backup and verification took
substantially longer than a brief interruption; announce a maintenance window and
allow time for it. Let users finish their current saves and background jobs.

```bash
sudo -iu ssm-user
cd /srv/C-LARA-2
git branch --show-current
git status --short
. .venv/bin/activate
cd platform_server
set -a && . /etc/clara2.env && set +a
python manage.py shell -c "from django.conf import settings; assert settings.DATABASES['default']['ENGINE'] == 'django.db.backends.postgresql', 'This backup sequence expects the AWS PostgreSQL database'; print('PostgreSQL configured')" &&
/usr/lib/postgresql/18/bin/pg_dump --version &&
/usr/lib/postgresql/18/bin/pg_restore --version
```

The checkout should be clean and on `main`. If the database assertion fails, a
backup tool is missing, or the status is unexpected, stop before taking the site
offline. This sequence uses the `POSTGRES_*` environment variables used by the
repository's Django settings. Do not paste their values into a conversation.
The server reported PostgreSQL 18.3; client 18.6 was installed successfully. Use
both versioned 18 binaries, since the unversioned tools previously selected 16.15.
For another host, verify its database/client major versions before stopping services.

Before creating another full backup, check free space, source sizes and leftover
processes. Do not assume the 48 GB available before the successful backup is still
available afterwards. Do not delete an archive just because it is old without
checking whether it is needed for recovery.

```bash
df -h /srv/C-LARA-2 "$HOME"
ps -C tar,gzip,pg_dump -o pid,etime,pcpu,stat,comm
sudo du -sh /srv/C-LARA-2/platform_server/media \
  /srv/C-LARA-2/platform_server/private_uploads/community_dictionary \
  "$HOME/clara2-backups"
```

The two source paths above are the confirmed deployment paths. Use the configured
paths if they change. Allow room for an uncompressed media copy, the database dump
and operating headroom. A process-list heading with no process rows is normal.

## 3. Make a fresh backup before pulling or migrating

These commands keep backups outside the repository and web-served directories.
They copy the complete database and the configured public/private media roots.

The restrictive mask below is confined to a subshell. The named directory is
exported in the parent shell so the subsequent media command can use it. Stop
if any command fails. A fresh directory keeps earlier attempts intact.

```bash
export CLARA_PARTICIPATION_BACKUP="$HOME/clara2-backups/participation-$(date +%Y%m%d-%H%M%S)"
(
  umask 077
  mkdir -m 700 "$CLARA_PARTICIPATION_BACKUP" &&
  git rev-parse HEAD > "$CLARA_PARTICIPATION_BACKUP/deployed-commit.txt" &&
  sudo systemctl stop gunicorn-clara2 djangoq-clara2 project-understanding-worker &&
  PGPASSWORD="${POSTGRES_PASSWORD:-}" /usr/lib/postgresql/18/bin/pg_dump \
    --no-password --verbose \
    --host="${POSTGRES_HOST:-}" --port="${POSTGRES_PORT:-5432}" \
    --username="${POSTGRES_USER:-postgres}" --dbname="${POSTGRES_DB:-clara2}" \
    --format=custom --file="$CLARA_PARTICIPATION_BACKUP/database.dump.partial" &&
  /usr/lib/postgresql/18/bin/pg_restore \
    --list "$CLARA_PARTICIPATION_BACKUP/database.dump.partial" >/dev/null &&
  mv "$CLARA_PARTICIPATION_BACKUP/database.dump.partial" \
     "$CLARA_PARTICIPATION_BACKUP/database.dump" &&
  echo "Database backup complete."
)
```

Only continue after the success message. Listing the database archive is a basic
check, not a full restore rehearsal. Keep any off-server/RDS backup policy as well;
this local copy is an immediate upgrade recovery point.

The media command uses uncompressed archives and compares their contents with the
source files while writers remain stopped. Progress counters restart for each
creation/comparison pass. Private directory access is checked using the same sudo
identity as the archive commands. A partial filename becomes a final archive only
after comparison succeeds.

```bash
python manage.py shell -v 0 <<'PYMEDIA'
import os
import subprocess
from pathlib import Path
from django.conf import settings

os.umask(0o077)
backup = Path(os.environ['CLARA_PARTICIPATION_BACKUP'])
roots = [('public-media', settings.MEDIA_ROOT),
         ('community-private-media', settings.COMMUNITY_DICTIONARY_MEDIA_ROOT)]
for name, configured in roots:
    root = Path(configured).absolute()
    temporary = backup / (name + '.tar.partial')
    final = backup / (name + '.tar')
    if final.exists() or temporary.exists():
        raise RuntimeError(f'Backup file already exists for {name}; stop and inspect.')
    subprocess.run(['sudo', '-n', 'test', '-d', str(root)], check=True)
    print(f'Creating {name} archive from {root} ...', flush=True)
    with temporary.open('xb') as stream:
        subprocess.run([
            'sudo', '-n', 'tar', '--create', '--sparse', '--file=-',
            '--directory', str(root), '--checkpoint=10000',
            '--checkpoint-action=echo', '--totals', '.'
        ], stdout=stream, check=True)
    print(f'Comparing {name} archive with its source files ...', flush=True)
    subprocess.run([
        'sudo', '-n', 'tar', '--compare', '--file', str(temporary),
        '--directory', str(root), '--checkpoint=10000',
        '--checkpoint-action=echo'
    ], check=True)
    temporary.rename(final)
    (backup / (name + '-path.txt')).write_text(str(root) + '\n')
    print(f'{name}: archive comparison passed.', flush=True)
print(f'Backup complete: {backup}', flush=True)
PYMEDIA
```

If a backup fails, stop. Since the code has not yet been pulled or migrated, the
old site can be brought back with `sudo systemctl start gunicorn-clara2
djangoq-clara2 project-understanding-worker` while the backup issue is resolved.

## 4. Update and check the one-time migration

```bash
cd /srv/C-LARA-2
umask 022
git pull --ff-only && git rev-parse HEAD
```

The `umask 022` is essential: application code and dependencies must be readable
by the service account. Never carry a restrictive backup mask into Git/pip/static
operations. Backups remain private because of their directory and file modes.
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

If shell checks succeed but services fail after a pull performed with `umask 077`,
the confirmed incident was repaired with the following source-only change:

```bash
umask 022
sudo chmod -R a+rX /srv/C-LARA-2/platform_server/community_dictionary &&
sudo systemctl reset-failed gunicorn-clara2 djangoq-clara2 project-understanding-worker &&
sudo systemctl restart gunicorn-clara2 djangoq-clara2 project-understanding-worker &&
sudo systemctl status --no-pager gunicorn-clara2 djangoq-clara2 project-understanding-worker
```

Do not extend that recursive permission change to the repository as a whole,
private uploads or backups. If a service still fails, inspect its actual exception:

```bash
sudo journalctl -u djangoq-clara2 -n 80 --no-pager -o cat
```

## 5. Test on the server

- Refresh the browser. Check ordinary C-LARA-2 login/project access, then browse
  the Swedish dictionary's images, words, translations and audio.
- Use a small temporary dictionary and two accounts for one withdraw/restore cycle;
  verify the other account's view and previously accepted content's immediate return.
- Then test with the substantial dictionary. **Do not casually withdraw as its
  owner:** that transfers ownership, and restoring does not transfer it back.
  Test owner handover in the temporary dictionary.
- Repeat the basic cycle on a phone and note any cosmetic feedback for Sophie.

Manny subsequently reported all services running normally, access to the new
controls and successful execution of the suggested withdrawal/restoration sequence.
This is server acceptance evidence; detailed phone/device coverage and Sophie's
community assessment of the final workflow remain open.
