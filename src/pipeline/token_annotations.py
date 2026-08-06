"""Shared cleanup helpers for token-level linguistic annotations."""
from __future__ import annotations

from typing import Any, Iterable


LINGUISTIC_ANNOTATION_KEYS = ("mwe_id", "lemma", "pos", "gloss")


def strip_whitespace_token_annotations(
    text: dict[str, Any],
    *,
    keys: Iterable[str] = LINGUISTIC_ANNOTATION_KEYS,
) -> dict[str, Any]:
    """Remove linguistic annotations that cannot apply to whitespace tokens.

    Model output occasionally copies an adjacent token's annotations onto a
    whitespace-only token.  Such values are structurally meaningless and can
    also make MWE consistency validation fail in manual editors.
    """

    annotation_keys = tuple(keys)
    for page in text.get("pages", []) or []:
        for segment in page.get("segments", []) or []:
            for token in segment.get("tokens", []) or []:
                if str(token.get("surface") or "").strip():
                    continue
                annotations = token.get("annotations")
                if not isinstance(annotations, dict):
                    continue
                for key in annotation_keys:
                    annotations.pop(key, None)
                if not annotations:
                    token.pop("annotations", None)
    return text
