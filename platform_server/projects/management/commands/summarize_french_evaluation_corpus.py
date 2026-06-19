from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from pipeline.stage_artifacts import read_stage_artifact, stage_artifact_path
from projects.models import Project


WHITESPACE_RE = re.compile(r"\s+", flags=re.UNICODE)


@dataclass(slots=True)
class ProjectCorpusStats:
    project_id: int
    title: str
    owner: str
    language: str
    target_language: str
    latest_segmentation_run: str
    latest_segmentation_path: str
    has_segmentation_phase_2: bool
    page_count: int
    segment_count: int
    token_count: int
    non_whitespace_token_count: int
    whitespace_only_token_count: int
    token_surface_chars_including_whitespace: int
    token_surface_chars_excluding_whitespace: int
    segment_surface_chars_including_whitespace: int
    segment_surface_chars_excluding_whitespace: int
    project_source_chars_including_whitespace: int
    project_source_chars_excluding_whitespace: int
    average_tokens_per_segment: float
    average_non_whitespace_tokens_per_segment: float
    max_tokens_in_segment: int
    max_non_whitespace_tokens_in_segment: int
    segments_with_no_tokens: int
    tokens_with_empty_surface: int
    tokens_with_leading_or_trailing_whitespace: int
    punctuation_only_token_count: int


class Command(BaseCommand):
    help = "Summarize imported French projects for segmentation_phase_2 evaluation planning."

    def add_arguments(self, parser):
        parser.add_argument("--username", default="mannyrayner")
        parser.add_argument("--language", default="fr")
        parser.add_argument(
            "--language-match",
            choices=("exact", "prefix"),
            default="exact",
            help="Use exact language-code matching by default; prefix also matches values like fr-CA.",
        )
        parser.add_argument("--output-dir", default="")
        parser.add_argument("--json", dest="json_path", default="")
        parser.add_argument("--csv", dest="csv_path", default="")
        parser.add_argument("--markdown", dest="markdown_path", default="")

    def handle(self, *args, **options):
        username = str(options["username"] or "").strip()
        language = str(options["language"] or "").strip().lower()
        if not username:
            raise CommandError("--username must not be empty")
        if not language:
            raise CommandError("--language must not be empty")

        user_model = get_user_model()
        try:
            user = user_model.objects.get(username=username)
        except user_model.DoesNotExist as exc:
            raise CommandError(f"No user found with username {username!r}") from exc

        projects = Project.objects.filter(owner=user).order_by("title", "id")
        if options["language_match"] == "exact":
            projects = projects.filter(language__iexact=language)
        else:
            projects = projects.filter(language__istartswith=language)

        project_stats = [summarize_project(project) for project in projects]
        summary = build_summary(project_stats, username=username, language=language, language_match=options["language_match"])
        payload = {"summary": summary, "projects": [asdict(item) for item in project_stats]}

        output_dir = Path(options["output_dir"]).resolve() if options["output_dir"] else None
        json_path = _resolve_output_path(options["json_path"], output_dir)
        csv_path = _resolve_output_path(options["csv_path"], output_dir)
        markdown_path = _resolve_output_path(options["markdown_path"], output_dir)

        if output_dir:
            output_dir.mkdir(parents=True, exist_ok=True)
        if json_path:
            json_path.parent.mkdir(parents=True, exist_ok=True)
            json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if csv_path:
            csv_path.parent.mkdir(parents=True, exist_ok=True)
            write_csv(csv_path, project_stats)
        if markdown_path:
            markdown_path.parent.mkdir(parents=True, exist_ok=True)
            markdown_path.write_text(render_markdown(payload), encoding="utf-8")

        self.stdout.write(render_console_summary(payload))
        if json_path:
            self.stdout.write(f"JSON: {json_path}")
        if csv_path:
            self.stdout.write(f"CSV: {csv_path}")
        if markdown_path:
            self.stdout.write(f"Markdown: {markdown_path}")


def _resolve_output_path(value: str, output_dir: Path | None) -> Path | None:
    if value:
        path = Path(value)
        if not path.is_absolute() and output_dir:
            path = output_dir / path
        return path.resolve()
    return None


