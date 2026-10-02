# Share back to the original dictionary

> Historical revision. The current [dictionary-wide participation model](community-participation.md)
> replaces individual withdrawal/sharing, editable personal collections and the
> per-entry return shortcut. Use its runbook for the new migration and laptop trial.


Prepared 2 October 2026 against main `e4153586cb3e0d15e8e7001e79bea6807f3d9722`.
This is a follow-up to the installed contribution-control and entry-display patches.
It adds no migrations or dependencies.

## Current return route

Manny found the original confirmation-and-review shortcut too complicated.
The [immediate-restoration follow-up](community-immediate-restore.md) now makes
**Share back to the original dictionary** a one-click operation. Unchanged,
previously accepted material voluntarily withdrawn by its custodian keeps its
approval in the original entry. New or moderated material still needs review;
newer shared text and private copies are preserved.

Install that follow-up after this original patch. Its runbook and 148-test/browser
evidence supersede the original behaviour described in the dated trial record.

## Original patch installation (only if not already installed)

Stop the development server. Save `community_dictionary_share_back.patch` one
directory above the checkout containing last night's commit `e4153586`.

```bash
cd /home/github/c-lara-2
git apply --check ../community_dictionary_share_back.patch &&
git apply --index ../community_dictionary_share_back.patch
```

After that succeeds:

```bash
cd platform_server
../.venv/Scripts/python.exe -E manage.py check &&
../.venv/Scripts/python.exe -E manage.py test community_dictionary &&
../.venv/Scripts/python.exe -E manage.py runserver --insecure
```

No `migrate` or package installation is needed for this follow-up. Expected test
count: **140**. Mock provider-failure log messages remain expected when the final
result is `OK`.

For the current one-click test and follow-up installation, use
[community-immediate-restore.md](community-immediate-restore.md).

For later AWS deployment, include this patch in the normal commit/pull/restart
workflow. Machines that have not installed the original contribution-control
revision still need its database backup and migrations 0006/0007.

## Evidence

See [the dated trial record](../../experiments/community_dictionary/share-back-2026-10-02.md).
Manny reports an improvement but requests fewer steps. The immediate-restoration follow-up remains pending human acceptance and AWS/physical-phone deployment.
