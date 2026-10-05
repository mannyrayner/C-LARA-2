# Faster language-port review and attention flags

Prepared 5 October 2026 after Manny's 61-entry French AWS trial. The existing
conversion works, with four initially unsatisfactory recordings reported. This
increment changes the review workflow, not the TTS model, hints or billing.

## What changes

- **Save and next** saves the current result and opens the next available review
  item, including across results pages. It skips saved, discarded, stale and
  set-aside items. After the last eligible item it returns to results. A success
  message names the saved word and links to its entry.
- Saved result cards show the **current saved word**, such as **chien · saved**,
  and **Open saved entry**. They do not retain another translation copy merely
  for display. Unavailable/withdrawn content stays hidden.
- **Flag for later and next** keeps wording edits and an optional note privately,
  without publishing the item or making an AI request. Its generated audio still
  identifies the original generated word; editing text does not relabel old audio.
- **Needs attention** filters the results. A flagged preview reopens with its edits
  and note. When saving, clear **Keep flagged for attention after saving** if the
  issue is resolved, or leave it checked to save an entry that still needs work.
- Already saved rows also offer **Flag for attention**, an optional note and
  **Mark as resolved**. This works with existing conversion jobs after migration;
  there is no need to regenerate the 61-entry dictionary to use these controls.
- The language-version update page links to **Previous results**, including each
  job's attention list, so older flags remain retrievable after a later update.

Flags belong to the private conversion review, visible only to its authorised
owner. They do not change dictionary membership, publication or review status.
Flagged unsaved previews must still be saved or discarded before estimating an
update to that language version. Withdrawal clears affected notes/drafts along
with the existing preview and contribution protections. Cancel/discard clears
unsaved annotations; flags on still-accessible saved results remain until resolved.

Migration **0014_port_review_attention** adds three review-metadata fields with
empty/default values. Existing translations, audio and images are not rewritten.

## Laptop installation

Stop the local server and finish any active conversion job. Save the patch in
`/home/github/`. Back up SQLite outside the checkout:

```bash
cd /home/github/c-lara-2/platform_server
../.venv/Scripts/python.exe -E manage.py shell -v 0 -c "exec(__import__('sys').stdin.read())" <<'PY'
import sqlite3
from pathlib import Path
from datetime import datetime
from django.conf import settings
config = settings.DATABASES['default']
assert config['ENGINE'] == 'django.db.backends.sqlite3', 'Stop: not the laptop SQLite database'
source = Path(config['NAME']).resolve()
assert source.is_file(), f'Missing database: {source}'
folder = Path.cwd().parent.parent / 'clara2-backups'
folder.mkdir(exist_ok=True)
backup = folder / ('before-port-review-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '.sqlite3')
with sqlite3.connect(str(source)) as src, sqlite3.connect(str(backup)) as dst:
    src.backup(dst)
    assert dst.execute('PRAGMA quick_check').fetchall() == [('ok',)]
print('Database backup verified:', backup)
PY
```

Apply the incremental patch over the TTS guidance and release-notes updates:

```bash
cd /home/github/c-lara-2
git apply --check --whitespace=nowarn ../community_dictionary_port_review.patch &&
git apply --index --whitespace=nowarn ../community_dictionary_port_review.patch &&
git diff --cached --check -- . ':(exclude)docs/global_workspace/archive/inputs/rev-0047/*'

cd platform_server
../.venv/Scripts/python.exe -E manage.py check &&
../.venv/Scripts/python.exe -E manage.py test community_dictionary &&
../.venv/Scripts/python.exe -E manage.py migrate &&
../.venv/Scripts/python.exe -E manage.py showmigrations community_dictionary
```

The whitespace check excludes only the verbatim archived user messages, which
retain original spacing.

Expected: **286 tests pass**, migration 0014 has `[X]`. Simulated provider failures
in the test output are intentional; the final result must be `OK`. Start with:

```bash
../.venv/Scripts/python.exe -E manage.py runserver --insecure
```

Try a saved conversion first: check word labels, flag an entry and filter/resolve
it. If there are unsaved results, try Save and next and Flag for later and next;
return through Needs attention and check that your edits survived. No new paid
conversion is needed just to test saved flags. A fresh small conversion, if needed
for sequential review, still requires the usual cost approval.

After laptop acceptance, commit/push and use the [AWS runbook](community-language-porting-aws.md)
with a fresh backup and normal forward migration. This update's only new migration
is **0014**. Finish with **restart** of all three services, even if an earlier stop
was missed. Keep DEBUG false. Static collection remains part of the normal runbook.

## Verification and evidence

286 app tests pass on Linux/Python 3.12/SQLite, including 11 new tests of sequential
review, pagination, preserved drafts, saved flags, retries, filtering, source
withdrawal, access/CSRF boundaries, HTML escaping and older-job navigation. Django
checks and the migration drift check pass. A real Django/Chromium rehearsal with
simulated provider data exercised the controls; layouts were checked at 390px and
1280px and the phone-width screenshots were visually inspected. No new paid API
call or AWS deployment was performed by the assistant.

See [Manny's AWS trial and the prepared UX follow-up](../../experiments/community_dictionary/porting-aws-2026-10-05.md).
The new UI still awaits Manny's laptop acceptance; this is not a new physical-phone
trial or an independent assessment of French pronunciation.
