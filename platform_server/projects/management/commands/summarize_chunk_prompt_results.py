from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError


CYCLE_RE = re.compile(r"^cycle_(\d+)$")
VALIDATION_RE = re.compile(r"^(?P<source_split>.+)-cycle_(?P<cycle>\d+)-on-(?P<split>.+)$")


class Command(BaseCommand):
    help = "Summarize available chunk prompt results across languages, splits, and cycles."

    def add_arguments(self, parser):
        parser.add_argument("--generated-dir", required=True)
        parser.add_argument("--output-json", required=True)
        parser.add_argument("--output-markdown", required=True)
        parser.add_argument("--languages", default="fr,de,en")
        parser.add_argument("--prompt-kind", default="segmentation")
        parser.add_argument("--overwrite", action="store_true")

    def handle(self, *args, **options):
        generated_dir = Path(options["generated_dir"]).resolve()
        output_json = Path(options["output_json"]).resolve()
        output_markdown = Path(options["output_markdown"]).resolve()
        languages = [item.strip() for item in options["languages"].split(",") if item.strip()]
        prompt_kind = options["prompt_kind"]
        if not generated_dir.exists():
            raise CommandError(f"generated directory not found: {generated_dir}")
        if not generated_dir.is_dir():
            raise CommandError(f"generated path is not a directory: {generated_dir}")
        if not options["overwrite"]:
            for path in (output_json, output_markdown):
                if path.exists():
                    raise CommandError(f"output already exists: {path}; pass --overwrite")

        results = summarize_results(generated_dir, languages=languages, prompt_kind=prompt_kind)
        payload = {
            "schema_version": 1,
            "generated_dir": str(generated_dir),
            "languages": languages,
            "prompt_kind": prompt_kind,
            "result_count": len(results),
            "results": results,
        }
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_markdown.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        output_markdown.write_text(render_markdown(payload), encoding="utf-8")
        self.stdout.write("Summarized chunk prompt results")
        self.stdout.write(f"Results: {len(results)}")
        self.stdout.write(f"JSON: {output_json}")
        self.stdout.write(f"Markdown: {output_markdown}")


def summarize_results(generated_dir: Path, *, languages: list[str], prompt_kind: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    results.extend(summarize_development_cycles(generated_dir, languages=languages, prompt_kind=prompt_kind))
    results.extend(summarize_validation_runs(generated_dir, languages=languages, prompt_kind=prompt_kind))
    return sorted(results, key=result_sort_key)


def summarize_development_cycles(generated_dir: Path, *, languages: list[str], prompt_kind: str) -> list[dict[str, Any]]:
    root = generated_dir / "prompt_improvement"
    if not root.exists():
        return []
    results: list[dict[str, Any]] = []
    for language in languages:
        prefix = f"{language}-{prompt_kind}-"
        for base_dir in root.iterdir():
            if not base_dir.is_dir() or not base_dir.name.startswith(prefix):
                continue
            split = base_dir.name[len(prefix) :]
            for cycle_dir in base_dir.iterdir():
                match = CYCLE_RE.match(cycle_dir.name)
                if not cycle_dir.is_dir() or not match:
                    continue
                cycle_number = int(match.group(1))
                result = result_from_brief(
                    brief_path=cycle_dir / "prompt_improvement_brief.json",
                    language=language,
                    prompt_kind=prompt_kind,
                    split=split,
                    source_split=split,
                    source_cycle_number=cycle_number,
                    result_type="development_cycle",
                    result_dir=cycle_dir,
                )
                if result:
                    results.append(result)
    return results


def summarize_validation_runs(generated_dir: Path, *, languages: list[str], prompt_kind: str) -> list[dict[str, Any]]:
    root = generated_dir / "prompt_validation"
    if not root.exists():
        return []
    results: list[dict[str, Any]] = []
    for language in languages:
        prefix = f"{language}-{prompt_kind}-"
        for run_dir in root.iterdir():
            if not run_dir.is_dir() or not run_dir.name.startswith(prefix):
                continue
            match = VALIDATION_RE.match(run_dir.name[len(prefix) :])
            if not match:
                continue
            result = result_from_brief(
                brief_path=run_dir / "prompt_improvement_brief.json",
                language=language,
                prompt_kind=prompt_kind,
                split=match.group("split"),
                source_split=match.group("source_split"),
                source_cycle_number=int(match.group("cycle")),
                result_type="heldout_evaluation",
                result_dir=run_dir,
            )
            if result:
                results.append(result)
    return results


def result_from_brief(
    *,
    brief_path: Path,
    language: str,
    prompt_kind: str,
    split: str,
    source_split: str,
    source_cycle_number: int,
    result_type: str,
    result_dir: Path,
) -> dict[str, Any] | None:
    if not brief_path.exists():
        return None
    brief = read_json(brief_path)
    summary = brief.get("summary") if isinstance(brief.get("summary"), dict) else {}
    records_compared = int(summary.get("records_compared") or 0)
    error_count = int(summary.get("error_count") or 0)
    accuracy = summary.get("accuracy")
    error_rate = round(1 - float(accuracy), 4) if isinstance(accuracy, (int, float)) else None
    return {
        "result_type": result_type,
        "language": language,
        "prompt_kind": prompt_kind,
        "split": split,
        "source_split": source_split,
        "source_cycle_number": source_cycle_number,
        "result_dir": str(result_dir),
        "brief_json": str(brief_path),
        "brief_markdown": str(result_dir / "prompt_improvement_brief.md"),
        "prompt_path": str(result_dir / "prompt.md"),
        "predictions_jsonl": str(result_dir / "predictions.jsonl"),
        "records_compared": records_compared,
        "accuracy": accuracy,
        "error_rate": error_rate,
        "error_count": error_count,
        "success_count": int(summary.get("success_count") or 0),
        "status_counts": summary.get("status_counts") if isinstance(summary.get("status_counts"), dict) else {},
    }


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def result_sort_key(result: dict[str, Any]) -> tuple[Any, ...]:
    split_order = {"development": 0, "validation": 1, "test": 2}
    return (
        result["language"],
        split_order.get(result["split"], 99),
        result["split"],
        result["source_split"],
        result["source_cycle_number"],
        result["result_type"],
    )


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Chunk prompt result summary",
        "",
        f"- Generated directory: `{payload['generated_dir']}`",
        f"- Languages: `{', '.join(payload['languages'])}`",
        f"- Prompt kind: `{payload['prompt_kind']}`",
        f"- Results found: {payload['result_count']}",
        "",
        "| Language | Split | Source cycle | Type | Records | Accuracy | Error rate | Errors | Status counts | Brief |",
        "|---|---|---:|---|---:|---:|---:|---:|---|---|",
    ]
    for result in payload["results"]:
        status_counts = json.dumps(result["status_counts"], ensure_ascii=False, sort_keys=True)
        accuracy = format_number(result["accuracy"])
        error_rate = format_number(result["error_rate"])
        lines.append(
            "| {language} | {split} | {source_cycle_number} | {result_type} | {records_compared} | {accuracy} | {error_rate} | {error_count} | `{status_counts}` | `{brief_json}` |".format(
                language=result["language"],
                split=result["split"],
                source_cycle_number=result["source_cycle_number"],
                result_type=result["result_type"],
                records_compared=result["records_compared"],
                accuracy=accuracy,
                error_rate=error_rate,
                error_count=result["error_count"],
                status_counts=status_counts,
                brief_json=result["brief_json"],
            )
        )
    return "\n".join(lines) + "\n"


def format_number(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        return f"{float(value):.4f}"
    return str(value)
