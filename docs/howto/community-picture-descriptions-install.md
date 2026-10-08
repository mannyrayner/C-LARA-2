# Community Dictionaries: picture descriptions — laptop installation

7 October 2026. Incremental patch against main `2a0a75e` (the French stakeholder
note/authorship update). It adds migration **0015_picture_descriptions**. No new
Python packages or credentials are required. The new dictionary option starts off.

## 1. Stop the laptop server and check the working tree

Stop runserver with Ctrl-C. From Cygwin:

```bash
cd /home/github/c-lara-2
git status --short
```

If there are unexpected changes, keep them and inspect them before applying the
patch. These instructions assume the preceding accepted work is already committed.
No need to activate the Windows virtual environment; use its Python directly.

## 2. Make a verified SQLite backup outside the repository

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
backup = destination / ('before-picture-descriptions-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '.sqlite3')
with sqlite3.connect(str(source)) as src, sqlite3.connect(str(backup)) as dst:
    src.backup(dst)
    assert dst.execute('PRAGMA quick_check').fetchall() == [('ok',)], 'Backup verification failed'
print('Database backup verified:', backup)
PY
```

The explicit `-c` avoids the Cygwin/native-Windows interactive-shell problem from
our earlier installation. Keep the backup; do not put it into Git.

## 3. Apply the downloaded patch

Save `community_dictionary_picture_descriptions.patch` in `/home/github/`, beside
the checkout. Then:

```bash
cd /home/github/c-lara-2
git apply --check ../community_dictionary_picture_descriptions.patch &&
git apply --index ../community_dictionary_picture_descriptions.patch &&
git diff --cached --check
```

If the check fails, stop and send the output; do not force it or apply an older patch.

## 4. Check, test, migrate and restart

```bash
cd /home/github/c-lara-2/platform_server
../.venv/Scripts/python.exe -E manage.py check &&
../.venv/Scripts/python.exe -E manage.py test community_dictionary &&
../.venv/Scripts/python.exe -E manage.py migrate &&
../.venv/Scripts/python.exe -E manage.py showmigrations community_dictionary
```

Expected: **310 tests**, ending `OK`, and `[X] 0015_picture_descriptions`.
Some deliberately simulated timeout/silence/provider-failure messages are normal
inside the tests; their final result must be `OK`.

```bash
../.venv/Scripts/python.exe -E manage.py runserver --insecure
```

The normal laptop threaded job adapter creates audio in the background; keep
runserver running. If you deliberately use real Django-Q (`DJANGO_Q_USE_REAL=1`),
its qcluster must run as usual. No change is needed to the existing AWS queue setup.

## 5. Try it

1. In the small Swedish/English dictionary, open **Settings**. Enable
   **Picture descriptions (OpenAI)** and keep **saved spoken audio** enabled. Save.
2. On Browse, choose **Describe a picture**. Take/upload a picture and type a short
   English description. Approve the disclosed API processing and choose
   **Prepare suggestion**.
3. Check the bilingual result and choose **Yes — save and share**. You should get a
   sentence, linked dictionary-form words, and synthetic audio. Existing matching
   word entries/recordings are reused. Audio may take a little longer; you can
   move to the next picture while background processing continues.
4. Try **Speak** in English, then Swedish. Spoken confirmation should use the same
   language; tap Play if the browser does not play automatically. The transcript
   is inspectable. Try correcting the description before confirming.
5. Open one of Cathy's existing accepted pictures, choose **Describe this picture**,
   and save its sentence. **Next picture** should move to another existing picture
   without a saved description, or offer a new upload when none remains.
6. Follow sentence ↔ word links, listen inline, reveal translations, and check the
   Pictures/Words/Sentences views. Flag an entry under **Needs attention**. An owner
   or editor can edit it and mark the current wording checked.
7. On the small test dictionary, check withdrawal/restore and that editing wording
   hides stale generated audio and automatic sentence links.

The new workflow publishes after contributor confirmation; it clearly distinguishes
this from expert linguistic checking. Human-only contributions retain their existing
workflow. The dictionary owner controls whether this optional experiment is enabled.

First-cut bounds: short sentences (255 characters), up to six useful words per
sentence; no question/answer exercises. At the time of this original release, language porting included word
entries only, not the new sentences or their links. Source-image withdrawal follows
existing contribution dependencies. Private previews expire after 48 hours.

The 310 automated tests and desktop/mobile-width Chromium rehearsal use simulated
provider responses. Your trial is still needed for real image interpretation,
translation, lemmatisation, speech recognition and pronunciation quality. Physical
phone/AWS acceptance is not yet claimed.

## After laptop acceptance

Review `git diff --cached --stat` and `git diff --cached --check`, then commit/push
the staged patch when satisfied. The patch includes code, migration, tests, workflow
notes and global-workspace revision 49. It contains no database, recordings, credentials,
or generated private previews. AWS deployment can follow after laptop feedback;
it will need migration, collectstatic and restart of the web and existing Q workers.
Do not turn on DEBUG on AWS.

The later [sentence-porting follow-up](community-sentence-porting-install.md) removes
that word-only restriction. Use its runbook after applying that follow-up.