def summarize_project(project: Project) -> ProjectCorpusStats:
    run_dir, stage_path, payload = latest_stage_payload(project, "segmentation_phase_2")
    pages = payload.get("pages") if isinstance(payload, dict) else []
    if not isinstance(pages, list):
        pages = []

    page_count = len([page for page in pages if isinstance(page, dict)])
    segment_count = 0
    token_count = 0
    non_ws_token_count = 0
    ws_only_token_count = 0
    token_chars_ws = 0
    token_chars_no_ws = 0
    segment_chars_ws = 0
    segment_chars_no_ws = 0
    max_tokens = 0
    max_non_ws_tokens = 0
    empty_segments = 0
    empty_token_surfaces = 0
    boundary_ws_tokens = 0
    punctuation_only_tokens = 0

    for page in pages:
        if not isinstance(page, dict):
            continue
        segments = page.get("segments")
        if not isinstance(segments, list):
            continue
        for segment in segments:
            if not isinstance(segment, dict):
                continue
            segment_count += 1
            segment_surface = str(segment.get("surface") or "")
            segment_chars_ws += len(segment_surface)
            segment_chars_no_ws += len(_without_whitespace(segment_surface))
            tokens = segment.get("tokens")
            if not isinstance(tokens, list):
                tokens = []
            if not tokens:
                empty_segments += 1
            segment_tokens = 0
            segment_non_ws_tokens = 0
            for token in tokens:
                if not isinstance(token, dict):
                    continue
                surface = str(token.get("surface") or "")
                token_count += 1
                segment_tokens += 1
                token_chars_ws += len(surface)
                token_chars_no_ws += len(_without_whitespace(surface))
                if surface == "":
                    empty_token_surfaces += 1
                if surface != surface.strip():
                    boundary_ws_tokens += 1
                if not surface.strip():
                    ws_only_token_count += 1
                else:
                    non_ws_token_count += 1
                    segment_non_ws_tokens += 1
                    if _is_punctuation_only(surface):
                        punctuation_only_tokens += 1
            max_tokens = max(max_tokens, segment_tokens)
            max_non_ws_tokens = max(max_non_ws_tokens, segment_non_ws_tokens)

    source_text = project.source_text or ""
    return ProjectCorpusStats(
        project_id=project.id,
        title=project.title,
        owner=project.owner.username,
        language=project.language,
        target_language=project.target_language,
        latest_segmentation_run=run_dir.name if run_dir else "",
        latest_segmentation_path=str(stage_path) if stage_path else "",
        has_segmentation_phase_2=payload is not None,
        page_count=page_count,
        segment_count=segment_count,
        token_count=token_count,
        non_whitespace_token_count=non_ws_token_count,
        whitespace_only_token_count=ws_only_token_count,
        token_surface_chars_including_whitespace=token_chars_ws,
        token_surface_chars_excluding_whitespace=token_chars_no_ws,
        segment_surface_chars_including_whitespace=segment_chars_ws,
        segment_surface_chars_excluding_whitespace=segment_chars_no_ws,
        project_source_chars_including_whitespace=len(source_text),
        project_source_chars_excluding_whitespace=len(_without_whitespace(source_text)),
        average_tokens_per_segment=_safe_average(token_count, segment_count),
        average_non_whitespace_tokens_per_segment=_safe_average(non_ws_token_count, segment_count),
        max_tokens_in_segment=max_tokens,
        max_non_whitespace_tokens_in_segment=max_non_ws_tokens,
        segments_with_no_tokens=empty_segments,
        tokens_with_empty_surface=empty_token_surfaces,
        tokens_with_leading_or_trailing_whitespace=boundary_ws_tokens,
        punctuation_only_token_count=punctuation_only_tokens,
    )


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


