# AWS connection exhaustion and fallback queue repair — 9 October 2026

## Human-reported evidence

Manny reports the two-stage porting release appeared to work on the laptop and
initially on AWS, then Community Dictionaries and ordinary C-LARA pages returned
HTTP 500. A command run through systemd with the service identity/environment
passed Django checks but failed to connect to PostgreSQL: remaining slots were
reserved for the RDS reserved role.

The later diagnostic succeeds. `django_q.tasks` resolves to the repository's
`src/django_q/tasks.py`; `USE_REAL_DJANGO_Q` is false, configured workers are two,
and PostgreSQL `max_connections` is 79. The census counts nine connections:
six database-less internal connections, two rdsadmin connections and the single
active clara2 diagnostic connection. All app migrations through 0018 are applied.
This confirms database connection recovery, not browser acceptance of the repair.

## Diagnosis and change

The fallback launched an unrestricted daemon thread per task and did not close
Django connections when tasks or hooks returned/failed. The normal request cleanup
does not run in those threads. This is a concrete defect consistent with the
incident; the exact original population of the 79 slots was not captured.

The prepared patch closes thread-local connections in `finally`, bounds active
task bodies/hooks/cleanup per process, preserves synchronous transaction behavior
and dotted task paths, and logs production request errors to stderr. It adds a
read-only `community_queue_check` command for the deployed backend. There are no
schema, credit, content, provider, queue-backend or dependency changes.

The fallback remains in-memory: waiting threads and active work are interrupted
when their submitting process stops. A durable production queue and global
concurrency budget remain separate operational work. Stopping the stub qcluster
alone cannot stop fallback jobs inside Gunicorn.

## Local verification

- Baseline/patched comparison, file-backed SQLite and retained wrappers with GC
  disabled: 20 open connections after baseline tasks; zero after patched tasks.
- Eight new regression tests cover success/task failure/hook failure and multiple
  database aliases, synchronous transaction preservation, bounded execution through
  cleanup, nested fan-out, safe limits, unconfigured Django, the server probe,
  and private production tracebacks.
- All 451 Community Dictionaries and admin-tools regression tests pass on Linux,
  Python 3.12 / Django 5.2.17 / SQLite (104 seconds), including the eight new
  tests. Providers are mocked; no paid requests were made. Django checks pass
  and migration detection reports no changes.

The local environment has no PostgreSQL server, so these are not production RDS
or PostgreSQL load tests. The supplied probe must pass on AWS and normal browsing
and a resumed conversion must be checked before claiming incident resolution.
Saved results must be preserved; uncertain interrupted paid requests are not
automatically repeated. See the [recovery runbook](../../docs/howto/community-queue-recovery.md).
