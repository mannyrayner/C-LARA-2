"""Test helpers to configure import paths."""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

# Ensure the repository root is importable so `core` can be loaded in tests.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
