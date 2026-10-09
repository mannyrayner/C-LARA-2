# Two-stage language porting: installation and first trial

9 October 2026. Apply on top of the sentence-port release now reported working on
AWS. This patch includes **one additive migration, 0018_port_vocabulary_stages**.
It adds job/review tracking; it does not rewrite dictionary contents during migration.
No dependency or settings change is required.

## Laptop

Let running AI calls finish, then stop runserver and any local queue worker. Save
`community_dictionary_two_stage_porting.patch` in `/home/github/`.

First back up the laptop database. The explicit `-c` wrapper is necessary with
Windows Python running from Cygwin; do not omit it.

```bash
cd /home/github/c-lara-2/platform_server
../.venv/Scripts/python.exe -E manage.py shell -v 0 -c "exec(__import__('sys').stdin.read())" <<'PY'
import sqlite3
from contextlib import closing
from pathlib import Path
from datetime import datetime
from django.conf import settings
config = settings.DATABASES['default']
assert config['ENGINE'] == 'django.db.backends.sqlite3', 'Stop: not the laptop SQLite setup'
source = Path(config['NAME']).resolve()
assert source.is_file(), f'Missing database: {source}'
directory = Path.cwd().parent.parent / 'clara2-backups'
directory.mkdir(exist_ok=True)
backup = directory / ('before-port-vocabulary-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '.sqlite3')
with closing(sqlite3.connect(str(source))) as src, closing(sqlite3.connect(str(backup))) as dst:
    src.backup(dst)
    assert dst.execute('PRAGMA quick_check').fetchall() == [('ok',)], 'Backup verification failed'
print('Database backup verified:', backup)
PY
```

Continue only after **Database backup verified**. Check the working tree; investigate
unexpected unstaged changes rather than resetting them. Previously accepted staged
patches are okay if the index and working copies agree.

```bash
cd /home/github/c-lara-2
git status --short
git diff --name-only
git apply --whitespace=nowarn --check ../community_dictionary_two_stage_porting.patch &&
git apply --whitespace=nowarn --index ../community_dictionary_two_stage_porting.patch &&
git diff --cached --check -- . ':!docs/global_workspace/archive/inputs/rev-0059/'
```

The whitespace check excludes this revision's verbatim discussion archive: one
original message ends a line with a space. It still checks all code and other docs.
Do not use Git's whitespace-fixing option on the archived human messages.

Then, stopping if any command fails:

```bash
cd /home/github/c-lara-2/platform_server
../.venv/Scripts/python.exe -E manage.py check &&
../.venv/Scripts/python.exe -E manage.py test community_dictionary &&
../.venv/Scripts/python.exe -E manage.py migrate &&
../.venv/Scripts/python.exe -E manage.py showmigrations community_dictionary
```

Expect **410 tests, OK**, and `[X] 0018_port_vocabulary_stages` after migration.
The tests deliberately simulate some provider failures and print warning messages.
They make no paid API calls. Start the web server and the background queue in two
terminals, using the same local environment settings as before:

```bash
cd /home/github/c-lara-2/platform_server
../.venv/Scripts/python.exe -E manage.py runserver --insecure
```

```bash
cd /home/github/c-lara-2/platform_server
../.venv/Scripts/python.exe -E manage.py qcluster
```

If a local queue worker is already managed separately, restart that worker instead
of starting a second copy.

## First trial

1. Use a small Swedish dictionary containing sentences. Create a French version;
   approve the sentence estimate and review its sentences. Edit one before saving.
   Try **Accept all remaining suggestions** too.
2. Choose **Build vocabulary from accepted sentences**, approve its separate estimate,
   and review a result. You should see the final French sentence, its image and an
   editable list of words/expressions. Save and proceed, or accept the remaining ones.
3. Let word audio finish. Check sentence-to-word links and links back to sentences.
   Two sentences using the same lemma and meaning should share a word page and audio;
   different meanings should remain separate.
4. Edit a saved sentence or a word's meaning. Its sentence page should show
   **Vocabulary needs updating**. The next vocabulary estimate includes changed
   sentences and skips unchanged ones. It does not translate sentences again.
5. To repair an existing French version, go directly to its **Settings → Build or
   update vocabulary from accepted sentences**. Keep the dictionary. Check the
   `repose → reposer` example and a few shared words before bulk acceptance.

