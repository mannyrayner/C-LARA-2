# Locating compile progress logs

When you compile a project in the Django platform, the pipeline records progress updates to a JSON Lines log so you can inspect the stages after a run.

## Default path
By default, logs live under the platform media directory:

```
platform_server/media/users/<user_id>/projects/project_<project_id>/runs/run_<timestamp>/stages/progress.jsonl
```

* `<user_id>` is your Django user ID (visible in the admin or database).
* `<project_id>` is the numeric ID of the project (visible in the URL for the project detail page).
* `<timestamp>` matches the run folder created for the compile (e.g. `run_20240620_163055`).

If `PIPELINE_OUTPUT_ROOT` is set in Django settings, replace the leading `platform_server/media/users` with that custom root.

## Contents
Each line in `progress.jsonl` is a JSON object that records a stage name, status message, and timestamp. Timestamps are stored in your configured profile time zone when available, otherwise UTC.

## Quick lookup from the UI
On the project detail page, the **Stages** section lists the most recent run directory and provides a link to `progress.jsonl` if it exists, so you can download it directly without browsing the filesystem.

## Debug logging for message delivery
Pipeline stages run in a DjangoQ-style background task and write to `progress.jsonl`. A watcher in the web process tails this log and mirrors each entry into the user's session so messages surface while the job is in flight. If a progress entry cannot be converted into a UI message, the watcher logs a detailed exception via the `projects.views` logger. With the default settings in this repository, those log lines appear in whichever console is executing tasks (the stub `qcluster` process started by `make run-platform-with-q`, or the real `python manage.py qcluster` if you install Django Q; when using the stub only, they still show up with `runserver`). In deployed environments, check your configured Django logging handlers (e.g., Gunicorn or systemd service logs) for entries from `projects.views`.

If you suspect the stub queue is masking behaviour differences, install a Django 5-compatible queue package such as `django-q2` and start the stack with `make run-platform-with-real-q` so progress messages flow through the real worker implementation.
