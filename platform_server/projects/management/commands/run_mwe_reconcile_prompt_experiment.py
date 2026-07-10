from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path
from typing import Any, Callable

from django.core.management.base import BaseCommand, CommandError

from core.ai_api import OpenAIClient

from .review_fewshots import _resolve_cli_path
from .run_mwe_prompt_experiment import (
    count_records_with_translation_context,
    load_existing_outputs,
    load_mwe_records,
    normalize_translation_context,
    parse_project_ids,
)


class Command(BaseCommand):
    help = "Run a multi-analysis + reconciliation MWE prompt experiment."

    def add_arguments(self, parser):
        parser.add_argument("--input-records-jsonl", required=True)
        parser.add_argument("--output-dir", required=True)
        parser.add_argument("--run-label", required=True)
        parser.add_argument("--analysis-template-dir", required=True)
        parser.add_argument("--reconcile-template", required=True)
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument("--overwrite", action="store_true")
        parser.add_argument("--resume", action="store_true")
        parser.add_argument("--max-record-attempts", type=int, default=3)
        parser.add_argument("--project-ids", default="")
        parser.add_argument("--model", default="")

    def handle(self, *args, **options):
        input_path = _resolve_cli_path(options["input_records_jsonl"], "")
        output_root = _resolve_cli_path(options["output_dir"], "")
        run_dir = output_root / str(options["run_label"])
        resume = bool(options.get("resume"))
        if resume and options["overwrite"]:
            raise CommandError("--resume and --overwrite cannot be used together")
        if run_dir.exists() and not options["overwrite"] and not resume:
            raise CommandError(f"run output already exists: {run_dir}; pass --overwrite")
        if run_dir.exists() and options["overwrite"]:
            shutil.rmtree(run_dir)
        run_dir.mkdir(parents=True, exist_ok=True)

        project_ids = parse_project_ids(str(options.get("project_ids") or ""))
        records = load_mwe_records(input_path, limit=int(options.get("limit") or 0), project_ids=project_ids)
        if not records:
            raise CommandError(f"No records found in {input_path}")
        analysis_templates = load_analysis_templates(_resolve_cli_path(options["analysis_template_dir"], ""))
        reconcile_template_path = _resolve_cli_path(options["reconcile_template"], "")
        reconcile_template = reconcile_template_path.read_text(encoding="utf-8")
        outputs_path = run_dir / "outputs.jsonl"
        progress_path = run_dir / "progress.jsonl"
        existing_outputs = load_existing_outputs(outputs_path) if resume else {}
        if existing_outputs:
            records = [record for record in records if str(record.get("record_id") or "") not in existing_outputs]
            self.stdout.write(f"Resume enabled: found {len(existing_outputs)} existing outputs; {len(records)} records remain")
        output_count = len(existing_outputs)

        def record_progress(event: dict[str, Any]) -> None:
            with progress_path.open("a", encoding="utf-8") as progress_out:
                progress_out.write(json.dumps(event, ensure_ascii=False) + "\n")
            status = event.get("status")
            idx = event.get("index")
            total = event.get("total")
            record_id = event.get("record_id")
            if status == "running":
                self.stdout.write(f"[{idx}/{total}] running reconciled MWE prompt for {record_id}")
            elif status == "finished":
                self.stdout.write(f"[{idx}/{total}] finished {record_id}")
            elif status == "retry":
                self.stdout.write(f"[{idx}/{total}] retry {event.get('attempt')}/{event.get('max_attempts')} for {record_id}: {event.get('error')}")
            elif status == "error":
                self.stdout.write(f"[{idx}/{total}] error {record_id}: {event.get('error')}")

        def record_output(payload: dict[str, Any]) -> None:
            nonlocal output_count
            with outputs_path.open("a", encoding="utf-8") as outputs_out:
                outputs_out.write(json.dumps(payload, ensure_ascii=False) + "\n")
            output_count += 1

        self.stdout.write(f"Loaded {len(records)} MWE records from {input_path}")
        self.stdout.write(f"Reconcile analysis templates: {', '.join(name for name, _ in analysis_templates)}")
        self.stdout.write(f"Translation context available: {count_records_with_translation_context(records)}/{len(records)} records")
        if records:
            client = OpenAIClient()
            asyncio.run(
                run_reconciled_records(
                    records,
                    run_label=str(options["run_label"]),
                    analysis_templates=analysis_templates,
                    reconcile_template=reconcile_template,
                    client=client,
                    model=str(options.get("model") or "") or None,
                    max_record_attempts=max(1, int(options.get("max_record_attempts") or 1)),
                    on_progress=record_progress,
                    on_output=record_output,
                )
            )
        else:
            self.stdout.write("No remaining records to run.")

        manifest = {
            "schema_version": 1,
            "input_records_jsonl": str(input_path),
            "run_label": str(options["run_label"]),
            "record_count": output_count,
            "resumed": resume,
            "existing_output_count": len(existing_outputs),
            "project_ids": sorted(project_ids),
            "outputs_jsonl": str(outputs_path),
            "progress_jsonl": str(progress_path),
            "analysis_templates": [name for name, _ in analysis_templates],
            "reconcile_template": str(reconcile_template_path),
            "max_record_attempts": max(1, int(options.get("max_record_attempts") or 1)),
        }
        (run_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.stdout.write(f"Reconciled MWE prompt run complete: {output_count} records")
        self.stdout.write(f"Outputs: {outputs_path}")
        self.stdout.write(f"Progress: {progress_path}")


def load_analysis_templates(directory: Path) -> list[tuple[str, str]]:
    if not directory.exists():
        raise CommandError(f"analysis template directory not found: {directory}")
    paths = sorted(path for path in directory.glob("*.txt") if path.is_file())
    if len(paths) != 3:
        raise CommandError(f"expected exactly three analysis templates in {directory}, found {len(paths)}")
    return [(path.stem, path.read_text(encoding="utf-8")) for path in paths]


async def run_reconciled_records(
    records: list[dict[str, Any]],
    *,
    run_label: str,
    analysis_templates: list[tuple[str, str]],
    reconcile_template: str,
    client: OpenAIClient,
    model: str | None = None,
    max_record_attempts: int = 3,
    on_progress: Callable[[dict[str, Any]], None] | None = None,
    on_output: Callable[[dict[str, Any]], None] | None = None,
) -> list[dict[str, Any]]:
    outputs: list[dict[str, Any]] = []
    total = len(records)
    for idx, record in enumerate(records, start=1):
        progress_payload = {
            "index": idx,
            "total": total,
            "record_id": record.get("record_id"),
            "project_id": record.get("project_id"),
            "language": record.get("language"),
        }
        output_payload = None
        max_attempts = max(1, max_record_attempts)
        for attempt in range(1, max_attempts + 1):
            if on_progress:
                on_progress({**progress_payload, "status": "running", "attempt": attempt, "max_attempts": max_attempts})
            try:
                output_payload = await run_one_record(
                    record,
                    run_label=run_label,
                    record_index=idx,
                    attempt=attempt,
                    analysis_templates=analysis_templates,
                    reconcile_template=reconcile_template,
                    client=client,
                    model=model,
                )
                break
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
                if on_progress:
                    on_progress({**progress_payload, "status": "retry" if attempt < max_attempts else "error", "attempt": attempt, "max_attempts": max_attempts, "error": error})
                if attempt >= max_attempts:
                    raise
        if output_payload is None:
            raise RuntimeError(f"Reconciled MWE annotation failed without an exception for {record.get('record_id')}")
        outputs.append(output_payload)
        if on_output:
            on_output(output_payload)
        if on_progress:
            on_progress({**progress_payload, "status": "finished"})
    return outputs


async def run_one_record(
    record: dict[str, Any],
    *,
    run_label: str,
    record_index: int,
    attempt: int,
    analysis_templates: list[tuple[str, str]],
    reconcile_template: str,
    client: OpenAIClient,
    model: str | None,
) -> dict[str, Any]:
    segment_payload = segment_payload_for_record(record)
    analysis_results = []
    for name, template in analysis_templates:
        prompt = build_analysis_prompt(template, record=record, segment_payload=segment_payload)
        result = await client.chat_json(prompt, model=model, op_id=f"{run_label}:record_{record_index}:attempt_{attempt}:analysis:{name}")
        analysis_results.append({"name": name, "result": result})
    reconcile_prompt = build_reconcile_prompt(reconcile_template, segment_payload=segment_payload, analyses=analysis_results)
    reconciled = await client.chat_json(reconcile_prompt, model=model, op_id=f"{run_label}:record_{record_index}:attempt_{attempt}:reconcile")
    segment = normalize_reconciled_segment(record, reconciled)
    annotations = segment.get("annotations") if isinstance(segment, dict) else {}
    predicted_mwes = (annotations or {}).get("mwes") or []
    return {
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
        "mwe_analysis": (annotations or {}).get("mwe_analysis") or "",
        "mwe_candidate_analyses": analysis_results,
        "annotated_segment": segment,
        "translation_context": normalize_translation_context(record.get("translation_context") or []),
    }


def segment_payload_for_record(record: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "surface": record.get("segment_surface") or "",
        "tokens": [{"surface": str(surface)} for surface in (record.get("token_surfaces") or [])],
    }
    translation_context = normalize_translation_context(record.get("translation_context") or [])
    if translation_context:
        payload["translation_context"] = translation_context
    return payload


def build_analysis_prompt(template: str, *, record: dict[str, Any], segment_payload: dict[str, Any]) -> str:
    return "\n\n".join(
        [
            template.strip(),
            "Segment JSON:",
            json.dumps(segment_payload, ensure_ascii=False, indent=2),
            "Return only JSON.",
        ]
    )


def build_reconcile_prompt(template: str, *, segment_payload: dict[str, Any], analyses: list[dict[str, Any]]) -> str:
    return "\n\n".join(
        [
            template.strip(),
            "Segment JSON:",
            json.dumps(segment_payload, ensure_ascii=False, indent=2),
            "Independent analyses:",
            json.dumps(analyses, ensure_ascii=False, indent=2),
            "Return only JSON.",
        ]
    )


def normalize_reconciled_segment(record: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    segment = payload.get("segment") if isinstance(payload.get("segment"), dict) else payload
    annotations = segment.get("annotations") if isinstance(segment, dict) and isinstance(segment.get("annotations"), dict) else {}
    tokens = segment.get("tokens") if isinstance(segment, dict) and isinstance(segment.get("tokens"), list) else []
    if not tokens:
        tokens = [{"surface": str(surface)} for surface in (record.get("token_surfaces") or [])]
    normalized_tokens = []
    for token in tokens:
        if isinstance(token, dict):
            normalized_tokens.append(token)
        else:
            normalized_tokens.append({"surface": str(token)})
    translation_context = normalize_translation_context(record.get("translation_context") or [])
    if translation_context:
        annotations["mwe_translation_context"] = translation_context
    return {
        "surface": record.get("segment_surface") or segment.get("surface") or "",
        "tokens": normalized_tokens,
        "annotations": annotations,
    }
