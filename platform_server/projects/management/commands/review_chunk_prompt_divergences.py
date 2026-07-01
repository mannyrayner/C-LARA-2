from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from projects.management.commands.prepare_chunk_prompt_improvement import compare_records, latest_by_record_id, read_jsonl


class Command(BaseCommand):
    help = "Interactively review chunk prompt/gold divergences and optionally correct the gold JSONL."

    def add_arguments(self, parser):
        parser.add_argument("--gold-jsonl", required=True)
        parser.add_argument("--predictions-jsonl", required=True)
        parser.add_argument("--review-jsonl", required=True)
        parser.add_argument("--limit", type=int, default=0, help="Maximum new divergences to review; 0 means no limit.")
        parser.add_argument("--overwrite-review", action="store_true")

    def handle(self, *args, **options):
        gold_path = Path(options["gold_jsonl"]).resolve()
        predictions_path = Path(options["predictions_jsonl"]).resolve()
        review_path = Path(options["review_jsonl"]).resolve()
        if not gold_path.exists():
            raise CommandError(f"gold JSONL not found: {gold_path}")
        if not predictions_path.exists():
            raise CommandError(f"predictions JSONL not found: {predictions_path}")
        if review_path.exists() and options["overwrite_review"]:
            review_path.unlink()

        gold_records = latest_by_record_id(read_jsonl(gold_path))
        prediction_records = latest_by_record_id(read_jsonl(predictions_path))
        if not gold_records:
            raise CommandError(f"gold JSONL contains no records: {gold_path}")
        if not prediction_records:
            raise CommandError(f"predictions JSONL contains no records: {predictions_path}")

        reviewed = latest_by_record_id(read_jsonl(review_path) if review_path.exists() else [])
        review_path.parent.mkdir(parents=True, exist_ok=True)
        limit = int(options["limit"] or 0)
        reviewed_this_run = 0
        index = 0
        divergences = current_divergences(gold_records, prediction_records)
        while index < len(divergences):
            item = divergences[index]
            record_id = str(item.get("record_id") or "")
            if record_id in reviewed:
                index += 1
                continue
            if limit and reviewed_this_run >= limit:
                break
            action = prompt_for_divergence(item, index=index, total=len(divergences))
            if action["command"] == "quit":
                break
            if action["command"] == "back":
                target_index = index_for_back_target(divergences, str(action["target"]))
                if target_index is None:
                    self.stdout.write(f"Could not find divergence {action['target']!r}")
                    continue
                reviewed.pop(str(divergences[target_index].get("record_id") or ""), None)
                index = target_index
                continue
            if action["command"] in {"use_prediction", "correct"}:
                corrected = corrected_gold_record(gold_records[record_id], action["parts"], action["command"], action.get("notes", ""))
                append_jsonl(gold_path, corrected)
                gold_records[record_id] = corrected
            review_record = build_review_record(item, action)
            append_jsonl(review_path, review_record)
            reviewed[record_id] = review_record
            reviewed_this_run += 1
            index += 1

        self.stdout.write(f"Reviewed {reviewed_this_run} divergence(s) in this run")
        self.stdout.write(f"Review log: {review_path}")
        self.stdout.write(f"Gold JSONL: {gold_path}")


def current_divergences(gold_records: dict[str, dict[str, Any]], prediction_records: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [item for item in compare_records(gold_records, prediction_records) if item.get("status") != "correct"]


def prompt_for_divergence(item: dict[str, Any], *, index: int, total: int) -> dict[str, Any]:
    while True:
        print("\n" + "=" * 72)
        print(f"{index + 1}/{total}: {item.get('record_id')} ({item.get('status')})")
        print(f"Project: {item.get('project_title')}")
        print(f"Segment: {item.get('segment_surface')!r}")
        print(f"Chunk:   {item.get('chunk_surface')!r}")
        print(f"Gold:       {item.get('gold_display')}")
        print(f"Prediction: {item.get('predicted_display')}")
        response = input(
            "Gold action? [a=accept current gold, p=use prediction as gold, c PART|PART=correct gold, s=skip, b <id/number>=back, q=quit]: "
        ).strip()
        if not response:
            continue
        lowered = response.lower()
        if lowered == "q":
            return {"command": "quit"}
        if lowered == "s":
            return {"command": "skip", "notes": prompt_notes()}
        if lowered == "a":
            return {"command": "accept_gold", "parts": list(item.get("gold_parts") or []), "notes": prompt_notes()}
        if lowered == "p":
            parts = [str(part) for part in item.get("predicted_parts") or []]
            error = validate_parts(str(item.get("chunk_surface") or ""), parts)
            if error:
                print(error)
                continue
            return {"command": "use_prediction", "parts": parts, "notes": prompt_notes()}
        if lowered.startswith("c "):
            parts = [part for part in response[2:].strip().split("|") if part != ""]
            error = validate_parts(str(item.get("chunk_surface") or ""), parts)
            if error:
                print(error)
                continue
            return {"command": "correct", "parts": parts, "notes": prompt_notes()}
        if lowered.startswith("b "):
            return {"command": "back", "target": response[2:].strip()}
        print("Please enter a, p, c PART|PART, s, b <id/number>, or q.")


def prompt_notes() -> str:
    return input("Notes (optional): ").strip()


def validate_parts(chunk_surface: str, parts: list[str]) -> str:
    if not parts:
        return "Gold correction must contain at least one non-empty part."
    if "".join(parts) != chunk_surface:
        return f"Gold parts must concatenate exactly to chunk surface {chunk_surface!r}."
    return ""


def corrected_gold_record(record: dict[str, Any], parts: list[str], command: str, notes: str) -> dict[str, Any]:
    updated = dict(record)
    updated.setdefault("pre_review_gold_parts", record.get("gold_parts") or [])
    updated.setdefault("pre_review_gold_segments_display", record.get("gold_segments_display") or "|".join(record.get("gold_parts") or []))
    updated["human_judgement"] = "gold_corrected_from_prediction" if command == "use_prediction" else "gold_corrected"
    updated["gold_parts"] = [str(part) for part in parts]
    updated["gold_segments_display"] = "|".join(str(part) for part in parts)
    updated["human_notes"] = notes
    return updated


def build_review_record(item: dict[str, Any], action: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_id": str(item.get("record_id") or ""),
        "status": item.get("status"),
        "chunk_surface": item.get("chunk_surface"),
        "gold_parts_before": item.get("gold_parts") or [],
        "predicted_parts": item.get("predicted_parts") or [],
        "review_decision": action["command"],
        "gold_parts_after": action.get("parts") or item.get("gold_parts") or [],
        "notes": action.get("notes") or "",
    }


def index_for_back_target(records: list[dict[str, Any]], target: str) -> int | None:
    if target.isdigit():
        idx = int(target) - 1
        return idx if 0 <= idx < len(records) else None
    for idx, record in enumerate(records):
        if str(record.get("record_id") or "") == target:
            return idx
    return None


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as out:
        out.write(json.dumps(record, ensure_ascii=False) + "\n")
