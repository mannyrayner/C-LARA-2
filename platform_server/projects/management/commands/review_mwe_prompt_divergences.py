from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from .score_mwe_prompt_outputs import accepted_mwe_references, latest_records, mwe_spans

CATEGORIES = {
    "l": "lexicalization", "b": "span_boundary", "n": "proper_name",
    "h": "hyphenated_compound", "d": "discontinuous_expression",
    "p": "pedagogical_usefulness", "t": "translation_context", "o": "other",
}


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
            if record_id in gold and not prediction_is_acceptable(gold[record_id], output)
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
            if action["command"] in {"prediction", "correct", "none", "both"}:
                spans = action["spans"]
                corrected = dict(gold[record_id])
                corrected.setdefault("pre_review_gold_mwes", corrected.get("gold_mwes") or [])
                if action["command"] == "both":
                    add_acceptable_alternative(corrected, spans, action)
                else:
                    corrected["gold_mwes"] = spans_to_mwes(spans)
                corrected["human_mwe_review"] = action["command"]
                append_jsonl(gold_path, corrected)
                gold[record_id] = corrected
            append_jsonl(review_path, {**item, "review_decision": action["command"], "gold_spans_after": action.get("spans", item["gold_spans"]), "category": action.get("category", "unspecified"), "notes": action.get("notes", "")})
            count += 1
        self.stdout.write(f"Reviewed {count} MWE divergence(s)")
        self.stdout.write(f"Gold JSONL: {gold_path}")
        self.stdout.write(f"Review log: {review_path}")
        summary_path = write_review_summary(review_path)
        self.stdout.write(f"Review summary: {summary_path}")


def build_divergence(gold: dict[str, Any], output: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_id": str(gold.get("record_id") or ""),
        "project_id": gold.get("project_id"),
        "segment_surface": str(gold.get("segment_surface") or ""),
        "token_surfaces": gold.get("token_surfaces") or [],
        "gold_spans": [list(span) for span in sorted(mwe_spans(gold.get("gold_mwes") or []))],
        "predicted_spans": [list(span) for span in sorted(mwe_spans(output.get("predicted_mwes") or []))],
        "mwe_analysis": str(output.get("mwe_analysis") or ""),
        "translation_context": gold.get("translation_context") or output.get("translation_context") or "",
    }


def prompt_action(item: dict[str, Any], *, index: int, total: int) -> dict[str, Any]:
    while True:
        print("\n" + "=" * 72)
        print(f"{index}/{total}: {item['record_id']}")
        print(f"Segment: {item['segment_surface']}")
        print(f"Gold: {item['gold_spans']}")
        print(f"Prediction: {item['predicted_spans']}")
        if item.get("translation_context"):
            print(f"Translation context: {item['translation_context']}")
        print(f"Analysis: {item['mwe_analysis'] or 'not recorded'}")
        response = input("Gold action? [a=accept primary, b=both acceptable, p=use prediction, n=no MWEs, c JSON spans, s=skip, q=quit]: ").strip()
        if response == "a":
            return with_notes({"command": "accept"})
        if response == "p":
            return with_notes({"command": "prediction", "spans": item["predicted_spans"]})
        if response == "b":
            return with_notes({"command": "both", "spans": item["predicted_spans"]})
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
    raw = input("Category [l=lexicalization, b=boundary, n=name, h=hyphen, d=discontinuous, p=pedagogy, t=translation, o=other; Enter=unspecified]: ").strip()
    category = CATEGORIES.get(raw, "unspecified")
    return {**action, "category": category, "notes": input("Reason/notes (recommended for ambiguous MWEs): ").strip()}


def prediction_is_acceptable(gold: dict[str, Any], output: dict[str, Any]) -> bool:
    predicted = mwe_spans(output.get("predicted_mwes") or [])
    return any(reference["spans"] == predicted for reference in accepted_mwe_references(gold))


def add_acceptable_alternative(record: dict[str, Any], spans: list[list[str]], action: dict[str, Any]) -> None:
    alternatives = list(record.get("acceptable_mwe_analyses") or [])
    candidate = mwe_spans(spans_to_mwes(spans))
    if candidate == mwe_spans(record.get("gold_mwes") or []):
        return
    if any(mwe_spans(item.get("mwes") or []) == candidate for item in alternatives if isinstance(item, dict)):
        return
    alternatives.append({
        "analysis_id": f"alternative_{len(alternatives) + 1}",
        "mwes": spans_to_mwes(spans),
        "category": action.get("category", "unspecified"),
        "reason": action.get("notes", ""),
        "source": "reviewed_prompt_prediction",
    })
    record["acceptable_mwe_analyses"] = alternatives


def write_review_summary(review_path: Path) -> Path:
    records = latest_records(review_path)
    decisions: dict[str, int] = {}
    categories: dict[str, int] = {}
    for record in records.values():
        decision = str(record.get("review_decision") or "unresolved")
        category = str(record.get("category") or "unspecified")
        decisions[decision] = decisions.get(decision, 0) + 1
        categories[category] = categories.get(category, 0) + 1
    summary = {
        "schema_version": 1,
        "reviewed_records": len(records),
        "decision_counts": decisions,
        "category_counts": categories,
        "primary_gold_changed": sum(decisions.get(key, 0) for key in ("prediction", "correct", "none")),
        "both_acceptable": decisions.get("both", 0),
        "primary_gold_confirmed": decisions.get("accept", 0),
        "unresolved_or_skipped": decisions.get("skip", 0),
        "model_errors": decisions.get("accept", 0),
        "gold_errors": sum(decisions.get(key, 0) for key in ("prediction", "correct", "none")),
        "records_with_notes": sum(1 for record in records.values() if str(record.get("notes") or "").strip()),
    }
    summary_path = review_path.with_name(f"{review_path.stem}_summary.json")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path = summary_path.with_suffix(".md")
    lines = [
        "# MWE divergence review summary", "",
        f"- Reviewed records: {summary['reviewed_records']}",
        f"- Confirmed primary / model errors: {summary['model_errors']}",
        f"- Corrected primary / gold errors: {summary['gold_errors']}",
        f"- Both complete analyses acceptable: {summary['both_acceptable']}",
        f"- Unresolved or skipped: {summary['unresolved_or_skipped']}",
        f"- Records with reviewer notes: {summary['records_with_notes']}",
        "", "## Decision counts", "",
        *[f"- `{key}`: {value}" for key, value in sorted(decisions.items())],
        "", "## Diagnostic categories", "",
        *[f"- `{key}`: {value}" for key, value in sorted(categories.items())],
    ]
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary_path


def spans_to_mwes(spans: list[list[str]]) -> list[dict[str, Any]]:
    return [{"id": f"gold_mwe_{index}", "tokens": span, "label": ""} for index, span in enumerate(spans, start=1)]


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as out:
        out.write(json.dumps(record, ensure_ascii=False) + "\n")
