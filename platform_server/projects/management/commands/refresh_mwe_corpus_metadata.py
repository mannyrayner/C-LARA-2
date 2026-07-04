from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from projects.management.commands.extract_mwe_corpus import ProjectAssignment, latest_stage_payload, segment_gold_mwes
from projects.models import Project

SPLITS = ("development", "validation", "test")


class Command(BaseCommand):
    help = "Refresh MWE corpus project metadata from each project's latest saved mwe artifact."

    def add_arguments(self, parser):
        parser.add_argument("--corpus-split-dir", required=True)
        parser.add_argument("--languages", default="", help="Comma-separated language codes; defaults to directories present.")
        parser.add_argument("--splits", default=",".join(SPLITS), help="Comma-separated splits to refresh.")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        corpus_split_dir = Path(options["corpus_split_dir"]).resolve()
        if not corpus_split_dir.exists():
            raise CommandError(f"Corpus split directory does not exist: {corpus_split_dir}")
        languages = _resolve_languages(corpus_split_dir, str(options["languages"] or ""))
        splits = [item.strip() for item in str(options["splits"] or "").split(",") if item.strip()]
        invalid_splits = sorted(set(splits) - set(SPLITS))
        if invalid_splits:
            raise CommandError(f"Unknown split(s): {', '.join(invalid_splits)}")
        if not splits:
            raise CommandError("--splits must include at least one split")

        updates: list[dict[str, Any]] = []
        for language in languages:
            language_dir = corpus_split_dir / language
            if not language_dir.is_dir():
                raise CommandError(f"Missing language split directory: {language_dir}")
            language_updates = refresh_language_metadata(language_dir=language_dir, splits=splits, dry_run=options["dry_run"])
            updates.extend({"language": language, **update} for update in language_updates)

        if not options["dry_run"]:
            refresh_multilingual_manifest(corpus_split_dir=corpus_split_dir, languages=languages)
        self.stdout.write(json.dumps({"dry_run": bool(options["dry_run"]), "updated_projects": updates}, ensure_ascii=False, indent=2))


def _resolve_languages(corpus_split_dir: Path, languages_text: str) -> list[str]:
    if languages_text.strip():
        return [item.strip() for item in languages_text.split(",") if item.strip()]
    return sorted(path.name for path in corpus_split_dir.iterdir() if path.is_dir())


def refresh_language_metadata(*, language_dir: Path, splits: list[str], dry_run: bool) -> list[dict[str, Any]]:
    updates: list[dict[str, Any]] = []
    assignments_by_split: dict[str, list[ProjectAssignment]] = {}
    for split in splits:
        path = language_dir / f"{split}_projects.jsonl"
        if not path.exists():
            continue
        assignments = [_assignment_from_json(record) for record in _read_jsonl(path)]
        refreshed: list[ProjectAssignment] = []
        for assignment in assignments:
            new_assignment = refresh_assignment(assignment)
            refreshed.append(new_assignment)
            if new_assignment != assignment:
                updates.append(
                    {
                        "split": split,
                        "project_id": new_assignment.project_id,
                        "old_mwe_count": assignment.mwe_count,
                        "new_mwe_count": new_assignment.mwe_count,
                        "latest_mwe_run": new_assignment.latest_mwe_run,
                        "latest_mwe_path": new_assignment.latest_mwe_path,
                    }
                )
        assignments_by_split[split] = refreshed
        if not dry_run:
            _write_jsonl(path, [asdict(assignment) for assignment in refreshed])
    if not dry_run:
        refresh_language_manifest(language_dir=language_dir, refreshed_assignments=assignments_by_split)
    return updates


def refresh_assignment(assignment: ProjectAssignment) -> ProjectAssignment:
    try:
        project = Project.objects.get(id=assignment.project_id)
    except Project.DoesNotExist:
        return assignment
    run_dir, stage_path, payload = latest_stage_payload(project, "mwe")
    if not run_dir or not stage_path or not isinstance(payload, dict):
        return replace(assignment, latest_mwe_run="", latest_mwe_path="", segment_count=0, token_count=0, mwe_count=0)
    counts = count_mwe_payload(payload)
    return replace(
        assignment,
        source_chars=len(project.source_text or ""),
        segment_count=counts["segment_count"],
        token_count=counts["token_count"],
        mwe_count=counts["mwe_count"],
        latest_mwe_run=run_dir.name,
        latest_mwe_path=str(stage_path),
    )


def count_mwe_payload(payload: dict[str, Any]) -> dict[str, int]:
    segment_count = 0
    token_count = 0
    mwe_count = 0
    pages = payload.get("pages")
    if not isinstance(pages, list):
        return {"segment_count": 0, "token_count": 0, "mwe_count": 0}
    for page in pages:
        if not isinstance(page, dict):
            continue
        segments = page.get("segments")
        if not isinstance(segments, list):
            continue
        for segment in segments:
            if not isinstance(segment, dict):
                continue
            tokens = [token for token in segment.get("tokens") or [] if isinstance(token, dict)]
            content_tokens = [token for token in tokens if str(token.get("surface") or "").strip()]
            if not content_tokens:
                continue
            segment_count += 1
            token_count += len(content_tokens)
            mwe_count += len(segment_gold_mwes(segment))
    return {"segment_count": segment_count, "token_count": token_count, "mwe_count": mwe_count}


def refresh_language_manifest(*, language_dir: Path, refreshed_assignments: dict[str, list[ProjectAssignment]]) -> None:
    path = language_dir / "split_manifest.json"
    if not path.exists():
        return
    manifest = json.loads(path.read_text(encoding="utf-8"))
    for split, assignments in refreshed_assignments.items():
        split_manifest = manifest.get("splits", {}).get(split)
        if isinstance(split_manifest, dict):
            split_manifest["project_count"] = len(assignments)
            split_manifest["project_ids"] = [assignment.project_id for assignment in assignments]
    all_assignments = [assignment for assignments in refreshed_assignments.values() for assignment in assignments]
    if all_assignments:
        existing = {item.get("project_id"): item for item in manifest.get("project_assignments", []) if isinstance(item, dict)}
        for assignment in all_assignments:
            existing[assignment.project_id] = asdict(assignment)
        manifest["project_assignments"] = [existing[key] for key in sorted(existing)]
        manifest["mwe_count"] = sum(int(item.get("mwe_count") or 0) for item in manifest["project_assignments"])
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def refresh_multilingual_manifest(*, corpus_split_dir: Path, languages: list[str]) -> None:
    path = corpus_split_dir / "multilingual_split_manifest.json"
    if not path.exists():
        return
    manifest = json.loads(path.read_text(encoding="utf-8"))
    languages_detail = manifest.setdefault("languages_detail", {})
    for language in languages:
        language_manifest_path = corpus_split_dir / language / "split_manifest.json"
        if language_manifest_path.exists():
            languages_detail[language] = json.loads(language_manifest_path.read_text(encoding="utf-8"))
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _assignment_from_json(record: dict[str, Any]) -> ProjectAssignment:
    return ProjectAssignment(
        project_id=int(record["project_id"]),
        title=str(record["title"]),
        language=str(record["language"]),
        target_language=str(record["target_language"]),
        split=str(record["split"]),
        stratum=str(record["stratum"]),
        source_chars=int(record.get("source_chars") or 0),
        segment_count=int(record.get("segment_count") or 0),
        token_count=int(record.get("token_count") or 0),
        mwe_count=int(record.get("mwe_count") or 0),
        latest_mwe_run=str(record.get("latest_mwe_run") or ""),
        latest_mwe_path=str(record.get("latest_mwe_path") or ""),
    )


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as out:
        for record in records:
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
