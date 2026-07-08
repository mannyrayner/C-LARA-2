from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from projects.models import Project
from projects.snapshots import list_project_snapshots, restore_project_snapshot, save_project_snapshot


class Command(BaseCommand):
    help = "Save, list, or restore file-backed project snapshots."

    def add_arguments(self, parser):
        parser.add_argument("action", choices=["save", "list", "restore"])
        parser.add_argument("--project-id", type=int, required=True)
        parser.add_argument("--name", default="")
        parser.add_argument("--snapshot-id", default="")
        parser.add_argument("--created-by", default="management-command")
        parser.add_argument("--contains-gold-standard", action="store_true")
        parser.add_argument(
            "--gold-standard-component",
            action="append",
            default=[],
            help="Component covered by gold-standard data; may be repeated.",
        )

    def handle(self, *args, **options):
        try:
            project = Project.objects.get(pk=options["project_id"])
        except Project.DoesNotExist as exc:
            raise CommandError(f"Project {options['project_id']} does not exist.") from exc

        action = options["action"]
        if action == "save":
            if not options["name"]:
                raise CommandError("--name is required for save.")
            snapshot = save_project_snapshot(
                project,
                name=options["name"],
                created_by=options["created_by"],
                contains_gold_standard=options["contains_gold_standard"],
                gold_standard_components=options["gold_standard_component"],
            )
            self.stdout.write(self.style.SUCCESS(f"Saved snapshot {snapshot.snapshot_id}: {snapshot.name}"))
            return

        if action == "restore":
            if not options["snapshot_id"]:
                raise CommandError("--snapshot-id is required for restore.")
            snapshot = restore_project_snapshot(project, snapshot_id=options["snapshot_id"])
            self.stdout.write(self.style.SUCCESS(f"Restored snapshot {snapshot.snapshot_id}: {snapshot.name}"))
            return

        for snapshot in list_project_snapshots(project):
            gold = ""
            if snapshot.contains_gold_standard:
                components = ", ".join(snapshot.gold_standard_components) or "unspecified components"
                gold = f" [gold: {components}]"
            self.stdout.write(f"{snapshot.snapshot_id}\t{snapshot.created_at}\t{snapshot.name}{gold}")
