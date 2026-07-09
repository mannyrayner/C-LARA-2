from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path
from typing import Any, Callable

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
        parser.add_argument("--project-ids", default="", help="Optional comma-separated project ids to include from the input records.")
        parser.add_argument("--template-file", default="", help="Optional MWE prompt template file to use instead of the production prompt.")
        parser.add_argument("--use-translation-context", action="store_true", help="Include record translations in segment annotations for translation-aware MWE prompts.")

    def handle(self, *args, **options):
        input_path = _resolve_cli_path(options["input_records_jsonl"], "")
        output_root = _resolve_cli_path(options["output_dir"], "")
        run_dir = output_root / str(options["run_label"])
        if run_dir.exists() and not options["overwrite"]:
            raise CommandError(f"run output already exists: {run_dir}; pass --overwrite")
        if run_dir.exists():
            shutil.rmtree(run_dir)
        run_dir.mkdir(parents=True, exist_ok=True)
        project_ids = parse_project_ids(str(options.get("project_ids") or ""))
        template_path = _resolve_cli_path(options["template_file"], "") if options.get("template_file") else None
        records = load_mwe_records(input_path, limit=int(options.get("limit") or 0), project_ids=project_ids)
        if not records:
            raise CommandError(f"No records found in {input_path}")
        outputs_path = run_dir / "outputs.jsonl"
        progress_path = run_dir / "progress.jsonl"
        output_count = 0

        def record_progress(event: dict[str, Any]) -> None:
            with progress_path.open("a", encoding="utf-8") as progress_out:
                progress_out.write(json.dumps(event, ensure_ascii=False) + "\n")
            status = event.get("status")
            idx = event.get("index")
            total = event.get("total")
            record_id = event.get("record_id")
            if status == "running":
                self.stdout.write(f"[{idx}/{total}] running MWE prompt for {record_id}")
            elif status == "finished":
                self.stdout.write(f"[{idx}/{total}] finished {record_id}")
            elif status == "error":
                self.stdout.write(f"[{idx}/{total}] error {record_id}: {event.get('error')}")

        def record_output(payload: dict[str, Any]) -> None:
            nonlocal output_count
            with outputs_path.open("a", encoding="utf-8") as outputs_out:
                outputs_out.write(json.dumps(payload, ensure_ascii=False) + "\n")
            output_count += 1

        self.stdout.write(f"Loaded {len(records)} MWE records from {input_path}")
        asyncio.run(
            run_records(
                records,
                run_label=str(options["run_label"]),
                on_progress=record_progress,
                on_output=record_output,
                template_path=template_path,
                use_translation_context=bool(options.get("use_translation_context")),
            )
        )
        manifest = {
            "schema_version": 1,
            "input_records_jsonl": str(input_path),
            "run_label": str(options["run_label"]),
            "record_count": output_count,
            "project_ids": sorted(project_ids),
            "outputs_jsonl": str(outputs_path),
            "progress_jsonl": str(progress_path),
            "template_file": str(template_path) if template_path else None,
            "use_translation_context": bool(options.get("use_translation_context")),
        }
        manifest_path = run_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.stdout.write(f"MWE prompt run complete: {output_count} records")
        self.stdout.write(f"Outputs: {outputs_path}")
        self.stdout.write(f"Progress: {progress_path}")


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


def load_mwe_records(path: Path, *, limit: int = 0, project_ids: set[int] | None = None) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if not payload.get("token_surfaces"):
            continue
        if project_ids and int(payload.get("project_id") or 0) not in project_ids:
            continue
        records.append(payload)
        if limit and len(records) >= limit:
            break
    return records


async def run_records(
    records: list[dict[str, Any]],
    *,
    run_label: str,
    on_progress: Callable[[dict[str, Any]], None] | None = None,
    on_output: Callable[[dict[str, Any]], None] | None = None,
    template_path: Path | None = None,
    use_translation_context: bool = False,
) -> list[dict[str, Any]]:
    outputs: list[dict[str, Any]] = []
    total = len(records)
    for idx, record in enumerate(records, start=1):
        text_obj = record_to_text_obj(record, use_translation_context=use_translation_context)
        progress_payload = {
            "index": idx,
            "total": total,
            "record_id": record.get("record_id"),
            "project_id": record.get("project_id"),
            "language": record.get("language"),
        }
        if on_progress:
            on_progress({**progress_payload, "status": "running"})
        try:
            annotated = await annotate_mwes(
                MWESpec(
                    text=text_obj,
                    language=str(record.get("language") or "en"),
                    op_id=f"{run_label}:record_{idx}:mwe",
                    template_path=template_path,
                )
            )
        except Exception as exc:
            if on_progress:
                on_progress({**progress_payload, "status": "error", "error": f"{type(exc).__name__}: {exc}"})
            raise
        segment = annotated.get("pages", [{}])[0].get("segments", [{}])[0]
        predicted_mwes = ((segment.get("annotations") or {}).get("mwes") or []) if isinstance(segment, dict) else []
        output_payload = {
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
            "translation_context": record.get("translation_context") or [],
        }
        outputs.append(output_payload)
        if on_output:
            on_output(output_payload)
        if on_progress:
            on_progress({**progress_payload, "status": "finished"})
    return outputs


def record_to_text_obj(record: dict[str, Any], *, use_translation_context: bool = False) -> dict[str, Any]:
    tokens = [{"surface": str(surface), "annotations": {}} for surface in (record.get("token_surfaces") or [])]
    surface = str(record.get("segment_surface") or " ".join(token["surface"] for token in tokens))
    annotations: dict[str, Any] = {}
    if use_translation_context:
        translation_context = normalize_translation_context(record.get("translation_context") or [])
        if translation_context:
            annotations["mwe_translation_context"] = translation_context
    return {"pages": [{"segments": [{"surface": surface, "tokens": tokens, "annotations": annotations}]}]}


def normalize_translation_context(raw: Any) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return []
    context: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or item.get("translation") or "").strip()
        if not text:
            continue
        context.append(
            {
                "language": str(item.get("language") or item.get("target_language") or "").strip(),
                "source": str(item.get("source") or "segment_translation").strip(),
                "text": text,
            }
        )
    return context


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as out:
        for record in records:
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
