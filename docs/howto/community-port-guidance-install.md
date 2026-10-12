# Install language-version workflow suggestions

Patch: `community_dictionary_port_guidance.patch`.
Baseline: main `577343213cb603ee846057313bae0c1b4ba92721`
(`Add public practice and owner workflow guidance`).

This is a code/template update: **no database migration, dependency installation,
environment change or collectstatic is required**. The prior migration 0022 must
already be applied. Normal backups should continue; this update does not need
another large media archive.

## 1. Laptop installation

Stop the laptop development server. Save the patch in `/home/github`, beside
the repository, then check the starting state:

```bash
cd /home/github/c-lara-2
git status --short
git log -1 --oneline
```

Expect a clean tree at the baseline above, or a later compatible commit. Do not
discard unrelated changes. Apply and check:

```bash
git apply --check ../community_dictionary_port_guidance.patch &&
git apply --index ../community_dictionary_port_guidance.patch &&
git diff --cached --check
```

```bash
cd /home/github/c-lara-2/platform_server
../.venv/Scripts/python.exe -E manage.py check &&
../.venv/Scripts/python.exe -E manage.py test community_dictionary projects.tests.test_email_reset projects.tests.test_admin_tools projects.tests.test_profile &&
../.venv/Scripts/python.exe -E manage.py migrate --check
```

Expected at this revision: **609 tests, OK**. Tests deliberately simulate and log
some failures; the final result is what matters. Stop on a failed check.

```bash
../.venv/Scripts/python.exe -E manage.py runserver --insecure
```

## 2. Short acceptance check

Use a Swedish source and its existing French language version, owned by the
same account, with the relevant AI features and workflow suggestions enabled.

1. Finish any earlier reviews and vocabulary stages. Add and accept a new
   Swedish sentence, or use the existing batch workflow for a new picture.
2. After local tasks are complete, both dictionary cards should show an update
   notice. Follow the French notice. Check its new/changed counts, destination,
   estimated cost, voice, payer and any protected entries.
3. If the scope and small test cost are acceptable, approve the update. Review
   and save the French sentence; then follow the word-suggestion step. Confirm
   links match the accepted French sentence. The completed notice should go away.
4. Optionally edit a French sentence and change its Swedish source. A subsequent
   update must preserve the French correction. Other new sentences can still be
   ported. No update is offered when only protected entries remain.
5. Turn the French dictionary's workflow suggestions off: its update notices
   disappear at both ends. Turn them back on. Turning off only Swedish guidance
   should still allow French to show its own update notice.

The existing manual language-port controls remain available. A higher-priority
review, membership request or local generation step may be shown first.

## 3. Check in after laptop acceptance

```bash
cd /home/github/c-lara-2
git diff --cached --check &&
git diff --cached --stat
git status --short
git commit -m "Guide incremental updates to dictionary language versions"
git push
git rev-parse HEAD
```

Keep the new SHA for comparison on AWS. No database or backup file belongs in
this commit.

## 4. AWS preparation, while online

Finish running AI jobs before stopping workers. In one shell:

```bash
sudo -iu ssm-user
umask 022
cd /srv/C-LARA-2
git branch --show-current
git status --short
git fetch origin
git log --oneline HEAD..origin/main
git rev-parse origin/main
```

Expect `main`, a clean tree and your intended commit. Stop for unexpected changes.
Define the usual service-context command; it loads the protected environment
without exposing credentials or changing its permissions:

```bash
clara_manage() {
  sudo systemd-run --quiet --wait --pipe --collect \
    --property=User=ubuntu \
    --property=Group=www-data \
    --property=WorkingDirectory=/srv/C-LARA-2/platform_server \
    --property=EnvironmentFile=/etc/clara2.env \
    /srv/C-LARA-2/.venv/bin/python manage.py "$@"
}
clara_manage check &&
clara_manage migrate --check
CLARA_PORT_GUIDANCE_PREVIOUS=$(git rev-parse HEAD)
printf 'Pre-update commit: %s\n' "$CLARA_PORT_GUIDANCE_PREVIOUS"
```

## 5. Brief AWS update

Both apps share these services and will be briefly unavailable:

```bash
sudo systemctl stop gunicorn-clara2 djangoq-clara2 project-understanding-worker &&
git merge --ff-only origin/main &&
clara_manage check &&
clara_manage migrate --check &&
sudo systemctl start gunicorn-clara2 djangoq-clara2 project-understanding-worker

sudo systemctl status --no-pager gunicorn-clara2 djangoq-clara2 project-understanding-worker
git rev-parse HEAD
```

If a command fails, stop and retain the error rather than continuing past it.
No nginx restart, daemon-reload, pip installation or collectstatic is needed for
this patch. The previous practice update did change JavaScript and required
collectstatic; its runbook now includes the verified static-directory ownership
repair for that deployment.

## 6. AWS acceptance

Log in and open the Swedish and French dictionaries. Your six newly accepted
Swedish sentences should be proposed if not already ported. Finish any earlier
review/vocabulary prompt first. Check the count and cost before approving, then
review sentences followed by their French word suggestions. Verify a few linked
word pages and audio files. Try the notices on a phone as well.

Keep the prior SHA until acceptance. If rollback is needed, stop services and
revert only this commit through the normal repository workflow, then redeploy.
There is no schema reversal and no reason to restore an old database over new
contributions for this code update. Report any failure before attempting a
broader rollback.
