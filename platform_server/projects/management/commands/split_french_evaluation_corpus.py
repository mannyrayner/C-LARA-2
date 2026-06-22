from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError


@dataclass(frozen=True, slots=True)
class ProjectSplitAssignment:
    project_id: int
    title: str
    split: str
    stratum: str
    segment_count: int
    latest_segmentation_path: str


@dataclass(frozen=True, slots=True)
class SegmentManifestRecord:
    record_id: str
    split: str
    project_id: int
    project_title: str
    stratum: str
    latest_segmentation_path: str
    page_index: int
    segment_index: int
    surface: str
    token_surfaces: list[str]
    token_count: int
    non_whitespace_token_count: int
    whitespace_only_token_count: int


class Command(BaseCommand):
    help = "Create deterministic development/test manifests from a French corpus summary."

    def add_arguments(self, parser):
        parser.add_argument("--corpus-summary-json", required=True)
        parser.add_argument("--output-dir", required=True)
        parser.add_argument("--seed", default="fr-boundary-first-clitic-compound-v2")
        parser.add_argument("--dev-project-fraction", type=float, default=0.25)
        parser.add_argument("--max-development-segments", type=int, default=250)
        parser.add_argument("--max-test-segments", type=int, default=500)
        parser.add_argument("--development-jsonl", default="development.jsonl")
        parser.add_argument("--test-jsonl", default="test.jsonl")
        parser.add_argument("--manifest-json", default="split_manifest.json")

    def handle(self, *args, **options):
        summary_path = Path(options["corpus_summary_json"]).resolve()
        output_dir = Path(options["output_dir"]).resolve()
        dev_fraction = float(options["dev_project_fraction"])
        if not 0 < dev_fraction < 1:
            raise CommandError("--dev-project-fraction must be between 0 and 1")
        max_dev_segments = int(options["max_development_segments"])
        max_test_segments = int(options["max_test_segments"])
        if max_dev_segments <= 0 or max_test_segments <= 0:
            raise CommandError("segment caps must be positive")
        try:
            payload = json.loads(summary_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise CommandError(f"Could not read corpus summary JSON {summary_path}: {exc}") from exc

        projects = [project for project in payload.get("projects", []) if _usable_project(project)]
        if not projects:
            raise CommandError("Corpus summary contains no usable projects with segmentation_phase_2 artifacts")

        assignments = assign_project_splits(projects, seed=options["seed"], dev_project_fraction=dev_fraction)
        records_by_split = build_segment_records(assignments, seed=options["seed"])
        development_records = cap_records(records_by_split["development"], max_dev_segments, seed=options["seed"], split="development")
        test_records = cap_records(records_by_split["test"], max_test_segments, seed=options["seed"], split="test")

        output_dir.mkdir(parents=True, exist_ok=True)
        dev_path = _resolve_output_path(options["development_jsonl"], output_dir)
        test_path = _resolve_output_path(options["test_jsonl"], output_dir)
        manifest_path = _resolve_output_path(options["manifest_json"], output_dir)
        write_jsonl(dev_path, [asdict(record) for record in development_records])
        write_jsonl(test_path, [asdict(record) for record in test_records])

        manifest = build_manifest(
            source_summary=summary_path,
            assignments=assignments,
            development_records=development_records,
            test_records=test_records,
            seed=options["seed"],
            dev_project_fraction=dev_fraction,
            max_development_segments=max_dev_segments,
            max_test_segments=max_test_segments,
            development_jsonl=dev_path,
            test_jsonl=test_path,
        )
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        self.stdout.write("French evaluation corpus split")
        self.stdout.write(f"Projects: {len(assignments)} total; {manifest['summary']['development_project_count']} development; {manifest['summary']['test_project_count']} test")
        self.stdout.write(f"Segments: {len(development_records)} development; {len(test_records)} test")
        self.stdout.write(f"Development JSONL: {dev_path}")
        self.stdout.write(f"Test JSONL: {test_path}")
        self.stdout.write(f"Manifest: {manifest_path}")


def _usable_project(project: dict[str, Any]) -> bool:
    return bool(project.get("has_segmentation_phase_2") and project.get("latest_segmentation_path") and int(project.get("segment_count") or 0) > 0)


def assign_project_splits(
    projects: list[dict[str, Any]], *, seed: str, dev_project_fraction: float
) -> list[ProjectSplitAssignment]:
    strata = stratify_projects(projects)
    assignments: list[ProjectSplitAssignment] = []
    for stratum, stratum_projects in strata.items():
        ordered = sorted(
            stratum_projects,
            key=lambda project: _stable_hash(seed, "project", str(project.get("project_id")), str(project.get("title"))),
        )
        dev_count = round(len(ordered) * dev_project_fraction)
        if len(ordered) > 1:
            dev_count = min(max(dev_count, 1), len(ordered) - 1)
        else:
            dev_count = 1
        for idx, project in enumerate(ordered):
            split = "development" if idx < dev_count else "test"
            assignments.append(
                ProjectSplitAssignment(
                    project_id=int(project["project_id"]),
                    title=str(project.get("title") or ""),
                    split=split,
                    stratum=stratum,
                    segment_count=int(project.get("segment_count") or 0),
                    latest_segmentation_path=str(project.get("latest_segmentation_path") or ""),
                )
            )
    return sorted(assignments, key=lambda item: (item.split, item.stratum, item.project_id))


def stratify_projects(projects: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    ordered = sorted(projects, key=lambda project: int(project.get("segment_count") or 0))
    if len(ordered) < 3:
        return {"all": ordered}
    strata = {"small": [], "medium": [], "large": []}
    for idx, project in enumerate(ordered):
        bucket = (idx * 3) // len(ordered)
        if bucket == 0:
            strata["small"].append(project)
        elif bucket == 1:
            strata["medium"].append(project)
        else:
            strata["large"].append(project)
    return {key: value for key, value in strata.items() if value}


def build_segment_records(assignments: list[ProjectSplitAssignment], *, seed: str) -> dict[str, list[SegmentManifestRecord]]:
    records = {"development": [], "test": []}
    for assignment in assignments:
        for record in iter_project_segment_records(assignment):
            records[assignment.split].append(record)
    for split in records:
        records[split].sort(
            key=lambda record: _stable_hash(
                seed,
                "segment",
                split,
                str(record.project_id),
                str(record.page_index),
                str(record.segment_index),
                record.surface,
            )
        )
    return records


def iter_project_segment_records(assignment: ProjectSplitAssignment) -> list[SegmentManifestRecord]:
    path = Path(assignment.latest_segmentation_path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    pages = payload.get("pages") if isinstance(payload, dict) else []
    if not isinstance(pages, list):
        return []
    records: list[SegmentManifestRecord] = []
    for page_index, page in enumerate(pages, start=1):
        if not isinstance(page, dict):
            continue
        segments = page.get("segments")
        if not isinstance(segments, list):
            continue
        for segment_index, segment in enumerate(segments, start=1):
            if not isinstance(segment, dict):
                continue
            surface = str(segment.get("surface") or "")
            tokens = segment.get("tokens")
            if not isinstance(tokens, list):
                tokens = []
            token_surfaces = [str(token.get("surface") or "") for token in tokens if isinstance(token, dict)]
            non_ws = sum(1 for token in token_surfaces if token.strip())
            ws_only = sum(1 for token in token_surfaces if not token.strip())
            records.append(
                SegmentManifestRecord(
                    record_id=f"project_{assignment.project_id}:p{page_index}:s{segment_index}",
                    split=assignment.split,
                    project_id=assignment.project_id,
                    project_title=assignment.title,
                    stratum=assignment.stratum,
                    latest_segmentation_path=assignment.latest_segmentation_path,
                    page_index=page_index,
                    segment_index=segment_index,
                    surface=surface,
                    token_surfaces=token_surfaces,
                    token_count=len(token_surfaces),
                    non_whitespace_token_count=non_ws,
                    whitespace_only_token_count=ws_only,
                )
            )
    return records


def cap_records(records: list[SegmentManifestRecord], cap: int, *, seed: str, split: str) -> list[SegmentManifestRecord]:
    if len(records) <= cap:
        selected = list(records)
    else:
        selected = sorted(
            records,
            key=lambda record: _stable_hash(seed, "cap", split, record.record_id, record.surface),
        )[:cap]
    return sorted(selected, key=lambda record: (record.project_id, record.page_index, record.segment_index))


def build_manifest(
    *,
    source_summary: Path,
    assignments: list[ProjectSplitAssignment],
    development_records: list[SegmentManifestRecord],
    test_records: list[SegmentManifestRecord],
    seed: str,
    dev_project_fraction: float,
    max_development_segments: int,
    max_test_segments: int,
    development_jsonl: Path,
    test_jsonl: Path,
) -> dict[str, Any]:
    assignment_dicts = [asdict(assignment) for assignment in assignments]
    dev_project_ids = sorted({assignment.project_id for assignment in assignments if assignment.split == "development"})
    test_project_ids = sorted({assignment.project_id for assignment in assignments if assignment.split == "test"})
    return {
        "source_summary": str(source_summary),
        "seed": seed,
        "dev_project_fraction": dev_project_fraction,
        "max_development_segments": max_development_segments,
        "max_test_segments": max_test_segments,
        "development_jsonl": str(development_jsonl),
        "test_jsonl": str(test_jsonl),
        "summary": {
            "project_count": len(assignments),
            "development_project_count": len(dev_project_ids),
            "test_project_count": len(test_project_ids),
            "development_segment_count": len(development_records),
            "test_segment_count": len(test_records),
            "development_project_ids": dev_project_ids,
            "test_project_ids": test_project_ids,
            "project_level_separation": not bool(set(dev_project_ids) & set(test_project_ids)),
        },
        "hypotheses": [
            "H1: the curated French boundary_first clitic_compound_v2 few-shot set improves segmentation_phase_2 boundary quality relative to the default bundle on held-out French imported-project segments.",
            "H2: an AI boundary-quality evaluator, using curated exemplars and repeated judging, can identify default-vs-candidate wins/losses well enough that targeted human audit confirms the aggregate direction.",
            "H3: deterministic project-level development/test separation reduces accidental overfitting when prompts, examples, and evaluator wording are adjusted on development data.",
        ],
        "human_audit_plan": [
            "Before tuning: inspect the split manifest for project-level separation, genre/size coverage, and obvious malformed or empty-segment overrepresentation.",
            "During development: human-audit a small sample of AI evaluator judgements and all severe disagreement cases from the development split; prompt/evaluator changes may be made only from development evidence.",
            "Before reporting: lock the test manifest, run default-vs-candidate comparison once under the fixed procedure, then human-audit a stratified sample of test wins/losses/ties plus all high-impact anomalies before making claims.",
        ],
        "project_assignments": assignment_dicts,
    }


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as out:
        for record in records:
            out.write(json.dumps(record, ensure_ascii=False) + "\n")


def _resolve_output_path(value: str, output_dir: Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = output_dir / path
    return path.resolve()


def _stable_hash(*parts: str) -> str:
    h = hashlib.sha256()
    for part in parts:
        h.update(part.encode("utf-8"))
        h.update(b"\0")
    return h.hexdigest()
