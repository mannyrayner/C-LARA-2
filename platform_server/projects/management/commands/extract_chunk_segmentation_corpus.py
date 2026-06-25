from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from pipeline.stage_artifacts import read_stage_artifact, stage_artifact_path
from projects.models import Project

NONSPACE_RE = re.compile(r"\S+", flags=re.UNICODE)
SPLITS = ("development", "validation", "test")


@dataclass(frozen=True, slots=True)
class ProjectAssignment:
    project_id: int
    title: str
    language: str
    split: str
    stratum: str
    chunk_count: int
    latest_segmentation_run: str
    latest_segmentation_path: str


@dataclass(frozen=True, slots=True)
class ChunkCorpusRecord:
    record_id: str
    split: str
    language: str
    project_id: int
    project_title: str
    stratum: str
    latest_segmentation_path: str
    page_index: int
    segment_index: int
    chunk_index: int
    segment_surface: str
    chunk_surface: str
    gold_parts: list[str]
    gold_segments_display: str


class Command(BaseCommand):
    help = "Extract whitespace-chunk segmentation records and create deterministic dev/validation/test splits."

    def add_arguments(self, parser):
        parser.add_argument("--username", default="mannyrayner")
        parser.add_argument("--languages", default="fr,de,en", help="Comma-separated source language codes.")
        parser.add_argument("--language-match", choices=("exact", "prefix"), default="exact")
        parser.add_argument("--output-dir", required=True)
        parser.add_argument("--seed", default="chunk-decomposition-v1")
        parser.add_argument("--development-project-fraction", type=float, default=0.5)
        parser.add_argument("--validation-project-fraction", type=float, default=0.25)
        parser.add_argument("--max-development-chunks", type=int, default=800)
        parser.add_argument("--max-validation-chunks", type=int, default=400)
        parser.add_argument("--max-test-chunks", type=int, default=800)
        parser.add_argument("--overwrite", action="store_true")

    def handle(self, *args, **options):
        username = str(options["username"] or "").strip()
        languages = [item.strip().lower() for item in str(options["languages"] or "").split(",") if item.strip()]
        if not username:
            raise CommandError("--username must not be empty")
        if not languages:
            raise CommandError("--languages must contain at least one language code")
        dev_fraction = float(options["development_project_fraction"])
        validation_fraction = float(options["validation_project_fraction"])
        if dev_fraction <= 0 or validation_fraction < 0 or dev_fraction + validation_fraction >= 1:
            raise CommandError("development/validation project fractions must be positive and leave room for test")
        caps = {
            "development": int(options["max_development_chunks"]),
            "validation": int(options["max_validation_chunks"]),
            "test": int(options["max_test_chunks"]),
        }
        if any(value <= 0 for value in caps.values()):
            raise CommandError("chunk caps must be positive")

        user_model = get_user_model()
        try:
            user = user_model.objects.get(username=username)
        except user_model.DoesNotExist as exc:
            raise CommandError(f"No user found with username {username!r}") from exc

        output_dir = Path(options["output_dir"]).resolve()
        if output_dir.exists() and any(output_dir.iterdir()) and not options["overwrite"]:
            raise CommandError(f"output directory already exists and is not empty: {output_dir}; pass --overwrite")
        output_dir.mkdir(parents=True, exist_ok=True)

        manifest: dict[str, Any] = {
            "schema_version": 1,
            "username": username,
            "languages": languages,
            "language_match": options["language_match"],
            "seed": options["seed"],
            "development_project_fraction": dev_fraction,
            "validation_project_fraction": validation_fraction,
            "chunk_caps": caps,
            "languages_detail": {},
        }
        for language in languages:
            projects = _language_projects(user=user, language=language, language_match=options["language_match"])
            project_payloads = [payload for project in projects if (payload := summarize_project_chunks(project, language))]
            assignments = assign_project_splits(
                project_payloads,
                seed=options["seed"],
                development_project_fraction=dev_fraction,
                validation_project_fraction=validation_fraction,
            )
            records_by_split = build_chunk_records(assignments)
            capped_records = {
                split: cap_records(records_by_split[split], caps[split], seed=options["seed"], split=split)
                for split in SPLITS
            }
            language_dir = output_dir / language
            language_dir.mkdir(parents=True, exist_ok=True)
            for split, records in capped_records.items():
                write_jsonl(language_dir / f"{split}.jsonl", [asdict(record) for record in records])
            language_manifest = build_language_manifest(
                language=language,
                assignments=assignments,
                capped_records=capped_records,
                output_dir=language_dir,
            )
            (language_dir / "split_manifest.json").write_text(
                json.dumps(language_manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            manifest["languages_detail"][language] = language_manifest
            self.stdout.write(
                f"{language}: {len(assignments)} projects; "
                + "; ".join(f"{split}={len(capped_records[split])} chunks" for split in SPLITS)
            )

        manifest_path = output_dir / "multilingual_split_manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.stdout.write(f"Manifest: {manifest_path}")


def _language_projects(*, user, language: str, language_match: str):
    projects = Project.objects.filter(owner=user).order_by("title", "id")
    if language_match == "exact":
        return projects.filter(language__iexact=language)
    return projects.filter(language__istartswith=language)


def summarize_project_chunks(project: Project, language: str) -> dict[str, Any] | None:
    run_dir, stage_path, payload = latest_stage_payload(project, "segmentation_phase_2")
    if not run_dir or not stage_path or not isinstance(payload, dict):
        return None
    pages = payload.get("pages")
    if not isinstance(pages, list):
        return None
    records = list(iter_project_chunk_records(project=project, language=language, run_dir=run_dir, stage_path=stage_path, pages=pages))
    if not records:
        return None
    return {
        "project_id": project.id,
        "title": project.title,
        "language": language,
        "chunk_count": len(records),
        "latest_segmentation_run": run_dir.name,
        "latest_segmentation_path": str(stage_path),
        "records": records,
    }


def latest_stage_payload(project: Project, stage: str) -> tuple[Path | None, Path | None, dict[str, Any] | None]:
    runs_root = project.artifact_dir() / "runs"
    if not runs_root.exists():
        return None, None, None
    newest: tuple[Path, Path] | None = None
    newest_mtime = float("-inf")
    for run_dir in runs_root.iterdir():
        if not run_dir.is_dir():
            continue
        candidate = stage_artifact_path(run_dir, stage)
        if not candidate.exists():
            continue
        try:
            mtime = candidate.stat().st_mtime
        except OSError:
            continue
        if mtime > newest_mtime:
            newest = (run_dir, candidate)
            newest_mtime = mtime
    if newest is None:
        return None, None, None
    run_dir, path = newest
    try:
        payload = read_stage_artifact(run_dir, stage)
    except Exception:
        return run_dir, path, None
    return run_dir, path, payload if isinstance(payload, dict) else None


def iter_project_chunk_records(*, project: Project, language: str, run_dir: Path, stage_path: Path, pages: list[Any]):
    del run_dir
    for page_index, page in enumerate(pages, start=1):
        if not isinstance(page, dict):
            continue
        segments = page.get("segments")
        if not isinstance(segments, list):
            continue
        for segment_index, segment in enumerate(segments, start=1):
            if not isinstance(segment, dict):
                continue
            segment_surface = str(segment.get("surface") or "")
            tokens = segment.get("tokens")
            token_surfaces = [str(token.get("surface") or "") for token in tokens if isinstance(token, dict)] if isinstance(tokens, list) else []
            chunks = chunks_from_token_surfaces(token_surfaces) if token_surfaces else [[match.group(0)] for match in NONSPACE_RE.finditer(segment_surface)]
            for chunk_index, gold_parts in enumerate(chunks, start=1):
                chunk_surface = "".join(gold_parts)
                if not chunk_surface.strip():
                    continue
                yield ChunkCorpusRecord(
                    record_id=f"{language}:project_{project.id}:p{page_index}:s{segment_index}:c{chunk_index}",
                    split="",
                    language=language,
                    project_id=project.id,
                    project_title=project.title,
                    stratum="",
                    latest_segmentation_path=str(stage_path),
                    page_index=page_index,
                    segment_index=segment_index,
                    chunk_index=chunk_index,
                    segment_surface=segment_surface,
                    chunk_surface=chunk_surface,
                    gold_parts=gold_parts,
                    gold_segments_display="|".join(gold_parts),
                )


def chunks_from_token_surfaces(token_surfaces: list[str]) -> list[list[str]]:
    chunks: list[list[str]] = []
    current: list[str] = []
    for token_surface in token_surfaces:
        cursor = 0
        for match in NONSPACE_RE.finditer(token_surface):
            if token_surface[cursor:match.start()] and current:
                chunks.append(current)
                current = []
            current.append(match.group(0))
            cursor = match.end()
        if token_surface[cursor:] and current:
            chunks.append(current)
            current = []
    if current:
        chunks.append(current)
    return chunks


def assign_project_splits(
    projects: list[dict[str, Any]], *, seed: str, development_project_fraction: float, validation_project_fraction: float
) -> list[ProjectAssignment]:
    assignments: list[ProjectAssignment] = []
    for stratum, stratum_projects in stratify_projects(projects).items():
        ordered = sorted(
            stratum_projects,
            key=lambda project: _stable_hash(seed, str(project["language"]), "project", str(project["project_id"]), str(project["title"])),
        )
        split_names = split_names_for_count(
            len(ordered),
            development_project_fraction=development_project_fraction,
            validation_project_fraction=validation_project_fraction,
        )
        for project, split in zip(ordered, split_names, strict=True):
            assignments.append(
                ProjectAssignment(
                    project_id=int(project["project_id"]),
                    title=str(project["title"]),
                    language=str(project["language"]),
                    split=split,
                    stratum=stratum,
                    chunk_count=int(project["chunk_count"]),
                    latest_segmentation_run=str(project["latest_segmentation_run"]),
                    latest_segmentation_path=str(project["latest_segmentation_path"]),
                )
            )
    return sorted(assignments, key=lambda item: (item.language, item.split, item.stratum, item.project_id))


def split_names_for_count(count: int, *, development_project_fraction: float, validation_project_fraction: float) -> list[str]:
    if count <= 0:
        return []
    if count == 1:
        return ["development"]
    dev_count = max(1, round(count * development_project_fraction))
    validation_count = max(1, round(count * validation_project_fraction)) if count >= 3 else 0
    if dev_count + validation_count >= count:
        overflow = dev_count + validation_count - (count - 1)
        if validation_count >= overflow:
            validation_count -= overflow
        else:
            dev_count = max(1, dev_count - (overflow - validation_count))
            validation_count = 0
    test_count = count - dev_count - validation_count
    return ["development"] * dev_count + ["validation"] * validation_count + ["test"] * test_count


def stratify_projects(projects: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    ordered = sorted(projects, key=lambda project: int(project.get("chunk_count") or 0))
    if len(ordered) < 3:
        return {"all": ordered}
    strata = {"small": [], "medium": [], "large": []}
    for idx, project in enumerate(ordered):
        bucket = (idx * 3) // len(ordered)
        strata[("small", "medium", "large")[bucket]].append(project)
    return {key: value for key, value in strata.items() if value}


def build_chunk_records(assignments: list[ProjectAssignment]) -> dict[str, list[ChunkCorpusRecord]]:
    records = {split: [] for split in SPLITS}
    assignment_by_project = {assignment.project_id: assignment for assignment in assignments}
    for assignment in assignments:
        path = Path(assignment.latest_segmentation_path)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        pages = payload.get("pages") if isinstance(payload, dict) else []
        if not isinstance(pages, list):
            continue
        project_stub = Project(id=assignment.project_id, title=assignment.title, language=assignment.language)
        for record in iter_project_chunk_records(
            project=project_stub,
            language=assignment.language,
            run_dir=Path(assignment.latest_segmentation_run),
            stage_path=path,
            pages=pages,
        ):
            owning_assignment = assignment_by_project.get(record.project_id)
            if owning_assignment is None:
                continue
            records[assignment.split].append(
                ChunkCorpusRecord(
                    **{**asdict(record), "split": assignment.split, "stratum": assignment.stratum}
                )
            )
    return records


def cap_records(records: list[ChunkCorpusRecord], cap: int, *, seed: str, split: str) -> list[ChunkCorpusRecord]:
    if len(records) > cap:
        records = sorted(records, key=lambda record: _stable_hash(seed, "cap", split, record.record_id, record.chunk_surface))[:cap]
    return sorted(records, key=lambda record: (record.language, record.project_id, record.page_index, record.segment_index, record.chunk_index))


def build_language_manifest(
    *, language: str, assignments: list[ProjectAssignment], capped_records: dict[str, list[ChunkCorpusRecord]], output_dir: Path
) -> dict[str, Any]:
    split_project_ids = {split: sorted({item.project_id for item in assignments if item.split == split}) for split in SPLITS}
    overlaps = [
        set(split_project_ids["development"]) & set(split_project_ids["validation"]),
        set(split_project_ids["development"]) & set(split_project_ids["test"]),
        set(split_project_ids["validation"]) & set(split_project_ids["test"]),
    ]
    return {
        "language": language,
        "project_count": len(assignments),
        "project_assignments": [asdict(item) for item in assignments],
        "splits": {
            split: {
                "jsonl": str(output_dir / f"{split}.jsonl"),
                "project_ids": split_project_ids[split],
                "project_count": len(split_project_ids[split]),
                "chunk_count": len(capped_records[split]),
            }
            for split in SPLITS
        },
        "project_level_separation": not any(overlaps),
    }


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as out:
        for record in records:
            out.write(json.dumps(record, ensure_ascii=False) + "\n")


def _stable_hash(*parts: str) -> str:
    h = hashlib.sha256()
    for part in parts:
        h.update(part.encode("utf-8"))
        h.update(b"\0")
    return h.hexdigest()
