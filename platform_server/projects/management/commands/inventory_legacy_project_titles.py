from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from projects.legacy_batch import imported_project_records, inspect_render_input
from projects.models import Project


PLACEHOLDER_TITLE_RE = re.compile(r"^Imported legacy C-LARA project(?: \(([^)]+)\))?$", re.IGNORECASE)


def normalize_title(title: str) -> str:
    normalized = unicodedata.normalize("NFKC", title or "").casefold()
    normalized = re.sub(r"[^\w]+", " ", normalized, flags=re.UNICODE)
    return " ".join(normalized.split())


def _payload_text(payload: dict[str, Any]) -> str:
    page_texts: list[str] = []
    for page in payload.get("pages") or []:
        if not isinstance(page, dict):
            continue
        page_surface = str(page.get("surface") or "").strip()
        if page_surface:
            page_texts.append(page_surface)
            continue
        segment_texts = [
            str(segment.get("surface") or "").strip()
            for segment in page.get("segments") or []
            if isinstance(segment, dict) and str(segment.get("surface") or "").strip()
        ]
        page_texts.append(" ".join(segment_texts))
    return "\n".join(text for text in page_texts if text).strip()


def _project_text(project: Project) -> tuple[str, str]:
    render_input, _diagnostics = inspect_render_input(project)
    if render_input is not None:
        stage, _run_dir, payload = render_input
        text = _payload_text(payload)
        if text:
            return text, f"stage:{stage}"
    if (project.source_text or "").strip():
        return project.source_text.strip(), "project.source_text"
    if (project.description or "").strip():
        return project.description.strip(), "project.description"
    return "", "none"


class Command(BaseCommand):
    help = "Create a read-only inventory of imported legacy project titles and duplicate-title groups."

    def add_arguments(self, parser):
        parser.add_argument("--source-system", default="clara_adelaide")
        parser.add_argument("--only-id", action="append", default=[], help="Legacy project ID; repeatable.")
        parser.add_argument("--limit", type=int)
        parser.add_argument("--report", required=True, help="Destination JSON inventory report.")

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

        rows: list[dict[str, Any]] = []
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for record in records:
            project = record.project
            title = (project.title or "").strip()
            source_title = (record.source_title or "").strip()
            placeholder = bool(PLACEHOLDER_TITLE_RE.fullmatch(title))
            credible_source_title = bool(source_title and not PLACEHOLDER_TITLE_RE.fullmatch(source_title))
            collisions = []
            if credible_source_title:
                collisions = list(
                    Project.objects.filter(owner_id=project.owner_id, title__iexact=source_title)
                    .exclude(pk=project.pk)
                    .values_list("id", flat=True)
                )
            text, text_source = _project_text(project)
            compact_text = " ".join(text.split())
            row = {
                "source_system": record.source_system,
                "legacy_project_id": record.legacy_project_id,
                "project_id": project.id,
                "owner_id": project.owner_id,
                "owner_username": project.owner.get_username(),
                "original_owner_username": record.original_owner_username,
                "title": title,
                "normalized_title": normalize_title(title),
                "title_status": "placeholder" if placeholder else "named",
                "source_title": source_title,
                "credible_source_title": credible_source_title,
                "source_title_collision_project_ids": collisions,
                "text_language": project.language,
                "gloss_language": project.target_language,
                "is_published": project.is_published,
                "discovery_summary": project.discovery_summary,
                "discovery_keywords": project.discovery_keywords,
                "text_source": text_source,
                "text_preview": compact_text[:500],
                "text_sha256": hashlib.sha256(compact_text.encode("utf-8")).hexdigest() if compact_text else "",
            }
            rows.append(row)
            if row["normalized_title"] and not placeholder:
                groups[row["normalized_title"]].append(row)

        duplicate_groups = []
        for normalized_title, members in sorted(groups.items()):
            if len(members) < 2:
                continue
            gloss_languages = sorted({str(member["gloss_language"] or "") for member in members})
            fingerprints = {str(member["text_sha256"]) for member in members if member["text_sha256"]}
            duplicate_groups.append(
                {
                    "normalized_title": normalized_title,
                    "titles": sorted({str(member["title"]) for member in members}),
                    "project_ids": [member["project_id"] for member in members],
                    "legacy_project_ids": [member["legacy_project_id"] for member in members],
                    "language_pairs": sorted(
                        {f"{member['text_language']}->{member['gloss_language']}" for member in members}
                    ),
                    "gloss_languages": gloss_languages,
                    "all_text_fingerprints_equal": len(fingerprints) == 1 and bool(fingerprints),
                    "classification": (
                        "safe_language_disambiguation" if len(gloss_languages) > 1 else "same_language_duplicate"
                    ),
                }
            )

        report = {
            "schema_version": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_system": options["source_system"],
            "summary": {
                "project_count": len(rows),
                "placeholder_title_count": sum(row["title_status"] == "placeholder" for row in rows),
                "placeholder_with_credible_source_title_count": sum(
                    row["title_status"] == "placeholder" and row["credible_source_title"] for row in rows
                ),
                "source_title_collision_count": sum(bool(row["source_title_collision_project_ids"]) for row in rows),
                "duplicate_group_count": len(duplicate_groups),
                "safe_language_disambiguation_group_count": sum(
                    group["classification"] == "safe_language_disambiguation" for group in duplicate_groups
                ),
                "same_language_duplicate_group_count": sum(
                    group["classification"] == "same_language_duplicate" for group in duplicate_groups
                ),
            },
            "projects": rows,
            "duplicate_groups": duplicate_groups,
        }
        report_path = Path(options["report"]).expanduser().resolve()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.stdout.write(
            self.style.SUCCESS(
                f"Inventoried {len(rows)} legacy project(s): "
                f"placeholders={report['summary']['placeholder_title_count']}, "
                f"duplicate_groups={len(duplicate_groups)}; wrote {report_path}"
            )
        )
