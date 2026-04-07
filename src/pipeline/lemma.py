"""Token-level lemmatization using the generic annotation harness."""
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
    return annotation_prompts.load_template("lemma", language, prompts_root=prompts_root)


def _load_fewshots(language: str, *, prompts_root: Path) -> list[dict[str, Any]]:
    return annotation_prompts.load_fewshots("lemma", language, prompts_root=prompts_root)


@dataclass(slots=True)
class LemmaSpec:
    """Specification for lemmatizing tokens within segments."""

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
        "For each token, add annotations.lemma (canonical lemma) and annotations.pos (coarse POS tag).",
        "Tokens that share the same annotations.mwe_id should share the same lemma (e.g., phrasal verb parts).",
        "For MWE tokens, the shared lemma should match the full MWE surface string represented by those tokens.",
    ]

    segment_json = json.dumps(segment, ensure_ascii=False, indent=2)
    return annotation_prompts.build_prompt(
        template,
        content_label="Segment JSON to annotate with lemmas and POS:",
        content=segment_json,
        fewshots=fewshots,
        output_instructions=output_instructions,
    )


async def annotate_lemmas(
    spec: LemmaSpec,
    *,
    client: OpenAIClient | None = None,
) -> dict[str, Any]:
    """Annotate tokens with lemma and POS, preserving prior annotations."""

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
            operation="lemma",
            build_prompt=build,
            telemetry=telemetry,
            op_id=spec.op_id,
        ),
        client=ai_client,
    )

    return _normalize_mwe_lemmas_to_surface(annotated)


def _normalize_mwe_lemmas_to_surface(text: dict[str, Any]) -> dict[str, Any]:
    """Ensure each MWE group uses a lemma matching the detected MWE surface.

    We trust the MWE detector's token grouping. If the lemma model returns a
    shortened canonical form for that group, we overwrite it with the explicit
    MWE surface string so annotations remain internally consistent.
    """

    for page in text.get("pages", []) or []:
        for segment in page.get("segments", []) or []:
            tokens = segment.get("tokens", []) or []
            segment_mwes = (segment.get("annotations") or {}).get("mwes") or []

            mwe_surface_by_id: dict[str, str] = {}
            for mwe in segment_mwes:
                mwe_id = str(mwe.get("id") or "").strip()
                mwe_tokens = [str(tok).strip() for tok in (mwe.get("tokens") or []) if str(tok).strip()]
                if mwe_id and mwe_tokens:
                    mwe_surface_by_id[mwe_id] = " ".join(mwe_tokens)

            token_surfaces_by_id: dict[str, list[str]] = {}
            token_indices_by_id: dict[str, list[int]] = {}
            for idx, token in enumerate(tokens):
                ann = token.get("annotations") or {}
                mwe_id = ann.get("mwe_id")
                if not mwe_id:
                    continue
                key = str(mwe_id)
                surface = str(token.get("surface") or "").strip()
                if surface:
                    token_surfaces_by_id.setdefault(key, []).append(surface)
                token_indices_by_id.setdefault(key, []).append(idx)

            for mwe_id, indices in token_indices_by_id.items():
                normalized = (
                    mwe_surface_by_id.get(mwe_id)
                    or " ".join(token_surfaces_by_id.get(mwe_id, []))
                ).strip()
                if not normalized:
                    continue
                for token_idx in indices:
                    token = tokens[token_idx]
                    ann = token.setdefault("annotations", {})
                    ann["lemma"] = normalized

    return text
