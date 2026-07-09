from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from projects.models import Project

from .extract_mwe_corpus import iter_project_segment_records, latest_stage_payload
from .review_fewshots import _resolve_cli_path
from .run_mwe_prompt_experiment import parse_project_ids


class Command(BaseCommand):
    help = "Export all MWE segment records for an explicit gold project subset."

    def add_arguments(self, parser):
        parser.add_argument("--project-ids", required=True, help="Comma-separated project ids to export.")
        parser.add_argument("--language", default="en")
        parser.add_argument("--split", default="development")
        parser.add_argument("--output-jsonl", required=True)
        parser.add_argument("--summary-json", required=True)
        parser.add_argument("--review-markdown", required=True)
        parser.add_argument("--require-gold", action="store_true")
        parser.add_argument("--overwrite", action="store_true")

    def handle(self, *args, **options):
        project_ids = sorted(parse_project_ids(str(options["project_ids"] or "")))
        if not project_ids:
            raise CommandError("--project-ids must select at least one project")
        output_jsonl = _resolve_cli_path(options["output_jsonl"], "")
        summary_json = _resolve_cli_path(options["summary_json"], "")
        review_markdown = _resolve_cli_path(options["review_markdown"], "")
        for path in (output_jsonl, summary_json, review_markdown):
            if path.exists() and not options["overwrite"]:
                raise CommandError(f"output already exists: {path}; pass --overwrite")
            path.parent.mkdir(parents=True, exist_ok=True)

        projects = list(Project.objects.filter(id__in=project_ids).order_by("id"))
        found_ids = {project.id for project in projects}
        missing_ids = sorted(set(project_ids) - found_ids)
        if missing_ids:
            raise CommandError(f"Unknown project ids: {', '.join(str(item) for item in missing_ids)}")

        records: list[dict[str, Any]] = []
        project_summaries = []
        for project in projects:
            run_dir, stage_path, payload = latest_stage_payload(project, "mwe")
            _translation_run_dir, _translation_path, translation_payload = latest_stage_payload(project, "translation")
            translation_map = build_translation_context_map(
                translation_payload, target_language=getattr(project, "target_language", "") or ""
            )
            project_records = []
            if run_dir and stage_path and isinstance(payload, dict) and isinstance(payload.get("pages"), list):
                for record in iter_project_segment_records(
                    project=project,
                    language=str(options["language"] or project.language or "en"),
                    stage_path=stage_path,
                    pages=payload["pages"],
                ):
                    payload_record = {**asdict(record), "split": str(options["split"] or "development"), "stratum": "explicit-gold-subset"}
                    payload_record["translation_context"] = translation_map.get((record.page_index, record.segment_index), [])
                    project_records.append(payload_record)
            records.extend(project_records)
            project_summaries.append(
                {
                    "project_id": project.id,
                    "project_title": project.title,
                    "latest_mwe_run": run_dir.name if run_dir else "",
                    "latest_mwe_path": str(stage_path) if stage_path else "",
                    "record_count": len(project_records),
                    "records_with_gold_mwes": sum(1 for record in project_records if record.get("gold_mwes")),
                    "gold_mwe_count": sum(len(record.get("gold_mwes") or []) for record in project_records),
                }
            )

        records.sort(key=lambda record: (int(record["project_id"]), int(record["page_index"]), int(record["segment_index"])))
        total_gold = sum(len(record.get("gold_mwes") or []) for record in records)
        records_with_gold = sum(1 for record in records if record.get("gold_mwes"))
        if options["require_gold"] and total_gold == 0:
            raise CommandError("Selected records contain no gold MWEs; rerun extraction after manual annotation or inspect latest MWE artifacts.")

        write_jsonl(output_jsonl, records)
        summary = {
            "schema_version": 1,
            "project_ids": project_ids,
            "language": str(options["language"] or ""),
            "split": str(options["split"] or ""),
            "output_jsonl": str(output_jsonl),
            "review_markdown": str(review_markdown),
            "record_count": len(records),
            "records_with_gold_mwes": records_with_gold,
            "gold_mwe_count": total_gold,
            "projects": project_summaries,
        }
        summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        write_review_markdown(review_markdown, summary=summary, records=records)
        self.stdout.write(
            f"Exported MWE gold subset: records={len(records)} records_with_gold={records_with_gold} gold_mwes={total_gold}"
        )
        self.stdout.write(f"Records: {output_jsonl}")
        self.stdout.write(f"Summary: {summary_json}")
        self.stdout.write(f"Review: {review_markdown}")


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as out:
        for record in records:
            out.write(json.dumps(record, ensure_ascii=False) + "\n")


def write_review_markdown(path: Path, *, summary: dict[str, Any], records: list[dict[str, Any]]) -> None:
    lines = [
        "# MWE gold subset review",
        "",
        f"- Language: `{summary['language']}`",
        f"- Split label: `{summary['split']}`",
        f"- Projects: {summary['project_ids']}",
        f"- Records: {summary['record_count']}",
        f"- Records with gold MWEs: {summary['records_with_gold_mwes']}",
        f"- Gold MWEs: {summary['gold_mwe_count']}",
        "",
        "## Project summary",
        "",
    ]
    for project in summary["projects"]:
        lines.append(
            f"- `{project['project_id']}` {project['project_title']}: "
            f"records={project['record_count']}, records_with_gold={project['records_with_gold_mwes']}, "
            f"gold_mwes={project['gold_mwe_count']}, latest_mwe_path=`{project['latest_mwe_path']}`"
        )
    lines.extend(["", "## Gold-bearing segments", ""])
    gold_records = [record for record in records if record.get("gold_mwes")]
    if not gold_records:
        lines.append("No records with gold MWEs were found in this subset.")
    for record in gold_records:
        lines.extend(
            [
                f"### {record['record_id']}",
                "",
                record.get("segment_surface") or "",
                "",
                f"- Gold MWEs: {record.get('gold_mwes') or []}",
                "",
            ]
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_translation_context_map(payload: dict[str, Any] | None, *, target_language: str) -> dict[tuple[int, int], list[dict[str, str]]]:
    context: dict[tuple[int, int], list[dict[str, str]]] = {}
    if not isinstance(payload, dict):
        return context
    pages = payload.get("pages")
    if not isinstance(pages, list):
        return context
    for page_index, page in enumerate(pages, start=1):
        if not isinstance(page, dict):
            continue
        segments = page.get("segments")
        if not isinstance(segments, list):
            continue
        for segment_index, segment in enumerate(segments, start=1):
            if not isinstance(segment, dict):
                continue
            translation = str((segment.get("annotations") or {}).get("translation") or "").strip()
            if translation:
                context[(page_index, segment_index)] = [
                    {
                        "language": str(target_language or ""),
                        "source": "latest_translation_stage",
                        "text": translation,
                    }
                ]
    return context
