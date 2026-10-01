# Community Dictionaries: contribution control

Prepared 1 October 2026 against main `ffbbef9d24873cd930cb866d979e1bd3a735e41b`.
This increment implements Manny's agreed provenance, personal-collection,
withdrawal and membership model. It does not add image generation, games or
language migration. Those later features must respect the same custody rules.

Manny subsequently reports successful installation, restart and new-entry creation,
but finds the component list hard to identify. The
[entry-display follow-up](community-contributions-by-entry.md) groups contributions
by entry, with other people's material marked for reference. It adds no migration;
128 app tests and a new browser rehearsal pass. Manny now confirms laptop
acceptance of My contributions and requests check-in. His report does not specify
separate withdrawal/governance test cases or a new AWS/phone deployment.

## What changes for users

- **Word/phrase, translation/explanation and category have separate attribution,
  review, history and conflict checks.** Edit words remains one form. Submitting
  an unchanged field preserves its contributor and revision. Editing different
  fields concurrently does not overwrite the other person's work. Only word
  changes advance the version used by TTS; translation/category edits do not
  invalidate matching synthetic audio.
- **My contributions** is available from the account navigation and home page.
  Choose shared material or private collections, a dictionary and a material
  category. Withdraw selected contributions or all matching material across all
  result pages. Individual entry contributions also have a withdrawal control.
- **Withdrawal retains the material privately.** It moves contribution records
  to personal dictionaries scoped by contributor and source dictionary. Files
  stay in the private media store. Other members, including dictionary owners
  and editors, cannot open these personal dictionaries or old media URLs.
  Earlier revisions of a withdrawn component cannot be used to restore it to the
  project. Independently contributed components remain.
- **Share selected…** chooses a destination dictionary in the same language and
  either an existing entry or a new entry. Permission must be confirmed. Shared
  copies keep their attribution and enter the destination's review process.
  Repeated submission of the same confirmed request is idempotent.
- **Invited, active and inactive** memberships persist. Inactive members cannot
  browse or contribute to the shared dictionary, but retain their contribution
  controls through their account. Reactivation restores participation and
  preserves partnership records; it never republishes withdrawn content.
- **Editors return material instead of destroying it.** Returning a contribution
  or archiving an entry preserves the affected material in its contributors'
  personal collections. An editor's moderation action applies only within that
  dictionary; it does not revoke separately shared material in other projects.
- Editors can optionally credit new/changed components to another active member,
  with explicit confirmation of that person's permission. The upload/revision
  actor is retained separately, and the named contributor gets withdrawal
  control. This requires that the represented contributor has their own account.

## Provenance and dependent material

A real edit creates a separately attributed revision linked to the earlier one.
Unchanged text does not create a new revision. Copies and restorations keep
source attribution and record the sharing/restoring actor separately.

Withdrawing a component also withdraws shared copies and dependent revisions or
synthetic recordings linked to it. Each goes to its own contributor's collection;
this never gives someone access to another contributor's private material.
A derivative cannot be reshared while it depends on someone else's withdrawn
material. Unrelated components, such as Manny's independently recorded Swedish
pronunciation when Cathy withdraws a photograph, remain shared.

Image/word links are removed when their image is withdrawn. Completed requests
reopen if their response is withdrawn. Request explanations are retained as
attributed comments so they too can be withdrawn; withdrawing one clears its
cached request text. Photo/TTS previews containing withdrawn source material are
discarded, including attempts that finish after withdrawal.

Existing combined text histories are split by migration 0007. Unchanged fields
are traced through surviving accepted base versions. If the original history
was deleted, the migration keeps the earliest surviving attribution it can
support and records that basis. It cannot recover missing original authors.
An attribution-correction workflow is not included in this increment.

## Membership governance

Existing dictionaries retain **Owner manages membership** as their default.
Under People, an owner can appoint an active coordinator, then enable **Two
coordinators approve changes**. The owner counts as a coordinator.

Once enabled, changing a member's status or role, or changing the policy itself,
requires a proposal and approval by a different active coordinator. Proposals
record both actors. An intervening membership change makes older proposals stale.
The old invitation form cannot reactivate an inactive member or bypass the
protected role-change route. The former remove-member endpoint refuses deletion.

Members can voluntarily make themselves inactive. The owner must arrange an
ownership transfer before leaving; this revision does not add a transfer UI.
If voluntary departures leave fewer than two coordinators, protected changes
remain blocked: arrange recovery with the operator and the community's authority,
recording the decision, rather than weakening the policy automatically.

