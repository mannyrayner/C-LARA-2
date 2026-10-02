# Withdraw my content / Restore my content

Prepared 2 October 2026. This revision replaces the individual contribution
withdrawal/sharing interface with one participation state per person and dictionary.
It applies **after `community_dictionary_immediate_restore.patch`**, whether that
patch has been committed or is still staged. Test on the laptop before AWS.

## The user model

- **Participating:** browse and contribute normally. The dictionary's top page
  offers **View my contributions** and **Withdraw my content**.
- **Withdrawn:** all your contributions are retained privately. You can view your
  saved material or **Restore my content**; browsing and new contributions are
  blocked. The home page clearly marks the dictionary and has a Restore button.
- Withdrawal has a confirmation page; restoration takes one click. Private
  material is read-only. There are no component checkboxes, material filters,
  destination menus or editable personal dictionaries.
- An owner chooses an active replacement when confirming withdrawal. Transfer and
  withdrawal succeed together. Restoring rejoins as a member, not as owner.
  If nobody can take over, withdrawal archives the dictionary; the owner can
  restore to reopen it. Everyone keeps access to their own saved material.

Previous acceptance is retained; pending/rejected material keeps its review state,
and moderator-returned material needs review. Newer shared wording is preserved;
earlier text returns as history. Attribution, media, picture-word links and relevant
request relationships survive a normal withdrawal/restore cycle. Another person's
withdrawal can keep dependent material private until their source is restored.
Membership suspension and archived entries remain independent restrictions.

## Laptop installation

Stop the development server. Save `community_dictionary_participation.patch` one
directory above your checkout. Apply it on top of the installed immediate-restore
revision; do not reapply that earlier patch.

```bash
cd /home/github/c-lara-2
git status --short
git apply --check ../community_dictionary_participation.patch &&
git apply --index ../community_dictionary_participation.patch
cd platform_server
```

If the patch check fails, stop and retain the output rather than forcing it.

**Back up the configured laptop database before migrating.** For the usual SQLite
setup, this command makes a timestamped full database backup and prints its path.
It deliberately refuses a PostgreSQL database; use a PostgreSQL snapshot/dump
if that is your laptop configuration.

```bash
../.venv/Scripts/python.exe -E manage.py shell -c "from django.conf import settings; import sqlite3; from pathlib import Path; from datetime import datetime; db=settings.DATABASES['default']; assert db['ENGINE'].endswith('sqlite3'), 'Use your PostgreSQL backup procedure'; dest=Path(db['NAME']).with_name('db-before-participation-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'.sqlite3'); src=sqlite3.connect(str(db['NAME'])); dst=sqlite3.connect(str(dest)); src.backup(dst); dst.close(); src.close(); print(dest)"
```

Then:

```bash
../.venv/Scripts/python.exe -E manage.py community_withdrawal_audit &&
../.venv/Scripts/python.exe -E manage.py check &&
../.venv/Scripts/python.exe -E manage.py migrate &&
../.venv/Scripts/python.exe -E manage.py test community_dictionary &&
../.venv/Scripts/python.exe -E manage.py runserver --insecure
```

There are **two migrations, 0008 and 0009**. The second performs the one-time reset
you requested: retained experimental content returns to its original shared entries,
and everyone begins in the participating state. Duplicate originals/returned copies
retain their provenance but only one identical copy remains visible as current
material. Newer wording is kept. Private additions without a former entry get one
entry in the source dictionary and need review. No media files are deleted or copied.
The migration fails rather than guessing if a collection has no shared origin.

Expected tests: **156, OK**. Mock provider timeouts/invalid responses are deliberate
when the final result is OK. No package installation is needed. Reload the browser
so it fetches stylesheet version 9.

## Suggested laptop acceptance

1. Check the initial dictionary after migration: the experimental withdrawn
   pictures have returned, attribution is intact and no extra visible copies appear.
2. As an ordinary member, choose **View my contributions**, then withdraw. Try
   Cancel first; then confirm. Verify the other account cannot see that material.
3. Check the withdrawn status on both the dictionary page and platform home page.
   View saved content: it should contain only your own material, with no editing
   controls. An old shared-entry URL must no longer let you browse or contribute.
4. Restore from the home page. Previously accepted content should be immediately
   visible to another account. Repeat the cycle and check for duplicates.
5. In a small disposable dictionary, withdraw as owner and choose a successor.
   Check that the successor can administer it and that restoring does not take
   ownership back. A solo dictionary should archive and reopen on restoration.
6. If practical, try overlapping withdrawals where one person revised another's
   text. Neither person's restore should override the other's remaining withdrawal.

## AWS deployment

Manny now reports successful laptop acceptance (2 October). The server is still on
an older revision. Use the [complete AWS deployment sequence](community-participation-aws.md),
which applies any missing schema migrations up to 0008 before running the audit
and allowing 0009. The audit below requires the earlier personal-collection schema;
it cannot run against a server that still precedes migration 0006.


AWS deployment and a withdrawal/restoration trial are now reported successful;
see the [server record](../../experiments/community_dictionary/participation-aws-2026-10-02.md).
The following preflight applies to a server that has not yet applied 0009. Before the first deployment
of migration 0009, use the normal database/private-media backup procedure and pause
writes during the upgrade. Confirm the assumption that AWS has no private material:

```bash
python manage.py community_withdrawal_audit --expect-empty
```

This command works before the new schema exists. If it fails, stop before migrating
and inspect the discrepancy: the migration restores retained material. This is a
one-time pre-migration check, not a permanent ban on future private withdrawals.
After acceptance and this check, use the normal check/migrate/collectstatic/service
restart runbook, then test on a physical phone.

The data reset has no safe automatic reverse. For rollback, stop writes, restore
the pre-upgrade database backup and matching code/media snapshot, then restart.
Do not merely reverse the schema or restore an old database over later withdrawals
without reconciling those decisions.

## Evidence and remaining limits

156 Django tests and a Chromium phone/desktop rehearsal pass. Tests use disposable
SQLite and synthetic media, including migration fixtures. They cover privacy,
permissions, overlapping withdrawals, duplicate/stale requests, moderation, newer
text, ownership handover, failed-handover rollback and one-time migration behaviour.
The subsequent human-reported AWS trial adds deployment and basic
withdrawal/restoration evidence. No new physical Safari/Android matrix or
PostgreSQL concurrency stress test is claimed.
See [the dated record](../../experiments/community_dictionary/participation-2026-10-02.md).
