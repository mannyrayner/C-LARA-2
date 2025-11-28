"""Text generation pipeline step using the OpenAI chat API."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from core.ai_api import OpenAIClient
from core.telemetry import NullTelemetry, Telemetry


@dataclass(slots=True)
class TextGenSpec:
    """Specification for generating a new text."""

    description: dict[str, Any]
    language: str = "en"
    template_path: Path | None = None
    fewshot_paths: Iterable[Path] | None = None
    telemetry: Telemetry | None = None
    op_id: str | None = None


def _default_prompts_root() -> Path:
    return Path(__file__).resolve().parents[2] / "prompts"


def _load_template(language: str, *, prompts_root: Path) -> str:
    template_path = prompts_root / "text_gen" / language / "template.txt"
    return template_path.read_text(encoding="utf-8")


def _load_fewshots(language: str, *, prompts_root: Path) -> list[dict[str, Any]]:
    fewshot_dir = prompts_root / "text_gen" / language / "fewshots"
    if not fewshot_dir.exists():
        return []
    fewshots: list[dict[str, Any]] = []
    for path in sorted(fewshot_dir.glob("*.json")):
        fewshots.append(json.loads(path.read_text(encoding="utf-8")))
    return fewshots


def _build_prompt(template: str, *, description: dict[str, Any], fewshots: list[dict[str, Any]]) -> str:
    lines = [template.strip(), "", "Description:", json.dumps(description, indent=2)]
    if fewshots:
        lines.append("")
        lines.append("Few-shot examples:")
        for idx, example in enumerate(fewshots, start=1):
            lines.append(f"Example {idx} description:")
            lines.append(json.dumps(example.get("description", {}), indent=2))
            lines.append("Example output:")
            lines.append(json.dumps(example.get("output", {}), indent=2))
            lines.append("")
    lines.append(
        "Return a JSON object with keys: title, surface, annotations (object), pages (array), l2 (source language code), and optional l1 (target language code)."
    )
    return "\n".join(lines)


def _normalize_response(
    response: dict[str, Any], *, language: str, description: dict[str, Any]
) -> dict[str, Any]:
    text_json = {
        "l2": response.get("l2") or description.get("l2") or language,
        "l1": response.get("l1") or description.get("l1"),
        "title": response.get("title") or description.get("title"),
        "surface": response.get("surface", ""),
        "pages": response.get("pages") or [],
        "annotations": response.get("annotations") or {},
    }
    # Remove None entries while preserving expected keys
    return {k: v for k, v in text_json.items() if v is not None}


async def generate_text(
    spec: TextGenSpec,
    *,
    client: OpenAIClient | None = None,
) -> dict[str, Any]:
    """Generate a text from a description using a prompt template and few-shots."""

    prompts_root = spec.template_path.parent.parent if spec.template_path else _default_prompts_root()
    template = spec.template_path.read_text(encoding="utf-8") if spec.template_path else _load_template(spec.language, prompts_root=prompts_root)
    fewshots = (
        [json.loads(path.read_text(encoding="utf-8")) for path in spec.fewshot_paths]
        if spec.fewshot_paths
        else _load_fewshots(spec.language, prompts_root=prompts_root)
    )

    prompt = _build_prompt(template, description=spec.description, fewshots=fewshots)
    telemetry = spec.telemetry or NullTelemetry()
    ai_client = client or OpenAIClient()
    response = await ai_client.chat_json(prompt, telemetry=telemetry, op_id=spec.op_id)
    return _normalize_response(response, language=spec.language, description=spec.description)
