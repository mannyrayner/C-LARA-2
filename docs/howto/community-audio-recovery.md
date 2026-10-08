# Returning to an example after repairing its audio

7 October 2026. Incremental patch on top of the deployed picture/audio fixes
(GitHub main observed at `0659b966efa21cb769a0f0913b4347c98234357b`).
No migration, dependency, settings, nginx or service-unit change is needed.

## What this fixes

After an automatic recording fails, an accepted replacement saved from the word's
entry should be usable wherever that word is linked. The ordinary server lookup
already finds that recording. Two presentation gaps are repaired:

- Returning to a browser-restored example, or to a tab that was hidden, rechecks its
  audio with a read-only request even after all original audio jobs have finished.
  Changed recordings appear without a full-page reload. Open translations and
  unchanged players are retained. Unsaved vocabulary forms are not refreshed.
- A saved example no longer shows an old timeout warning once the displayed entry
  has a valid, accepted recording. Historical attempts, diagnostics and charges
  are retained. No generation or charge is triggered by these refreshes.

This is a plausible explanation of Manny's `i bakgrunden` recovery problem, not
proof that his browser used its history cache. The original provider timeout and
whether that replacement was saved/accepted are not independently observed.

**Immediate check with the current version:** after creating a replacement, use
**Save audio to entry** (and publish/accept it as appropriate), then reload the
example. Generation alone creates a private preview. A pending contribution needs
an editor's acceptance. If an accepted recording still fails to appear after a
reload, preserve the word and example URLs for diagnosis; do not generate it again.

## Laptop

Stop runserver. Download `community_dictionary_audio_recovery.patch` to `/home/github/`.
Start from clean main with the preceding picture/audio patch already committed.

```bash
cd /home/github/c-lara-2
git status --short
git apply --check ../community_dictionary_audio_recovery.patch &&
git apply --index ../community_dictionary_audio_recovery.patch &&
git diff --cached --check
cd platform_server
../.venv/Scripts/python.exe -E manage.py check &&
../.venv/Scripts/python.exe -E manage.py test community_dictionary &&
../.venv/Scripts/python.exe -E manage.py migrate --check
```

Expect **338 tests**, ending `OK`. Simulated timeout messages during tests are
expected. There are no migrations to apply. Restart:

```bash
../.venv/Scripts/python.exe -E manage.py runserver --insecure
```

Test an example with a missing word recording. From its word page, open the original
entry, create a preview and save/publish it. Return to the example using Back or a
previously open tab: Listen should become available and the old error should disappear.
The same accepted audio should be available on the ordinary sentence page. A normal
refresh remains a fallback if the browser does not restore the page as expected.

## Check in after acceptance

```bash
cd /home/github/c-lara-2
git diff --cached --stat
git diff --cached --check
git diff --name-only
git status --short
```

The patch is already staged. Expect only Community Dictionary code/tests and
accompanying docs/global-state records; keep databases, backups and credentials out
of Git. If the staged changes are expected and the unstaged diff is empty:

```bash
git commit -m "Refresh repaired dictionary audio when returning to examples" &&
git push origin main &&
git rev-parse HEAD &&
git status --short
```

## AWS

Let active AI jobs finish before this brief shared-site interruption. This is a
code/static update only; retain normal backups, with no special database operation.

```bash
sudo -iu ssm-user
cd /srv/C-LARA-2
umask 022
git branch --show-current
git status --short
. .venv/bin/activate
set -a && . /etc/clara2.env && set +a
```

Expect clean main. Then:

```bash
sudo systemctl stop gunicorn-clara2 djangoq-clara2 project-understanding-worker &&
git pull --ff-only origin main &&
git rev-parse HEAD
```

Compare the printed SHA with the laptop commit; stop on a mismatch/error. Continue:

```bash
cd /srv/C-LARA-2/platform_server
python manage.py check &&
python manage.py migrate --check &&
python manage.py collectstatic --noinput &&
sudo systemctl restart gunicorn-clara2 djangoq-clara2 project-understanding-worker
sudo systemctl status --no-pager gunicorn-clara2 djangoq-clara2 project-understanding-worker
```

Keep DEBUG=False; no nginx restart or daemon-reload is needed. Stop on failed checks
rather than applying unexpected migrations. All services should stay active.
Refresh once to load the new script, then retry navigation to the existing example.
No new audio generation is needed if the replacement was already saved and accepted.

If an accepted replacement is still missing after a full refresh, record the word
and example URLs and whether the word's entry lists the recording as Accepted.
A new provider timeout can be diagnosed with:

```bash
sudo journalctl -u gunicorn-clara2 -u djangoq-clara2 \
  --since "2 hours ago" --no-pager \
  --grep='Capture speech.*failed|Audio study.*failed'
```

Manny's planned fresh-eye test with Cathy should guide subsequent workflow changes;
this patch deliberately addresses audio recovery without restructuring the workflow.
