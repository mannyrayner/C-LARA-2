from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError


CYCLE_RE = re.compile(r"^cycle_(\d+)$")


class Command(BaseCommand):
    help = "Summarize cycle-specific chunk prompt-improvement artifacts."

    def add_arguments(self, parser):
        parser.add_argument("--cycles-dir", required=True)
        parser.add_argument("--output-json", required=True)
        parser.add_argument("--output-markdown", required=True)
        parser.add_argument("--overwrite", action="store_true")

    def handle(self, *args, **options):
        cycles_dir = Path(options["cycles_dir"]).resolve()
        output_json = Path(options["output_json"]).resolve()
        output_markdown = Path(options["output_markdown"]).resolve()
        if not cycles_dir.exists():
            raise CommandError(f"cycles directory not found: {cycles_dir}")
        if not cycles_dir.is_dir():
            raise CommandError(f"cycles path is not a directory: {cycles_dir}")
        if not options["overwrite"]:
            for path in (output_json, output_markdown):
                if path.exists():
                    raise CommandError(f"output already exists: {path}; pass --overwrite")

        cycles = summarize_cycles(cycles_dir)
        payload = {
            "schema_version": 1,
            "cycles_dir": str(cycles_dir),
            "cycle_count": len(cycles),
            "cycles": cycles,
        }
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_markdown.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        output_markdown.write_text(render_markdown(payload), encoding="utf-8")
        self.stdout.write("Summarized chunk prompt-improvement cycles")
        self.stdout.write(f"Cycles: {len(cycles)}")
        self.stdout.write(f"JSON: {output_json}")
        self.stdout.write(f"Markdown: {output_markdown}")


def summarize_cycles(cycles_dir: Path) -> list[dict[str, Any]]:
    cycles: list[dict[str, Any]] = []
    for path in cycles_dir.iterdir():
        if not path.is_dir():
            continue
        match = CYCLE_RE.match(path.name)
        if not match:
            continue
        cycle_number = int(match.group(1))
        brief_path = path / "prompt_improvement_brief.json"
        brief = read_json(brief_path) if brief_path.exists() else {}
        summary = brief.get("summary") if isinstance(brief.get("summary"), dict) else {}
        cycles.append(
            {
                "cycle_number": cycle_number,
                "cycle_dir": str(path),
                "prompt_path": str(path / "prompt.md"),
                "predictions_jsonl": str(path / "predictions.jsonl"),
                "prompt_revision_path": str(path / "prompt_revision.md"),
                "has_prompt": (path / "prompt.md").exists(),
                "has_predictions": (path / "predictions.jsonl").exists(),
                "has_prompt_revision": (path / "prompt_revision.md").exists(),
                "has_brief": brief_path.exists(),
                "records_compared": int(summary.get("records_compared") or 0),
                "accuracy": summary.get("accuracy"),
                "error_count": int(summary.get("error_count") or 0),
                "success_count": int(summary.get("success_count") or 0),
                "status_counts": summary.get("status_counts") if isinstance(summary.get("status_counts"), dict) else {},
            }
        )
    return sorted(cycles, key=lambda item: item["cycle_number"])


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Chunk prompt-improvement cycle summary",
        "",
        f"- Cycles directory: `{payload['cycles_dir']}`",
        f"- Cycle count: {payload['cycle_count']}",
        "",
        "| Cycle | Records | Accuracy | Errors | Status counts | Prompt | Predictions | Revision | Brief |",
        "|---:|---:|---:|---:|---|---|---|---|---|",
    ]
    for cycle in payload["cycles"]:
        status_counts = json.dumps(cycle["status_counts"], ensure_ascii=False, sort_keys=True)
        accuracy = "" if cycle["accuracy"] is None else str(cycle["accuracy"])
        lines.append(
            "| {cycle_number} | {records_compared} | {accuracy} | {error_count} | `{status_counts}` | {prompt} | {predictions} | {revision} | {brief} |".format(
                cycle_number=cycle["cycle_number"],
                records_compared=cycle["records_compared"],
                accuracy=accuracy,
                error_count=cycle["error_count"],
                status_counts=status_counts,
                prompt=checkbox(cycle["has_prompt"]),
                predictions=checkbox(cycle["has_predictions"]),
                revision=checkbox(cycle["has_prompt_revision"]),
                brief=checkbox(cycle["has_brief"]),
            )
        )
    return "\n".join(lines) + "\n"


def checkbox(value: bool) -> str:
    return "yes" if value else "no"
