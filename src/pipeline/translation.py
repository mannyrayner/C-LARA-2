"""Segment-level translation using the generic annotation harness."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from core.ai_api import OpenAIClient
from core.telemetry import NullTelemetry, Telemetry

from . import annotation_prompts
from .generic_annotation import GenericAnnotationSpec, generic_annotation


def _load_template(language: str, *, prompts_root: Path) -> str:
    return annotation_prompts.load_template(
        "translation", language, prompts_root=prompts_root
    )


def _load_fewshots(language: str, *, prompts_root: Path) -> list[dict[str, Any]]:
    return annotation_prompts.load_fewshots(
        "translation", language, prompts_root=prompts_root
    )


@dataclass(slots=True)
class TranslationSpec:
    """Specification for translating segments from L2 to L1."""

    text: dict[str, Any]
    language: str = "en"  # L2
    target_language: str = "fr"  # L1
    template_path: Path | None = None
    fewshot_paths: Iterable[Path] | None = None
    telemetry: Telemetry | None = None
    op_id: str | None = None


def _build_prompt(
    template: str,
    *,
    segment: dict[str, Any] | None = None,
    segment_surface: str | None = None,
    fewshots: list[dict[str, Any]],
    target_language: str,
) -> str:
    # Backward compatibility: some callers provided a raw surface string instead of a
    # segment object. Normalize to a segment dict here so tests and downstream
    # callers can use either style without breaking.
    if segment is None:
        segment = {"surface": segment_surface or ""}
    elif segment_surface is not None and "surface" not in segment:
        segment = {**segment, "surface": segment_surface}

    output_instructions = [
        "Return a JSON object representing the segment.",
        "Keep the original surface unchanged.",
        "Add annotations.translation set to the translation string in the target language.",
    ]

    header = f"Segment to translate into {target_language}:"
    return annotation_prompts.build_prompt(
        template,
        content_label=header,
        content=segment.get("surface", ""),
        fewshots=fewshots,
        output_instructions=output_instructions,
    )


async def translate(
    spec: TranslationSpec,
    *,
    client: OpenAIClient | None = None,
) -> dict[str, Any]:
    """Annotate each segment with an L1 translation."""

    prompts_root = (
        spec.template_path.parent.parent
        if spec.template_path
        else annotation_prompts.default_prompts_root()
    )
    template = (
        spec.template_path.read_text(encoding="utf-8")
        if spec.template_path
        else _load_template(spec.language, prompts_root=prompts_root)
    )
    fewshots = (
        [json.loads(path.read_text(encoding="utf-8")) for path in spec.fewshot_paths]
        if spec.fewshot_paths
        else _load_fewshots(spec.language, prompts_root=prompts_root)
    )

    def build(segment: dict[str, Any]) -> str:
        return _build_prompt(
            template,
            segment=segment,
            fewshots=fewshots,
            target_language=spec.target_language,
        )

    telemetry = spec.telemetry or NullTelemetry()
    ai_client = client or OpenAIClient()

    annotated = await generic_annotation(
        GenericAnnotationSpec(
            text=spec.text,
            language=spec.language,
            operation="translation",
            build_prompt=build,
            telemetry=telemetry,
            op_id=spec.op_id,
            max_concurrency=8,
        ),
        client=ai_client,
    )

    # Ensure the target language is recorded at the text level.
    if annotated.get("l1") is None:
        annotated["l1"] = spec.target_language

    return annotated

