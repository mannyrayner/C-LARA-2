"""Generic annotation flow for per-segment operations."""
from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from typing import Any, Callable

from core.ai_api import OpenAIClient
from core.telemetry import NullTelemetry, Telemetry


@dataclass(slots=True)
class GenericAnnotationSpec:
    """Specification for a per-segment annotation operation."""

    text: dict[str, Any]
    language: str
    operation: str
    build_prompt: Callable[[dict[str, Any]], str]
    telemetry: Telemetry | None = None
    op_id: str | None = None


async def generic_annotation(
    spec: GenericAnnotationSpec,
    *,
    client: OpenAIClient,
) -> dict[str, Any]:
    """Apply an annotation operation to every segment in the text."""

    telemetry = spec.telemetry or NullTelemetry()
    base_op_id = spec.op_id or f"{spec.operation}-{uuid.uuid4()}"

    pages = spec.text.get("pages", [])
    tasks: list[asyncio.Task] = []
    index: list[tuple[int, int]] = []

    for page_idx, page in enumerate(pages):
        for seg_idx, segment in enumerate(page.get("segments", [])):
            prompt = spec.build_prompt(segment)
            op_id = f"{base_op_id}-p{page_idx}-s{seg_idx}"
            task = asyncio.create_task(
                client.chat_json(prompt, telemetry=telemetry, op_id=op_id)
            )
            tasks.append(task)
            index.append((page_idx, seg_idx))

    results: dict[tuple[int, int], dict[str, Any]] = {}
    if tasks:
        responses = await asyncio.gather(*tasks)
        for idx, response in zip(index, responses):
            results[idx] = response

    new_pages: list[dict[str, Any]] = []
    for page_idx, page in enumerate(pages):
        new_segments: list[dict[str, Any]] = []
        for seg_idx, segment in enumerate(page.get("segments", [])):
            updated = _merge_segment(segment, results.get((page_idx, seg_idx), {}))
            new_segments.append(updated)
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


def _merge_segment(segment: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    merged = dict(segment)

    annotations = _merge_annotations(segment.get("annotations"), response.get("annotations"))
    if annotations:
        merged["annotations"] = annotations

    tokens = _merge_tokens(segment.get("tokens", []), response.get("tokens"))
    if tokens:
        merged["tokens"] = tokens

    for key, value in response.items():
        if key in {"annotations", "tokens"} or value is None:
            continue
        merged[key] = value

    return merged


def _merge_annotations(
    base: dict[str, Any] | None, updates: dict[str, Any] | None
) -> dict[str, Any]:
    base = dict(base or {})
    if updates:
        for key, value in updates.items():
            if value is None:
                continue
            base[key] = value
    return base


def _merge_tokens(
    base_tokens: list[dict[str, Any]] | None, response_tokens: list[dict[str, Any]] | None
) -> list[dict[str, Any]]:
    if not base_tokens and not response_tokens:
        return []
    base_tokens = base_tokens or []
    response_tokens = response_tokens or []

    merged: list[dict[str, Any]] = []
    max_len = max(len(base_tokens), len(response_tokens))

    for idx in range(max_len):
        base = base_tokens[idx] if idx < len(base_tokens) else {}
        update = response_tokens[idx] if idx < len(response_tokens) else {}

        token = dict(base)

        if update:
            token["surface"] = update.get("surface", token.get("surface", ""))
            token.update(
                {
                    k: v
                    for k, v in update.items()
                    if k not in {"annotations", "surface"} and v is not None
                }
            )

        annotations = _merge_annotations(base.get("annotations"), update.get("annotations"))
        if annotations:
            token["annotations"] = annotations
        elif "annotations" in token and not token["annotations"]:
            token.pop("annotations", None)

        merged.append({k: v for k, v in token.items() if v is not None})

    return merged
