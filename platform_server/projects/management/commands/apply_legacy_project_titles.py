from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from projects.management.commands.inventory_legacy_project_titles import PLACEHOLDER_TITLE_RE
from projects.models import LegacyProjectImport, Project


class Command(BaseCommand):
    help = "Apply explicitly reviewed legacy title proposals, with stale-data and collision guards."

    def add_arguments(self, parser):
        parser.add_argument("--proposals", required=True)
        parser.add_argument("--report", required=True, help="Destination JSON application report.")
        parser.add_argument("--only-id", action="append", default=[], help="Legacy project ID; repeatable.")
        parser.add_argument("--apply", action="store_true", help="Actually rename projects; otherwise perform a dry run.")

    def handle(self, *args, **options):
        proposals_path = Path(options["proposals"]).expanduser().resolve()
        report_path = Path(options["report"]).expanduser().resolve()
        if not proposals_path.is_file():
            raise CommandError(f"proposal report not found: {proposals_path}")
        if report_path.exists():
            raise CommandError(f"application report already exists: {report_path}")
        try:
            proposal_report = json.loads(proposals_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CommandError(f"proposal report is not valid JSON: {proposals_path}") from exc
        if proposal_report.get("schema_version") != 1 or not isinstance(proposal_report.get("proposals"), list):
            raise CommandError("unsupported title-proposal schema")

        only_ids = {str(value).strip() for value in options["only_id"] if str(value).strip()}
        proposals = [
            row
            for row in proposal_report["proposals"]
            if isinstance(row, dict)
            and row.get("status") == "proposed"
            and (not only_ids or str(row.get("legacy_project_id")) in only_ids)
        ]
        found_ids = {str(row.get("legacy_project_id")) for row in proposals}
        if only_ids - found_ids:
            raise CommandError("Applicable legacy IDs not found in proposals: " + ", ".join(sorted(only_ids - found_ids)))
        if not proposals:
            raise CommandError("proposal report contains no applicable reviewed proposals")

        outcomes = []
        for row in proposals:
            legacy_id = str(row.get("legacy_project_id"))
            new_title = " ".join(str(row.get("proposed_title") or "").split())[:200].rstrip()
            outcome = {"legacy_project_id": legacy_id, "project_id": row.get("project_id"), "proposed_title": new_title}
            try:
                with transaction.atomic():
                    record = LegacyProjectImport.objects.select_related("project").select_for_update().get(
                        source_system=row.get("source_system"),
                        legacy_project_id=legacy_id,
                        project_id=row.get("project_id"),
                    )
                    project = Project.objects.select_for_update().get(pk=record.project_id)
                    if project.owner_id != row.get("owner_id"):
                        raise ValueError("project owner changed since proposal")
                    if project.title != row.get("current_title"):
                        raise ValueError(f"project title changed since proposal: {project.title!r}")
                    if not PLACEHOLDER_TITLE_RE.fullmatch(project.title):
                        raise ValueError("current project title is no longer a placeholder")
                    if not new_title or PLACEHOLDER_TITLE_RE.fullmatch(new_title):
                        raise ValueError("proposed title is empty or still a placeholder")
                    collision_ids = list(
                        Project.objects.filter(owner_id=project.owner_id, title__iexact=new_title)
                        .exclude(pk=project.pk)
                        .values_list("id", flat=True)
                    )
                    if collision_ids:
                        raise ValueError(f"title collides with project IDs: {collision_ids}")
                    if options["apply"]:
                        project.title = new_title
                        project.save(update_fields=["title", "updated_at"])
                        outcome["status"] = "applied"
                    else:
                        outcome["status"] = "would_apply"
            except Exception as exc:
                outcome.update({"status": "skipped", "error": str(exc)})
            outcomes.append(outcome)
            self.stdout.write(f"{legacy_id} {outcome['status']}")

        report = {
            "schema_version": 1,
            "mode": "apply" if options["apply"] else "dry_run",
            "proposals_path": str(proposals_path),
            "summary": {
                "candidate_count": len(proposals),
                "applied_count": sum(row["status"] == "applied" for row in outcomes),
                "would_apply_count": sum(row["status"] == "would_apply" for row in outcomes),
                "skipped_count": sum(row["status"] == "skipped" for row in outcomes),
            },
            "outcomes": outcomes,
        }
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"Wrote title application report to {report_path}"))
