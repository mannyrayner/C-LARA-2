"""Segment-level translation using the generic annotation harness."""
from __future__ import annotations

import json
import asyncio
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from core.ai_api import OpenAIClient
from core.telemetry import NullTelemetry, Telemetry

from . import annotation_prompts
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


_ESCAPED_U4_RE = re.compile(r"\\u([0-9a-fA-F]{4})")
_ESCAPED_U8_RE = re.compile(r"\\U([0-9a-fA-F]{8})")
_ESCAPED_X2_RE = re.compile(r"\\x([0-9a-fA-F]{2})")
_ESCAPED_MALFORMED_U2_RE = re.compile(r"\\u0000([0-9a-fA-F]{2})")
_MALFORMED_NULL_HEX_RE = re.compile(r"\x00([0-9a-fA-F]{2})")


def _decode_escaped_unicode(text: str) -> str:
    def _replace_hex(match: re.Match[str]) -> str:
        try:
            return chr(int(match.group(1), 16))
        except ValueError:
            return match.group(0)

    normalized = _ESCAPED_MALFORMED_U2_RE.sub(_replace_hex, text)
    normalized = _ESCAPED_U4_RE.sub(_replace_hex, normalized)
    normalized = _ESCAPED_U8_RE.sub(_replace_hex, normalized)
    normalized = _ESCAPED_X2_RE.sub(_replace_hex, normalized)
    normalized = _MALFORMED_NULL_HEX_RE.sub(_replace_hex, normalized)
    normalized = normalized.replace("\x00", "")
    return normalized.replace('\\"', '"').replace("\\'", "'")


def _postprocess_translation_response(raw_text: str) -> str:
    text = raw_text.strip()

    if text.startswith("```"):
        stripped = text.strip("`")
        text = stripped.replace("json\n", "", 1).strip()

    parsed: Any = None
    try:
        parsed = json.loads(text)
    except Exception:
        parsed = None

    if isinstance(parsed, dict):
        for key in ("translated_text", "translation", "text", "output"):
            value = parsed.get(key)
            if isinstance(value, str):
                text = value
                break
        else:
            text = next((str(v) for v in parsed.values() if isinstance(v, str)), text)
    elif isinstance(parsed, str):
        text = parsed

    text = text.strip()
    if "<start>" in text and "</end>" in text:
        try:
            text = text.split("<start>", 1)[1].split("</end>", 1)[0].strip()
        except Exception:
            pass
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        text = text[1:-1].strip()
    return _decode_escaped_unicode(text)


def _preview_text(text: str, *, limit: int = 200) -> str:
    compact = " ".join(text.split())
    return compact if len(compact) <= limit else f"{compact[:limit]}..."


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

    template_text = template.format(glossing_language=target_language).strip()
    lines: list[str] = [template_text, ""]

    if fewshots:
        lines.append(f"Here are some examples showing English glossed with {target_language}.")
        lines.append("")
        for idx, example in enumerate(fewshots, start=1):
            lines.append(f"Example {idx} input:")
            lines.append(example.get("input", "").strip())
            lines.append("Example output:")
            lines.append(example.get("output", "").strip())
            lines.append("")

    lines.append("Text to translate:")
    lines.append(f"<start>{segment.get('surface', '')}</end>")
    lines.append("")
    lines.append("Return format: <start>...</end>")
    return "\n".join(lines)


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

    normalized_fewshots: list[dict[str, Any]] = []
    for item in fewshots:
        input_obj = item.get("input") if isinstance(item, dict) else None
        output_obj = item.get("output") if isinstance(item, dict) else None
        try:
            if isinstance(input_obj, str):
                input_obj = json.loads(input_obj)
            if isinstance(output_obj, str):
                output_obj = json.loads(output_obj)
        except Exception:
            pass
        input_surface = ""
        output_translation = ""
        if isinstance(input_obj, dict):
            input_surface = str(input_obj.get("surface") or "")
        elif isinstance(input_obj, str):
            input_surface = input_obj
        if isinstance(output_obj, dict):
            output_translation = str(
                (output_obj.get("annotations") or {}).get("translation") or ""
            )
        elif isinstance(output_obj, str):
            output_translation = output_obj
        normalized_fewshots.append(
            {"input": input_surface, "output": output_translation}
        )

    def build(segment: dict[str, Any]) -> str:
        return _build_prompt(
            template,
            segment=segment,
            fewshots=normalized_fewshots,
            target_language=spec.target_language,
        )

    telemetry = spec.telemetry or NullTelemetry()
    ai_client = client or OpenAIClient()

    base_op_id = spec.op_id or f"translation-{uuid.uuid4()}"
    semaphore = asyncio.Semaphore(8)
    tasks: list[asyncio.Task[str]] = []
    index: list[tuple[int, int]] = []

    async def _translate_segment(prompt: str, op_id: str) -> str:
        async with semaphore:
            telemetry.event(op_id, "info", "translation segment request sent")
            raw_text = await ai_client.chat_text(prompt, telemetry=telemetry, op_id=op_id)
            telemetry.event(
                op_id,
                "info",
                "translation segment raw response received",
                {"preview": _preview_text(raw_text)},
            )
            normalized_text = _postprocess_translation_response(raw_text)
            if normalized_text != raw_text.strip():
                telemetry.event(
                    op_id,
                    "warn",
                    "translation segment response normalized",
                    {
                        "raw_preview": _preview_text(raw_text),
                        "normalized_preview": _preview_text(normalized_text),
                    },
                )
            if not normalized_text:
                telemetry.event(op_id, "warn", "translation segment produced empty output")
            return normalized_text

    pages = spec.text.get("pages", [])
    for page_idx, page in enumerate(pages):
        for seg_idx, segment in enumerate(page.get("segments", [])):
            prompt = build(segment)
            op_id = f"{base_op_id}-p{page_idx}-s{seg_idx}"
            tasks.append(asyncio.create_task(_translate_segment(prompt, op_id)))
            index.append((page_idx, seg_idx))

    responses: dict[tuple[int, int], str] = {}
    if tasks:
        for idx, text in zip(index, await asyncio.gather(*tasks)):
            responses[idx] = text

    new_pages: list[dict[str, Any]] = []
    for page_idx, page in enumerate(pages):
        new_segments: list[dict[str, Any]] = []
        for seg_idx, segment in enumerate(page.get("segments", [])):
            updated = dict(segment)
            annotations = dict(segment.get("annotations") or {})
            annotations["translation"] = responses.get((page_idx, seg_idx), "")
            updated["annotations"] = annotations
            new_segments.append(updated)
        new_pages.append(
            {
                "surface": page.get("surface", ""),
                "segments": new_segments,
                "annotations": page.get("annotations", {}),
            }
        )

    annotated: dict[str, Any] = {
        "l2": spec.text.get("l2", spec.language),
        "l1": spec.text.get("l1") or spec.target_language,
        "title": spec.text.get("title"),
        "surface": spec.text.get("surface", ""),
        "pages": new_pages,
        "annotations": spec.text.get("annotations", {}),
    }

    # Ensure the target language is recorded at the text level.
    return {k: v for k, v in annotated.items() if v is not None}
