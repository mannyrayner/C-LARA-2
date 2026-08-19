from __future__ import annotations

import asyncio
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify

from pipeline.audio import AudioSpec, annotate_audio
from pipeline.stage_artifacts import write_stage_artifact
from projects.legacy_batch import (
    append_jsonl,
    imported_project_records,
    inspect_render_input,
    prepare_report,
    render_project_html,
)


def _audio_repository_dir(language: str) -> Path:
    language_slug = slugify((language or "und").replace("_", "-")).replace("-", "_") or "und"
    return Path(settings.MEDIA_ROOT).resolve() / "audio_repository" / language_slug


def _input_trace(project) -> dict:
    artifact_root = project.artifact_dir().resolve()
    runs_root = artifact_root / "runs"
    trace = {
        "computed_artifact_root": str(artifact_root),
        "stored_artifact_root": project.artifact_root,
        "runs_root": str(runs_root),
        "runs_root_exists": runs_root.exists(),
        "runs_root_is_directory": runs_root.is_dir(),
        "runs_root_readable": os.access(runs_root, os.R_OK),
        "runs_root_searchable": os.access(runs_root, os.X_OK),
        "runs": [],
    }
    try:
        run_dirs = sorted((path for path in runs_root.iterdir() if path.is_dir()), key=lambda path: path.name)
    except OSError as exc:
        trace["listing_error"] = str(exc)
        return trace
    for run_dir in run_dirs:
        stages_dir = run_dir / "stages"
        stage_files = []
        try:
            for stage_path in sorted(stages_dir.glob("*.json")):
                stage_files.append(
                    {
                        "name": stage_path.name,
                        "readable": os.access(stage_path, os.R_OK),
                        "size": stage_path.stat().st_size,
                    }
                )
        except OSError as exc:
            stage_files.append({"inspection_error": str(exc)})
        trace["runs"].append({"name": run_dir.name, "stages": stage_files})
    return trace


class Command(BaseCommand):
    help = "Regenerate current-quality audio for imported legacy projects and rebuild their published HTML."

    def add_arguments(self, parser):
        parser.add_argument("--source-system", default="clara_adelaide")
        parser.add_argument(
            "--project-id",
            action="append",
            type=int,
            default=[],
            help="C-LARA-2 project ID; repeatable.",
        )
        parser.add_argument("--limit", type=int)
        parser.add_argument("--voice", default="", help="Optional TTS voice; otherwise use the configured default.")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--trace", action="store_true", help="Print detailed artifact/run/stage diagnostics.")
        parser.add_argument("--report", help="Optional JSONL outcome report.")

    def handle(self, *args, **options):
        if options["limit"] is not None and options["limit"] < 1:
            raise CommandError("--limit must be a positive integer.")
        project_ids = {int(value) for value in options["project_id"]}
        records_query = imported_project_records(source_system=options["source_system"])
        if project_ids:
            records_query = records_query.filter(project_id__in=project_ids)
        records = list(records_query)
        found_ids = {record.project_id for record in records}
        if project_ids - found_ids:
            missing = ", ".join(str(project_id) for project_id in sorted(project_ids - found_ids))
            raise CommandError(
                f"C-LARA-2 project IDs are not successful {options['source_system']} imports: {missing}"
            )
        if options["limit"] is not None:
            records = records[: options["limit"]]

        report = prepare_report(options.get("report"))
        counts: Counter[str] = Counter()
        for index, record in enumerate(records, 1):
            project = record.project
            base = {
                "source_system": record.source_system,
                "legacy_project_id": record.legacy_project_id,
                "project_id": project.id,
                "title": project.title,
                "language": project.language,
            }
            render_input, diagnostics = inspect_render_input(project)
            artifact_trace = _input_trace(project) if options["trace"] or render_input is None else None
            if render_input is None:
                row = {
                    **base,
                    "status": "skipped_missing_input",
                    "message": "no readable annotation artifact with a pages list",
                    "diagnostics": diagnostics,
                    "artifact_trace": artifact_trace,
                }
            elif options["dry_run"]:
                stage, run_dir, _payload = render_input
                row = {**base, "status": "would_regenerate", "input_stage": stage, "input_run": run_dir.name}
            else:
                stage, run_dir, payload = render_input
                try:
                    annotated = asyncio.run(
                        annotate_audio(
                            AudioSpec(
                                text=payload,
                                language=project.language,
                                voice=(options.get("voice") or "").strip() or None,
                                cache_dir=_audio_repository_dir(project.language),
                                require_real_tts=True,
                            )
                        )
                    )
                    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
                    audio_run = project.artifact_dir().resolve() / "runs" / f"run_legacy_audio_{timestamp}"
                    write_stage_artifact(audio_run, "audio", annotated)
                    html_path, _render_stage, _render_input_run = render_project_html(project)
                    row = {
                        **base,
                        "status": "regenerated",
                        "input_stage": stage,
                        "input_run": run_dir.name,
                        "audio_run": audio_run.name,
                        "compiled_path": str(html_path),
                        "render_run": html_path.parent.parent.name,
                    }
                except Exception as exc:
                    row = {**base, "status": "failed", "message": str(exc)}
            counts[row["status"]] += 1
            append_jsonl(report, row)
            self.stdout.write(
                f"[{index}/{len(records)}] project_id={project.id} "
                f"legacy_id={record.legacy_project_id} {row['status']}"
            )
            if row["status"] == "skipped_missing_input":
                for diagnostic in row.get("diagnostics", []):
                    self.stdout.write(f"  input diagnostic: {diagnostic}")
            if options["trace"]:
                self.stdout.write(json.dumps(artifact_trace, ensure_ascii=False, indent=2))

        summary = ", ".join(f"{status}={count}" for status, count in sorted(counts.items())) or "no candidates"
        self.stdout.write(self.style.SUCCESS(f"Legacy audio regeneration complete: {summary}"))
