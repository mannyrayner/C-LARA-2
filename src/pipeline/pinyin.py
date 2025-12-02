"""Chinese pinyin annotation using pypinyin."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from core.telemetry import NullTelemetry, Telemetry


@dataclass(slots=True)
class PinyinSpec:
    """Specification for adding pinyin to tokenized Chinese text."""

    text: dict[str, Any]
    language: str = "zh"
    telemetry: Telemetry | None = None
    op_id: str | None = None


def _ensure_pypinyin():
    try:
        from pypinyin import Style, lazy_pinyin  # type: ignore

        return Style, lazy_pinyin
    except Exception as exc:  # pragma: no cover - exercised in user envs
        raise ImportError("pypinyin is required for pinyin annotation; install via pip install pypinyin") from exc


def _is_lexical(surface: str) -> bool:
    if not surface or surface.isspace():
        return False
    # Heuristic: treat tokens with CJK or alphanumerics as lexical; punctuation is skipped.
    return bool(re.search(r"[\w\u4e00-\u9fff]", surface)) and not bool(re.fullmatch(r"\W+", surface))


def annotate_pinyin(spec: PinyinSpec) -> dict[str, Any]:
    """Attach pinyin annotations to lexical tokens using pypinyin."""

    telemetry = spec.telemetry or NullTelemetry()
    op_id = spec.op_id or "pinyin"

    Style, lazy_pinyin = _ensure_pypinyin()
    telemetry.event(op_id, "info", "Adding pinyin annotations with pypinyin", {"language": spec.language})

    pages = spec.text.get("pages", [])
    new_pages: list[dict[str, Any]] = []

    for page in pages:
        new_segments: list[dict[str, Any]] = []
        for segment in page.get("segments", []):
            tokens = []
            for token in segment.get("tokens", []):
                token_copy = dict(token)
                if _is_lexical(token.get("surface", "")):
                    syllables = lazy_pinyin(token["surface"], style=Style.TONE3, errors="default")
                    if syllables:
                        pinyin_value = " ".join(syllables)
                        annotations = dict(token_copy.get("annotations", {}))
                        annotations["pinyin"] = pinyin_value
                        token_copy["annotations"] = annotations
                tokens.append(token_copy)

            new_segments.append(
                {
                    "surface": segment.get("surface", ""),
                    "tokens": tokens,
                    "annotations": segment.get("annotations", {}),
                }
            )

        new_pages.append(
            {
                "surface": page.get("surface", ""),
                "segments": new_segments,
                "annotations": page.get("annotations", {}),
            }
        )

    normalized = {
        "l2": spec.text.get("l2", spec.language),
        "l1": spec.text.get("l1"),
        "title": spec.text.get("title"),
        "surface": spec.text.get("surface", ""),
        "pages": new_pages,
        "annotations": spec.text.get("annotations", {}),
    }

    return {k: v for k, v in normalized.items() if v is not None}


__all__ = ["PinyinSpec", "annotate_pinyin"]
