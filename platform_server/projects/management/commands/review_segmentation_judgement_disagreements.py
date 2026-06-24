from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from .review_fewshots import _resolve_cli_path

ACCEPT_ALIASES = {"a", "accept", "c", "correct", "y", "yes"}
REJECT_ALIASES = {"r", "reject", "i", "incorrect", "n", "no"}
SKIP_ALIASES = {"s", "skip", ""}
QUIT_ALIASES = {"q", "quit", "exit"}


class Command(BaseCommand):
    help = "Review AI-vs-human segmentation judgement disagreements and append gold corrections."

    def add_arguments(self, parser):
        parser.add_argument("--disagreements-jsonl", required=True)
        parser.add_argument("--gold-judgements", required=True)
        parser.add_argument("--reviewed-jsonl", required=True)
        parser.add_argument("--run-label", default="")
        parser.add_argument("--limit", type=int, default=0)

    def handle(self, *args, **options):
        disagreements_path = _resolve_cli_path(options["disagreements_jsonl"], "")
        gold_path = _resolve_cli_path(options["gold_judgements"], "")
        reviewed_path = _resolve_cli_path(options["reviewed_jsonl"], "")
        disagreements = load_disagreements(disagreements_path)
        if not disagreements:
            raise CommandError(f"No disagreements found in {disagreements_path}")
        limit = int(options.get("limit") or 0)
        if limit > 0:
            disagreements = disagreements[:limit]
        gold_path.parent.mkdir(parents=True, exist_ok=True)
        reviewed_path.parent.mkdir(parents=True, exist_ok=True)

        appended = 0
        reviewed = 0
        current = 0
        with gold_path.open("a", encoding="utf-8") as gold_out, reviewed_path.open("a", encoding="utf-8") as reviewed_out:
            while current < len(disagreements):
                item = disagreements[current]
                action, judgement, notes, target = prompt_for_review(item, position=current + 1, total=len(disagreements))
                if action == "quit":
                    break
                if action == "back":
                    resolved = resolve_back_target(disagreements, target)
                    if resolved is None:
                        self.stdout.write(f"No disagreement item found for {target!r}; continuing.")
                        continue
                    position, correction_item = resolved
                    action, judgement, notes, _ = prompt_for_review(
                        correction_item, position=position, total=len(disagreements), correction=True
                    )
                    if action == "quit":
                        break
                    if action == "back":
                        self.stdout.write("Nested back commands are ignored while correcting; returning to current item.")
                        continue
                    append_review_records(
                        correction_item,
                        judgement=judgement,
                        notes=notes,
                        run_label=options["run_label"],
                        gold_out=gold_out,
                        reviewed_out=reviewed_out,
                    )
                    appended += int(judgement != "skip")
                    reviewed += 1
                    continue
                append_review_records(
                    item,
                    judgement=judgement,
                    notes=notes,
                    run_label=options["run_label"],
                    gold_out=gold_out,
                    reviewed_out=reviewed_out,
                )
                appended += int(judgement != "skip")
                reviewed += 1
                current += 1

        self.stdout.write("Segmentation judgement disagreement review complete")
        self.stdout.write(f"Disagreements: {disagreements_path}")
        self.stdout.write(f"Gold judgements: {gold_path}")
        self.stdout.write(f"Review log: {reviewed_path}")
        self.stdout.write(f"Reviewed: {reviewed}; appended_gold_corrections: {appended}")


def load_disagreements(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise CommandError(f"Disagreements file not found: {path}")
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise CommandError(f"Disagreement record must be an object at {path}:{line_number}")
        records.append(payload)
    return records


def prompt_for_review(
    item: dict[str, Any], *, position: int, total: int, correction: bool = False
) -> tuple[str, str, str, str]:
    print("\n" + "=" * 72)
    prefix = "Correction " if correction else ""
    print(f"{prefix}{position}/{total}: {item.get('record_id')}")
    print(f"Input surface: {json.dumps(item.get('input_surface'), ensure_ascii=False)}")
    print(f"Segments: {json.dumps(item.get('segments_display'), ensure_ascii=False)}")
    print(f"Current gold: {item.get('gold_judgement')} | AI evaluator: {item.get('evaluator_judgement')}")
    if item.get("evaluator_notes"):
        print(f"AI notes: {item.get('evaluator_notes')}")
    while True:
        answer = input("Correct gold judgement? [a=accept, r=reject, s=skip, b <id>=back, q=quit]: ").strip().lower()
        if answer in QUIT_ALIASES:
            return "quit", "", "", ""
        if answer.startswith("b "):
            return "back", "", "", answer.split(None, 1)[1]
        if answer in ACCEPT_ALIASES:
            notes = input("Notes (optional): ")
            return "judgement", "accept", notes, ""
        if answer in REJECT_ALIASES:
            notes = input("Notes (optional): ")
            return "judgement", "reject", notes, ""
        if answer in SKIP_ALIASES:
            notes = input("Skip notes (optional): ")
            return "judgement", "skip", notes, ""
        print("Unrecognised response. Use a, r, s, b <id>, or q.")


def resolve_back_target(records: list[dict[str, Any]], target: str) -> tuple[int, dict[str, Any]] | None:
    normalized = target.strip()
    if normalized.isdigit():
        position = int(normalized)
        if 1 <= position <= len(records):
            return position, records[position - 1]
    for position, record in enumerate(records, start=1):
        if str(record.get("record_id") or "") == normalized:
            return position, record
    return None


def append_review_records(
    item: dict[str, Any], *, judgement: str, notes: str, run_label: str, gold_out: Any, reviewed_out: Any
) -> None:
    reviewed_record = {
        "schema_version": 1,
        "reviewed_at": utc_now(),
        "run_label": run_label,
        "record_id": item.get("record_id"),
        "project_id": item.get("project_id"),
        "project_title": item.get("project_title"),
        "split": item.get("split"),
        "input_surface": item.get("input_surface"),
        "segments_display": item.get("segments_display"),
        "previous_gold_judgement": item.get("gold_judgement"),
        "evaluator_judgement": item.get("evaluator_judgement"),
        "corrected_gold_judgement": judgement,
        "notes": notes,
    }
    reviewed_out.write(json.dumps(reviewed_record, ensure_ascii=False) + "\n")
    reviewed_out.flush()
    if judgement == "skip":
        return
    gold_record = {
        "schema_version": 1,
        "run_label": run_label,
        "record_id": item.get("record_id"),
        "project_id": item.get("project_id"),
        "project_title": item.get("project_title"),
        "split": item.get("split"),
        "input_surface": item.get("input_surface"),
        "segments_display": item.get("segments_display"),
        "judgement": judgement,
        "notes": notes,
        "source": "ai_evaluator_disagreement_review",
        "reviewed_at": reviewed_record["reviewed_at"],
    }
    gold_out.write(json.dumps(gold_record, ensure_ascii=False) + "\n")
    gold_out.flush()


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