def build_summary(projects: list[ProjectCorpusStats], *, username: str, language: str, language_match: str) -> dict[str, Any]:
    projects_with_seg2 = [project for project in projects if project.has_segmentation_phase_2]
    return {
        "username": username,
        "language": language,
        "language_match": language_match,
        "project_count": len(projects),
        "projects_with_segmentation_phase_2": len(projects_with_seg2),
        "projects_without_segmentation_phase_2": len(projects) - len(projects_with_seg2),
        "page_count": sum(project.page_count for project in projects),
        "segment_count": sum(project.segment_count for project in projects),
        "token_count": sum(project.token_count for project in projects),
        "non_whitespace_token_count": sum(project.non_whitespace_token_count for project in projects),
        "whitespace_only_token_count": sum(project.whitespace_only_token_count for project in projects),
        "token_surface_chars_including_whitespace": sum(project.token_surface_chars_including_whitespace for project in projects),
        "token_surface_chars_excluding_whitespace": sum(project.token_surface_chars_excluding_whitespace for project in projects),
        "segment_surface_chars_including_whitespace": sum(project.segment_surface_chars_including_whitespace for project in projects),
        "segment_surface_chars_excluding_whitespace": sum(project.segment_surface_chars_excluding_whitespace for project in projects),
        "segments_with_no_tokens": sum(project.segments_with_no_tokens for project in projects),
        "tokens_with_empty_surface": sum(project.tokens_with_empty_surface for project in projects),
        "tokens_with_leading_or_trailing_whitespace": sum(project.tokens_with_leading_or_trailing_whitespace for project in projects),
        "punctuation_only_token_count": sum(project.punctuation_only_token_count for project in projects),
    }


def write_csv(path: Path, projects: list[ProjectCorpusStats]) -> None:
    rows = [asdict(item) for item in projects]
    fieldnames = list(rows[0].keys()) if rows else [field.name for field in ProjectCorpusStats.__dataclass_fields__.values()]
    with path.open("w", encoding="utf-8", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def render_console_summary(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    return "\n".join(
        [
            "French evaluation corpus summary",
            f"User: {summary['username']}",
            f"Language: {summary['language']} ({summary['language_match']})",
            f"Projects: {summary['project_count']} ({summary['projects_with_segmentation_phase_2']} with segmentation_phase_2)",
            f"Segments: {summary['segment_count']}",
            f"Tokens: {summary['token_count']} total; {summary['non_whitespace_token_count']} non-whitespace; {summary['whitespace_only_token_count']} whitespace-only",
            f"Token surface chars: {summary['token_surface_chars_including_whitespace']} including whitespace; {summary['token_surface_chars_excluding_whitespace']} excluding whitespace",
            f"Potential anomalies: {summary['segments_with_no_tokens']} empty-token segments; {summary['tokens_with_empty_surface']} empty-token surfaces",
        ]
    )


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# French segmentation evaluation corpus summary",
        "",
        "## Totals",
        "",
        f"- User: `{summary['username']}`",
        f"- Language: `{summary['language']}` (`{summary['language_match']}` match)",
        f"- Projects: {summary['project_count']}",
        f"- Projects with `segmentation_phase_2`: {summary['projects_with_segmentation_phase_2']}",
        f"- Segments: {summary['segment_count']}",
        f"- Tokens: {summary['token_count']} total; {summary['non_whitespace_token_count']} non-whitespace; {summary['whitespace_only_token_count']} whitespace-only",
        f"- Token surface characters: {summary['token_surface_chars_including_whitespace']} including whitespace; {summary['token_surface_chars_excluding_whitespace']} excluding whitespace",
        f"- Segment surface characters: {summary['segment_surface_chars_including_whitespace']} including whitespace; {summary['segment_surface_chars_excluding_whitespace']} excluding whitespace",
        f"- Potential anomalies: {summary['segments_with_no_tokens']} empty-token segments; {summary['tokens_with_empty_surface']} empty-token surfaces; {summary['tokens_with_leading_or_trailing_whitespace']} tokens with boundary whitespace",
        "",
        "## Per-project details",
        "",
        "| Project | Segments | Tokens | Non-ws tokens | Token chars incl ws | Token chars excl ws | Latest run |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for project in payload["projects"]:
        title = str(project["title"]).replace("|", "\\|")
        lines.append(
            f"| {title} | {project['segment_count']} | {project['token_count']} | "
            f"{project['non_whitespace_token_count']} | {project['token_surface_chars_including_whitespace']} | "
            f"{project['token_surface_chars_excluding_whitespace']} | `{project['latest_segmentation_run']}` |"
        )
    return "\n".join(lines) + "\n"


def _without_whitespace(text: str) -> str:
    return WHITESPACE_RE.sub("", text)


def _safe_average(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 3)


def _is_punctuation_only(text: str) -> bool:
    stripped = _without_whitespace(text)
    return bool(stripped) and not any(ch.isalnum() for ch in stripped)
