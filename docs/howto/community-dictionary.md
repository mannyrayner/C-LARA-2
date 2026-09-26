# Community dictionary: setup and testing

Status as of 26 September 2026: the implementation and microphone/text repairs
are on `main` and deployed alongside ordinary C-LARA-2 on AWS. Manny reports
successful laptop use on that server and a first physical-phone trial: Cathy
took and saved a picture on her phone, then Manny added a recording. See the
[AWS/phone trial record](../../experiments/community_dictionary/aws-phone-trial-2026-09-25.md)
for the evidence and limits. Phone/browser details and a broader compatibility
matrix remain unrecorded. The Icelandic pilot has been invited but not reported.
`DEBUG = False` is confirmed on the server; remaining deployment warnings about
cookies, redirects and HSTS still need resolution with the nginx configuration.
The next proposed increment adds optional image generation and TTS; it is
specified in the [AI-media and maintenance roadmap](../roadmap/community-dictionary-ai-and-maintenance.md).
Those features and a write-capable operational agent are not installed by the
documentation update. The existing explanation Assistant remains read-only. The later same-day
[situated-learning proposal](../roadmap/community-dictionary-ai-and-maintenance.md#later-26-september-direction-sentences-grounded-in-experience)
adds sentences about pictures, links to earlier entries and personal-history adaptation
to the proposed direction; these are also unimplemented.

- [Specification](../roadmap/community-dictionary.md)
- [App boundary](../../platform_server/community_dictionary/README.md)
- [Existing platform setup](run-django-platform.md)
- [Existing server administration](server-admin-tasks.md)
- [Initial stakeholder report](../publications/community_dictionaries_initial/README.md)

## Current installation

Use the current `main` branch and the normal server deployment procedure below.
Do not reapply the historical prototype or repair patches to `main`; their
changes are included in implementation commit `692e44d`. Private media storage,
database migrations and `collectstatic` remain part of initial server setup.
As of `a7e8870`, the shared settings hardcode `DEBUG = False`, including on a
laptop. A local development configuration must explicitly enable debug mode
to use Django's normal development static/public-media serving; production
nginx already serves those public paths. Environment-specific settings are a
pending configuration improvement, not an implemented environment switch.

## Historical instructions: update an installed prototype 1

These instructions describe the earlier patch installation before merge to `main`.

Save `community_dictionary_repair_02.patch` one directory above the checkout.
Preserve unrelated local edits, then run from the repository root:

```bash
git switch feature/community-dictionary-prototype
git apply --check ../community_dictionary_repair_02.patch
git apply ../community_dictionary_repair_02.patch
cd platform_server
python manage.py test community_dictionary
python manage.py runserver
```

Apply only if the check succeeds. This patch is based on the delivered prototype
1 file contents; a different commit message or SHA does not matter. It needs no
new dependency or database migration. Restart the local server and hard-refresh
(**Ctrl+F5** on Windows). On the deployed server, also run the existing
`collectstatic` and service-restart steps so the new recorder script is served.

Choose **Check microphone**, grant access and speak. The input level should move.
If it stays still, stop the check, select the input used successfully in Audacity,
and check again. Device names may appear only after permission is granted.
Record, stop and listen before sharing. Detected silent takes are not saved and
do not replace an earlier recording. If this still fails, report the browser
version, selected input, level-meter behavior and displayed message.

For existing entries, **Add words** or **Edit words** opens the visible word,
translation/meaning and category fields. For example, enter `katt` and `cat`,
then **Save words**. Either can be searched in Browse; category filtering is
also available. Members' proposed changes still need editor acceptance. For new
entries, all three fields are visible below the picture/voice controls and remain
optional. Existing pictures and recordings are retained.

After reviewing the repair, commit from the repository root:

```bash
git add platform_server/community_dictionary experiments/community_dictionary \
  docs/howto/community-dictionary.md docs/global_workspace
git diff --cached --check
git diff --cached --stat
git commit -m "Improve community dictionary recording and word discovery"
git push
```

## Historical instructions: apply the functional patch

These instructions describe the original bootstrap-to-prototype installation.

Save `community_dictionary_prototype_01.patch` one directory above the checkout.
With unrelated work preserved and the working tree clean, run from the repo root:

```bash
git switch feature/community-dictionary-prototype
git rev-parse HEAD
git apply --check ../community_dictionary_prototype_01.patch
git apply ../community_dictionary_prototype_01.patch
```

The recorded HEAD is `bc21188595bae9f2ee89c080243a76fdd4a960b1`. Run the
application command only if the check succeeds. Inspect conflicts if your
branch has moved; do not force application.

Activate the existing development environment, or create one:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt -r requirements-dev.txt
cd platform_server
python manage.py check
python manage.py makemigrations --check --dry-run community_dictionary
python manage.py test community_dictionary
python manage.py migrate
python manage.py runserver
```

The migration is included; do not generate a replacement. The new dependency
is Pillow, used to validate, resize and strip metadata from pictures. Use a
local development database for tests, with no production database environment
variables set. The tests use temporary private media and require no AI keys.

Open `http://127.0.0.1:8000/community-dictionaries/` and log in with an existing
C-LARA account. For a fresh local database, `python manage.py createsuperuser`
creates an initial login. Additional test accounts can be created through the
existing administration interface. The app sends no invitation emails.

After reviewing the patch and checks, stage its changes and commit from the
repository root:

```bash
git add .gitignore .github/workflows/ci.yml requirements.txt \
  platform_server/platform_server/settings.py platform_server/platform_server/urls.py \
  platform_server/community_dictionary docs/README.md \
  docs/roadmap/community-dictionary.md docs/howto/community-dictionary.md \
  experiments/community_dictionary docs/global_workspace
git diff --cached --check
git diff --cached --stat
git commit -m "Implement community dictionary construction prototype"
git push
```

## First use

1. Create a dictionary, for example “Svenska tillsammans”, with Swedish as its
   language. The owner can contribute and accept their own material immediately.
2. Under **People**, invite an existing account by username. The invited person
   opens **Community dictionaries** and accepts. Membership does not send an email.
3. Create a named partnership with another joined dictionary member. They accept
   that separate invitation under **People**.
4. Choose **Contribute**, take/choose a picture or record audio, listen, confirm
   permission to share and submit. Written information is optional.
5. On the entry, choose **Ask partners**, select the partnership and request audio
   or a picture. An explanation may be written or spoken.
6. The partner opens **For our group**, responds on the same entry, and discusses
   it. An editor accepts the response; the request becomes complete. Try the
   reverse direction as well.

**Awaiting review** shows pending contributions; **Accepted** is the default
browse view. Contributions and versions preserve attribution. **Edit words**
proposes a complete wording revision; older accepted wording remains until
review. A stale proposal produces a conflict message. An editor can restore an
accepted wording version or choose another accepted main picture. Owners manage
roles and dictionary settings under **People**. Dictionary access remains private.

## Deploy through the existing server

Use the normal server runbook and preserve its existing environment/security
configuration. Before deploying, back up the database and existing platform media.
Deploy from `main`, which now includes the dictionary implementation and repairs.

For the documented `/srv/C-LARA-2` installation, create private storage owned
by the application service account (the existing runbook uses `ubuntu:www-data`):

```bash
sudo install -d -m 2770 -o ubuntu -g www-data /srv/C-LARA-2/platform_server/private_uploads/community_dictionary
```

The default location is that directory. Alternatively set
`CLARA_COMMUNITY_MEDIA_ROOT` in `/etc/clara2.env` to another private, writable
absolute path. Do not put it under public `media` or `staticfiles`, or create an
nginx alias for it. Django checks the configured public roots; an operator must
also check any other nginx aliases. Media is served through authenticated views.

After pulling the reviewed `main` commit, activate the environment and run:

```bash
cd /srv/C-LARA-2
. .venv/bin/activate
python -m pip install -r requirements.txt
cd platform_server
set -a
. /etc/clara2.env
set +a
python manage.py check
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart gunicorn-clara2
```

The app uses no task worker. Follow the existing runbook if other changes in the
deployed commit require worker restarts. Verify ordinary C-LARA login/project
access as well as `/community-dictionaries/`.

Use HTTPS for phone recording. In the existing nginx server block, permit a
request body large enough for a picture plus a recording, for example
`client_max_body_size 32m;`. Each individual file is limited to 15 MiB by the app.
Run `sudo nginx -t` before reloading nginx if its configuration changes. Keep
normal production TLS, session and debug settings from the existing deployment;
this feature patch does not replace the platform's deployment configuration.

## Drafts, recovery and removal

Text, selected photos and completed recordings are saved in IndexedDB where the
browser permits it. The page says whether a draft is local, sharing is in progress,
or the server has confirmed receipt. A retry carries the same submission ID;
the database commits the receipt and contributions together. Reusing an ID with
changed content gives a conflict, rather than overwriting an earlier submission.

Reloading the same form under the same account restores its draft. Keep the
page open if local storage is unavailable. An active recording is not saved
until it stops. Browser data clearing, eviction, private browsing policies and
a device change can lose local drafts. This is not an offline app: opening pages,
retrieving others' work and submitting need a connection. Drafts persist on that
browser after logout, so avoid shared browser profiles for sensitive material;
**Discard local draft** removes the saved draft for that form.

Editors can remove contributions or entire entries, with a confirmation. Media
files are deleted after the database transaction commits; removed contributions
retain a minimal attribution/status record, with their content cleared. Server
backups and existing owner exports may still contain earlier copies. Changing
membership removes future server access but cannot recall files already downloaded.

## Export, backup and restoration

The owner's **Export dictionary** button downloads a ZIP containing:

- `manifest.json`: format/version, dictionary ID, original contributor IDs and usernames;
- `records.json`: Django records for the dictionary, members, partnerships, entries,
  individual contributions, requests and activity events;
- `media/`: files matching contribution `file_path` values;
- `README.txt`: package interpretation.

It excludes passwords, email addresses and submission receipts. It is an interchange
export, not a one-click import or a complete server backup. Retain usernames/IDs
when moving data; a new installation needs explicit user and record-ID mapping.

For operational recovery, back up **both the complete platform database and the
private media directory**, alongside the existing public media backup. Include
auth accounts and submission receipts. Stop writers during the snapshot so the
database and media refer to the same point in time. Use the installed database's
normal backup tool: SQLite's backup API for SQLite, `pg_dump`/`pg_restore` for
PostgreSQL. Preserve service permissions and the deployed commit/dependencies.

For a local SQLite restoration rehearsal, stop the development server, copy
`platform_server/db.sqlite3` and the configured private media directory into a
dated backup directory, then restore those copies into a separate test checkout
with the same commit and media setting. Never rehearse by overwriting production.
Run `manage.py check`, log in as both contributors, play media, inspect the group
queue and review history, and retry a recorded submission. The automated fixture
restore test checks IDs, attribution, requests and media bytes; it does not replace
this full operational rehearsal on the actual server/database.

## Phone trial and feedback packet

Record the installed commit, phone model, OS and browser version. Run on one
actual iPhone/Safari and one Android/Chrome device; they have not been selected
or tested in this development environment.

- Take a photograph and record without entering a target-language word. Listen,
  rerecord, submit, reload and check the saved result.
- Have the other account request/respond/discuss/review in both directions.
  Play each phone's recording on the other phone. Add a third partner if available.
- Deny microphone permission, recover, and try choosing an existing audio file.
  Try camera capture and gallery selection. If a HEIC image cannot be decoded,
  choose/export a JPEG; supported server image formats are JPEG/PNG/WebP/GIF.
- Make a draft, reload and recover it. Temporarily disconnect during an upload,
  reconnect and retry; verify there is one contribution. Also check the honest
  warning when local draft storage is unavailable.
- Propose conflicting wording changes; review one, check the conflict on the
  other, restore an older version, and remove test media.
- Verify a non-member cannot open copied entry/media links. Export the test
  dictionary and rehearse a backup restoration in a separate environment.
- After a short introduction, try the central tasks without live coaching.
  Record confusing steps, editor effort, enjoyment and whether you want to continue.

Browser recording selects a supported MP4/WebM/Ogg format; uploaded WAV/MP3 are
also supported. This prototype does not transcode audio, so cross-device playback
is a specific acceptance check. Long recordings, background recording, full offline
use, public dictionaries, AI media generation and practice are outside this build.

Send one consolidated report with successes, failures, reproduction steps and
screenshots/log excerpts without credentials or private community media. That
report initiates the next repair iteration.
