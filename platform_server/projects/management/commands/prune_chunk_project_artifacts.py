from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Remove JSONL records for a project from a generated chunk-experiment artifact subtree."

    def add_arguments(self, parser):
        parser.add_argument("--root-dir", required=True)
        parser.add_argument("--project-id", type=int, default=None)
        parser.add_argument("--project-title", default="")
        parser.add_argument("--apply", action="store_true", help="Actually rewrite files; omit for a dry run.")

    def handle(self, *args, **options):
        root_dir = Path(options["root_dir"]).resolve()
        project_id = options.get("project_id")
        project_title = str(options.get("project_title") or "")
        apply = bool(options.get("apply"))
        if not root_dir.exists():
            raise CommandError(f"root directory not found: {root_dir}")
        if not root_dir.is_dir():
            raise CommandError(f"root path is not a directory: {root_dir}")
        if project_id is None and not project_title:
            raise CommandError("provide --project-id and/or --project-title")

        summary = prune_tree(root_dir=root_dir, project_id=project_id, project_title=project_title, apply=apply)
        mode = "Applied" if apply else "Dry run"
        self.stdout.write(f"{mode}: pruned chunk project artifacts")
        self.stdout.write(f"Root: {root_dir}")
        self.stdout.write(f"Files scanned: {summary['files_scanned']}")
        self.stdout.write(f"Files changed: {summary['files_changed']}")
        self.stdout.write(f"Records removed: {summary['records_removed']}")
        if not apply:
            self.stdout.write("No files were modified; pass --apply to rewrite matching JSONL files.")


def prune_tree(*, root_dir: Path, project_id: int | None, project_title: str, apply: bool) -> dict[str, Any]:
    files_scanned = 0
    files_changed = 0
    records_removed = 0
    for path in sorted(root_dir.rglob("*.jsonl")):
        files_scanned += 1
        kept_lines: list[str] = []
        removed_here = 0
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                kept_lines.append(line)
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                kept_lines.append(line)
                continue
            if isinstance(payload, dict) and matches_project(payload, project_id=project_id, project_title=project_title):
                removed_here += 1
                continue
            kept_lines.append(line)
        if removed_here:
            files_changed += 1
            records_removed += removed_here
            if apply:
                path.write_text("\n".join(kept_lines) + ("\n" if kept_lines else ""), encoding="utf-8")
    return {"files_scanned": files_scanned, "files_changed": files_changed, "records_removed": records_removed}


def matches_project(record: dict[str, Any], *, project_id: int | None, project_title: str) -> bool:
    if project_id is not None:
        try:
            if int(record.get("project_id")) == project_id:
                return True
        except (TypeError, ValueError):
            pass
    if project_title and str(record.get("project_title") or "") == project_title:
        return True
    return False
