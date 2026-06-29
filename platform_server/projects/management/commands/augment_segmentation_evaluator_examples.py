from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from pipeline.fewshot_curation import _filesystem_path, _path_exists, _write_text
from .review_fewshots import _resolve_cli_path


class Command(BaseCommand):
    help = "Augment segmentation evaluator exemplars with adjudicated evaluator-disagreement cases."

    def add_arguments(self, parser):
        parser.add_argument("--base-examples-jsonl", required=True)
        parser.add_argument("--disagreements-jsonl", required=True)
        parser.add_argument("--output-jsonl", required=True)
        parser.add_argument("--manifest-json", required=True)
        parser.add_argument("--max-examples", type=int, default=0)
        parser.add_argument("--include-gold", choices=["reject", "accept", "all"], default="reject")
        parser.add_argument("--overwrite", action="store_true")

    def handle(self, *args, **options):
        base_path = _resolve_cli_path(options["base_examples_jsonl"], "")
        disagreements_path = _resolve_cli_path(options["disagreements_jsonl"], "")
        output_path = _resolve_cli_path(options["output_jsonl"], "")
        manifest_path = _resolve_cli_path(options["manifest_json"], "")
        if _path_exists(output_path) and not options["overwrite"]:
            raise CommandError(f"output already exists: {output_path}; pass --overwrite")
        if _path_exists(manifest_path) and not options["overwrite"]:
            raise CommandError(f"manifest already exists: {manifest_path}; pass --overwrite")

        base_examples = load_jsonl(base_path, label="base evaluator example")
        disagreements = load_jsonl(disagreements_path, label="disagreement")
        additions = disagreement_examples(
            disagreements,
            include_gold=options["include_gold"],
            max_examples=int(options.get("max_examples") or 0),
            existing_keys=example_keys(base_examples),
        )
        combined = base_examples + additions
        _write_text(output_path, "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in combined))
        manifest = {
            "schema_version": 1,
            "base_examples_jsonl": str(base_path),
            "disagreements_jsonl": str(disagreements_path),
            "output_jsonl": str(output_path),
            "base_count": len(base_examples),
            "added_count": len(additions),
            "combined_count": len(combined),
            "include_gold": options["include_gold"],
            "max_examples": int(options.get("max_examples") or 0),
        }
        _write_text(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        self.stdout.write("Augmented segmentation evaluator examples")
        self.stdout.write(f"Base examples: {len(base_examples)}")
        self.stdout.write(f"Added examples: {len(additions)}")
        self.stdout.write(f"Output: {output_path}")
        self.stdout.write(f"Manifest: {manifest_path}")


def load_jsonl(path: Path, *, label: str) -> list[dict[str, Any]]:
    if not _path_exists(path):
        raise CommandError(f"{label} file not found: {path}")
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(_filesystem_path(path).read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise CommandError(f"{label} must be an object at {path}:{line_number}")
        records.append(payload)
    return records


def example_keys(examples: list[dict[str, Any]]) -> set[tuple[str, str, str]]:
    keys: set[tuple[str, str, str]] = set()
    for example in examples:
        judgement = normalise_judgement(example.get("expected_decision") or example.get("judgement"))
        candidate = str(example.get("candidate_segments") or example.get("boundary_marked") or "")
        keys.add((str(example.get("input") or ""), candidate, judgement))
    return keys


def disagreement_examples(
    disagreements: list[dict[str, Any]], *, include_gold: str, max_examples: int, existing_keys: set[tuple[str, str, str]]
) -> list[dict[str, Any]]:
    additions: list[dict[str, Any]] = []
    seen = set(existing_keys)
    for item in disagreements:
        gold = normalise_judgement(item.get("gold_judgement"))
        if include_gold != "all" and gold != include_gold:
            continue
        input_surface = str(item.get("input_surface") or "")
        candidate_segments = str(item.get("segments_display") or "")
        key = (input_surface, candidate_segments, gold)
        if not input_surface or not candidate_segments or key in seen:
            continue
        seen.add(key)
        additions.append(
            {
                "example_id": f"DISAGREEMENT-{len(additions) + 1:04d}-{item.get('record_id')}",
                "input": input_surface,
                "candidate_segments": candidate_segments,
                "boundary_separator": "|",
                "expected_decision": gold,
                "expected_severity": "major" if gold == "reject" else "none",
                "phenomenon": "segmentation_evaluator_disagreement",
                "rationale": rationale_for(item, gold),
                "provenance": {
                    "source": "evaluator_disagreements",
                    "record_id": item.get("record_id"),
                    "evaluator_label": item.get("evaluator_label"),
                    "evaluator_judgement": item.get("evaluator_judgement"),
                    "evaluator_notes": item.get("evaluator_notes", ""),
                },
            }
        )
        if max_examples > 0 and len(additions) >= max_examples:
            break
    return additions


def normalise_judgement(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if raw in {"accept", "reject"}:
        return raw
    return "reject"


def rationale_for(item: dict[str, Any], gold: str) -> str:
    if gold == "reject":
        notes = str(item.get("evaluator_notes") or "").strip()
        return (
            "Gold adjudication rejects this candidate; use it as a calibration example for evaluator false accepts."
            + (f" Previous evaluator note: {notes}" if notes else "")
        )
    return "Gold adjudication accepts this candidate; use it as a calibration example for evaluator false rejects."
