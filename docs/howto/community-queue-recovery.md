# Background queue connection recovery — 9 October 2026

The AWS incident was database connection exhaustion. A later diagnostic succeeded:
all Community Dictionaries migrations through 0018 were applied, PostgreSQL allowed
79 connections, and only one application connection was present during the check.
The deployed queue resolved to `src/django_q/tasks.py`, with
`USE_REAL_DJANGO_Q=False`. This is the local thread-based fallback. Previously it
ignored `Q_CLUSTER['workers']` and did not close task connections explicitly.

The repair closes all thread-local database connections after each asynchronous
task and hook, including failures. It limits active task bodies and cleanup to
`Q_CLUSTER['workers']` per process (default two, bounded between one and eight).
Synchronous tasks retain their caller's transaction. With three Gunicorn workers
and the current setting, the fallback permits up to six active background tasks
across those workers, in addition to request and other service connections.

This is a focused containment fix. Waiting tasks remain daemon threads in memory;
they do not survive process restarts. The stub `qcluster` service does not execute
them. Do not switch `DJANGO_Q_USE_REAL` during this recovery: durable queue setup,
migrations and deployment need a separate checked change. Do not increase RDS
connection limits as a substitute for cleanup.

Request tracebacks now go to stderr/the service journal with `DEBUG=False`.
Public error pages remain generic. Treat traceback logs as operational information
and redact sensitive request details before sharing them.

## Laptop: apply and test

Download `community_dictionary_queue_recovery.patch` beside the repository. Stop
the laptop development server. Review `git status --short` first; do not overwrite
unrelated local changes. This incremental patch follows the two-stage vocabulary
release and adds no migration, dependency or static asset.

```bash
cd /home/github/c-lara-2
git status --short
git apply --check ../community_dictionary_queue_recovery.patch &&
git apply --index ../community_dictionary_queue_recovery.patch
git diff --cached --check

cd platform_server
../.venv/Scripts/python.exe -E manage.py check &&
../.venv/Scripts/python.exe -E manage.py test community_dictionary projects.tests.test_admin_tools
```

The eight focused new tests can also be run as
`manage.py test community_dictionary.tests.test_background_queue`. The full suite
intentionally exercises failures; the new logging may print their tracebacks.
The final unittest `OK`/`FAILED` result determines whether the run passed.

For a file-backed laptop database, run the following read-only probe too:

```bash
../.venv/Scripts/python.exe -E manage.py community_queue_check --tasks 20
```

It executes only `SELECT 1`, never contacts an AI provider, and checks that every
completed task has released its connection. It deliberately rejects in-memory
SQLite and unpatched/external queue implementations. Expect 20/20 completed, a
peak of at most two with current settings, zero remaining task connections and
`Queue check passed`.

Once tests pass, review the staged files, then commit and push:

```bash
cd /home/github/c-lara-2
git diff --cached --stat
git commit -m "Close fallback task DB connections and bound concurrency"
git push
git status --short
```

## AWS: short restart and read-only verification

Keep new AI jobs paused. From the current login:

```bash
sudo -iu ssm-user
umask 022
cd /srv/C-LARA-2
git branch --show-current
git status --short
git rev-parse HEAD
```

Expect the intended deployment branch (`main`) and a clean working tree; retain
the printed commit ID. Stop if that is not what you see. The next step briefly
takes both applications offline. No database/media changes or backup operation
are needed for this patch itself.

```bash
sudo systemctl stop gunicorn-clara2 djangoq-clara2 project-understanding-worker &&
git pull --ff-only
```

If this fails, stop and inspect the error. Do not continue with a mixed release.
Do not run `pip install`, `migrate`, `collectstatic` or edit `/etc/clara2.env` for
this patch. The existing 0018 migration has already been confirmed applied.

Use systemd to read the protected environment file and run as the normal app
user. Do not loosen the file's permissions or run Django as root:

```bash
sudo systemd-run --wait --pipe --collect \
  --property=User=ubuntu \
  --property=Group=www-data \
  --property=WorkingDirectory=/srv/C-LARA-2/platform_server \
  --property=EnvironmentFile=/etc/clara2.env \
  /srv/C-LARA-2/.venv/bin/python manage.py shell -v 0 -c \
  "from django.core.management import call_command; call_command('check'); call_command('community_queue_check', tasks=20)"
```

Proceed only if both checks pass, especially **zero task connections left open**:

```bash
sudo systemctl start gunicorn-clara2
sudo systemctl status --no-pager gunicorn-clara2
```

Log in, open the dictionary list and an entry, and check ordinary C-LARA-2 too.
If successful, restore the other previously used services:

```bash
sudo systemctl start djangoq-clara2 project-understanding-worker
sudo systemctl status --no-pager gunicorn-clara2 djangoq-clara2 project-understanding-worker
```

The stub djangoq service still prints a notice that it does not execute work.
Starting it does not convert this installation into a durable queue. No nginx
restart or systemd daemon reload is required because neither configuration changed.

If a service/check fails, leave AI work paused and inspect:

```bash
sudo journalctl -u gunicorn-clara2 -u djangoq-clara2 \
  -u project-understanding-worker --since "10 minutes ago" -n 160 --no-pager
```

Keep `DEBUG=False`. The read-only check proves cleanup in a fresh process; browser
checks prove the restarted web process loaded successfully. Neither proves
long-run production stability. If the patch must be reverted, revert its commit
through the normal Git workflow and restart with AI jobs paused; reverting also
removes the cleanup safeguard, so do not resume the large job on that code.

## Resume work deliberately

Do not recreate the entire conversion merely because the server restarted.
Previously saved entries and review results remain in the database. Open the
existing conversion run and inspect its counts. **Resume waiting work** enqueues
waiting/queued records; old running attempts (over 15 minutes) are marked failed
rather than automatically sending a possibly already charged request again.
Recovery handles vocabulary audio too. Review failed or uncertain results before
approving another paid attempt. Resume one run first, while confirming ordinary
browsing continues to work; report its outcome before starting several large runs.

If connection exhaustion returns, capture the private journal traceback and a
connection census where access is possible. Pause background services and restart
Gunicorn to release its fallback task connections. This can interrupt in-flight
AI calls, so return to the existing run rather than silently repeating them.

## Evidence and limits

The deterministic local reproduction retained wrappers and disabled cyclic garbage
collection: the baseline left 20/20 file-backed Django connections open; patched
code left 0/20 open. This establishes a code defect and its repair, not an exact
reconstruction of all RDS slots at the time of the outage. There was no pre-restart
connection census. The production probe and a sustained conversion still need
Manny's verification.

See [the incident record](../../experiments/community_dictionary/queue-recovery-2026-10-09.md)
and [Django's connection management guidance](https://docs.djangoproject.com/en/5.2/ref/databases/#persistent-connections).
