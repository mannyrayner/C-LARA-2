"""Load small language-specific resources used by pipeline postprocessing."""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from . import annotation_prompts


def language_resource_root(*, prompts_root: Path | None = None) -> Path:
    return (prompts_root or annotation_prompts.default_prompts_root()) / "language_resources"


@lru_cache(maxsize=None)
def _load_abbreviation_resource(language: str, resource_root_text: str) -> tuple[frozenset[str], bool]:
    resource_root = Path(resource_root_text)
    abbreviations: set[str] = set()
    initialism_pattern = False
    for name in ("common", language):
        path = resource_root / "abbreviations" / f"{name}.json"
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        abbreviations.update(str(item) for item in payload.get("abbreviations", []) if item)
        initialism_pattern = initialism_pattern or bool(payload.get("initialism_pattern"))
    return frozenset(abbreviations), initialism_pattern


def is_known_abbreviation_surface(surface: str, language: str, *, prompts_root: Path | None = None) -> bool:
    language_key = (language or "").lower().split("-", 1)[0]
    resource_root = language_resource_root(prompts_root=prompts_root)
    abbreviations, initialism_pattern = _load_abbreviation_resource(language_key, str(resource_root))
    if surface in abbreviations:
        return True
    return bool(initialism_pattern and re.fullmatch(r"(?:[A-Za-z]\.){2,}", surface))
