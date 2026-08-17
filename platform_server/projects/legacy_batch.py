"""Helpers for final rendering and publication of imported C-LARA projects."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pipeline.compile_html import CompileHTMLSpec, compile_html
from pipeline.stage_artifacts import read_stage_artifact, write_stage_artifact

from .models import LegacyProjectImport, Project


RENDER_INPUT_STAGES = (
    "audio",
    "pinyin",
    "gloss",
    "lemma",
    "mwe",
    "translation",
    "segmentation_phase_2",
    # Legacy imports initially wrote their rich converted annotation payload to
    # every later-stage file, including compile_html.json.  A normal renderer
    # result has no pages list and is rejected below, while the legacy payload
    # remains a valid last-resort rendering input.
    "compile_html",
)


def imported_project_records(*, source_system: str, legacy_ids: set[str] | None = None):
    records = LegacyProjectImport.objects.filter(
        source_system=source_system,
        status=LegacyProjectImport.STATUS_IMPORTED,
        project__isnull=False,
    ).select_related("project")
    if legacy_ids:
        records = records.filter(legacy_project_id__in=legacy_ids)
    return records.order_by("legacy_project_id", "id")


def valid_compiled_index(project: Project) -> Path | None:
    """Return a safe existing compiled entry point, or ``None``."""

    raw = (project.compiled_path or "").strip()
    if not raw:
        return None
    root = project.artifact_dir().resolve()
    candidate = Path(raw)
    candidate = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate if candidate.is_file() and candidate.suffix.lower() == ".html" else None


def inspect_render_input(project: Project) -> tuple[tuple[str, Path, dict[str, Any]] | None, list[str]]:
    """Find a render input and explain why no usable artifact was found."""

    runs_root = project.artifact_dir().resolve() / "runs"
    if not runs_root.is_dir():
        return None, [f"runs directory does not exist: {runs_root}"]
    candidates: list[tuple[float, int, str, Path]] = []
    run_count = 0
    for run_dir in runs_root.iterdir():
        if not run_dir.is_dir():
            continue
        run_count += 1
        for priority, stage in enumerate(RENDER_INPUT_STAGES):
            path = run_dir / "stages" / f"{stage}.json"
            if path.is_file():
                candidates.append((path.stat().st_mtime, -priority, stage, run_dir))
    if not candidates:
        searched = ", ".join(f"{stage}.json" for stage in RENDER_INPUT_STAGES)
        return None, [
            f"found {run_count} run director{'y' if run_count == 1 else 'ies'} below {runs_root}",
            f"none contained a stages artifact named: {searched}",
        ]
    rejected: list[str] = []
    for _mtime, _priority, stage, run_dir in sorted(
        candidates, key=lambda row: (row[0], row[1], row[2], str(row[3])), reverse=True
    ):
        try:
            payload = read_stage_artifact(run_dir, stage)
        except Exception as exc:
            rejected.append(f"{run_dir.name}/stages/{stage}.json is unreadable: {exc}")
            continue
        if not isinstance(payload, dict):
            rejected.append(f"{run_dir.name}/stages/{stage}.json is not a JSON object")
            continue
        if not isinstance(payload.get("pages"), list):
            rejected.append(f"{run_dir.name}/stages/{stage}.json has no pages list")
            continue
        if not payload["pages"]:
            rejected.append(f"{run_dir.name}/stages/{stage}.json has an empty pages list")
            continue
        # Image availability is not a rendering prerequisite; images are
        # optional annotations within a page payload.
        return (stage, run_dir, payload), []
    return None, rejected


def latest_render_input(project: Project) -> tuple[str, Path, dict[str, Any]] | None:
    """Find the newest readable, structurally valid final-stage rendering input."""

    render_input, _diagnostics = inspect_render_input(project)
    return render_input


def render_project_html(project: Project) -> tuple[Path, str, Path]:
    """Run only ``compile_html`` from an existing imported annotation artifact."""

    render_input, diagnostics = inspect_render_input(project)
    if render_input is None:
        raise ValueError("no readable upstream stage artifact with a pages list: " + "; ".join(diagnostics))
    stage, source_run, payload = render_input
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    output_dir = project.artifact_dir().resolve() / "runs" / f"run_legacy_render_{timestamp}"
    result = compile_html(CompileHTMLSpec(text=payload, output_dir=output_dir, title=project.title))
    html_path = Path(str(result.get("html_path") or "")).resolve()
    if not html_path.is_file():
        raise RuntimeError("HTML renderer returned no existing entry point")
    write_stage_artifact(
        output_dir,
        "compile_html",
        {
            **result,
            "legacy_batch_render": {
                "input_stage": stage,
                "input_run": source_run.name,
            },
        },
    )
    project.compiled_path = html_path.relative_to(project.artifact_dir().resolve()).as_posix()
    project.artifact_root = str(project.artifact_dir().resolve())
    project.save(update_fields=["compiled_path", "artifact_root", "updated_at"])
    return html_path, stage, source_run


def append_jsonl(path: Path | None, row: dict[str, Any]) -> None:
    if path is None:
        return
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def prepare_report(path_value: str | None) -> Path | None:
    if not path_value:
        return None
    path = Path(path_value).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")
    return path
