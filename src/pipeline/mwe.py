"""Multi-word expression detection using the generic annotation harness."""
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
    return annotation_prompts.load_template("mwe", language, prompts_root=prompts_root)


def _load_fewshots(language: str, *, prompts_root: Path) -> list[dict[str, Any]]:
    return annotation_prompts.load_fewshots("mwe", language, prompts_root=prompts_root)


@dataclass(slots=True)
class MWESpec:
    """Specification for detecting MWEs within tokenized segments."""

    text: dict[str, Any]
    language: str = "en"
    template_path: Path | None = None
    fewshot_paths: Iterable[Path] | None = None
    telemetry: Telemetry | None = None
    op_id: str | None = None


def _build_prompt(
    template: str,
    *,
    segment: dict[str, Any],
    fewshots: list[dict[str, Any]],
) -> str:
    output_instructions = [
        "Return a JSON object representing the segment.",
        "Preserve the original surface and tokens.",
        "If MWEs are found, attach segment.annotations.mwes as a list of objects with keys id, tokens (array of token surfaces), and label.",
        "Also attach segment.annotations.mwe_analysis as a brief explanation of the candidate MWEs considered and why the final MWEs were selected or rejected.",
        "Only include MWEs containing at least two tokens; never mark single-token expressions as MWEs.",
        "For each token that belongs to an MWE, set token.annotations.mwe_id to the corresponding MWE id.",
    ]

    segment_payload: dict[str, Any] = {"tokens": segment.get("tokens", [])}
    translation_context = (segment.get("annotations") or {}).get("mwe_translation_context")
    if isinstance(translation_context, list) and translation_context:
        segment_payload["translation_context"] = translation_context
    segment_json = json.dumps(
        segment_payload,
        ensure_ascii=False,
        indent=2,
    )
    return annotation_prompts.build_prompt(
        template,
        content_label="Segment JSON to annotate for MWEs:",
        content=segment_json,
        fewshots=fewshots,
        output_instructions=output_instructions,
    )


async def annotate_mwes(
    spec: MWESpec,
    *,
    client: OpenAIClient | None = None,
) -> dict[str, Any]:
    """Detect multi-word expressions and mark tokens with shared IDs."""

    prompts_root = (
        spec.template_path.parent.parent if spec.template_path else annotation_prompts.default_prompts_root()
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
        return _build_prompt(template, segment=segment, fewshots=fewshots)

    telemetry = spec.telemetry or NullTelemetry()
    ai_client = client or OpenAIClient()

    annotated = await generic_annotation(
        GenericAnnotationSpec(
            text=spec.text,
            language=spec.language,
            operation="mwe",
            build_prompt=build,
            telemetry=telemetry,
            op_id=spec.op_id,
            preserve_segment_surface=True,
        ),
        client=ai_client,
    )
    restored = _restore_token_surfaces(spec.text, annotated)
    return normalize_mwes(restored)


def _restore_token_surfaces(original: dict[str, Any], annotated: dict[str, Any]) -> dict[str, Any]:
    original_pages = original.get("pages") if isinstance(original, dict) else None
    annotated_pages = annotated.get("pages") if isinstance(annotated, dict) else None
    if not isinstance(original_pages, list) or not isinstance(annotated_pages, list):
        return annotated

    for p_idx, page in enumerate(annotated_pages):
        if p_idx >= len(original_pages):
            break
        orig_page = original_pages[p_idx] if isinstance(original_pages[p_idx], dict) else {}
        orig_segments = orig_page.get("segments") if isinstance(orig_page, dict) else []
        segments = page.get("segments") if isinstance(page, dict) else []
        if not isinstance(orig_segments, list) or not isinstance(segments, list):
            continue
        for s_idx, segment in enumerate(segments):
            if s_idx >= len(orig_segments):
                break
            orig_segment = orig_segments[s_idx] if isinstance(orig_segments[s_idx], dict) else {}
            orig_tokens = orig_segment.get("tokens") if isinstance(orig_segment, dict) else []
            tokens = segment.get("tokens") if isinstance(segment, dict) else []
            if not isinstance(orig_tokens, list) or not isinstance(tokens, list):
                continue
            for t_idx, token in enumerate(tokens):
                if t_idx >= len(orig_tokens):
                    break
                if not isinstance(token, dict) or not isinstance(orig_tokens[t_idx], dict):
                    continue
                token["surface"] = str(orig_tokens[t_idx].get("surface", ""))
    return annotated


def normalize_mwes(text: dict[str, Any]) -> dict[str, Any]:
    pages = text.get("pages")
    if not isinstance(pages, list):
        return text

    for page_idx, page in enumerate(pages):
        segments = page.get("segments")
        if not isinstance(segments, list):
            continue
        page_counter = 1
        for seg_idx, segment in enumerate(segments):
            annotations = segment.get("annotations")
            if not isinstance(annotations, dict):
                continue
            mwes = annotations.get("mwes")
            if not isinstance(mwes, list):
                continue

            id_to_surfaces: dict[str, list[str]] = {}
            tokens = segment.get("tokens")
            if isinstance(tokens, list):
                for token in tokens:
                    if not isinstance(token, dict):
                        continue
                    tok_surface = str(token.get("surface") or "")
                    tok_ann = token.get("annotations")
                    if not isinstance(tok_ann, dict):
                        continue
                    mwe_id = tok_ann.get("mwe_id")
                    if not mwe_id:
                        continue
                    if tok_surface.strip():
                        id_to_surfaces.setdefault(str(mwe_id), []).append(tok_surface)

            valid_ids: set[str] = set()
            filtered: list[dict[str, Any]] = []
            for entry in mwes:
                if not isinstance(entry, dict):
                    continue
                mwe_id = str(entry.get("id") or "")
                tokens = entry.get("tokens")
                if not mwe_id or not isinstance(tokens, list):
                    continue
                token_surfaces = id_to_surfaces.get(mwe_id) or [str(tok) for tok in tokens if str(tok).strip()]
                if len(token_surfaces) < 2:
                    continue
                normalized_entry = dict(entry)
                normalized_entry["tokens"] = token_surfaces
                filtered.append(normalized_entry)
                valid_ids.add(mwe_id)

            id_remap = {old_id: f"p{page_idx}m{page_counter + i}" for i, old_id in enumerate(sorted(valid_ids))}
            page_counter += len(id_remap)
            for entry in filtered:
                old_id = str(entry.get("id") or "")
                if old_id in id_remap:
                    entry["id"] = id_remap[old_id]
            annotations["mwes"] = filtered

            tokens = segment.get("tokens")
            if not isinstance(tokens, list):
                continue
            for token in tokens:
                token_ann = token.get("annotations")
                if not isinstance(token_ann, dict):
                    continue
                mwe_id = token_ann.get("mwe_id")
                if not mwe_id:
                    continue
                str_id = str(mwe_id)
                if str_id not in valid_ids:
                    token_ann.pop("mwe_id", None)
                    continue
                token_ann["mwe_id"] = id_remap.get(str_id, str_id)
    return text