## Privacy limits

Personal collections are private from other application users, including project
editors. This is not encryption against server administrators. Withdrawal cannot
recall downloads, screenshots or earlier exports. Old backups must not be restored
into public service without reconciling subsequent withdrawal decisions. Offline
copies and local browser recovery drafts need their own device controls.

Export format 3 includes component attribution and membership decision history,
but excludes private/withdrawn material from a shared dictionary export. Cross-
dictionary revision references are omitted from the exported fixture; the live
server retains the complete dependency graph. Exports are portable snapshots,
not a mechanism for enforcing revocation in independently operated systems.

## Install on the laptop first

Save `community_dictionary_contribution_control.patch` one directory above the
checkout. Stop the development server. Start from a clean checkout containing
main `ffbbef9`; preserve unrelated work rather than resetting it.

```bash
cd /home/github/c-lara-2
git status --short
git apply --check ../community_dictionary_contribution_control.patch &&
git apply --index ../community_dictionary_contribution_control.patch
cd platform_server
```

Back up the actual configured SQLite database. This command refuses PostgreSQL;
use a PostgreSQL snapshot/dump instead if that is your laptop configuration.
It copies the database, not just dictionary tables.

```bash
../.venv/Scripts/python.exe -E manage.py shell -c "from django.conf import settings; import sqlite3; from pathlib import Path; from datetime import datetime; db=settings.DATABASES['default']; assert db['ENGINE'].endswith('sqlite3'), 'Use your PostgreSQL backup procedure'; dest=Path(db['NAME']).with_name('db-before-contribution-control-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'.sqlite3'); src=sqlite3.connect(str(db['NAME'])); dst=sqlite3.connect(str(dest)); src.backup(dst); dst.close(); src.close(); print(dest)"
```

Then:

```bash
../.venv/Scripts/python.exe -E manage.py check &&
../.venv/Scripts/python.exe -E manage.py migrate &&
../.venv/Scripts/python.exe -E manage.py test community_dictionary &&
../.venv/Scripts/python.exe -E manage.py runserver --insecure
```

Migrations **0006 and 0007** are required. There are no new runtime dependencies.
0007 is deliberately irreversible: rollback requires the pre-upgrade database
and matching old code, not reversing this migration. It does not delete media
files. Keep the normal private-media backup as well. Test using expendable sample
entries before withdrawing real shared material.

Suggested acceptance sequence:

1. Cathy adds a photo and English translation. An editor accepts them.
2. Manny adds Swedish and a category. Check that English still credits Cathy.
3. Change the translation/category and check matching TTS remains available.
4. Make Cathy inactive. Verify she cannot browse the project but can open My
   contributions and withdraw her translation or picture.
5. Check other members cannot retrieve withdrawn material through old URLs,
   history, word pages or a new export. Independent Swedish content should remain.
6. Reactivate Cathy. Her withdrawn material must remain private.
7. Share chosen material back to the existing entry and accept it there.
8. Optionally enable two-person membership decisions and confirm that the
   proposer cannot approve their own request or bypass it via invitations.

## Check in and deploy after laptop acceptance

```bash
cd /home/github/c-lara-2
git diff --cached --check
git diff --cached --stat
git commit -m "Add contribution provenance, private collections and inactive memberships"
git push
```

On AWS, take a verified database snapshot and the normal private-media backup.
Schedule a brief maintenance window: this data migration must run without
concurrent dictionary writes. Use the normal environment, stop Gunicorn and
Django-Q before migration, run `check`, `migrate` and `collectstatic --noinput`,
then restart and inspect the service status. Keep the old code/database available
until the initial checks pass. Do not restore an older backup after live users
have withdrawn material without reconciling those withdrawals.

## Evidence and boundaries

118 Django tests pass, including historical-schema migration, field-specific
conflicts, private media/search/export restrictions, delegated attribution,
dependent-copy withdrawal, inactive-member controls, and governance decisions.
A disposable Chromium rehearsal passes at phone and desktop viewports using
synthetic media and separate accounts; it exercises creation, review, independent
attribution, inactivation, withdrawal, reactivation and explicit resharing.
The suite uses SQLite. PostgreSQL lock scopes are explicit, but a live AWS
PostgreSQL upgrade and physical-phone acceptance remain pending. No provider
calls, remote commits, production data access or deployment were performed.
