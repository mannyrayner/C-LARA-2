# C-LARA-2

C-LARA-2 is a ground-up rewrite of the C-LARA platform for AI-assisted language learning content:
- Create texts (author or AI-generate), then segment (pages → segments → tokens)
- Add AI annotations (translation, MWE, lemma/POS, gloss, pinyin)
- Generate coherent image sets (style, elements, per-page)
- Render to multiple outputs (classic interactive HTML, mobile-first manga/audio, etc.)
- Documented by design (MkDocs + API refs + ADRs), with a well-typed, testable Python codebase

This repository starts with docs and scaffolding; we’ll fill in modules iteratively.

## Quick start (docs)
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
mkdocs serve