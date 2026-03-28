"""Segmentation pipeline steps."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
import re
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


def _render_fewshot_examples(fewshots: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for idx, example in enumerate(fewshots, start=1):
        lines.append(f"Example {idx}:")
        lines.append("<startoftext>")
        lines.append((example.get("input") or "").strip())
        lines.append("<endoftext>")
        lines.append("Annotated output:")
        lines.append("<startoftext>")
        output = example.get("output")
        if isinstance(output, str):
            lines.append(output.strip())
        else:
            lines.append(_json_like_output_to_tagged_text(output).strip())
        lines.append("<endoftext>")
        lines.append("")
    return "\n".join(lines).strip()


def _json_like_output_to_tagged_text(output: Any) -> str:
    if not isinstance(output, dict):
        return str(output or "")
    pages = output.get("pages")
    if not isinstance(pages, list) or not pages:
        return str(output.get("surface") or "")
    rendered_pages: list[str] = []
    for page in pages:
        if not isinstance(page, dict):
            continue
        segments = page.get("segments")
        if isinstance(segments, list) and segments:
            segment_texts = [str((seg or {}).get("surface") if isinstance(seg, dict) else seg or "") for seg in segments]
            rendered_pages.append("||".join(segment_texts))
        else:
            rendered_pages.append(str(page.get("surface") or ""))
    return "<page>".join(rendered_pages)


def _build_prompt(template: str, *, text: str, fewshots: list[dict[str, Any]], language: str) -> str:
    examples = _render_fewshot_examples(fewshots)
    template_has_placeholders = any(
        token in template for token in ("{l2_language}", "{examples}", "{text}", "{text_type_advice}")
    )
    if template_has_placeholders:
        return template.format(
            l2_language=language,
            examples=examples or "[No examples provided]",
            text=text,
            text_type_advice="",
        )

    # Backward-compatible fallback for plain-text templates without format placeholders.
    lines = [template.strip(), "", "Examples:", examples or "[No examples provided]", "", "Input text:"]
    lines.append("<startoftext>")
    lines.append(text.strip())
    lines.append("<endoftext>")
    lines.append("")
    lines.append(
        "Output only the annotated text enclosed in <startoftext> and <endoftext> tags, "
        "using <page> for page boundaries and || for segment boundaries."
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

    prompt = _build_prompt(template, text=spec.text, fewshots=fewshots, language=spec.language)
    telemetry = spec.telemetry or NullTelemetry()
    ai_client = client or OpenAIClient()
    raw_response = await ai_client.chat_text(prompt, telemetry=telemetry, op_id=spec.op_id)
    return _normalize_phase1_response(raw_response, text=spec.text, language=spec.language)


def _normalize_phase1_response(raw_response: str, *, text: str, language: str) -> dict[str, Any]:
    try:
        parsed_json = json.loads(raw_response)
        if isinstance(parsed_json, dict):
            return _normalize_response(parsed_json, text=text, language=language)
    except Exception:
        pass

    annotated = _extract_between_tags(raw_response, "startoftext", "endoftext").strip()
    if not annotated:
        annotated = raw_response.strip()
    if not annotated:
        annotated = text

    original_non_ws = len(re.sub(r"\s+", "", text))
    annotated_non_ws = len(re.sub(r"\s+", "", annotated))
    if original_non_ws > 0 and annotated_non_ws < max(3, int(original_non_ws * 0.5)):
        annotated = text

    page_chunks = annotated.split("<page>")
    pages: list[dict[str, Any]] = []
    for chunk in page_chunks:
        page_surface = chunk
        segment_chunks = chunk.split("||") if "||" in chunk else [chunk]
        segments = [{"surface": seg} for seg in segment_chunks if seg != ""]
        if not segments:
            segments = [{"surface": page_surface}]
        pages.append({"surface": page_surface, "segments": segments, "annotations": {}})

    return {
        "l2": language,
        "surface": annotated,
        "pages": pages,
        "annotations": {},
    }


def _extract_between_tags(text: str, start_tag: str, end_tag: str) -> str:
    pattern = re.compile(
        rf"<{start_tag}>\s*(.*?)\s*<{end_tag}>",
        flags=re.DOTALL | re.IGNORECASE,
    )
    match = pattern.search(text)
    if not match:
        return ""
    return match.group(1)


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
    """Annotate segments with tokens using jieba for Mandarin or the generic flow."""

    telemetry = spec.telemetry or NullTelemetry()

    if spec.language.lower().startswith("zh"):
        return _tokenize_with_jieba(spec.text, language=spec.language, telemetry=telemetry, op_id=spec.op_id)

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

    def build(segment: dict[str, Any]) -> str:
        return annotation_prompts.build_prompt(
            template,
            content_label="Segment to tokenize:",
            content=segment.get("surface", ""),
            fewshots=fewshots,
            output_instructions=output_instructions,
        )

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


def _tokenize_with_jieba(
    text: dict[str, Any], *, language: str, telemetry: Telemetry, op_id: str | None
) -> dict[str, Any]:
    try:
        import jieba  # type: ignore
    except Exception as exc:  # pragma: no cover - exercised in user envs
        raise ImportError("jieba is required for Mandarin segmentation; install via pip install jieba") from exc

    base_op = op_id or "segmentation-phase-2-jieba"
    telemetry.event(base_op, "info", "Using jieba for Mandarin tokenization", {"language": language})

    def _cut_preserve_whitespace(surface: str) -> list[dict[str, Any]]:
        tokens: list[dict[str, Any]] = []
        cursor = 0
        for match in re.finditer(r"\s+", surface):
            chunk = surface[cursor : match.start()]
            if chunk:
                tokens.extend({"surface": tok} for tok in jieba.cut(chunk, cut_all=False))
            tokens.append({"surface": match.group(0)})
            cursor = match.end()

        tail = surface[cursor:]
        if tail:
            tokens.extend({"surface": tok} for tok in jieba.cut(tail, cut_all=False))
        return tokens

    new_pages: list[dict[str, Any]] = []
    for page in text.get("pages", []):
        new_segments: list[dict[str, Any]] = []
        for segment in page.get("segments", []):
            tokens = _cut_preserve_whitespace(segment.get("surface", ""))
            merged = dict(segment)
            if tokens:
                merged["tokens"] = tokens
            new_segments.append(merged)

        new_pages.append(
            {
                "surface": page.get("surface", ""),
                "segments": new_segments,
                "annotations": page.get("annotations", {}),
            }
        )

    normalized = {
        "l2": text.get("l2", language),
        "l1": text.get("l1"),
        "title": text.get("title"),
        "surface": text.get("surface", ""),
        "pages": new_pages,
        "annotations": text.get("annotations", {}),
    }
    return {k: v for k, v in normalized.items() if v is not None}


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
