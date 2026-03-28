"""Helpers for loading prompt templates and building prompts for annotation steps."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable


def default_prompts_root() -> Path:
    """Return the repository prompts directory."""

    return Path(__file__).resolve().parents[2] / "prompts"


def load_template(operation: str, language: str, *, prompts_root: Path | None = None) -> str:
    prompts_root = prompts_root or default_prompts_root()
    candidate_paths = [
        prompts_root / operation / language / "template.txt",
        prompts_root / operation / "default" / "template.txt",
        prompts_root / operation / "en" / "template.txt",
    ]
    for template_path in candidate_paths:
        if template_path.exists():
            return template_path.read_text(encoding="utf-8")
    raise FileNotFoundError(
        f"No template found for operation={operation!r}, language={language!r} under {prompts_root}"
    )


def load_fewshots(operation: str, language: str, *, prompts_root: Path | None = None) -> list[dict[str, Any]]:
    prompts_root = prompts_root or default_prompts_root()
    candidate_dirs = [
        prompts_root / operation / language / "fewshots",
        prompts_root / operation / "default" / "fewshots",
        prompts_root / operation / "en" / "fewshots",
    ]
    fewshot_dir = next((path for path in candidate_dirs if path.exists()), None)
    if fewshot_dir is None:
        return []
    fewshots: list[dict[str, Any]] = []
    for path in sorted(fewshot_dir.glob("*.json")):
        fewshots.append(json.loads(path.read_text(encoding="utf-8")))
    return fewshots


def build_prompt(
    template: str,
    *,
    content_label: str,
    content: str,
    fewshots: Iterable[dict[str, Any]] = (),
    output_instructions: Iterable[str] = (),
) -> str:
    lines: list[str] = [template.strip(), "", content_label, content.strip(), ""]
    fewshot_list = list(fewshots)
    if fewshot_list:
        lines.append("Few-shot examples:")
        for idx, example in enumerate(fewshot_list, start=1):
            lines.append(f"Example {idx} input:")
            lines.append(example.get("input", "").strip())
            lines.append("Example output:")
            lines.append(json.dumps(example.get("output", {}), indent=2))
            lines.append("")
    for instruction in output_instructions:
        lines.append(instruction)
    return "\n".join(lines)
