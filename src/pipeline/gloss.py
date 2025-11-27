"""Token-level glossing using the generic annotation harness."""
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
    return annotation_prompts.load_template("gloss", language, prompts_root=prompts_root)


def _load_fewshots(language: str, *, prompts_root: Path) -> list[dict[str, Any]]:
    return annotation_prompts.load_fewshots("gloss", language, prompts_root=prompts_root)


@dataclass(slots=True)
class GlossSpec:
    """Specification for glossing tokens within segments."""

    text: dict[str, Any]
    language: str = "en"  # L2
    target_language: str = "fr"  # L1 gloss language
    template_path: Path | None = None
    fewshot_paths: Iterable[Path] | None = None
    telemetry: Telemetry | None = None
    op_id: str | None = None


def _build_prompt(
    template: str,
    *,
    segment: dict[str, Any],
    fewshots: list[dict[str, Any]],
    target_language: str,
) -> str:
    output_instructions = [
        "Return a JSON object representing the segment.",
        "Preserve the original surface and tokens.",
        "For each token, add annotations.gloss: a short {} gloss.".format(target_language.upper()),
        "Tokens that share the same annotations.mwe_id must share the same gloss value (gloss the whole MWE).",
        "Use annotations.translation as a hint when present, but prefer concise dictionary-style glosses even when the translation is non-literal.",
    ]

    segment_json = json.dumps(segment, ensure_ascii=False, indent=2)
    header = f"Segment JSON to gloss into {target_language}:"
    return annotation_prompts.build_prompt(
        template,
        content_label=header,
        content=segment_json,
        fewshots=fewshots,
        output_instructions=output_instructions,
    )


async def annotate_gloss(
    spec: GlossSpec,
    *,
    client: OpenAIClient | None = None,
) -> dict[str, Any]:
    """Annotate tokens with glosses, preserving prior annotations."""

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
            operation="gloss",
            build_prompt=build,
            telemetry=telemetry,
            op_id=spec.op_id,
        ),
        client=ai_client,
    )

    # Ensure target language recorded if missing.
    if annotated.get("l1") is None:
        annotated["l1"] = spec.target_language

    return annotated
