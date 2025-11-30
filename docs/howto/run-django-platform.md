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

This launches `python manage.py runserver` bound to `http://127.0.0.1:8000/`.

## Manual steps (if you prefer)
```bash
cd platform_server
python manage.py migrate
python manage.py runserver
```

## Using the UI
- Visit `http://127.0.0.1:8000/`.
- Register a new account or log in (registration is open in dev).
- Create a project; provide the required metadata and run **Compile** to execute the pipeline and generate HTML/audio assets.
- Toggle **Publish** on a compiled project to expose its HTML viewer; published artifacts live under `platform_server/media/projects/<user>/<project>/`.

## Notes
- The current UI is the advanced/technical workspace; a minimal guided UI for non-technical users will be layered on later.
- The dev server uses SQLite at `platform_server/db.sqlite3`; media assets (compiled HTML/audio) are under `platform_server/media/`.
- Pipelines require real AI/TTS credentials; without them, compilation will raise an error instead of falling back to stub output.
