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
        "For each token that belongs to an MWE, set token.annotations.mwe_id to the corresponding MWE id.",
    ]

    segment_json = json.dumps(segment, ensure_ascii=False, indent=2)
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
        ),
        client=ai_client,
    )

    return annotated
