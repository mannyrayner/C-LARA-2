"""Test helpers to configure import paths."""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

# Ensure the `src/` tree (and repo root fallback) is importable so `core` can
# be loaded in tests regardless of where the package lives in development.
for path in (SRC, ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
