# Running the Django platform locally

This guide explains how to start the Django layer (`platform_server/`) so you can log in, create projects, compile to HTML, and view published outputs.

## Prerequisites
- Python 3.11+
- Dependencies installed: `pip install -r requirements-dev.txt`
- Optional: `OPENAI_API_KEY` (and `OPENAI_TTS_MODEL` if you want OpenAI TTS); without a key, pipeline-backed actions will fail fast.

## One-line dev server
After dependencies are installed, start the server (runs migrations automatically):

```bash
make run-platform
```

This launches `python manage.py runserver` bound to `http://127.0.0.1:8000/`; the root path shows the project list.

Notes:
- The target clears `PYTHONPATH` and forces `DJANGO_SETTINGS_MODULE=platform_server.settings` so host settings (common on Windows) don’t break the interpreter. Override the interpreter with `PYTHON=<path/to/python>` if needed.

## With the background worker (django-q style)
Compilation messages are delivered from background tasks. For parity with C-LARA, run both the web server and the Django Q worker:

```bash
make run-platform-with-q
```

The `run-platform-with-q` target runs migrations, starts a stub `qcluster` process (good enough for local dev with the bundled `django_q` shim), and then launches the dev server. If you want to exercise the *real* Django Q worker instead of the stub, install [`django-q2`](https://pypi.org/project/django-q2/) (or another Django 5-compatible fork) and use:

```bash
pip install django-q2
make run-platform-with-real-q
```

The `run-platform-with-real-q` target sets `DJANGO_Q_USE_REAL=1`, which gives precedence to the installed `django_q` package so the genuine `qcluster` runs alongside the dev server. It also starts `python manage.py process_project_understanding_queue --worker-id local-project-understanding-worker` in the background, so local laptop runs can exercise the same dedicated Assistant/project-understanding queue path used on production. This is useful when debugging message delivery differences between the stub and a real queue service, and when checking whether Assistant-tab Codex failures reproduce outside AWS.

The project-understanding worker inherits your shell environment. To test real Assistant queries locally, make sure your laptop shell can run Codex non-interactively and has any required `OPENAI_API_KEY`, `CODEX_HOME`, `HOME`, and Codex CLI path settings before invoking `make run-platform-with-real-q`.

The default `Q_CLUSTER` settings in `platform_server/settings.py` use a long timeout for compile jobs and a larger retry window (`retry` > `timeout`) so a real `django-q` install starts cleanly without warning about misconfiguration. If you override these values, keep that relationship in mind to avoid noisy startup warnings.

## Manual steps (if you prefer)
```bash
cd platform_server
python manage.py migrate
python manage.py qcluster  # keep running in its own terminal to process Django-Q tasks
python manage.py process_project_understanding_queue  # keep running in another terminal for Assistant/Codex requests
python manage.py runserver
```

## Using the UI
- Visit `http://127.0.0.1:8000/`.
- Register a new account or log in (registration is open in dev).
- Create a project; provide the required metadata and run **Compile** to execute the pipeline and generate HTML/audio assets.
- Toggle **Publish** on a compiled project to expose its HTML viewer; published artifacts live under `platform_server/media/projects/<user>/<project>/`.

## Notes
- The current UI is the advanced/technical workspace; a minimal guided UI for non-technical users will be layered on later.
- The default local setup uses SQLite at `platform_server/db.sqlite3`; media assets (compiled HTML/audio) are under `platform_server/media/`.
- To run against PostgreSQL (for example on AWS), set `POSTGRES_HOST` (or `DJANGO_DB_ENGINE=postgres`) and provide:
  - `POSTGRES_DB`
  - `POSTGRES_USER` (for AWS/RDS secrets this is commonly `postgres`)
  - `POSTGRES_PASSWORD`
  - `POSTGRES_PORT` (optional, default `5432`)
- Pipelines require real AI/TTS credentials; without them, compilation will raise an error instead of falling back to stub output.
- For production server operations (deploy/restart/logs/env/permissions/TLS), see `docs/howto/server-admin-tasks.md`.


## AWS timeout checklist for image generation/expansion

If long-running image requests intermittently fail with **502 Bad Gateway** or a generic internal error, check these in order:

1. **Confirm where the timeout occurs**
   - Review `images/elements/telemetry.jsonl` for events such as `elements expansion run start`, `element expansion timeout`, `elements expansion failed`, and elapsed seconds.
   - Compare with application logs (`gunicorn`/`uvicorn`) and reverse-proxy logs (`nginx`) for matching timestamps.

2. **Reverse proxy timeouts (nginx)**
   - Verify `proxy_read_timeout`, `proxy_send_timeout`, and `send_timeout` are long enough for expansion jobs on your hardware/network.
   - If these are shorter than the expansion runtime, nginx may return 502/504 before Django finishes.

3. **Application server timeouts (gunicorn/uvicorn)**
   - For gunicorn, verify `timeout` and `graceful-timeout` are high enough.
   - Ensure worker count is appropriate so one long request does not starve other requests.

4. **OpenAI/API latency variability**
   - Element expansion performs one model call per element; total latency can vary significantly with element count and provider response times.
   - Intermittent success/failure is often a symptom of runtime being near infrastructure timeout thresholds.

5. **Stabilization options**
   - Short term: raise proxy/app-server timeouts.
   - Medium term: move long expansion jobs to background tasks with polling/status UI so web requests stay short.
