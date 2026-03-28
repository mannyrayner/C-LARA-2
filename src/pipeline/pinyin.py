"""Romanization annotation (Chinese pinyin / Hindi transliteration)."""
from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any

from core.ai_api import OpenAIClient
from core.telemetry import NullTelemetry, Telemetry
from .generic_annotation import GenericAnnotationSpec, generic_annotation


@dataclass(slots=True)
class PinyinSpec:
    """Specification for adding pinyin-style romanization to tokenized text."""

    text: dict[str, Any]
    language: str = "zh"
    telemetry: Telemetry | None = None
    op_id: str | None = None
    method: str = "auto"


def _ensure_pypinyin():
    try:
        from pypinyin import Style, lazy_pinyin  # type: ignore

        return Style, lazy_pinyin
    except Exception as exc:  # pragma: no cover - exercised in user envs
        raise ImportError("pypinyin is required for pinyin annotation; install via pip install pypinyin") from exc


def _is_lexical(surface: str) -> bool:
    if not surface or surface.isspace():
        return False
    # Heuristic: treat tokens with CJK/Devanagari/alphanumerics as lexical; punctuation is skipped.
    return bool(re.search(r"[\w\u4e00-\u9fff]", surface)) and not bool(re.fullmatch(r"\W+", surface))


def _ensure_indic_transliteration():
    try:
        from indic_transliteration import sanscript  # type: ignore
        from indic_transliteration.sanscript import transliterate  # type: ignore

        return sanscript, transliterate
    except Exception as exc:  # pragma: no cover - exercised in user envs
        raise ImportError(
            "indic_transliteration is required for Hindi romanization; install via pip install indic-transliteration"
        ) from exc


def _annotate_with_pypinyin(spec: PinyinSpec) -> dict[str, Any]:
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


def _annotate_with_indic_transliteration(spec: PinyinSpec) -> dict[str, Any]:
    telemetry = spec.telemetry or NullTelemetry()
    op_id = spec.op_id or "pinyin"
    sanscript, transliterate = _ensure_indic_transliteration()
    telemetry.event(op_id, "info", "Adding Hindi romanization with indic_transliteration", {"language": spec.language})

    pages = spec.text.get("pages", [])
    new_pages: list[dict[str, Any]] = []
    for page in pages:
        new_segments: list[dict[str, Any]] = []
        for segment in page.get("segments", []):
            tokens = []
            for token in segment.get("tokens", []):
                token_copy = dict(token)
                surface = str(token.get("surface", ""))
                if _is_lexical(surface) and re.search(r"[\u0900-\u097f]", surface):
                    romanized = transliterate(surface, sanscript.DEVANAGARI, sanscript.ITRANS)
                    annotations = dict(token_copy.get("annotations", {}))
                    annotations["pinyin"] = romanized
                    token_copy["annotations"] = annotations
                tokens.append(token_copy)
            new_segments.append(
                {"surface": segment.get("surface", ""), "tokens": tokens, "annotations": segment.get("annotations", {})}
            )
        new_pages.append({"surface": page.get("surface", ""), "segments": new_segments, "annotations": page.get("annotations", {})})

    normalized = {
        "l2": spec.text.get("l2", spec.language),
        "l1": spec.text.get("l1"),
        "title": spec.text.get("title"),
        "surface": spec.text.get("surface", ""),
        "pages": new_pages,
        "annotations": spec.text.get("annotations", {}),
    }
    return {k: v for k, v in normalized.items() if v is not None}


def _build_ai_prompt(segment: dict[str, Any], *, language: str) -> str:
    return "\n".join(
        [
            f"You annotate token-level romanization for language '{language}'.",
            "Return a JSON object representing the same segment.",
            "Preserve segment surface and token surfaces exactly.",
            "For lexical tokens, set token.annotations.pinyin to a concise romanization.",
            "Do not add pinyin for punctuation or whitespace tokens.",
            "Segment JSON:",
            json.dumps({"surface": segment.get("surface", ""), "tokens": segment.get("tokens", [])}, ensure_ascii=False, indent=2),
        ]
    )


async def _annotate_with_ai(spec: PinyinSpec, *, client: OpenAIClient) -> dict[str, Any]:
    telemetry = spec.telemetry or NullTelemetry()
    return await generic_annotation(
        GenericAnnotationSpec(
            text=spec.text,
            language=spec.language,
            operation="pinyin",
            build_prompt=lambda segment: _build_ai_prompt(segment, language=spec.language),
            telemetry=telemetry,
            op_id=spec.op_id,
            preserve_segment_surface=True,
        ),
        client=client,
    )


async def annotate_pinyin(spec: PinyinSpec, *, client: OpenAIClient | None = None) -> dict[str, Any]:
    """Attach romanization annotations according to the configured method."""

    language = (spec.language or "").lower()
    method = (spec.method or "auto").strip().lower()
    if method == "auto":
        if language.startswith("zh"):
            method = "pypinyin"
        elif language.startswith("hi"):
            method = "indic_transliteration"
        else:
            return spec.text

    if method == "pypinyin":
        if not language.startswith("zh"):
            raise ValueError("pypinyin method is only valid for Chinese (zh*)")
        return _annotate_with_pypinyin(spec)
    if method == "indic_transliteration":
        if not language.startswith("hi"):
            raise ValueError("indic_transliteration method is only valid for Hindi (hi*)")
        return _annotate_with_indic_transliteration(spec)
    if method == "ai":
        ai_client = client or OpenAIClient()
        return await _annotate_with_ai(spec, client=ai_client)
    raise ValueError(f"Unknown pinyin/romanization method: {method}")


__all__ = ["PinyinSpec", "annotate_pinyin"]
