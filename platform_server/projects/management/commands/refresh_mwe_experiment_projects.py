from __future__ import annotations

import asyncio
import json
import shutil
import traceback
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from pipeline.full_pipeline import PIPELINE_ORDER, FullPipelineSpec, run_full_pipeline
from pipeline.stage_artifacts import read_stage_artifact, stage_artifact_path
from projects.models import Project


class Command(BaseCommand):
    help = "Refresh segmentation_phase_2 through gloss artifacts for many projects."

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
        parser.add_argument("--end-stage", default="gloss")
        parser.add_argument("--overwrite", action="store_true")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--resume-from-project-id", type=int, default=0)
        parser.add_argument("--max-project-retries", type=int, default=2)
        parser.add_argument("--failed-projects-jsonl", default="")
        parser.add_argument("--fail-fast", action="store_true")

    def handle(self, *args, **options):
        stage_parameters = load_stage_parameters(options["stage_parameters_file"])
        project_ids = resolve_project_ids(
            project_ids_text=str(options["project_ids"] or ""),
            split_manifest_text=str(options["split_manifest"] or ""),
            splits=[item.strip() for item in str(options["splits"] or "").split(",") if item.strip()],
        )
        if not project_ids:
            raise CommandError("No projects selected; pass --project-ids or --split-manifest")
        resume_from_project_id = int(options.get("resume_from_project_id") or 0)
        if resume_from_project_id:
            project_ids = [project_id for project_id in project_ids if project_id >= resume_from_project_id]
        if not project_ids:
            raise CommandError("No projects selected after applying --resume-from-project-id")
        self.stdout.write(f"Selected project ids: {', '.join(str(item) for item in project_ids)}")
        projects = list(Project.objects.filter(id__in=project_ids).order_by("id"))
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

        results, failures = asyncio.run(
            refresh_projects(
                projects,
                run_label_prefix=run_label_prefix,
                start_stage=str(options["start_stage"] or "segmentation_phase_2"),
                end_stage=str(options["end_stage"] or "gloss"),
                stage_parameters=stage_parameters,
                max_project_retries=int(options.get("max_project_retries") or 0),
                fail_fast=bool(options.get("fail_fast")),
                log=self.stdout.write,
            )
        )
        failed_projects_path = str(options.get("failed_projects_jsonl") or "")
        if failures and failed_projects_path:
            write_jsonl(Path(failed_projects_path), failures)
            self.stdout.write(f"Failed projects: {failed_projects_path}")
        self.stdout.write("MWE refresh complete" if not failures else "MWE refresh complete with failures")
        for result in results:
            self.stdout.write(
                f"project={result['project_id']} language={result['language']} run_dir={result['run_dir']} "
                f"mwe={result['mwe_path']} lemma={result['lemma_path']} gloss={result['gloss_path']}"
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
    max_project_retries: int = 0,
    fail_fast: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    results: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
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
                    "refresh-annotations preserves existing page/segment structure and starts at segmentation_phase_2"
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
        attempts_allowed = max(1, max_project_retries + 1)
        for attempt in range(1, attempts_allowed + 1):
            attempt_state = build_attempt_state(
                run_dir=run_dir,
                configured_start_stage=start_stage,
                end_stage=end_stage,
                original_raw_text=raw_text,
                original_text_obj=text_obj,
                original_input_stage_path=input_stage_path,
            )
            if attempt_state["already_complete"]:
                if log:
                    log(f"  {project.id}: all requested stages already complete; skipping remaining retries")
                break
            if log and attempt_state.get("resume_from_stage"):
                log(
                    f"  {project.id}: resuming after {attempt_state['resume_from_stage']} "
                    f"at {attempt_state['start_stage']}"
                )
            try:
                await run_full_pipeline(
                    FullPipelineSpec(
                        text=attempt_state["raw_text"],
                        text_obj=attempt_state["text_obj"],
                        language=project.language,
                        target_language=project.target_language,
                        output_dir=run_dir,
                        op_id=run_label,
                        start_stage=str(attempt_state["start_stage"]),
                        end_stage=end_stage,
                        persist_intermediates=True,
                        progress_callback=(
                            (lambda stage, status, timestamp: log(f"  {project.id}: {stage} {status} {timestamp}"))
                            if log
                            else None
                        ),
                        stage_parameters=stage_parameters,
                        audio_mode="none",
                    )
                )
                break
            except Exception as exc:
                failure = build_failure_record(
                    project=project,
                    run_label=run_label,
                    run_dir=run_dir,
                    input_stage_path=input_stage_path,
                    attempt_start_stage=str(attempt_state["start_stage"]),
                    attempt_input_stage_path=str(attempt_state.get("input_stage_path") or ""),
                    resume_from_stage=str(attempt_state.get("resume_from_stage") or ""),
                    attempt=attempt,
                    attempts_allowed=attempts_allowed,
                    exc=exc,
                )
                if log:
                    log(f"  {project.id}: attempt {attempt}/{attempts_allowed} failed: {exc}")
                if attempt >= attempts_allowed:
                    failures.append(failure)
                    if fail_fast:
                        raise
                elif log:
                    log(f"  {project.id}: retrying from latest completed stage")
        else:
            continue
        if failures and failures[-1].get("project_id") == project.id:
            continue
        results.append(
            {
                "project_id": project.id,
                "language": project.language,
                "run_dir": str(run_dir),
                "input_segmentation_phase_1_path": input_stage_path,
                "segmentation_phase_2_path": str(stage_artifact_path(run_dir, "segmentation_phase_2")),
                "translation_path": str(stage_artifact_path(run_dir, "translation")),
                "mwe_path": str(stage_artifact_path(run_dir, "mwe")),
                "lemma_path": str(stage_artifact_path(run_dir, "lemma")),
                "gloss_path": str(stage_artifact_path(run_dir, "gloss")),
            }
        )
    return results, failures


def build_attempt_state(
    *,
    run_dir: Path,
    configured_start_stage: str,
    end_stage: str,
    original_raw_text: str | None,
    original_text_obj: dict[str, Any] | None,
    original_input_stage_path: str,
) -> dict[str, Any]:
    """Return the most advanced safe input for the next project retry attempt.

    The refresh target persists every completed stage in ``run_dir``. If an API
    timeout occurs in a downstream phase, retry from the stage after the newest
    readable artifact instead of repeating already-completed phases.
    """

    stages = stage_slice(configured_start_stage, end_stage)
    for completed_stage in reversed(stages):
        payload = read_stage_artifact(run_dir, completed_stage, default=None)
        if payload is None:
            continue
        if completed_stage == end_stage:
            return {
                "already_complete": True,
                "start_stage": end_stage,
                "raw_text": None,
                "text_obj": payload,
                "input_stage_path": str(stage_artifact_path(run_dir, completed_stage)),
                "resume_from_stage": completed_stage,
            }
        next_stage = PIPELINE_ORDER[PIPELINE_ORDER.index(completed_stage) + 1]
        return {
            "already_complete": False,
            "start_stage": next_stage,
            "raw_text": None,
            "text_obj": payload,
            "input_stage_path": str(stage_artifact_path(run_dir, completed_stage)),
            "resume_from_stage": completed_stage,
        }
    return {
        "already_complete": False,
        "start_stage": configured_start_stage,
        "raw_text": original_raw_text,
        "text_obj": original_text_obj,
        "input_stage_path": original_input_stage_path or "source_text",
        "resume_from_stage": "",
    }


def stage_slice(start_stage: str, end_stage: str) -> list[str]:
    start_index = PIPELINE_ORDER.index(start_stage)
    end_index = PIPELINE_ORDER.index(end_stage)
    if start_index > end_index:
        raise ValueError("start_stage must come before end_stage")
    return PIPELINE_ORDER[start_index : end_index + 1]


def build_failure_record(
    *,
    project: Project,
    run_label: str,
    run_dir: Path,
    input_stage_path: str,
    attempt_start_stage: str,
    attempt_input_stage_path: str,
    resume_from_stage: str,
    attempt: int,
    attempts_allowed: int,
    exc: Exception,
) -> dict[str, Any]:
    return {
        "project_id": project.id,
        "title": project.title,
        "language": project.language,
        "target_language": project.target_language,
        "run_label": run_label,
        "run_dir": str(run_dir),
        "input_segmentation_phase_1_path": input_stage_path,
        "attempt_start_stage": attempt_start_stage,
        "attempt_input_stage_path": attempt_input_stage_path,
        "resume_from_stage": resume_from_stage,
        "attempt": attempt,
        "attempts_allowed": attempts_allowed,
        "error_type": type(exc).__name__,
        "error": str(exc),
        "traceback": traceback.format_exc(),
    }


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as out:
        for record in records:
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
