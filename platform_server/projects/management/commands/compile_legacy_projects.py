from __future__ import annotations

from collections import Counter

from django.core.management.base import BaseCommand, CommandError

from projects.legacy_batch import (
    append_jsonl,
    imported_project_records,
    inspect_render_input,
    prepare_report,
    render_project_html,
    valid_compiled_index,
)


class Command(BaseCommand):
    help = "Render HTML, and only HTML, for imported C-LARA projects with existing annotation artifacts."

    def add_arguments(self, parser):
        parser.add_argument("--source-system", default="clara_adelaide")
        parser.add_argument("--only-id", action="append", default=[], help="Legacy project ID; repeatable.")
        parser.add_argument("--limit", type=int)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--force", action="store_true", help="Render again even when valid HTML already exists.")
        parser.add_argument("--report", help="Optional JSONL outcome report.")

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
            existing = valid_compiled_index(project)
            render_input, input_diagnostics = inspect_render_input(project)
            if existing and not options["force"]:
                row = {**base, "status": "skipped_compiled", "message": str(existing)}
            elif render_input is None:
                row = {**base, "status": "skipped_missing_input",
                       "message": "no readable upstream stage artifact with a pages list",
                       "diagnostics": input_diagnostics}
            elif options["dry_run"]:
                stage, run_dir, _payload = render_input
                row = {**base, "status": "would_compile", "input_stage": stage, "input_run": run_dir.name}
            else:
                try:
                    html_path, stage, run_dir = render_project_html(project)
                    row = {**base, "status": "compiled", "compiled_path": str(html_path),
                           "input_stage": stage, "input_run": run_dir.name}
                except Exception as exc:
                    row = {**base, "status": "failed", "message": str(exc)}
            counts[row["status"]] += 1
            append_jsonl(report, row)
            detail = ""
            if row["status"] == "skipped_missing_input":
                detail = ": " + "; ".join(row["diagnostics"])
            self.stdout.write(f"[{index}/{len(records)}] {record.legacy_project_id} {row['status']}{detail}")
        summary = ", ".join(f"{key}={value}" for key, value in sorted(counts.items())) or "no candidates"
        self.stdout.write(self.style.SUCCESS(f"Legacy HTML batch complete: {summary}"))
