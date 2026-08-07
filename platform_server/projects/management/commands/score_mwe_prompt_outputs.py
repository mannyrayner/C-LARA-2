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
        parser.add_argument("--gold-jsonl", default="", help="Optional latest gold records to override gold embedded in outputs.")
        parser.add_argument("--output-dir", required=True)
        parser.add_argument("--split", default="development")
        parser.add_argument("--overwrite", action="store_true")
        parser.add_argument("--project-ids", default="", help="Optional comma-separated project ids to score from the outputs file.")

    def handle(self, *args, **options):
        outputs_path = _resolve_cli_path(options["outputs_jsonl"], "")
        output_dir = _resolve_cli_path(options["output_dir"], "")
        if output_dir.exists() and any(output_dir.iterdir()) and not options["overwrite"]:
            raise CommandError(f"output directory already exists and is not empty: {output_dir}; pass --overwrite")
        output_dir.mkdir(parents=True, exist_ok=True)
        project_ids = parse_project_ids(str(options.get("project_ids") or ""))
        records = [json.loads(line) for line in outputs_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if options.get("gold_jsonl"):
            gold_path = _resolve_cli_path(options["gold_jsonl"], "")
            latest_gold = latest_records(gold_path)
            records = [merge_latest_gold(record, latest_gold.get(str(record.get("record_id") or ""))) for record in records]
        if project_ids:
            records = [record for record in records if int(record.get("project_id") or 0) in project_ids]
        scored = [score_record(record) for record in records]
        summary = summarize_scores(scored, split=str(options["split"] or ""), outputs_path=outputs_path)
        summary["project_ids"] = sorted(project_ids)
        per_record_path = output_dir / "per_record_scores.jsonl"
        with per_record_path.open("w", encoding="utf-8") as out:
            for record in scored:
                out.write(json.dumps(record, ensure_ascii=False) + "\n")
        summary["per_record_scores_jsonl"] = str(per_record_path)
        summary_path = output_dir / "summary.json"
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        write_markdown(output_dir / "summary.md", summary=summary, scored=scored)
        self.stdout.write(f"MWE scoring complete: F1={summary['f1']:.3f} precision={summary['precision']:.3f} recall={summary['recall']:.3f}")
        self.stdout.write(
            "Ambiguity-aware: "
            f"F1={summary['ambiguity_aware']['f1']:.3f} "
            f"precision={summary['ambiguity_aware']['precision']:.3f} "
            f"recall={summary['ambiguity_aware']['recall']:.3f}"
        )
        self.stdout.write(f"Summary: {summary_path}")


def latest_records(path: Path) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            record = json.loads(line)
            record_id = str(record.get("record_id") or "")
            if record_id:
                records[record_id] = record
    return records


def parse_project_ids(raw: str) -> set[int]:
    ids: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.add(int(part))
        except ValueError as exc:
            raise CommandError(f"Invalid project id in --project-ids: {part}") from exc
    return ids


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


def merge_latest_gold(record: dict[str, Any], latest_gold: dict[str, Any] | None) -> dict[str, Any]:
    """Overlay both the primary gold and experiment-only alternatives."""
    if not latest_gold:
        return record
    return {
        **record,
        "gold_mwes": latest_gold.get("gold_mwes", record.get("gold_mwes") or []),
        "acceptable_mwe_analyses": latest_gold.get("acceptable_mwe_analyses", []),
    }


def accepted_mwe_references(record: dict[str, Any]) -> list[dict[str, Any]]:
    """Return mutually exclusive complete analyses; never union alternatives."""
    references = [{"reference": "primary", "spans": mwe_spans(record.get("gold_mwes") or [])}]
    seen = {frozenset(references[0]["spans"])}
    for index, analysis in enumerate(record.get("acceptable_mwe_analyses") or [], start=1):
        if not isinstance(analysis, dict):
            continue
        spans = mwe_spans(analysis.get("mwes") or [])
        key = frozenset(spans)
        if key in seen:
            continue
        seen.add(key)
        references.append(
            {
                "reference": str(analysis.get("analysis_id") or f"alternative_{index}"),
                "spans": spans,
                "category": str(analysis.get("category") or "unspecified"),
                "reason": str(analysis.get("reason") or ""),
            }
        )
    return references


def _counts(gold: set[tuple[str, ...]], predicted: set[tuple[str, ...]]) -> tuple[int, int, int]:
    return len(gold & predicted), len(predicted - gold), len(gold - predicted)


def score_record(record: dict[str, Any]) -> dict[str, Any]:
    references = accepted_mwe_references(record)
    gold = references[0]["spans"]
    predicted = mwe_spans(record.get("predicted_mwes") or [])
    tp, fp, fn = _counts(gold, predicted)
    # Maximise F1 contribution, then exact overlap, and finally prefer primary.
    candidates = []
    for index, reference in enumerate(references):
        ref_tp, ref_fp, ref_fn = _counts(reference["spans"], predicted)
        denominator = 2 * ref_tp + ref_fp + ref_fn
        ref_f1 = 2 * ref_tp / denominator if denominator else 1.0
        candidates.append((ref_f1, ref_tp, -(ref_fp + ref_fn), -index, reference, ref_tp, ref_fp, ref_fn))
    _, _, _, _, selected, accepted_tp, accepted_fp, accepted_fn = max(candidates, key=lambda item: item[:4])
    return {
        "record_id": record.get("record_id"),
        "language": record.get("language"),
        "project_id": record.get("project_id"),
        "segment_surface": record.get("segment_surface"),
        "gold_spans": [list(span) for span in sorted(gold)],
        "predicted_spans": [list(span) for span in sorted(predicted)],
        "mwe_analysis": record.get("mwe_analysis") or "",
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
        "exact_match": gold == predicted,
        "acceptable_reference_count": len(references),
        "ambiguity_aware_reference": selected["reference"],
        "ambiguity_aware_gold_spans": [list(span) for span in sorted(selected["spans"])],
        "ambiguity_aware_true_positive": accepted_tp,
        "ambiguity_aware_false_positive": accepted_fp,
        "ambiguity_aware_false_negative": accepted_fn,
        "ambiguity_aware_exact_match": selected["spans"] == predicted,
    }


def summarize_scores(scored: list[dict[str, Any]], *, split: str, outputs_path: Path) -> dict[str, Any]:
    tp = sum(int(record["true_positive"]) for record in scored)
    fp = sum(int(record["false_positive"]) for record in scored)
    fn = sum(int(record["false_negative"]) for record in scored)
    precision = tp / (tp + fp) if tp + fp else 1.0 if not any(record["gold_spans"] for record in scored) else 0.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    exact = sum(1 for record in scored if record["exact_match"])
    ambiguity = metric_summary(scored, prefix="ambiguity_aware_")
    return {
        "schema_version": 2,
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
        "strict_primary": {
            "exact_match_count": exact,
            "exact_match_rate": exact / len(scored) if scored else 0.0,
            "true_positive": tp, "false_positive": fp, "false_negative": fn,
            "precision": precision, "recall": recall, "f1": f1,
        },
        "ambiguity_aware": ambiguity,
        "records_with_alternatives": sum(1 for record in scored if record["acceptable_reference_count"] > 1),
        "predictions_accepted_via_alternative": sum(
            1 for record in scored
            if record["ambiguity_aware_exact_match"] and record["ambiguity_aware_reference"] != "primary"
        ),
    }


def metric_summary(scored: list[dict[str, Any]], *, prefix: str) -> dict[str, Any]:
    tp = sum(int(record[f"{prefix}true_positive"]) for record in scored)
    fp = sum(int(record[f"{prefix}false_positive"]) for record in scored)
    fn = sum(int(record[f"{prefix}false_negative"]) for record in scored)
    precision = tp / (tp + fp) if tp + fp else 1.0 if not any(record[f"{prefix}gold_spans"] for record in scored) else 0.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    exact = sum(1 for record in scored if record[f"{prefix}exact_match"])
    return {
        "exact_match_count": exact, "exact_match_rate": exact / len(scored) if scored else 0.0,
        "true_positive": tp, "false_positive": fp, "false_negative": fn,
        "precision": precision, "recall": recall, "f1": f1,
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
        "## Ambiguity-aware score",
        "",
        f"- Records with acceptable alternatives: {summary['records_with_alternatives']}",
        f"- Predictions accepted via an alternative: {summary['predictions_accepted_via_alternative']}",
        f"- Exact match: {summary['ambiguity_aware']['exact_match_count']} ({summary['ambiguity_aware']['exact_match_rate']:.1%})",
        f"- Precision: {summary['ambiguity_aware']['precision']:.3f}",
        f"- Recall: {summary['ambiguity_aware']['recall']:.3f}",
        f"- F1: {summary['ambiguity_aware']['f1']:.3f}",
        "",
        "## Remaining ambiguity-aware error examples",
        "",
    ]
    examples = [
        record for record in scored
        if record["ambiguity_aware_false_positive"] or record["ambiguity_aware_false_negative"]
    ][:25]
    if not examples:
        lines.append("No mismatching records in the first scored set.")
    for record in examples:
        lines.extend(
            [
                f"### {record['record_id']}",
                "",
                record.get("segment_surface") or "",
                "",
                f"- Accepted reference ({record['ambiguity_aware_reference']}): {record['ambiguity_aware_gold_spans']}",
                f"- Predicted: {record['predicted_spans']}",
                f"- Model analysis: {record.get('mwe_analysis') or 'not recorded'}",
                "",
            ]
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
