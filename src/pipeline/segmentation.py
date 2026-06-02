"""Segmentation pipeline steps."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
import re
import unicodedata
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
    prioritise_sentences: bool = False


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


def _build_prompt(
    template: str,
    *,
    text: str,
    fewshots: list[dict[str, Any]],
    language: str,
    text_type_advice: str = "",
) -> str:
    examples = _render_fewshot_examples(fewshots)
    template_has_placeholders = any(
        token in template for token in ("{l2_language}", "{examples}", "{text}", "{text_type_advice}")
    )
    if template_has_placeholders:
        return template.format(
            l2_language=language,
            examples=examples or "[No examples provided]",
            text=text,
            text_type_advice=text_type_advice,
        )

    # Backward-compatible fallback for plain-text templates without format placeholders.
    lines = [template.strip()]
    if text_type_advice.strip():
        lines.extend(["", "Additional segmentation guidance:", text_type_advice.strip()])
    lines.extend(["", "Examples:", examples or "[No examples provided]", "", "Input text:"])
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


def _fallback_tokenize_surface(surface: str) -> list[dict[str, Any]]:
    tokens: list[str] = []
    current = ""
    current_type = ""

    def _kind(ch: str) -> str:
        if ch.isspace():
            return "ws"
        cat = unicodedata.category(ch)
        if cat.startswith("P"):
            return "punct"
        return "word"

    for ch in surface:
        kind = _kind(ch)
        if kind == "punct":
            if current:
                tokens.append(current)
                current = ""
                current_type = ""
            tokens.append(ch)
            continue
        if not current:
            current = ch
            current_type = kind
            continue
        if kind == current_type:
            current += ch
        else:
            tokens.append(current)
            current = ch
            current_type = kind

    if current:
        tokens.append(current)

    return [{"surface": p} for p in tokens if p != ""]


def _normalize_phase2_output(text_obj: dict[str, Any]) -> dict[str, Any]:
    for page in text_obj.get("pages", []) or []:
        for segment in page.get("segments", []) or []:
            surface = str(segment.get("surface", ""))
            tokens = segment.get("tokens")
            if not isinstance(tokens, list) or not tokens:
                segment["tokens"] = _fallback_tokenize_surface(surface)
                continue
            concatenated = "".join(str((tok or {}).get("surface", "")) for tok in tokens if isinstance(tok, dict))
            if re.sub(r"\s+", "", concatenated) != re.sub(r"\s+", "", surface):
                segment["tokens"] = _fallback_tokenize_surface(surface)
    return text_obj


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

    text_type_advice = ""
    if spec.prioritise_sentences:
        text_type_advice = (
            "For prose, prioritise sentence boundaries: by default, make each segment a complete "
            "sentence. Only split inside a sentence when it is unusually long or pedagogically "
            "unmanageable, and avoid fragmenting ordinary prose into short clauses."
        )

    prompt = _build_prompt(
        template,
        text=spec.text,
        fewshots=fewshots,
        language=spec.language,
        text_type_advice=text_type_advice,
    )
    telemetry = spec.telemetry or NullTelemetry()
    ai_client = client or OpenAIClient()
    max_attempts = 3
    last_mismatch: dict[str, Any] = {}
    for attempt in range(1, max_attempts + 1):
        raw_response = await ai_client.chat_text(prompt, telemetry=telemetry, op_id=spec.op_id)
        normalized = _normalize_phase1_response(raw_response, text=spec.text, language=spec.language)
        if _phase1_surface_matches_text(spec.text, str(normalized.get("surface") or "")):
            return normalized
        last_mismatch = _phase1_mismatch_details(spec.text, str(normalized.get("surface") or ""))
        telemetry.event(
            spec.op_id or "segmentation_phase_1",
            "warn",
            "segmentation_phase_1 output changed base text; retrying",
            {"attempt": attempt, "max_attempts": max_attempts, "mismatch": last_mismatch},
        )

    mismatch_summary = ""
    if last_mismatch:
        mismatch_summary = (
            f" last mismatch: diff_index={last_mismatch.get('diff_index')}, "
            f"base_char={last_mismatch.get('base_char')!r}, "
            f"annotated_char={last_mismatch.get('annotated_char')!r}, "
            f"base_excerpt={last_mismatch.get('base_excerpt')!r}, "
            f"annotated_excerpt={last_mismatch.get('annotated_excerpt')!r}, "
            f"nfc_equal_after_strip={last_mismatch.get('nfc_equal_after_strip')}."
        )
        telemetry.event(
            spec.op_id or "segmentation_phase_1",
            "error",
            "segmentation_phase_1 failed validation after retries",
            {"max_attempts": max_attempts, "mismatch": last_mismatch},
        )

    raise ValueError(
        "Segmentation phase 1 failed validation: model output changed the text content "
        f"after {max_attempts} attempts.{mismatch_summary}"
    )


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
    annotated = re.sub(r"</\s*page\s*>", "<page>", annotated, flags=re.IGNORECASE)
    annotated = re.sub(r"<\s*page\s*>", "<page>", annotated, flags=re.IGNORECASE)

    original_non_ws = len(re.sub(r"\s+", "", text))
    annotated_non_ws = len(re.sub(r"\s+", "", annotated))
    if original_non_ws > 0 and annotated_non_ws < max(3, int(original_non_ws * 0.5)):
        annotated = text

    page_chunks = annotated.split("<page>")
    pages: list[dict[str, Any]] = []
    for chunk in page_chunks:
        if not str(chunk).strip():
            continue
        page_surface = chunk
        segment_chunks = chunk.split("||") if "||" in chunk else [chunk]
        segments = [{"surface": seg} for seg in segment_chunks if seg != ""]
        if not segments:
            segments = [{"surface": page_surface}]
        pages.append({"surface": page_surface, "segments": segments, "annotations": {}})
    if not pages:
        pages = [{"surface": text, "segments": [{"surface": text}], "annotations": {}}]

    return {
        "l2": language,
        "surface": annotated,
        "pages": pages,
        "annotations": {},
    }


def _strip_phase1_markers(surface: str) -> str:
    stripped = surface.replace("\r\n", "\n")
    stripped = re.sub(r"</?\s*page\s*>", "", stripped, flags=re.IGNORECASE)
    stripped = stripped.replace("||", "")
    return stripped


def _phase1_surface_matches_text(base_text: str, annotated_surface: str) -> bool:
    normalized_base = base_text.replace("\r\n", "\n")
    normalized_annotated = _strip_phase1_markers(annotated_surface)
    if normalized_base == normalized_annotated:
        return True
    base_ws = re.sub(r"\s+", " ", normalized_base).strip()
    annotated_ws = re.sub(r"\s+", " ", normalized_annotated).strip()
    return base_ws == annotated_ws


def _phase1_mismatch_details(base_text: str, annotated_surface: str) -> dict[str, Any]:
    normalized_base = base_text.replace("\r\n", "\n")
    normalized_annotated = annotated_surface.replace("\r\n", "\n")
    stripped_annotated = _strip_phase1_markers(normalized_annotated)

    min_len = min(len(normalized_base), len(stripped_annotated))
    diff_index = -1
    for idx in range(min_len):
        if normalized_base[idx] != stripped_annotated[idx]:
            diff_index = idx
            break
    if diff_index < 0 and len(normalized_base) != len(stripped_annotated):
        diff_index = min_len

    def _char_or_empty(text: str, idx: int) -> str:
        if idx < 0 or idx >= len(text):
            return ""
        return text[idx]

    def _excerpt(text: str, idx: int, radius: int = 24) -> str:
        if not text:
            return ""
        if idx < 0:
            idx = 0
        start = max(0, idx - radius)
        end = min(len(text), idx + radius)
        return text[start:end]

    nfc_base = unicodedata.normalize("NFC", normalized_base)
    nfc_annotated = unicodedata.normalize("NFC", stripped_annotated)
    ws_base = re.sub(r"\s+", " ", normalized_base).strip()
    ws_annotated = re.sub(r"\s+", " ", stripped_annotated).strip()
    return {
        "base_len": len(normalized_base),
        "annotated_len_with_tags": len(normalized_annotated),
        "annotated_len_without_tags": len(stripped_annotated),
        "diff_index": diff_index,
        "base_char": _char_or_empty(normalized_base, diff_index),
        "annotated_char": _char_or_empty(stripped_annotated, diff_index),
        "base_excerpt": _excerpt(normalized_base, diff_index),
        "annotated_excerpt": _excerpt(stripped_annotated, diff_index),
        "page_marker_count": normalized_annotated.count("<page>"),
        "segment_marker_count": normalized_annotated.count("||"),
        "nfc_equal_after_strip": nfc_base == nfc_annotated,
        "whitespace_equal_after_strip": ws_base == ws_annotated,
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
    method: str = "auto"
    mechanism: str = "json_direct"


async def segmentation_phase_2(
    spec: SegmentationPhase2Spec,
    *,
    client: OpenAIClient | None = None,
) -> dict[str, Any]:
    """Annotate segments with tokens using jieba for Mandarin or the generic flow."""

    telemetry = spec.telemetry or NullTelemetry()
    method = (spec.method or "auto").strip().lower()
    mechanism = (spec.mechanism or "json_direct").strip().lower()
    if mechanism in {"", "default"}:
        mechanism = "json_direct"

    if spec.language.lower().startswith("zh") and method in {"auto", "jieba"}:
        return _tokenize_with_jieba(spec.text, language=spec.language, telemetry=telemetry, op_id=spec.op_id)
    if method not in {"auto", "ai", "jieba"}:
        raise ValueError(f"Unknown segmentation method: {method}")
    if mechanism not in {"json_direct", "boundary_first"}:
        raise ValueError(f"Unknown segmentation_phase_2 mechanism: {mechanism}")
    if mechanism == "boundary_first":
        return await _segmentation_phase_2_boundary_first(spec, client=client, telemetry=telemetry)

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
    annotated = await generic_annotation(
        GenericAnnotationSpec(
            text=spec.text,
            language=spec.language,
            operation="segmentation_phase_2",
            build_prompt=build,
            telemetry=telemetry,
            op_id=spec.op_id,
            preserve_segment_surface=True,
        ),
        client=ai_client,
    )
    return _normalize_phase2_output(annotated)


_BOUNDARY_MARKER = "¦"


def _boundary_first_prompt(surface: str, *, language: str) -> str:
    return (
        "Insert token boundary markers into the segment for language-learning annotation.\n"
        f"Language: {language}\n"
        f"Use the marker {_BOUNDARY_MARKER!r} only between tokens. Do not add the marker at the beginning or end.\n"
        "Preserve every original character, including spaces and punctuation, exactly as given.\n"
        "Return only the boundary-marked segment, with no JSON, comments, markdown, or explanation.\n\n"
        "Segment:\n"
        "<startofsegment>\n"
        f"{surface}\n"
        "<endofsegment>"
    )


def _tokens_from_boundary_marked_text(marked: str, *, surface: str) -> list[dict[str, Any]] | None:
    candidate = _extract_between_tags(marked, "startofsegment", "endofsegment").strip()
    if not candidate:
        candidate = marked.strip()
    if not candidate:
        return None
    candidate = candidate.replace("|", _BOUNDARY_MARKER)
    if candidate.replace(_BOUNDARY_MARKER, "") != surface:
        return None
    parts = [part for part in candidate.split(_BOUNDARY_MARKER) if part != ""]
    if not parts or "".join(parts) != surface:
        return None
    return [{"surface": part} for part in parts]


async def _segmentation_phase_2_boundary_first(
    spec: SegmentationPhase2Spec,
    *,
    client: OpenAIClient | None,
    telemetry: Telemetry,
) -> dict[str, Any]:
    ai_client = client or OpenAIClient()
    base_op = spec.op_id or "segmentation_phase_2"
    telemetry.event(base_op, "info", "Using boundary-first segmentation_phase_2 mechanism")
    text_obj = json.loads(json.dumps(spec.text))
    for page_idx, page in enumerate(text_obj.get("pages", []) or []):
        for segment_idx, segment in enumerate(page.get("segments", []) or []):
            surface = str(segment.get("surface", ""))
            if not surface:
                segment["tokens"] = []
                continue
            segment_op_id = f"{base_op}-boundary-p{page_idx}-s{segment_idx}"
            prompt = _boundary_first_prompt(surface, language=spec.language)
            raw = await ai_client.chat_text(prompt, telemetry=telemetry, op_id=segment_op_id)
            tokens = _tokens_from_boundary_marked_text(str(raw or ""), surface=surface)
            if tokens is None:
                telemetry.event(
                    segment_op_id,
                    "warn",
                    "boundary-first segmentation_phase_2 output failed preservation check; using fallback tokenizer",
                    {"surface_preview": surface[:80], "response_preview": str(raw or "")[:120]},
                )
                tokens = _fallback_tokenize_surface(surface)
            segment["tokens"] = tokens
    return _normalize_phase2_output(text_obj)

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
