from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from .score_mwe_prompt_outputs import latest_records, mwe_spans


class Command(BaseCommand):
    help = "Interactively review MWE prompt/gold divergences and optionally correct gold JSONL."

    def add_arguments(self, parser):
        parser.add_argument("--gold-jsonl", required=True)
        parser.add_argument("--outputs-jsonl", required=True)
        parser.add_argument("--review-jsonl", required=True)
        parser.add_argument("--limit", type=int, default=0)

    def handle(self, *args, **options):
        gold_path = Path(options["gold_jsonl"]).resolve()
        outputs_path = Path(options["outputs_jsonl"]).resolve()
        review_path = Path(options["review_jsonl"]).resolve()
        if not gold_path.exists() or not outputs_path.exists():
            raise CommandError("gold and output JSONL files must both exist")
        gold = latest_records(gold_path)
        outputs = latest_records(outputs_path)
        reviewed = latest_records(review_path) if review_path.exists() else {}
        divergences = [
            build_divergence(gold[record_id], output)
            for record_id, output in outputs.items()
            if record_id in gold and mwe_spans(gold[record_id].get("gold_mwes") or []) != mwe_spans(output.get("predicted_mwes") or [])
        ]
        review_path.parent.mkdir(parents=True, exist_ok=True)
        count = 0
        for index, item in enumerate(divergences, start=1):
            record_id = item["record_id"]
            if record_id in reviewed:
                continue
            if options["limit"] and count >= options["limit"]:
                break
            action = prompt_action(item, index=index, total=len(divergences))
            if action["command"] == "quit":
                break
            if action["command"] in {"prediction", "correct", "none"}:
                spans = action["spans"]
                corrected = dict(gold[record_id])
                corrected.setdefault("pre_review_gold_mwes", corrected.get("gold_mwes") or [])
                corrected["gold_mwes"] = spans_to_mwes(spans)
                corrected["human_mwe_review"] = action["command"]
                append_jsonl(gold_path, corrected)
                gold[record_id] = corrected
            append_jsonl(review_path, {**item, "review_decision": action["command"], "gold_spans_after": action.get("spans", item["gold_spans"]), "notes": action.get("notes", "")})
            count += 1
        self.stdout.write(f"Reviewed {count} MWE divergence(s)")
        self.stdout.write(f"Gold JSONL: {gold_path}")
        self.stdout.write(f"Review log: {review_path}")


def build_divergence(gold: dict[str, Any], output: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_id": str(gold.get("record_id") or ""),
        "project_id": gold.get("project_id"),
        "segment_surface": str(gold.get("segment_surface") or ""),
        "token_surfaces": gold.get("token_surfaces") or [],
        "gold_spans": [list(span) for span in sorted(mwe_spans(gold.get("gold_mwes") or []))],
        "predicted_spans": [list(span) for span in sorted(mwe_spans(output.get("predicted_mwes") or []))],
        "mwe_analysis": str(output.get("mwe_analysis") or ""),
    }


def prompt_action(item: dict[str, Any], *, index: int, total: int) -> dict[str, Any]:
    while True:
        print("\n" + "=" * 72)
        print(f"{index}/{total}: {item['record_id']}")
        print(f"Segment: {item['segment_surface']}")
        print(f"Gold: {item['gold_spans']}")
        print(f"Prediction: {item['predicted_spans']}")
        print(f"Analysis: {item['mwe_analysis'] or 'not recorded'}")
        response = input("Gold action? [a=accept, p=use prediction, n=no MWEs, c JSON spans, s=skip, q=quit]: ").strip()
        if response == "a":
            return with_notes({"command": "accept"})
        if response == "p":
            return with_notes({"command": "prediction", "spans": item["predicted_spans"]})
        if response == "n":
            return with_notes({"command": "none", "spans": []})
        if response == "s":
            return with_notes({"command": "skip"})
        if response == "q":
            return {"command": "quit"}
        if response.startswith("c "):
            try:
                spans = json.loads(response[2:].strip())
                if not isinstance(spans, list) or any(not isinstance(span, list) or len(span) < 2 for span in spans):
                    raise ValueError
                return with_notes({"command": "correct", "spans": [[str(token) for token in span] for span in spans]})
            except (json.JSONDecodeError, ValueError):
                print('Use JSON such as c [["put", "up"], ["in", "spite", "of"]]')


def with_notes(action: dict[str, Any]) -> dict[str, Any]:
    return {**action, "notes": input("Reason/notes (recommended for ambiguous MWEs): ").strip()}


def spans_to_mwes(spans: list[list[str]]) -> list[dict[str, Any]]:
    return [{"id": f"gold_mwe_{index}", "tokens": span, "label": ""} for index, span in enumerate(spans, start=1)]


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as out:
        out.write(json.dumps(record, ensure_ascii=False) + "\n")
