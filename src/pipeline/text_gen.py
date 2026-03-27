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

    description: dict[str, Any] | str
    language: str = "en"
    template_path: Path | None = None
    fewshot_paths: Iterable[Path] | None = None
    telemetry: Telemetry | None = None
    op_id: str | None = None


def _default_prompts_root() -> Path:
    return Path(__file__).resolve().parents[2] / "prompts"


def _load_template(language: str, *, prompts_root: Path) -> str:
    candidate_paths = [
        prompts_root / "text_gen" / language / "template.txt",
        prompts_root / "text_gen" / "default" / "template.txt",
        prompts_root / "text_gen" / "en" / "template.txt",
    ]
    for template_path in candidate_paths:
        if template_path.exists():
            return template_path.read_text(encoding="utf-8")
    raise FileNotFoundError(f"No text_gen template found for language={language!r}")


def _load_fewshots(language: str, *, prompts_root: Path) -> list[dict[str, Any]]:
    candidate_dirs = [
        prompts_root / "text_gen" / language / "fewshots",
        prompts_root / "text_gen" / "default" / "fewshots",
        prompts_root / "text_gen" / "en" / "fewshots",
    ]
    fewshot_dir = next((path for path in candidate_dirs if path.exists()), None)
    if fewshot_dir is None:
        return []
    fewshots: list[dict[str, Any]] = []
    for path in sorted(fewshot_dir.glob("*.json")):
        fewshots.append(json.loads(path.read_text(encoding="utf-8")))
    return fewshots


def _instantiate_language_vars(value: Any, *, language: str) -> Any:
    if isinstance(value, str):
        return value.replace("{text_language}", language)
    if isinstance(value, list):
        return [_instantiate_language_vars(item, language=language) for item in value]
    if isinstance(value, dict):
        return {k: _instantiate_language_vars(v, language=language) for k, v in value.items()}
    return value


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
    response: dict[str, Any], *, language: str, description: dict[str, Any] | str
) -> dict[str, Any]:
    desc_dict: dict[str, Any]
    if isinstance(description, dict):
        desc_dict = description
    else:
        desc_dict = {}
    text_json = {
        "l2": response.get("l2") or desc_dict.get("l2") or language,
        "l1": response.get("l1") or desc_dict.get("l1"),
        "title": response.get("title") or desc_dict.get("title"),
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
    template = _instantiate_language_vars(template, language=spec.language)
    fewshots = _instantiate_language_vars(fewshots, language=spec.language)

    description_payload: dict[str, Any] | str = spec.description
    if isinstance(description_payload, str):
        description_payload = {"description": description_payload}

    prompt = _build_prompt(template, description=description_payload, fewshots=fewshots)
    telemetry = spec.telemetry or NullTelemetry()
    ai_client = client or OpenAIClient()
    response = await ai_client.chat_json(prompt, telemetry=telemetry, op_id=spec.op_id)
    return _normalize_response(response, language=spec.language, description=description_payload)
