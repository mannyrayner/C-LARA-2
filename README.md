# C-LARA-2

C-LARA-2 is a ground-up rewrite of the C-LARA platform for AI-assisted language learning content:
- Create texts (author or AI-generate), then segment (pages → segments → tokens)
- Add AI annotations (translation, MWE, lemma/POS, gloss, pinyin) plus cached audio
- Generate coherent image sets (style, elements, per-page)
- Render to multiple outputs (classic interactive HTML, mobile-first manga/audio, etc.)
- Documented by design (MkDocs + API refs + ADRs), with a well-typed, testable Python codebase

This repository starts with docs and scaffolding; we’ll fill in modules iteratively.

## Quick start (docs)
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
mkdocs serve
```

## Running tests
From the repository root:
```bash
make -C tests test
```

This invokes `pytest` (with `pytest-asyncio`) and writes a log to
`tests/test_results.log`. Integration tests use the real OpenAI API when
`OPENAI_API_KEY` is set (and optionally `OPENAI_TEST_MODEL`, defaulting to
`gpt-5`). Without a key, those tests are skipped while the unit suite still
runs locally.

## Continuous integration
GitHub Actions run the suite with coverage on pushes and pull requests. Results
are uploaded as artifacts (JUnit XML, coverage XML/HTML, and a JSON summary).

## Restoring a single file from the repo
If you need to reset a file (e.g., `src/core/ai_api.py`) to the last committed
version in this branch, run:

```bash
git restore src/core/ai_api.py
```

This overwrites your local edits with the tracked copy without affecting other
files.

## Pull request flow
1. Commit changes on your feature branch after running tests locally.
2. Push the branch; GitHub will offer a **Create PR** control in the UI.
3. After opening the PR, the control changes to **View PR**, which you can click anytime to review or update the pull request.
