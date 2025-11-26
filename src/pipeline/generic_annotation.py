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
    annotations = merged.get("annotations") or {}
    response_annotations = response.get("annotations")
    if response_annotations is not None:
        annotations = response_annotations
    merged.update({k: v for k, v in response.items() if v is not None})
    merged["annotations"] = annotations
    return merged
