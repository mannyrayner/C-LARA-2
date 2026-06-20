from __future__ import annotations

import asyncio
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from pipeline.segmentation import SegmentationPhase2Spec, segmentation_phase_2
from pipeline.stage_artifacts import write_stage_artifact


@dataclass(frozen=True, slots=True)
class ExperimentInputRecord:
    record_id: str
    surface: str
    project_id: int | None = None
    project_title: str = ""
    split: str = ""
    page_index: int | None = None
    segment_index: int | None = None
    source_payload: dict[str, Any] | None = None


class Command(BaseCommand):
    help = "Run a repeatable linguistic-pipeline experiment over JSONL segment manifests."

    def add_arguments(self, parser):
        parser.add_argument("--input-records-jsonl", required=True)
        parser.add_argument("--start-stage", default="segmentation_phase_2")
        parser.add_argument("--end-stage", default="segmentation_phase_2")
        parser.add_argument("--stage-parameters-file", required=True)
        parser.add_argument("--run-label", required=True)
        parser.add_argument("--output-root", required=True)
        parser.add_argument("--language", default="fr")
        parser.add_argument("--overwrite", action="store_true")

    def handle(self, *args, **options):
        start_stage = str(options["start_stage"] or "")
        end_stage = str(options["end_stage"] or "")
        if start_stage != "segmentation_phase_2" or end_stage != "segmentation_phase_2":
            raise CommandError("initial experiment runner supports only segmentation_phase_2 -> segmentation_phase_2")
        input_path = Path(options["input_records_jsonl"]).resolve()
        params_path = Path(options["stage_parameters_file"]).resolve()
        output_root = Path(options["output_root"]).resolve()
        run_dir = output_root / options["run_label"]
        if run_dir.exists() and not options["overwrite"]:
            raise CommandError(f"run output already exists: {run_dir}; pass --overwrite")
        if run_dir.exists():
            shutil.rmtree(run_dir)
        run_dir.mkdir(parents=True, exist_ok=True)

        try:
            stage_parameters = json.loads(params_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise CommandError(f"Could not read stage parameters {params_path}: {exc}") from exc
        records = load_input_records(input_path)
        if not records:
            raise CommandError(f"No input records found in {input_path}")

        outputs = asyncio.run(
            run_segmentation_phase_2_records(
                records,
                language=str(options["language"] or "fr"),
                stage_parameters=stage_parameters,
                run_label=str(options["run_label"]),
            )
        )
        output_records_path = run_dir / "outputs.jsonl"
        with output_records_path.open("w", encoding="utf-8") as out:
            for payload in outputs:
                out.write(json.dumps(payload, ensure_ascii=False) + "\n")
        stage_dir = run_dir / "stage_outputs"
        stage_dir.mkdir(parents=True, exist_ok=True)
        for payload in outputs:
            record_dir = stage_dir / safe_record_id(str(payload["record_id"]))
            write_stage_artifact(record_dir, "segmentation_phase_2", payload["segmentation_phase_2"])
        manifest = build_manifest(
            input_path=input_path,
            params_path=params_path,
            output_records_path=output_records_path,
            run_dir=run_dir,
            run_label=str(options["run_label"]),
            language=str(options["language"] or "fr"),
            stage_parameters=stage_parameters,
            records=records,
            outputs=outputs,
        )
        manifest_path = run_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        self.stdout.write("Linguistic pipeline experiment complete")
        self.stdout.write(f"Run dir: {run_dir}")
        self.stdout.write(f"Records: {len(outputs)}")
        self.stdout.write(f"Outputs: {output_records_path}")
        self.stdout.write(f"Manifest: {manifest_path}")


def load_input_records(path: Path) -> list[ExperimentInputRecord]:
    records: list[ExperimentInputRecord] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        surface = str(payload.get("surface") or payload.get("input") or "")
        if not surface:
            continue
        record_id = str(payload.get("record_id") or f"line_{line_number}")
        records.append(
            ExperimentInputRecord(
                record_id=record_id,
                surface=surface,
                project_id=int(payload["project_id"]) if payload.get("project_id") is not None else None,
                project_title=str(payload.get("project_title") or ""),
                split=str(payload.get("split") or ""),
                page_index=int(payload["page_index"]) if payload.get("page_index") is not None else None,
                segment_index=int(payload["segment_index"]) if payload.get("segment_index") is not None else None,
                source_payload=payload,
            )
        )
    return records


async def run_segmentation_phase_2_records(
    records: list[ExperimentInputRecord], *, language: str, stage_parameters: dict[str, Any], run_label: str
) -> list[dict[str, Any]]:
    seg2_params = stage_parameters.get("segmentation_phase_2", {}) if isinstance(stage_parameters, dict) else {}
    if not isinstance(seg2_params, dict):
        seg2_params = {}
    outputs: list[dict[str, Any]] = []
    for idx, record in enumerate(records, start=1):
        text_obj = text_obj_for_record(record, language=language)
        variant = str(seg2_params.get("variant") or "")
        annotated = await segmentation_phase_2(
            SegmentationPhase2Spec(
                text=text_obj,
                language=language,
                op_id=f"{run_label}:record_{idx}:segmentation_phase_2",
                mechanism=str(seg2_params.get("mechanism") or "json_direct"),
                prompt_variant=str(seg2_params.get("prompt_variant") or seg2_params.get("template_variant") or variant),
                fewshot_variant=str(seg2_params.get("fewshot_variant") or variant),
                fewshot_count=str(
                    seg2_params.get("fewshot_count")
                    or seg2_params.get("fewshot_limit")
                    or seg2_params.get("fewshot_tranche")
                    or "all"
                ),
            )
        )
        outputs.append(
            {
                "record_id": record.record_id,
                "project_id": record.project_id,
                "project_title": record.project_title,
                "split": record.split,
                "page_index": record.page_index,
                "segment_index": record.segment_index,
                "input_surface": record.surface,
                "segmentation_phase_2": annotated,
                "stage_parameters": {"segmentation_phase_2": seg2_params},
            }
        )
    return outputs


def text_obj_for_record(record: ExperimentInputRecord, *, language: str) -> dict[str, Any]:
    return {
        "l2": language,
        "surface": record.surface,
        "pages": [
            {
                "surface": record.surface,
                "segments": [
                    {
                        "surface": record.surface,
                        "annotations": {},
                    }
                ],
                "annotations": {},
            }
        ],
        "annotations": {
            "experiment_record_id": record.record_id,
            "project_id": record.project_id,
            "split": record.split,
        },
    }


def build_manifest(
    *,
    input_path: Path,
    params_path: Path,
    output_records_path: Path,
    run_dir: Path,
    run_label: str,
    language: str,
    stage_parameters: dict[str, Any],
    records: list[ExperimentInputRecord],
    outputs: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "run_label": run_label,
        "language": language,
        "start_stage": "segmentation_phase_2",
        "end_stage": "segmentation_phase_2",
        "input_records_jsonl": str(input_path),
        "stage_parameters_file": str(params_path),
        "run_dir": str(run_dir),
        "outputs_jsonl": str(output_records_path),
        "record_count": len(records),
        "completed_count": len(outputs),
        "stage_parameters": stage_parameters,
        "record_ids": [record.record_id for record in records],
    }


def safe_record_id(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in value)
    return cleaned.strip("_") or "record"
