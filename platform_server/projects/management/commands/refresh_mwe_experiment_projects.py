from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from pipeline.full_pipeline import FullPipelineSpec, run_full_pipeline
from pipeline.stage_artifacts import read_stage_artifact, stage_artifact_path
from projects.models import Project


class Command(BaseCommand):
    help = "Refresh segmentation_phase_2, translation, and MWE artifacts for many projects."

    def add_arguments(self, parser):
        parser.add_argument("--project-ids", default="", help="Comma-separated project ids to refresh.")
        parser.add_argument(
            "--split-manifest",
            default="",
            help="MWE split manifest from extract_mwe_corpus; refreshes all project ids in it unless --splits filters them.",
        )
        parser.add_argument("--splits", default="development,validation,test")
        parser.add_argument("--run-label-prefix", default="mwe_refresh")
        parser.add_argument("--stage-parameters-file", default="")
        parser.add_argument("--start-stage", default="segmentation_phase_2")
        parser.add_argument("--end-stage", default="mwe")
        parser.add_argument("--overwrite", action="store_true")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        stage_parameters = load_stage_parameters(options["stage_parameters_file"])
        project_ids = resolve_project_ids(
            project_ids_text=str(options["project_ids"] or ""),
            split_manifest_text=str(options["split_manifest"] or ""),
            splits=[item.strip() for item in str(options["splits"] or "").split(",") if item.strip()],
        )
        if not project_ids:
            raise CommandError("No projects selected; pass --project-ids or --split-manifest")
        self.stdout.write(f"Selected project ids: {', '.join(str(item) for item in project_ids)}")
        projects = list(Project.objects.filter(id__in=project_ids).order_by("language", "title", "id"))
        found_ids = {project.id for project in projects}
        missing_ids = sorted(set(project_ids) - found_ids)
        if missing_ids:
            raise CommandError(f"Unknown project ids: {', '.join(str(item) for item in missing_ids)}")

        run_label_prefix = str(options["run_label_prefix"] or "mwe_refresh")
        plan = [build_project_plan(project, run_label_prefix=run_label_prefix) for project in projects]
        if options["dry_run"]:
            self.stdout.write(json.dumps({"project_count": len(plan), "projects": plan}, ensure_ascii=False, indent=2))
            return

        for item in plan:
            run_dir = Path(item["run_dir"])
            if run_dir.exists() and not options["overwrite"]:
                raise CommandError(f"run output already exists: {run_dir}; pass --overwrite")
            if run_dir.exists():
                shutil.rmtree(run_dir)

        results = asyncio.run(
            refresh_projects(
                projects,
                run_label_prefix=run_label_prefix,
                start_stage=str(options["start_stage"] or "segmentation_phase_2"),
                end_stage=str(options["end_stage"] or "mwe"),
                stage_parameters=stage_parameters,
                log=self.stdout.write,
            )
        )
        self.stdout.write("MWE refresh complete")
        for result in results:
            self.stdout.write(
                f"project={result['project_id']} language={result['language']} run_dir={result['run_dir']} mwe={result['mwe_path']}"
            )


def load_stage_parameters(path_text: str) -> dict[str, dict[str, Any]]:
    if not path_text:
        return {}
    path = Path(path_text).resolve()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise CommandError(f"Could not read stage parameters {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise CommandError("stage parameter file must contain a JSON object")
    return payload  # type: ignore[return-value]


def resolve_project_ids(*, project_ids_text: str, split_manifest_text: str, splits: list[str]) -> list[int]:
    ids: set[int] = set()
    for item in project_ids_text.split(","):
        item = item.strip()
        if item:
            ids.add(int(item))
    if ids:
        return sorted(ids)
    if split_manifest_text:
        manifest = json.loads(Path(split_manifest_text).resolve().read_text(encoding="utf-8"))
        if "languages_detail" in manifest:
            language_manifests = manifest.get("languages_detail", {}).values()
        else:
            language_manifests = [manifest]
        for language_manifest in language_manifests:
            split_payloads = (language_manifest or {}).get("splits", {})
            for split in splits:
                for project_id in (split_payloads.get(split, {}) or {}).get("project_ids", []):
                    ids.add(int(project_id))
    return sorted(ids)


def build_project_plan(project: Project, *, run_label_prefix: str) -> dict[str, Any]:
    run_label = f"{run_label_prefix}_project_{project.id}"
    run_dir = project.artifact_dir() / "runs" / run_label
    return {
        "project_id": project.id,
        "title": project.title,
        "language": project.language,
        "target_language": project.target_language,
        "source_chars": len(project.source_text or ""),
        "run_dir": str(run_dir),
        "latest_segmentation_phase_1_path": latest_stage_path_text(project, "segmentation_phase_1"),
    }


def latest_stage_payload(project: Project, stage: str) -> tuple[Path | None, dict[str, Any] | None]:
    path_text = latest_stage_path_text(project, stage)
    if not path_text:
        return None, None
    path = Path(path_text)
    try:
        payload = read_stage_artifact(path.parent.parent, stage)
    except Exception:
        return path, None
    return path, payload if isinstance(payload, dict) else None


def latest_stage_path_text(project: Project, stage: str) -> str:
    runs_root = project.artifact_dir() / "runs"
    if not runs_root.exists():
        return ""
    newest_path: Path | None = None
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
            newest_path = candidate
            newest_mtime = mtime
    return str(newest_path) if newest_path else ""


async def refresh_projects(
    projects: list[Project],
    *,
    run_label_prefix: str,
    start_stage: str,
    end_stage: str,
    stage_parameters: dict[str, dict[str, Any]],
    log: Any | None = None,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for project in projects:
        run_label = f"{run_label_prefix}_project_{project.id}"
        run_dir = project.artifact_dir() / "runs" / run_label
        text_obj: dict[str, Any] | None = None
        raw_text: str | None = None
        input_stage_path = ""
        if start_stage == "segmentation_phase_2":
            stage_path, text_obj = latest_stage_payload(project, "segmentation_phase_1")
            if text_obj is None or stage_path is None:
                raise CommandError(
                    f"Project {project.id} has no segmentation_phase_1 artifact; "
                    "refresh-upstream preserves existing page/segment structure and starts at segmentation_phase_2"
                )
            input_stage_path = str(stage_path)
        elif start_stage == "segmentation_phase_1":
            if not project.source_text:
                raise CommandError(f"Project {project.id} has no source_text; cannot refresh from segmentation_phase_1")
            raw_text = project.source_text
        if log:
            log(
                f"Refreshing project={project.id} title={project.title!r} language={project.language} "
                f"start={start_stage} end={end_stage} input={input_stage_path or 'source_text'} run_dir={run_dir}"
            )
        await run_full_pipeline(
            FullPipelineSpec(
                text=raw_text,
                text_obj=text_obj,
                language=project.language,
                target_language=project.target_language,
                output_dir=run_dir,
                op_id=run_label,
                start_stage=start_stage,
                end_stage=end_stage,
                persist_intermediates=True,
                progress_callback=(lambda stage, status, timestamp: log(f"  {project.id}: {stage} {status} {timestamp}")) if log else None,
                stage_parameters=stage_parameters,
                audio_mode="none",
            )
        )
        results.append(
            {
                "project_id": project.id,
                "language": project.language,
                "run_dir": str(run_dir),
                "input_segmentation_phase_1_path": input_stage_path,
                "segmentation_phase_2_path": str(stage_artifact_path(run_dir, "segmentation_phase_2")),
                "translation_path": str(stage_artifact_path(run_dir, "translation")),
                "mwe_path": str(stage_artifact_path(run_dir, "mwe")),
            }
        )
    return results
