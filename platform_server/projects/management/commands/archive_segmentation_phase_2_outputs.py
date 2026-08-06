from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from projects.models import Project

from .refresh_mwe_experiment_projects import latest_stage_path_text, resolve_project_ids


class Command(BaseCommand):
    help = "Archive current segmentation_phase_2 artifacts for selected projects before manual correction."

    def add_arguments(self, parser):
        parser.add_argument("--project-ids", default="", help="Comma-separated project ids to archive.")
        parser.add_argument(
            "--split-manifest",
            default="",
            help="MWE split manifest from extract_mwe_corpus; archives project ids in selected splits.",
        )
        parser.add_argument("--splits", default="development,validation,test")
        parser.add_argument("--output-dir", required=True)
        parser.add_argument("--archive-label", default="initial-gpt-5.6-segmentation-phase-2")
        parser.add_argument("--model", default="gpt-5.6")
        parser.add_argument("--overwrite", action="store_true")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        splits = [item.strip() for item in str(options["splits"] or "").split(",") if item.strip()]
        project_ids = resolve_project_ids(
            project_ids_text=str(options["project_ids"] or ""),
            split_manifest_text=str(options["split_manifest"] or ""),
            splits=splits,
        )
        if not project_ids:
            raise CommandError("No projects selected; pass --project-ids or --split-manifest")

        projects = list(Project.objects.filter(id__in=project_ids).order_by("id"))
        found_ids = {project.id for project in projects}
        missing_ids = sorted(set(project_ids) - found_ids)
        if missing_ids:
            raise CommandError(f"Unknown project ids: {', '.join(str(item) for item in missing_ids)}")

        output_dir = Path(str(options["output_dir"])).resolve()
        if output_dir.exists() and not options["overwrite"] and not options["dry_run"]:
            raise CommandError(f"archive output already exists: {output_dir}; pass --overwrite")

        manifest: dict[str, Any] = {
            "schema_version": 1,
            "archive_label": str(options["archive_label"] or "initial-gpt-5.6-segmentation-phase-2"),
            "model": str(options["model"] or ""),
            "stage": "segmentation_phase_2",
            "project_ids": project_ids,
            "splits": splits,
            "dry_run": bool(options["dry_run"]),
            "projects": [],
        }
        for project in projects:
            source_path_text = latest_stage_path_text(project, "segmentation_phase_2")
            if not source_path_text:
                raise CommandError(f"Project {project.id} has no segmentation_phase_2 artifact to archive")
            source_path = Path(source_path_text).resolve()
            destination = output_dir / f"project_{project.id}" / "segmentation_phase_2.json"
            record = {
                "project_id": project.id,
                "project_title": project.title,
                "language": project.language,
                "target_language": project.target_language,
                "source_path": str(source_path),
                "archive_path": str(destination),
                "would_copy": bool(options["dry_run"]),
            }
            manifest["projects"].append(record)
            if options["dry_run"]:
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, destination)

        if not options["dry_run"]:
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        self.stdout.write(json.dumps(manifest, ensure_ascii=False, indent=2))
