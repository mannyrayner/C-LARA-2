"""Segmentation phase 1: split raw text into pages and segments."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from core.ai_api import OpenAIClient
from core.telemetry import NullTelemetry, Telemetry


@dataclass(slots=True)
class SegmentationSpec:
    """Specification for segmentation phase 1."""

    text: str
    language: str = "en"
    template_path: Path | None = None
    fewshot_paths: Iterable[Path] | None = None
    telemetry: Telemetry | None = None
    op_id: str | None = None


def _default_prompts_root() -> Path:
    return Path(__file__).resolve().parents[2] / "prompts"


def _load_template(language: str, *, prompts_root: Path) -> str:
    template_path = prompts_root / "segmentation_phase_1" / language / "template.txt"
    return template_path.read_text(encoding="utf-8")


def _load_fewshots(language: str, *, prompts_root: Path) -> list[dict[str, Any]]:
    fewshot_dir = prompts_root / "segmentation_phase_1" / language / "fewshots"
    if not fewshot_dir.exists():
        return []
    fewshots: list[dict[str, Any]] = []
    for path in sorted(fewshot_dir.glob("*.json")):
        fewshots.append(json.loads(path.read_text(encoding="utf-8")))
    return fewshots


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

    prompts_root = spec.template_path.parent.parent if spec.template_path else _default_prompts_root()
    template = spec.template_path.read_text(encoding="utf-8") if spec.template_path else _load_template(spec.language, prompts_root=prompts_root)
    fewshots = (
        [json.loads(path.read_text(encoding="utf-8")) for path in spec.fewshot_paths]
        if spec.fewshot_paths
        else _load_fewshots(spec.language, prompts_root=prompts_root)
    )

    prompt = _build_prompt(template, text=spec.text, fewshots=fewshots)
    telemetry = spec.telemetry or NullTelemetry()
    ai_client = client or OpenAIClient()
    response = await ai_client.chat_json(prompt, telemetry=telemetry, op_id=spec.op_id)
    return _normalize_response(response, text=spec.text, language=spec.language)
