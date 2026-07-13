from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from .review_fewshots import _resolve_cli_path


class Command(BaseCommand):
    help = "Format MWE prompt outputs JSONL as human-readable Markdown."

    def add_arguments(self, parser):
        parser.add_argument("--outputs-jsonl", required=True)
        parser.add_argument("--output-markdown", required=True)
        parser.add_argument("--max-records", type=int, default=0, help="Maximum records to include; 0 means all records.")
        parser.add_argument("--errors-only", action="store_true", help="Only include records where gold and predicted spans differ.")
        parser.add_argument("--overwrite", action="store_true")

    def handle(self, *args, **options):
        outputs_path = _resolve_cli_path(options["outputs_jsonl"], "")
        output_markdown = _resolve_cli_path(options["output_markdown"], "")
        if not outputs_path.exists():
            raise CommandError(f"outputs JSONL not found: {outputs_path}")
        if output_markdown.exists() and not options["overwrite"]:
            raise CommandError(f"output markdown already exists: {output_markdown}; pass --overwrite")
        records = load_records(outputs_path)
        if options["errors_only"]:
            records = [record for record in records if spans(record.get("gold_mwes") or []) != spans(record.get("predicted_mwes") or [])]
        max_records = int(options["max_records"] or 0)
        if max_records > 0:
            records = records[:max_records]
        output_markdown.parent.mkdir(parents=True, exist_ok=True)
        output_markdown.write_text(build_markdown(records, source_path=outputs_path), encoding="utf-8")
        self.stdout.write(f"Formatted MWE outputs: records={len(records)} markdown={output_markdown}")


def load_records(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise CommandError(f"Invalid JSON on line {line_number} of {path}: {exc}") from exc
    return records


def spans(mwes: list[Any]) -> list[list[str]]:
    normalized: list[list[str]] = []
    for mwe in mwes:
        if not isinstance(mwe, dict):
            continue
        tokens = mwe.get("tokens")
        if not isinstance(tokens, list):
            continue
        span = [str(token) for token in tokens if str(token).strip()]
        if len(span) >= 2:
            normalized.append(span)
    return sorted(normalized, key=lambda span: (" ".join(token.lower() for token in span), len(span)))


def build_markdown(records: list[dict[str, Any]], *, source_path: Path) -> str:
    lines = [
        "# MWE prompt outputs",
        "",
        f"- Source: `{source_path}`",
        f"- Records shown: {len(records)}",
        "",
    ]
    if not records:
        lines.append("No records to display.")
        return "\n".join(lines) + "\n"
    for record in records:
        record_id = record.get("record_id") or "unknown-record"
        lines.extend(
            [
                f"## {record_id}",
                "",
                f"- Project: {record.get('project_id')} — {record.get('project_title') or ''}",
                f"- Page/segment: {record.get('page_index')} / {record.get('segment_index')}",
                "",
                "### Segment",
                "",
                markdown_text(record.get("segment_surface")),
                "",
                "### Gold MWEs",
                "",
                format_spans(spans(record.get("gold_mwes") or [])),
                "",
                "### Predicted MWEs",
                "",
                format_spans(spans(record.get("predicted_mwes") or [])),
                "",
                "### Model analysis",
                "",
                markdown_text(record.get("mwe_analysis"), default="not recorded"),
                "",
            ]
        )
        translation_context = record.get("translation_context") or []
        if translation_context:
            lines.extend(["### Translation context", ""])
            for item in translation_context:
                if not isinstance(item, dict):
                    continue
                label = item.get("language") or "unknown"
                source = item.get("source") or "unknown source"
                text = markdown_text(item.get("text"))
                lines.append(f"- **{label}** ({source}): {text}")
            lines.append("")
    return "\n".join(lines) + "\n"


def format_spans(span_list: list[list[str]]) -> str:
    if not span_list:
        return "None"
    return "\n".join(f"- {' '.join(span)}" for span in span_list)


def markdown_text(value: Any, *, default: str = "") -> str:
    if value is None or value == "":
        return default
    if isinstance(value, str):
        return value
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)
