from __future__ import annotations

from collections import Counter

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from projects.legacy_batch import append_jsonl, imported_project_records, prepare_report, valid_compiled_index
from projects.metadata import update_project_discovery_metadata


class Command(BaseCommand):
    help = "Publish imported C-LARA projects that have a valid compiled HTML entry point."

    def add_arguments(self, parser):
        parser.add_argument("--source-system", default="clara_adelaide")
        parser.add_argument("--only-id", action="append", default=[], help="Legacy project ID; repeatable.")
        parser.add_argument("--limit", type=int)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--report", help="Optional JSONL outcome report.")
        parser.add_argument("--skip-discovery-metadata", action="store_true",
                            help="Publish without generating missing discovery metadata.")

    def handle(self, *args, **options):
        if options["limit"] is not None and options["limit"] < 1:
            raise CommandError("--limit must be a positive integer.")
        only_ids = {str(value).strip() for value in options["only_id"] if str(value).strip()}
        records = list(imported_project_records(source_system=options["source_system"], legacy_ids=only_ids))
        found_ids = {record.legacy_project_id for record in records}
        if only_ids - found_ids:
            raise CommandError("Imported legacy IDs not found: " + ", ".join(sorted(only_ids - found_ids)))
        if options["limit"] is not None:
            records = records[: options["limit"]]
        report = prepare_report(options.get("report"))
        counts: Counter[str] = Counter()
        for index, record in enumerate(records, 1):
            project = record.project
            base = {"source_system": record.source_system, "legacy_project_id": record.legacy_project_id,
                    "project_id": project.id, "title": project.title}
            compiled = valid_compiled_index(project)
            if compiled is None:
                row = {**base, "status": "skipped_missing_html", "message": "no safe existing compiled HTML entry point"}
            elif project.is_published:
                row = {**base, "status": "skipped_published", "compiled_path": str(compiled)}
            elif options["dry_run"]:
                row = {**base, "status": "would_publish", "compiled_path": str(compiled)}
            else:
                project.is_published = True
                project.published_at = project.published_at or timezone.now()
                project.save(update_fields=["is_published", "published_at", "updated_at"])
                metadata_updated = False
                if not options["skip_discovery_metadata"]:
                    metadata_updated = update_project_discovery_metadata(project, force=False)
                row = {**base, "status": "published", "compiled_path": str(compiled),
                       "discovery_metadata_updated": metadata_updated}
            counts[row["status"]] += 1
            append_jsonl(report, row)
            self.stdout.write(f"[{index}/{len(records)}] {record.legacy_project_id} {row['status']}")
        summary = ", ".join(f"{key}={value}" for key, value in sorted(counts.items())) or "no candidates"
        self.stdout.write(self.style.SUCCESS(f"Legacy publish batch complete: {summary}"))
