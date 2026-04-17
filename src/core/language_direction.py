"""Canonical language-direction registry used across platform and pipeline."""
from __future__ import annotations

from typing import Final


RTL_LANGUAGE_CODES: Final[frozenset[str]] = frozenset(
    {
        "ar",  # Arabic
        "fa",  # Persian / Farsi
    }
)


def normalize_language_code(language_code: str | None) -> str:
    value = str(language_code or "").strip().lower()
    if not value:
        return ""
    normalized = value.replace("_", "-")
    return normalized.split("-", 1)[0]


def language_direction(language_code: str | None) -> str:
    normalized = normalize_language_code(language_code)
    if normalized in RTL_LANGUAGE_CODES:
        return "rtl"
    return "ltr"


def is_rtl_language(language_code: str | None) -> bool:
    return language_direction(language_code) == "rtl"
