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
        "Only include MWEs containing at least two tokens; never mark single-token expressions as MWEs.",
        "For each token that belongs to an MWE, set token.annotations.mwe_id to the corresponding MWE id.",
    ]

    # Only send token-level material for MWE analysis.
    # Segment-level fields such as translation can distract the model and are not
    # required to identify MWEs.
    segment_json = json.dumps(
        {
            "tokens": segment.get("tokens", []),
        },
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
    return _normalize_mwes(annotated)


def _normalize_mwes(text: dict[str, Any]) -> dict[str, Any]:
    pages = text.get("pages")
    if not isinstance(pages, list):
        return text

    for page in pages:
        segments = page.get("segments")
        if not isinstance(segments, list):
            continue
        for segment in segments:
            annotations = segment.get("annotations")
            if not isinstance(annotations, dict):
                continue
            mwes = annotations.get("mwes")
            if not isinstance(mwes, list):
                continue

            valid_ids: set[str] = set()
            filtered: list[dict[str, Any]] = []
            for entry in mwes:
                if not isinstance(entry, dict):
                    continue
                mwe_id = str(entry.get("id") or "")
                tokens = entry.get("tokens")
                if not mwe_id or not isinstance(tokens, list):
                    continue
                token_surfaces = [str(tok) for tok in tokens if str(tok).strip()]
                if len(token_surfaces) < 2:
                    continue
                normalized_entry = dict(entry)
                normalized_entry["tokens"] = token_surfaces
                filtered.append(normalized_entry)
                valid_ids.add(mwe_id)
            annotations["mwes"] = filtered

            tokens = segment.get("tokens")
            if not isinstance(tokens, list):
                continue
            for token in tokens:
                token_ann = token.get("annotations")
                if not isinstance(token_ann, dict):
                    continue
                mwe_id = token_ann.get("mwe_id")
                if mwe_id and str(mwe_id) not in valid_ids:
                    token_ann.pop("mwe_id", None)
    return text
