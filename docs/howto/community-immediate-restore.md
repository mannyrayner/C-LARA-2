# One-click restoration to the original dictionary

> Historical revision. The current [dictionary-wide participation model](community-participation.md)
> replaces individual withdrawal/sharing, editable personal collections and the
> per-entry return shortcut. Use its runbook for the new migration and laptop trial.


Prepared 2 October 2026, on top of `community_dictionary_share_back.patch`.
Install this follow-up after that patch, whether or not it has been committed.
No database migration or additional package is needed.

## Behaviour

**Share back to the original dictionary** now returns the current material in
one click from either its private entry or My contributions → Private collection.
There is no confirmation page or dialogue. The button states how many current
contributions it will return; the collection's material filter is respected.
The original entry opens after the operation.

Unchanged, previously accepted material voluntarily withdrawn by its custodian
retains its acceptance in that same original entry. Other active members can see
it immediately. Attribution and private copies remain, and it can be withdrawn
again. Accepted material already returned as pending by the previous patch can
also recover its approval using this shortcut, without creating another copy.

New/unreviewed material and rejected or moderator-returned material still need
review. Private acceptance alone does not imply community approval. New shared
wording is never overwritten; earlier private revisions and obsolete synthetic
audio are not returned automatically. Sharing to another destination through
**Share selected…** retains its existing confirmation and review process.

A stale page cannot add material created after that page loaded, bypass another
contributor's withdrawal, or restore through an inactive membership. Retries do
not duplicate shared contributions or undo a later withdrawal. The shortcut does
not recreate deleted extra picture-word links or restore an archived entry.

## Install on the laptop

Stop the development server. Save `community_dictionary_immediate_restore.patch`
one directory above the checkout where you installed the previous Share back patch.
Do not reapply that earlier patch if it is already installed.

```bash
cd /home/github/c-lara-2
git apply --check ../community_dictionary_immediate_restore.patch &&
git apply --index ../community_dictionary_immediate_restore.patch
```

Once that succeeds:

```bash
cd platform_server
../.venv/Scripts/python.exe -E manage.py check &&
../.venv/Scripts/python.exe -E manage.py test community_dictionary &&
../.venv/Scripts/python.exe -E manage.py runserver --insecure
```

Expected result: **148 tests, OK**. The tests deliberately log simulated provider
timeouts/invalid responses. No `migrate` or dependency installation is needed.
If `git apply --check` reports a conflict, stop and retain its output; do not force it.

Reload My contributions → Private collection. Try the already-withdrawn Swedish
picture: press **Share back to the original dictionary** once. You should land on
the original entry and see its picture immediately, without an Accept button or
an awaiting-review label for that restored picture. Check from Cathy's account
as well. Your private copy stays available. If it is already accepted in the shared
entry, the card instead offers **Open original entry**.

For later AWS deployment, check in the changes together and use the existing
backup/pull/check/migrate/collectstatic/restart runbook. This follow-up itself adds
no migration. It has not been deployed to AWS by the assistant.

## Verification

148 Django tests pass with disposable SQLite/private media. The focused tests
cover normal members and owners, legacy withdrawals, text fields and version
counters, matching TTS, repeated cycles, previous pending copies, rejection and
moderation, source custody, stale forms and permission changes. A Chromium
rehearsal with phone-sized and desktop viewports verifies both direct controls,
no restore dialogue, immediate visibility in a second account, independent form
ownership and layout. This is not physical-phone or PostgreSQL concurrency evidence.
See [the trial record](../../experiments/community_dictionary/immediate-restore-2026-10-02.md).
