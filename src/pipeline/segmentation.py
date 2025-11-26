"""Segmentation pipeline steps."""
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
    return annotation_prompts.load_template("segmentation_phase_1", language, prompts_root=prompts_root)


def _load_fewshots(language: str, *, prompts_root: Path) -> list[dict[str, Any]]:
    return annotation_prompts.load_fewshots("segmentation_phase_1", language, prompts_root=prompts_root)


@dataclass(slots=True)
class SegmentationSpec:
    """Specification for segmentation phase 1."""

    text: str
    language: str = "en"
    template_path: Path | None = None
    fewshot_paths: Iterable[Path] | None = None
    telemetry: Telemetry | None = None
    op_id: str | None = None


def _build_prompt(template: str, *, text: str, fewshots: list[dict[str, Any]]) -> str:
    lines = [template.strip(), "", "Input text:", text.strip(), ""]
    if fewshots:
        lines.append("Few-shot examples:")
        for idx, example in enumerate(fewshots, start=1):
            lines.append(f"Example {idx} input:")
            lines.append(example.get("input", "").strip())
            lines.append("Example output:")
            lines.append(json.dumps(example.get("output", {}), indent=2))
            lines.append("")
    lines.append(
        "Return a JSON object with keys: l2, optional l1, surface (original text), pages (array of pages with surface and segmen"
        "ts arrays), and annotations (object)."
    )
    lines.append(
        "Each segment should only include a surface field; do not add tokens or other annotations in this phase."
    )
    return "\n".join(lines)


def _normalize_response(response: dict[str, Any], *, text: str, language: str) -> dict[str, Any]:
    normalized = {
        "l2": response.get("l2") or language,
        "l1": response.get("l1"),
        "title": response.get("title"),
        "surface": response.get("surface") or text,
        "pages": response.get("pages") or [],
        "annotations": response.get("annotations") or {},
    }
    return {k: v for k, v in normalized.items() if v is not None}


async def segmentation_phase_1(
    spec: SegmentationSpec,
    *,
    client: OpenAIClient | None = None,
) -> dict[str, Any]:
    """Run segmentation phase 1 via prompt templates and the OpenAI client."""

    prompts_root = (
        spec.template_path.parent.parent if spec.template_path else annotation_prompts.default_prompts_root()
    )
    template = (
        spec.template_path.read_text(encoding="utf-8")
        if spec.template_path
        else annotation_prompts.load_template("segmentation_phase_1", spec.language, prompts_root=prompts_root)
    )
    fewshots = (
        [json.loads(path.read_text(encoding="utf-8")) for path in spec.fewshot_paths]
        if spec.fewshot_paths
        else annotation_prompts.load_fewshots("segmentation_phase_1", spec.language, prompts_root=prompts_root)
    )

    prompt = _build_prompt(template, text=spec.text, fewshots=fewshots)
    telemetry = spec.telemetry or NullTelemetry()
    ai_client = client or OpenAIClient()
    response = await ai_client.chat_json(prompt, telemetry=telemetry, op_id=spec.op_id)
    return _normalize_response(response, text=spec.text, language=spec.language)


@dataclass(slots=True)
class SegmentationPhase2Spec:
    """Specification for segmentation phase 2 (tokenization)."""

    text: dict[str, Any]
    language: str = "en"
    template_path: Path | None = None
    fewshot_paths: Iterable[Path] | None = None
    telemetry: Telemetry | None = None
    op_id: str | None = None


async def segmentation_phase_2(
    spec: SegmentationPhase2Spec,
    *,
    client: OpenAIClient | None = None,
) -> dict[str, Any]:
    """Annotate segments with tokens using the generic annotation flow."""

    prompts_root = (
        spec.template_path.parent.parent if spec.template_path else annotation_prompts.default_prompts_root()
    )
    template = (
        spec.template_path.read_text(encoding="utf-8")
        if spec.template_path
        else annotation_prompts.load_template("segmentation_phase_2", spec.language, prompts_root=prompts_root)
    )
    fewshots = (
        [json.loads(path.read_text(encoding="utf-8")) for path in spec.fewshot_paths]
        if spec.fewshot_paths
        else annotation_prompts.load_fewshots("segmentation_phase_2", spec.language, prompts_root=prompts_root)
    )

    output_instructions = [
        "Return a JSON object representing the segment with keys surface, tokens (array of token objects with surface),",
        "and annotations (object).",
        "Preserve punctuation and whitespace as separate tokens where they appear in the input.",
    ]

    def build(seg_surface: str) -> str:
        return annotation_prompts.build_prompt(
            template,
            content_label="Segment to tokenize:",
            content=seg_surface,
            fewshots=fewshots,
            output_instructions=output_instructions,
        )

    telemetry = spec.telemetry or NullTelemetry()
    ai_client = client or OpenAIClient()
    return await generic_annotation(
        GenericAnnotationSpec(
            text=spec.text,
            language=spec.language,
            operation="segmentation_phase_2",
            build_prompt=build,
            telemetry=telemetry,
            op_id=spec.op_id,
        ),
        client=ai_client,
    )


@dataclass(slots=True)
class SegmentationPipelineSpec:
    """Specification for the full segmentation pipeline."""

    text: str
    language: str = "en"
    telemetry: Telemetry | None = None
    op_id: str | None = None


async def segmentation(
    spec: SegmentationPipelineSpec,
    *,
    client: OpenAIClient | None = None,
) -> dict[str, Any]:
    """Run both segmentation phases sequentially and return annotated text."""

    telemetry = spec.telemetry or NullTelemetry()
    ai_client = client or OpenAIClient()

    phase1 = await segmentation_phase_1(
        SegmentationSpec(
            text=spec.text,
            language=spec.language,
            telemetry=telemetry,
            op_id=f"{spec.op_id}-phase1" if spec.op_id else None,
        ),
        client=ai_client,
    )

    return await segmentation_phase_2(
        SegmentationPhase2Spec(
            text=phase1,
            language=spec.language,
            telemetry=telemetry,
            op_id=f"{spec.op_id}-phase2" if spec.op_id else None,
        ),
        client=ai_client,
    )
