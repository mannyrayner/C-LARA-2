from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from .compare_segmentation_judgements import ACCEPT, REJECT, load_latest_judgements, normalise_judgement, parse_candidates, safe_rate
from .review_fewshots import _resolve_cli_path


class Command(BaseCommand):
    help = "Score AI segmentation evaluator judgements against human gold judgements."

    def add_arguments(self, parser):
        parser.add_argument("--gold-judgements", required=True)
        parser.add_argument("--evaluator", action="append", default=[], help="Evaluator judgement file as label:path")
        parser.add_argument("--output-dir", required=True)
        parser.add_argument("--split", default="development")
        parser.add_argument("--json", default="evaluator_accuracy.json")
        parser.add_argument("--markdown", default="evaluator_accuracy.md")
        parser.add_argument("--disagreements-jsonl", default="evaluator_disagreements.jsonl")

    def handle(self, *args, **options):
        gold_path = _resolve_cli_path(options["gold_judgements"], "")
        output_dir = _resolve_cli_path(options["output_dir"], "")
        output_dir.mkdir(parents=True, exist_ok=True)
        evaluators = parse_candidates(options.get("evaluator") or [])
        if not evaluators:
            raise CommandError("At least one --evaluator label:path argument is required")
        gold_records = load_latest_judgements(gold_path)
        evaluator_records = [(label, _resolve_cli_path(path, ""), load_latest_judgements(_resolve_cli_path(path, ""))) for label, path in evaluators]
        summaries = [score_one(label, path, gold_records, records)[0] for label, path, records in evaluator_records]
        disagreements = []
        for label, path, records in evaluator_records:
            disagreements.extend(score_one(label, path, gold_records, records)[1])
        majority_summary, majority_disagreements = majority_vote_score(gold_path, gold_records, evaluator_records)
        payload = {
            "schema_version": 1,
            "split": options["split"],
            "gold_judgements": str(gold_path),
            "evaluator_count": len(evaluator_records),
            "evaluators": summaries,
            "majority_vote": majority_summary,
        }
        json_path = output_dir / options["json"]
        markdown_path = output_dir / options["markdown"]
        disagreements_path = output_dir / options["disagreements_jsonl"]
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        markdown_path.write_text(render_markdown(payload), encoding="utf-8")
        with disagreements_path.open("w", encoding="utf-8") as out:
            for item in disagreements + majority_disagreements:
                out.write(json.dumps(item, ensure_ascii=False) + "\n")
        self.stdout.write("Segmentation evaluator scoring complete")
        self.stdout.write(f"Evaluators: {len(evaluator_records)}")
        self.stdout.write(f"Summary JSON: {json_path}")
        self.stdout.write(f"Summary Markdown: {markdown_path}")
        self.stdout.write(f"Disagreements: {disagreements_path}")


def score_one(
    label: str, path: Path, gold_records: dict[str, dict[str, Any]], evaluator_records: dict[str, dict[str, Any]]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    common_ids = sorted(set(gold_records).intersection(evaluator_records))
    categories: Counter[str] = Counter()
    gold_counts: Counter[str] = Counter()
    evaluator_counts: Counter[str] = Counter()
    disagreements: list[dict[str, Any]] = []
    for record_id in common_ids:
        gold = normalise_judgement(gold_records[record_id].get("judgement"))
        predicted = normalise_judgement(evaluator_records[record_id].get("judgement"))
        gold_counts[gold] += 1
        evaluator_counts[predicted] += 1
        category = accuracy_category(gold, predicted)
        categories[category] += 1
        if gold != predicted:
            disagreements.append(disagreement_payload(label, gold_records[record_id], evaluator_records[record_id], gold, predicted))
    total = len(common_ids)
    correct = categories["true_accept"] + categories["true_reject"]
    return (
        {
            "label": label,
            "path": str(path),
            "records_compared": total,
            "missing_from_evaluator": len(set(gold_records).difference(evaluator_records)),
            "missing_from_gold": len(set(evaluator_records).difference(gold_records)),
            "gold_judgements": dict(sorted(gold_counts.items())),
            "evaluator_judgements": dict(sorted(evaluator_counts.items())),
            "categories": dict(sorted(categories.items())),
            "accuracy": safe_rate(correct, total),
            "false_accept_count": categories["false_accept"],
            "false_reject_count": categories["false_reject"],
        },
        disagreements,
    )


def majority_vote_score(
    gold_path: Path,
    gold_records: dict[str, dict[str, Any]],
    evaluator_records: list[tuple[str, Path, dict[str, dict[str, Any]]]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    common_ids = set(gold_records)
    for _, _, records in evaluator_records:
        common_ids &= set(records)
    synthetic_records: dict[str, dict[str, Any]] = {}
    for record_id in sorted(common_ids):
        votes = Counter(normalise_judgement(records[record_id].get("judgement")) for _, _, records in evaluator_records)
        judgement = ACCEPT if votes[ACCEPT] >= votes[REJECT] else REJECT
        synthetic_records[record_id] = {**gold_records[record_id], "judgement": judgement, "notes": f"votes={dict(votes)}"}
    return score_one("majority-vote", gold_path, gold_records, synthetic_records)


def accuracy_category(gold: str, predicted: str) -> str:
    if gold == ACCEPT and predicted == ACCEPT:
        return "true_accept"
    if gold == REJECT and predicted == REJECT:
        return "true_reject"
    if gold == REJECT and predicted == ACCEPT:
        return "false_accept"
    if gold == ACCEPT and predicted == REJECT:
        return "false_reject"
    return "other"


def disagreement_payload(label: str, gold_record: dict[str, Any], evaluator_record: dict[str, Any], gold: str, predicted: str) -> dict[str, Any]:
    return {
        "evaluator_label": label,
        "record_id": gold_record.get("record_id"),
        "project_id": gold_record.get("project_id"),
        "project_title": gold_record.get("project_title"),
        "split": gold_record.get("split"),
        "input_surface": gold_record.get("input_surface"),
        "segments_display": gold_record.get("segments_display") or evaluator_record.get("segments_display"),
        "gold_judgement": gold,
        "evaluator_judgement": predicted,
        "evaluator_notes": evaluator_record.get("notes", ""),
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Segmentation evaluator accuracy",
        "",
        f"Split: `{payload['split']}`",
        f"Gold judgements: `{payload['gold_judgements']}`",
        "",
        "| Evaluator | Records | Accuracy | False accept | False reject | Missing evaluator | Missing gold |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for summary in payload["evaluators"] + [payload["majority_vote"]]:
        lines.append(
            "| {label} | {records_compared} | {accuracy:.1%} | {false_accept_count} | {false_reject_count} | "
            "{missing_from_evaluator} | {missing_from_gold} |".format(**summary)
        )
    return "\n".join(lines).rstrip() + "\n"
