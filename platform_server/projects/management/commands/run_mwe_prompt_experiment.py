from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from pipeline.mwe import MWESpec, annotate_mwes

from .review_fewshots import _resolve_cli_path


class Command(BaseCommand):
    help = "Run current MWE prompts over extracted MWE experiment segment records."

    def add_arguments(self, parser):
        parser.add_argument("--input-records-jsonl", required=True)
        parser.add_argument("--output-dir", required=True)
        parser.add_argument("--run-label", required=True)
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument("--overwrite", action="store_true")

    def handle(self, *args, **options):
        input_path = _resolve_cli_path(options["input_records_jsonl"], "")
        output_root = _resolve_cli_path(options["output_dir"], "")
        run_dir = output_root / str(options["run_label"])
        if run_dir.exists() and not options["overwrite"]:
            raise CommandError(f"run output already exists: {run_dir}; pass --overwrite")
        if run_dir.exists():
            shutil.rmtree(run_dir)
        run_dir.mkdir(parents=True, exist_ok=True)
        records = load_mwe_records(input_path, limit=int(options.get("limit") or 0))
        if not records:
            raise CommandError(f"No records found in {input_path}")
        outputs = asyncio.run(run_records(records, run_label=str(options["run_label"])))
        outputs_path = run_dir / "outputs.jsonl"
        write_jsonl(outputs_path, outputs)
        manifest = {
            "schema_version": 1,
            "input_records_jsonl": str(input_path),
            "run_label": str(options["run_label"]),
            "record_count": len(outputs),
            "outputs_jsonl": str(outputs_path),
        }
        manifest_path = run_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.stdout.write(f"MWE prompt run complete: {len(outputs)} records")
        self.stdout.write(f"Outputs: {outputs_path}")


def load_mwe_records(path: Path, *, limit: int = 0) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if not payload.get("token_surfaces"):
            continue
        records.append(payload)
        if limit and len(records) >= limit:
            break
    return records


async def run_records(records: list[dict[str, Any]], *, run_label: str) -> list[dict[str, Any]]:
    outputs: list[dict[str, Any]] = []
    for idx, record in enumerate(records, start=1):
        text_obj = record_to_text_obj(record)
        annotated = await annotate_mwes(
            MWESpec(
                text=text_obj,
                language=str(record.get("language") or "en"),
                op_id=f"{run_label}:record_{idx}:mwe",
            )
        )
        segment = annotated.get("pages", [{}])[0].get("segments", [{}])[0]
        predicted_mwes = ((segment.get("annotations") or {}).get("mwes") or []) if isinstance(segment, dict) else []
        outputs.append(
            {
                "record_id": record.get("record_id"),
                "split": record.get("split"),
                "language": record.get("language"),
                "project_id": record.get("project_id"),
                "project_title": record.get("project_title"),
                "page_index": record.get("page_index"),
                "segment_index": record.get("segment_index"),
                "segment_surface": record.get("segment_surface"),
                "token_surfaces": record.get("token_surfaces") or [],
                "gold_mwes": record.get("gold_mwes") or [],
                "predicted_mwes": predicted_mwes,
                "annotated_segment": segment,
            }
        )
    return outputs


def record_to_text_obj(record: dict[str, Any]) -> dict[str, Any]:
    tokens = [{"surface": str(surface), "annotations": {}} for surface in (record.get("token_surfaces") or [])]
    surface = str(record.get("segment_surface") or " ".join(token["surface"] for token in tokens))
    return {"pages": [{"segments": [{"surface": surface, "tokens": tokens, "annotations": {}}]}]}


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as out:
        for record in records:
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
