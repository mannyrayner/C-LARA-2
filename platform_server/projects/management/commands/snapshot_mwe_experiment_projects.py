from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from projects.models import Project
from projects.snapshots import save_project_snapshot

from .refresh_mwe_experiment_projects import resolve_project_ids

GOLD_COMPONENTS = ["MWE annotations", "gloss annotations", "lemma annotations"]


class Command(BaseCommand):
    help = "Save gold-standard snapshots for projects used in focused MWE experiments."

    def add_arguments(self, parser):
        parser.add_argument("--project-ids", default="", help="Comma-separated project ids to snapshot.")
        parser.add_argument(
            "--split-manifest",
            default="",
            help="MWE split manifest from extract_mwe_corpus; snapshots project ids in selected splits.",
        )
        parser.add_argument("--splits", default="development,validation,test")
        parser.add_argument("--snapshot-name-prefix", default="MWE gold checkpoint")
        parser.add_argument("--created-by", default="mwe-experiment")
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

        manifest: dict[str, Any] = {
            "schema_version": 1,
            "project_ids": project_ids,
            "gold_standard_components": GOLD_COMPONENTS,
            "snapshots": [],
            "dry_run": bool(options["dry_run"]),
        }
        for project in projects:
            snapshot_name = f"{options['snapshot_name_prefix']} project {project.id}"
            if options["dry_run"]:
                manifest["snapshots"].append(
                    {
                        "project_id": project.id,
                        "project_title": project.title,
                        "snapshot_name": snapshot_name,
                        "would_save": True,
                    }
                )
                continue
            snapshot = save_project_snapshot(
                project,
                name=snapshot_name,
                created_by=str(options["created_by"] or "mwe-experiment"),
                contains_gold_standard=True,
                gold_standard_components=GOLD_COMPONENTS,
            )
            manifest["snapshots"].append(
                {
                    "project_id": project.id,
                    "project_title": project.title,
                    "snapshot_id": snapshot.snapshot_id,
                    "snapshot_name": snapshot.name,
                    "created_at": snapshot.created_at,
                    "gold_standard_components": list(snapshot.gold_standard_components),
                }
            )
            self.stdout.write(f"Saved snapshot project={project.id} snapshot={snapshot.snapshot_id}")

        self.stdout.write(json.dumps(manifest, ensure_ascii=False, indent=2))
