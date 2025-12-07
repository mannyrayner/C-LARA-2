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

## Live progress in the UI
When you start a compile, the request queues a background task and redirects you to a monitor page. The monitor polls a JSON endpoint every few seconds for new entries written by the compile callback. Updates are stored in the `TaskUpdate` table and returned to the browser as soon as they arrive. When the pipeline sends a final `finished` or `error` status, the monitor automatically redirects back to the project detail page.

If you suspect the stub queue is masking behaviour differences, install a Django 5-compatible queue package such as `django-q2` and start the stack with `make run-platform-with-real-q` so progress messages flow through the real worker implementation.
