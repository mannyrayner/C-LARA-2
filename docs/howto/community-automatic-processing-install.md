# Install and try fully automatic processing

Patch: `community_dictionary_automatic.patch`.
Baseline: `7eebb12` — Improve language-port estimates, CJK vocabulary and audio recovery.

This update has **no migration, requirements, static-file or environment changes**.
It reuses the deployed queue, including the tested local Django-Q fallback on AWS.
Do not change `USE_REAL_DJANGO_Q` for this update. Normal database/media backups
remain appropriate; no special full-media archive is needed for this code-only change.

## 1. Laptop installation

Let current AI work finish, then stop the local server/worker. Save the patch in
`/home/github/`, beside the checkout. Inspect the tree before applying; if it is
not clean, preserve the unexpected changes and stop rather than resetting them.

```bash
cd /home/github/c-lara-2
git status --short
git log -1 --oneline
git apply --check ../community_dictionary_automatic.patch &&
git apply --index ../community_dictionary_automatic.patch &&
git diff --cached --check
```

Run checks; proceed only when the final test result is `OK`:

```bash
cd /home/github/c-lara-2/platform_server
../.venv/Scripts/python.exe -E manage.py check &&
../.venv/Scripts/python.exe -E manage.py test community_dictionary projects.tests.test_admin_tools projects.tests.test_email_reset projects.tests.test_profile &&
../.venv/Scripts/python.exe -E manage.py migrate --check
```

The suite contains 654 tests. Mocked timeouts and simulated failure tracebacks are
expected; they do not replace the final `OK`. No migration should be pending.

```bash
../.venv/Scripts/python.exe -E manage.py runserver --insecure
```

Restart a separately managed local qcluster only if that is your existing setup.
The local fallback does not require starting an extra worker.

## 2. Small laptop trial

1. Use a test dictionary with two or three pictures lacking sentences and AI
   picture-description/TTS enabled. In **Settings → Add missing sentences to
   pictures**, choose **Create everything automatically**. Select the intended
   picture statuses, including awaiting-review pictures if wanted.
2. Read the combined estimate and publication permission, then **Approve and
   create everything**. Refresh progress as needed; there should be no sentence
   or vocabulary acceptance step. Check the resulting sentence, word links and
   playable audio. The label must say it was published automatically, without
   human review. Existing contributors should retain their picture attribution.
3. In **Settings → Create a language version**, choose a small conversion and the
   same automatic mode. Confirm both languages and the estimate. Check that words
   derive from the translated sentences and share pages when appropriate.
4. Repeat an estimate for a completed job. It should skip completed work rather
   than translate everything again. If a real audio/provider failure occurs,
   **Retry incomplete work — show estimate** should keep the successes. Do not
   manufacture paid failures just to test this; the regression suite covers them.
5. Check that **Review step by step** is still available. On a standard workflow
   suggestion's estimate, **Estimate fully automatic processing instead** should
   produce a combined quote, without charging or starting the old quote.

For a credit-funded completed job, inspect the read-only audit:

```bash
../.venv/Scripts/python.exe -E manage.py community_credit_audit --username 'mannyrayner'
```

Expect zero held for completed root/child runs and zero reconciliation warnings.
There are two linked ledger runs internally; their charges together must stay
within the original approved allowance plus any explicitly approved top-up.
Existing unrelated jobs may still hold credit.

## 3. Check in after laptop acceptance

```bash
cd /home/github/c-lara-2
git diff --cached --check
git diff --cached --stat
git status --short
git commit -m "Add fully automatic dictionary description and language conversion" &&
git push origin main &&
git rev-parse HEAD
```

Keep the printed commit ID. The patch is already staged; do not add databases,
media, environment files or unrelated local material.

## 4. AWS deployment

Choose a quiet interval and let active AI jobs finish. This restarts both apps.

```bash
sudo -iu ssm-user
umask 022
cd /srv/C-LARA-2
git branch --show-current
git status --short
git fetch origin
git log --oneline HEAD..origin/main
CLARA_AUTOMATIC_OLD_SHA=$(git rev-parse HEAD)
git rev-parse HEAD
```

Expect `main`, a clean tree, and the tested commit in the incoming log. Define the
protected-environment helper:

```bash
clara_manage() {
  sudo systemd-run --quiet --wait --pipe --collect \
    --property=User=ubuntu \
    --property=Group=www-data \
    --property=WorkingDirectory=/srv/C-LARA-2/platform_server \
    --property=EnvironmentFile=/etc/clara2.env \
    /srv/C-LARA-2/.venv/bin/python manage.py "$@"
}
```

After active jobs finish:

```bash
sudo systemctl stop gunicorn-clara2 djangoq-clara2 project-understanding-worker
git merge --ff-only origin/main &&
clara_manage check &&
clara_manage migrate --check &&
clara_manage community_queue_check --tasks 20
```

Stop if a check fails. The queue check should complete 20/20 probes, respect its
configured concurrency limit and leave no task connections open. **It is valid
for it to print `/srv/C-LARA-2/src/django_q/tasks.py`.** This is the patched,
bounded fallback that has already passed on AWS. The obsolete real-Django-Q
assertion in the previous installation document is corrected by this patch.

No pip install, collectstatic, nginx restart or environment edit is needed here.

```bash
sudo systemctl start gunicorn-clara2 djangoq-clara2 project-understanding-worker
sudo systemctl status --no-pager gunicorn-clara2 djangoq-clara2 project-understanding-worker
git rev-parse HEAD
```

Compare the SHA with the laptop commit. Check an existing public dictionary and a
member entry, then repeat the small automatic trial before a large conversion.
After it finishes:

```bash
clara_manage community_credit_audit --username 'mannyrayner'
```

Record the combined estimate, actual charge, any pauses/failures, and whether the
result and navigation make sense. The first automated checks used mocked providers
on Linux/SQLite; this trial supplies actual provider/AWS evidence.

## If deployment fails

Keep `DEBUG=False`. Inspect:

```bash
sudo journalctl -u gunicorn-clara2 -u djangoq-clara2 \
  --since '10 minutes ago' -n 160 --no-pager
```

Before any automatic job has been approved, the previous code can be restored to
the saved SHA with services stopped and a clean tree. Once automatic jobs exist,
prefer a forward repair: older code does not understand their linked continuation
and reserved vocabulary allowance. Do not manually reset balances, delete jobs or
restore a whole database over new contributions.
