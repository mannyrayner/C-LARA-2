from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError


@dataclass(frozen=True, slots=True)
class JudgedChunkRecord:
    record_id: str
    split: str
    language: str
    project_id: int
    project_title: str
    page_index: int
    segment_index: int
    chunk_index: int
    segment_surface: str
    chunk_surface: str
    original_gold_parts: list[str]
    original_gold_segments_display: str
    human_judgement: str
    gold_parts: list[str]
    gold_segments_display: str
    human_notes: str


class Command(BaseCommand):
    help = "Interactively accept or correct extracted chunk-segmentation records into a gold JSONL file."

    def add_arguments(self, parser):
        parser.add_argument("--input-jsonl", required=True)
        parser.add_argument("--output-jsonl", required=True)
        parser.add_argument("--limit", type=int, default=0, help="Maximum new records to judge; 0 means no limit.")
        parser.add_argument("--overwrite", action="store_true")

    def handle(self, *args, **options):
        input_path = Path(options["input_jsonl"]).resolve()
        output_path = Path(options["output_jsonl"]).resolve()
        if not input_path.exists():
            raise CommandError(f"input JSONL not found: {input_path}")
        records = read_jsonl(input_path)
        if not records:
            raise CommandError(f"input JSONL is empty: {input_path}")

        if output_path.exists() and options["overwrite"]:
            output_path.unlink()
        judged_records = latest_records_by_id(read_jsonl(output_path) if output_path.exists() else [])
        if judged_records:
            self.stdout.write(f"Resuming existing chunk judgement file with {len(judged_records)} saved record(s): {output_path}")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        limit = int(options["limit"] or 0)
        judged_this_run = 0
        index = 0
        while index < len(records):
            record = records[index]
            record_id = str(record.get("record_id") or "")
            if not record_id:
                index += 1
                continue
            if record_id in judged_records:
                index += 1
                continue
            if limit and judged_this_run >= limit:
                break

            action = prompt_for_record(record, index=index, total=len(records))
            if action["command"] == "quit":
                break
            if action["command"] == "back":
                target = str(action["target"])
                target_index = index_for_back_target(records, target)
                if target_index is None:
                    self.stdout.write(f"Could not find prior record {target!r}")
                    continue
                target_record = records[target_index]
                judged_records.pop(str(target_record.get("record_id") or ""), None)
                index = target_index
                continue
            judged = build_judged_record(record, action)
            append_jsonl(output_path, asdict(judged))
            judged_records[judged.record_id] = asdict(judged)
            judged_this_run += 1
            index += 1

        self.stdout.write(f"Wrote/resumed {len(judged_records)} judged chunk record(s) at {output_path}")


def prompt_for_record(record: dict[str, Any], *, index: int, total: int) -> dict[str, Any]:
    while True:
        print("\n" + "=" * 72)
        print(f"{index + 1}/{total}: {record.get('record_id')}")
        print(f"Language: {record.get('language')} | Project: {record.get('project_title')}")
        print(f"Segment: {record.get('segment_surface')!r}")
        print(f"Chunk:   {record.get('chunk_surface')!r}")
        print(f"Current decomposition: {record.get('gold_segments_display')}")
        response = input(
            "Gold decomposition? [a=accept current, c PART|PART=correct, s=skip, b <id/number>=back, q=quit]: "
        ).strip()
        if not response:
            continue
        lowered = response.lower()
        if lowered == "q":
            return {"command": "quit"}
        if lowered == "s":
            return {"command": "skip", "notes": prompt_notes()}
        if lowered == "a":
            return {"command": "accept", "parts": list(record.get("gold_parts") or []), "notes": prompt_notes()}
        if lowered.startswith("b "):
            return {"command": "back", "target": response[2:].strip()}
        if lowered.startswith("c "):
            parts = parse_gold_parts(response[2:].strip())
            error = validate_gold_parts(record, parts)
            if error:
                print(error)
                continue
            return {"command": "correct", "parts": parts, "notes": prompt_notes()}
        print("Please enter a, c PART|PART, s, b <id/number>, or q.")


def prompt_notes() -> str:
    return input("Notes (optional): ").strip()


def parse_gold_parts(text: str) -> list[str]:
    return [part for part in text.split("|") if part != ""]


def validate_gold_parts(record: dict[str, Any], parts: list[str]) -> str:
    if not parts:
        return "Correction must contain at least one non-empty part."
    chunk_surface = str(record.get("chunk_surface") or "")
    if "".join(parts) != chunk_surface:
        return f"Correction parts must concatenate exactly to chunk surface {chunk_surface!r}."
    return ""


def build_judged_record(record: dict[str, Any], action: dict[str, Any]) -> JudgedChunkRecord:
    original_parts = [str(part) for part in record.get("gold_parts") or []]
    if action["command"] == "skip":
        human_judgement = "skipped"
        parts = original_parts
    elif action["command"] == "correct":
        human_judgement = "corrected"
        parts = [str(part) for part in action["parts"]]
    else:
        human_judgement = "accepted"
        parts = [str(part) for part in action["parts"]]
    return JudgedChunkRecord(
        record_id=str(record.get("record_id") or ""),
        split=str(record.get("split") or ""),
        language=str(record.get("language") or ""),
        project_id=int(record.get("project_id") or 0),
        project_title=str(record.get("project_title") or ""),
        page_index=int(record.get("page_index") or 0),
        segment_index=int(record.get("segment_index") or 0),
        chunk_index=int(record.get("chunk_index") or 0),
        segment_surface=str(record.get("segment_surface") or ""),
        chunk_surface=str(record.get("chunk_surface") or ""),
        original_gold_parts=original_parts,
        original_gold_segments_display=str(record.get("gold_segments_display") or ""),
        human_judgement=human_judgement,
        gold_parts=parts,
        gold_segments_display="|".join(parts),
        human_notes=str(action.get("notes") or ""),
    )


def index_for_back_target(records: list[dict[str, Any]], target: str) -> int | None:
    if target.isdigit():
        idx = int(target) - 1
        return idx if 0 <= idx < len(records) else None
    for idx, record in enumerate(records):
        if str(record.get("record_id") or "") == target:
            return idx
    return None


def latest_records_by_id(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for record in records:
        record_id = str(record.get("record_id") or "")
        if record_id:
            latest[record_id] = record
    return latest


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            records.append(payload)
    return records


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as out:
        out.write(json.dumps(record, ensure_ascii=False) + "\n")