Use **Flag for later and next** for uncertain suggestions. Bulk acceptance skips
flags, failures, unclear and stale results. In stage 2, finish/discard remaining
suggestions or cancel the job to release unused reserved credit. Existing matching
sentence audio is kept; use **Create audio** for an edited sentence or failed word.

## Check in after the laptop trial

```bash
cd /home/github/c-lara-2
git diff --cached --check -- . ':!docs/global_workspace/archive/inputs/rev-0059/'
git diff --cached --stat
git diff --name-only
git status --short
```

Only the intended app, tests, migration, documentation and global-state records
should be staged. Keep databases, backups and credentials outside Git. Then:

```bash
git commit -m "Derive shared port vocabulary from reviewed destination sentences" &&
git push origin main &&
git rev-parse HEAD &&
git status --short
```

## AWS, after laptop acceptance

Let active porting/capture jobs finish and announce a brief shared-site interruption.
This affects C-LARA-2 as well as Community Dictionaries. Keep the normal media
backups; this additive database migration does not require another 22 GB media
archive for installation.

```bash
sudo -iu ssm-user
cd /srv/C-LARA-2
umask 022
git branch --show-current
git status --short
. .venv/bin/activate
set -a && . /etc/clara2.env && set +a
```

Expect `main` and a clean working tree. Stop the application services, then make a
new database backup using the installed PostgreSQL **18** tools:

```bash
sudo systemctl stop gunicorn-clara2 djangoq-clara2 project-understanding-worker
cd /srv/C-LARA-2/platform_server
python manage.py shell -v 0 -c "exec(__import__('sys').stdin.read())" <<'PY'
import os
import subprocess
from pathlib import Path
from datetime import datetime
from django.conf import settings
config = settings.DATABASES['default']
assert config['ENGINE'] == 'django.db.backends.postgresql', 'Stop: unexpected database engine'
directory = Path.home() / 'clara2-backups' / ('before-port-vocabulary-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
directory.mkdir(parents=True, mode=0o700)
backup = directory / 'database.dump'
env = os.environ.copy()
env['PGPASSWORD'] = str(config.get('PASSWORD') or '')
args = ['/usr/lib/postgresql/18/bin/pg_dump', '--no-password', '--format=custom', '--file=' + str(backup), '--dbname=' + str(config['NAME'])]
for field, flag in [('HOST','--host'), ('PORT','--port'), ('USER','--username')]:
    if config.get(field):
        args.extend([flag, str(config[field])])
old_mask = os.umask(0o077)
try:
    subprocess.run(args, env=env, check=True)
    subprocess.run(['/usr/lib/postgresql/18/bin/pg_restore', '--list', str(backup)], stdout=subprocess.DEVNULL, check=True)
finally:
    os.umask(old_mask)
print('Database dump created and archive listing verified:', backup)
PY
```

The archive listing check is not a full restore rehearsal. If the backup fails,
stop here; restart the old services to restore availability while diagnosing it.
Do not continue to migration with an incomplete backup.

```bash
cd /srv/C-LARA-2
git pull --ff-only origin main &&
git rev-parse HEAD
```

Verify the SHA matches the tested laptop commit. Then:

```bash
cd /srv/C-LARA-2/platform_server
python manage.py check &&
python manage.py migrate &&
python manage.py collectstatic --noinput &&
python manage.py check &&
sudo systemctl start gunicorn-clara2 djangoq-clara2 project-understanding-worker
sudo systemctl status --no-pager gunicorn-clara2 djangoq-clara2 project-understanding-worker
```

No systemd or nginx configuration changes are required. If startup fails, inspect
`sudo journalctl -u gunicorn-clara2 -u djangoq-clara2 -u project-understanding-worker -n 100 --no-pager`;
keep `DEBUG=False` and do not paste credentials from logs. A code rollback to the
previous tested commit can leave the additive schema in place; do not reverse the
migration or restore the whole database after new contributions without a recovery
plan, since either can lose newly recorded work.

First check ordinary browsing and recording, then try stage 2 on a small port.
For the existing 150-entry French version, go directly to the vocabulary control
in its Settings. Check the estimate and a few contextual results before accepting
all. No retranslation or replacement dictionary is needed.
