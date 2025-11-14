# Dev setup

This project keeps docs simple and cross-platform (Windows, Cygwin, Linux, macOS).

## 1) Create & activate a virtual environment

**Windows (Cygwin/bash using the Windows Python):**
```bash
python3 -m venv .venv
# If activation errors mention $'\r', strip CRLFs then activate:
sed -i 's/\r$//' .venv/Scripts/activate
source .venv/Scripts/activate```

**Linux/macOS:**

```python3 -m venv .venv
source .venv/bin/activate```

Verify you’re in the venv:

```python3 -c "import sys, platform; print(sys.executable); print(platform.system())"```

## 2) Install dev dependencies

```pip install -r requirements-dev.txt```

If pip nags about upgrading and it doesn’t upgrade inside the venv:

```python3 -m pip install --upgrade pip```

## 3) Serve docs locally

```mkdocs serve```

Open the local URL shown in the terminal (usually http://127.0.0.1:8000/).

## 4) Lint & format docs

We use **mdformat** (formatter) and **PyMarkdown** (pymarkdownlnt, linter).

**Format all Markdown:**

```mdformat docs/**/*.md```

**Lint:**

```pymarkdown scan docs```

Fix issues and re-run until clean.

## 5) Optional: pre-commit hook

**To auto-format and lint on every commit:**

Install pre-commit:

```pip install pre-commit```

Create ```.pre-commit-config.yaml``` at the repo root:

```repos:
  - repo: local
    hooks:
      - id: mdformat
        name: mdformat
        entry: mdformat
        language: system
        files: \.md$
        args: [ "docs" ]
      - id: pymarkdown
        name: pymarkdown
        entry: pymarkdown
        language: system
        args: [ "scan", "docs" ]```

Enable:

```pre-commit install```

Now ```git commit``` runs formatter + linter for ```docs/```.

## 6) Windows/Cygwin tips

If you also have Cygwin’s ```/usr/bin/python3```, ensure the venv’s Python is first in PATH (activation does this).

If activation keeps complaining about CRLFs, re-run:

```sed -i 's/\r$//' .venv/Scripts/activate```

When in doubt, print the Python path (step 1) to confirm you’re using .venv.