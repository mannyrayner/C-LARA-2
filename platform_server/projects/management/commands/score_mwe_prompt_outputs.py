from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from .review_fewshots import _resolve_cli_path


class Command(BaseCommand):
    help = "Score MWE prompt outputs against extracted gold MWE annotations."

    def add_arguments(self, parser):
        parser.add_argument("--outputs-jsonl", required=True)
        parser.add_argument("--output-dir", required=True)
        parser.add_argument("--split", default="development")
        parser.add_argument("--overwrite", action="store_true")

    def handle(self, *args, **options):
        outputs_path = _resolve_cli_path(options["outputs_jsonl"], "")
        output_dir = _resolve_cli_path(options["output_dir"], "")
        if output_dir.exists() and any(output_dir.iterdir()) and not options["overwrite"]:
            raise CommandError(f"output directory already exists and is not empty: {output_dir}; pass --overwrite")
        output_dir.mkdir(parents=True, exist_ok=True)
        records = [json.loads(line) for line in outputs_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        scored = [score_record(record) for record in records]
        summary = summarize_scores(scored, split=str(options["split"] or ""), outputs_path=outputs_path)
        per_record_path = output_dir / "per_record_scores.jsonl"
        with per_record_path.open("w", encoding="utf-8") as out:
            for record in scored:
                out.write(json.dumps(record, ensure_ascii=False) + "\n")
        summary["per_record_scores_jsonl"] = str(per_record_path)
        summary_path = output_dir / "summary.json"
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        write_markdown(output_dir / "summary.md", summary=summary, scored=scored)
        self.stdout.write(f"MWE scoring complete: F1={summary['f1']:.3f} precision={summary['precision']:.3f} recall={summary['recall']:.3f}")
        self.stdout.write(f"Summary: {summary_path}")


def mwe_spans(mwes: list[Any]) -> set[tuple[str, ...]]:
    spans: set[tuple[str, ...]] = set()
    for mwe in mwes or []:
        if not isinstance(mwe, dict):
            continue
        tokens = mwe.get("tokens")
        if not isinstance(tokens, list):
            continue
        normalized = tuple(str(token).strip().lower() for token in tokens if str(token).strip())
        if len(normalized) >= 2:
            spans.add(normalized)
    return spans


def score_record(record: dict[str, Any]) -> dict[str, Any]:
    gold = mwe_spans(record.get("gold_mwes") or [])
    predicted = mwe_spans(record.get("predicted_mwes") or [])
    tp = len(gold & predicted)
    fp = len(predicted - gold)
    fn = len(gold - predicted)
    return {
        "record_id": record.get("record_id"),
        "language": record.get("language"),
        "project_id": record.get("project_id"),
        "segment_surface": record.get("segment_surface"),
        "gold_spans": [list(span) for span in sorted(gold)],
        "predicted_spans": [list(span) for span in sorted(predicted)],
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
        "exact_match": gold == predicted,
    }


def summarize_scores(scored: list[dict[str, Any]], *, split: str, outputs_path: Path) -> dict[str, Any]:
    tp = sum(int(record["true_positive"]) for record in scored)
    fp = sum(int(record["false_positive"]) for record in scored)
    fn = sum(int(record["false_negative"]) for record in scored)
    precision = tp / (tp + fp) if tp + fp else 1.0 if not any(record["gold_spans"] for record in scored) else 0.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    exact = sum(1 for record in scored if record["exact_match"])
    return {
        "schema_version": 1,
        "split": split,
        "outputs_jsonl": str(outputs_path),
        "record_count": len(scored),
        "exact_match_count": exact,
        "exact_match_rate": exact / len(scored) if scored else 0.0,
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def write_markdown(path: Path, *, summary: dict[str, Any], scored: list[dict[str, Any]]) -> None:
    lines = [
        "# MWE prompt score summary",
        "",
        f"- Split: `{summary['split']}`",
        f"- Records: {summary['record_count']}",
        f"- Exact match: {summary['exact_match_count']} ({summary['exact_match_rate']:.1%})",
        f"- Precision: {summary['precision']:.3f}",
        f"- Recall: {summary['recall']:.3f}",
        f"- F1: {summary['f1']:.3f}",
        "",
        "## Error examples",
        "",
    ]
    examples = [record for record in scored if record["false_positive"] or record["false_negative"]][:25]
    if not examples:
        lines.append("No mismatching records in the first scored set.")
    for record in examples:
        lines.extend(
            [
                f"### {record['record_id']}",
                "",
                record.get("segment_surface") or "",
                "",
                f"- Gold: {record['gold_spans']}",
                f"- Predicted: {record['predicted_spans']}",
                "",
            ]
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
