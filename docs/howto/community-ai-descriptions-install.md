# Community Dictionaries: AI-suggested descriptions

8 October 2026. Incremental patch for the accepted visibility release, observed on
GitHub main at `6a9de727f00476b80a3062a807c54e6131da12f0`.
No new migration, dependency or settings change. Earlier migrations through 0017
must already be applied. Stop on an unexpected error; do not reapply earlier patches.

## Laptop

Stop runserver. Save `community_dictionary_ai_descriptions.patch` in `/home/github/`.
Start from clean main with the preceding changes committed:

```bash
cd /home/github/c-lara-2
git branch --show-current
git status --short
```

Expect `main` and no status output. Then:

```bash
git apply --check ../community_dictionary_ai_descriptions.patch &&
git apply --index ../community_dictionary_ai_descriptions.patch &&
git diff --cached --check
cd platform_server
../.venv/Scripts/python.exe -E manage.py check &&
../.venv/Scripts/python.exe -E manage.py test community_dictionary &&
../.venv/Scripts/python.exe -E manage.py migrate --check
```

Expect **365 tests**, ending `OK`. Deliberate simulated timeout/failure messages
are expected inside tests. There are no migrations in this patch; `migrate --check`
verifies the existing database is current. If it reports unapplied migrations,
stop and identify the missing earlier update before continuing.

Restart as usual:

```bash
../.venv/Scripts/python.exe -E manage.py runserver --insecure
```

Refresh the browser once. The stylesheet and both scripts have new version URLs.

## First experiment

Use a dictionary with **Settings → Enable Picture descriptions (OpenAI)** and saved
spoken audio enabled. These are the existing options; no new AI switch is required.

1. Open an accepted image's entry. Under **Describe this picture**, select
   **Suggest a description**, then **Continue**.
2. Choose the feedback language, confirm the cost/data permission, then
   **Prepare suggestion**. No typed description or recording is required.
3. Review the two language versions and words. Try **Change this description** on
   one image: the proposed wording should be prefilled in your feedback language.
4. Choose **Yes — save and share**. Check the sentence, vocabulary links and audio.
5. Open **Next picture**: the AI option should still be selected. Try switching to
   Type and Speak; each uses the same normal review/save flow.

Also try starting with a new camera/upload image through **Describe a picture**.
The old **Learn from this photo** link is hidden where the unified workflow is
available; it remains the fallback when Picture descriptions is disabled or the
image is not yet accepted. AI suggestions remain fallible and can be corrected.

## Check in after acceptance

The patch is already staged. Inspect it:

```bash
cd /home/github/c-lara-2
git diff --cached --stat
git diff --cached --check
git diff --name-only
git status --short
```

Expect only Community Dictionary code/tests and associated documentation/state
records, with no unstaged changes. Keep databases, backups and keys out of Git.
Then:

```bash
git commit -m "Unify picture descriptions with typed spoken and AI input" &&
git push origin main &&
git rev-parse HEAD &&
git status --short
```

## AWS after laptop acceptance

Allow active AI jobs to finish. This is a short shared-site code/static update;
normal backups remain appropriate, with no special migration or media archive.

```bash
sudo -iu ssm-user
cd /srv/C-LARA-2
umask 022
git branch --show-current
git status --short
. .venv/bin/activate
set -a && . /etc/clara2.env && set +a
```

Expect clean main, then:

```bash
sudo systemctl stop gunicorn-clara2 djangoq-clara2 project-understanding-worker &&
git pull --ff-only origin main &&
git rev-parse HEAD
```

Check that SHA matches the laptop commit. Continue only if it does:

```bash
cd /srv/C-LARA-2/platform_server
python manage.py check &&
python manage.py migrate --check &&
python manage.py collectstatic --noinput &&
sudo systemctl restart gunicorn-clara2 djangoq-clara2 project-understanding-worker
sudo systemctl status --no-pager gunicorn-clara2 djangoq-clara2 project-understanding-worker
```

Keep DEBUG=False. No nginx restart, daemon-reload or dependency installation is
needed for this patch. All services should remain active. Refresh once, then repeat
the experiment from the phone. Local verification used mocked providers and Linux
Chromium; live image quality, listening and physical-phone behaviour need your trial.
