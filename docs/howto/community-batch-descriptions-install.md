# Install the batch-description update on the laptop

This incremental patch is based on main commit
`15772453d37457b3121c182567985fe9abae33a5` (Simplify dictionary entry and word pages).
It adds **Settings → Add missing sentences**, an explicit **Rename dictionary**
control and sentence/word counts on dictionary cards. There is one new migration,
`0019_batch_descriptions`. Test on the laptop before deploying to AWS.

## 1. Stop the laptop server and back up SQLite

Finish active AI jobs first, then stop runserver with Ctrl-C. The fallback queue
runs in that process and is interrupted by a restart. In Cygwin:

```bash
cd /home/github/c-lara-2
git status --short
git log -1 --oneline
```

Expect a clean working tree. If there are unexpected changes, stop rather than
restoring or mixing them into this patch. Save the downloaded
`community_dictionary_batch_descriptions.patch` in `/home/github/`.

```bash
cd /home/github/c-lara-2/platform_server
../.venv/Scripts/python.exe -E manage.py shell -v 0 -c "exec(__import__('sys').stdin.read())" <<'PY'
import sqlite3
from pathlib import Path
from datetime import datetime
from django.conf import settings

config = settings.DATABASES['default']
assert config['ENGINE'] == 'django.db.backends.sqlite3', 'Stop: this is not the laptop SQLite setup'
source = Path(config['NAME']).resolve()
assert source.is_file(), f'Missing database: {source}'
destination = Path.cwd().parent.parent / 'clara2-backups'
destination.mkdir(exist_ok=True)
backup = destination / ('before-batch-descriptions-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '.sqlite3')
with sqlite3.connect(str(source)) as src, sqlite3.connect(str(backup)) as dst:
    src.backup(dst)
    assert dst.execute('PRAGMA quick_check').fetchall() == [('ok',)], 'Backup verification failed'
print('Database backup verified:', backup)
PY
```

Proceed only after the verified-backup message. The backup stays outside Git.
The explicit `-c` above avoids the Cygwin/Windows interactive-shell problem.

## 2. Apply, check and migrate

```bash
cd /home/github/c-lara-2
git apply --check ../community_dictionary_batch_descriptions.patch &&
git apply --index ../community_dictionary_batch_descriptions.patch &&
git diff --cached --check
```

If that succeeded:

```bash
cd /home/github/c-lara-2/platform_server
../.venv/Scripts/python.exe -E manage.py check &&
../.venv/Scripts/python.exe -E manage.py test community_dictionary projects.tests.test_admin_tools &&
../.venv/Scripts/python.exe -E manage.py makemigrations --check --dry-run &&
../.venv/Scripts/python.exe -E manage.py migrate &&
../.venv/Scripts/python.exe -E manage.py showmigrations community_dictionary
```

The test suite intentionally logs simulated failures/timeouts; the final result
must be **OK**. The migration list should end with `[X] 0019_batch_descriptions`.
No requirements, settings-file, static-file or environment changes are needed.

## 3. Start and try a small batch

```bash
../.venv/Scripts/python.exe -E manage.py runserver --insecure
```

`--insecure` here only enables local development static-file serving with the
existing DEBUG=False configuration. Use the usual laptop URL.

1. Open **Settings** as the dictionary owner. Try **Rename dictionary → Save name**.
2. Make sure **Picture descriptions**, **Learn from a photo**, and **saved spoken
   audio** are enabled in the general settings form.
3. Open **Add missing sentences**. Choose both accepted/pending pictures (default)
   or a narrower set, and a voice. Estimate, review the price, and approve.
4. Review sentences and audio. **Save and next** advances automatically; you can
   instead accept all unflagged ready results. Existing words/translations are
   hints and remain intact. Accepting a sentence also accepts its source picture
   if that picture was awaiting review.
5. Select **Build vocabulary from accepted sentences**, estimate/approve, and
   review the words or accept the ready suggestions together. Check a sentence's
   word links and recordings.
6. Return to **My dictionaries** and check the sentence/word counts. Blank picture
   entries and unaccepted text are excluded from those counts.
7. Upload another picture, rerun, and confirm it is picked up while the earlier
   sentences and vocabulary are kept. Valid outstanding previews also remain
   available under Recent jobs.

Both stages make paid requests only after approval. Use a small test dictionary
first. Editing a sentence drops its old generated recording; Create audio on its
saved page produces the revised recording. The daily individual-description
allowance is separate from this explicitly cost-approved batch.

## 4. Check in after testing

The patch is already staged. Once the laptop trial is satisfactory:

```bash
cd /home/github/c-lara-2
git diff --cached --check &&
git diff --cached --stat &&
git commit -m "Add batch picture descriptions, dictionary renaming and counts" &&
git push
git status --short
```

For the later AWS deployment, migration 0019 must run before services start with
the new code. Finish active jobs, take the usual database backup, stop the three
application services, pull main, run check and migrate under the service identity
with `/etc/clara2.env`, then start the services. Keep the bounded queue repair and
DEBUG=False. This patch needs no dependency install, collectstatic or nginx change.
Do not reverse migration 0019 after creating batch items: distinct images on one
entry intentionally use the new uniqueness rule.
