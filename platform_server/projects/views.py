from __future__ import annotations

import json
import logging
import os
import shutil
import uuid
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import FileResponse, Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.db.models import F, Q
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.generic import CreateView, DetailView, ListView
from django_q.tasks import async_task
from django.utils.html import escape
from django.utils.text import slugify
from django.utils import timezone as django_timezone
import mimetypes
import tempfile
import zipfile
from urllib.parse import unquote

from core.config import DEFAULT_MODEL, OpenAIConfig
from core.ai_api import OpenAIClient
from pipeline.full_pipeline import FullPipelineSpec, PIPELINE_ORDER, run_full_pipeline

from .forms import (
    ClozeExerciseSetForm,
    FlashcardExerciseSetForm,
    ProfileForm,
    ProjectForm,
    ProjectImageElementFormSet,
    ProjectImagePageFormSet,
    ProjectImageStyleForm,
    RegistrationForm,
)
from .models import (
    Profile,
    Project,
    ProjectImageElement,
    ProjectImagePage,
    ProjectImageStyle,
    TaskUpdate,
    ProjectCollaborator,
    ContentComment,
    ContentRating,
    ExerciseSet,
    ExerciseItem,
)

logger = logging.getLogger(__name__)

AI_MODEL_CHOICES = [
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-5",
]

IMAGE_MODEL_CHOICES = [
    "gpt-image-1",
]

PAGE_IMAGE_PLACEMENT_CHOICES = ["none", "top", "bottom"]
SEGMENTATION_METHOD_CHOICES = ["auto", "jieba", "ai"]
ROMANIZATION_METHOD_CHOICES = ["auto", "pypinyin", "indic_transliteration", "ai"]
CONTENT_DATE_FILTERS = {
    "any": None,
    "last_3_days": timedelta(days=3),
    "last_month": timedelta(days=30),
    "last_3_months": timedelta(days=90),
    "last_year": timedelta(days=365),
}



ROLE_RANK = {
    ProjectCollaborator.ROLE_VIEWER: 1,
    ProjectCollaborator.ROLE_ANNOTATOR: 2,
    ProjectCollaborator.ROLE_OWNER: 3,
}


def _project_role_for_user(project: Project, user) -> str | None:
    if project.owner_id == user.id:
        return ProjectCollaborator.ROLE_OWNER
    collab = project.collaborators.filter(user=user).values_list("role", flat=True).first()
    return str(collab) if collab else None


def _get_project_for_user(*, pk: int, user, min_role: str = ProjectCollaborator.ROLE_VIEWER) -> Project:
    project = get_object_or_404(Project, pk=pk)
    role = _project_role_for_user(project, user)
    if role is None:
        raise Http404()
    if ROLE_RANK.get(role, 0) < ROLE_RANK.get(min_role, 0):
        raise Http404()
    return project


def _projects_for_user(user):
    return Project.objects.filter(Q(owner=user) | Q(collaborators__user=user)).distinct()


def _resolve_segmentation_method(language: str, configured: str | None) -> str:
    method = (configured or "auto").strip().lower()
    if language.lower().startswith("zh"):
        if method in {"auto", "jieba", "ai"}:
            return "jieba" if method == "auto" else method
        return "jieba"
    return "ai"


def _resolve_romanization_method(language: str, configured: str | None) -> str:
    method = (configured or "auto").strip().lower()
    lang = language.lower()
    if lang.startswith("zh"):
        if method in {"auto", "pypinyin", "ai"}:
            return "pypinyin" if method == "auto" else method
        return "pypinyin"
    if lang.startswith("hi"):
        if method in {"auto", "indic_transliteration", "ai"}:
            return "indic_transliteration" if method == "auto" else method
        return "indic_transliteration"
    return "auto"


class _TaskTelemetry:
    """Telemetry sink for compile runs (Django log + per-run JSONL + TaskUpdate)."""

    def __init__(self, *, log_path: Path, post_update: Callable[[str, str | None], None]) -> None:
        self._log_path = log_path
        self._post_update = post_update
        self._log_path.parent.mkdir(parents=True, exist_ok=True)

    def _append(self, record: dict[str, Any]) -> None:
        try:
            with self._log_path.open("a", encoding="utf-8") as fp:
                fp.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception:
            logger.exception("Failed to append telemetry log entry; log_path=%s", self._log_path)

    def heartbeat(self, op_id: str, elapsed_s: float, note: str | None = None) -> None:
        msg = f"[heartbeat] {op_id} +{elapsed_s:.1f}s"
        if note:
            msg = f"{msg} ({note})"
        logger.info(msg)
        self._append(
            {
                "type": "heartbeat",
                "op_id": op_id,
                "elapsed_s": round(elapsed_s, 3),
                "note": note,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    def event(self, op_id: str, level: str, msg: str, data: dict | None = None) -> None:
        text = f"[{level}] {op_id} {msg}"
        if data:
            text = f"{text} data={json.dumps(data, ensure_ascii=False)}"

        logger_level = {
            "debug": logging.DEBUG,
            "info": logging.INFO,
            "warn": logging.WARNING,
            "warning": logging.WARNING,
            "error": logging.ERROR,
        }.get(level.lower(), logging.INFO)
        logger.log(logger_level, text)

        self._append(
            {
                "type": "event",
                "op_id": op_id,
                "level": level,
                "message": msg,
                "data": data or {},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

        # Surface warnings/errors, and API request-start diagnostics, in compile monitor updates.
        should_surface = logger_level >= logging.WARNING or msg in {
            "openai.chat request start",
            "openai.chat_text request start",
            "stage failed",
        }
        if should_surface:
            self._post_update(text[:1024], status="error" if logger_level >= logging.ERROR else None)


def _format_timestamp(ts: str, tz_name: str) -> tuple[str, datetime | None]:
    """Return a user-friendly timestamp string and the parsed datetime.

    Falls back to the raw value when parsing fails.
    """

    try:
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt_local = dt.astimezone(ZoneInfo(tz_name))

        # Round to 0.1 second for a concise display.
        rounded_microseconds = int(round(dt_local.microsecond / 100_000) * 100_000)
        if rounded_microseconds == 1_000_000:
            dt_local = dt_local + timedelta(seconds=1)
            rounded_microseconds = 0
        dt_local = dt_local.replace(microsecond=rounded_microseconds)

        offset = dt_local.strftime("%z")
        offset_fmt = f"{offset[:3]}:{offset[3:]}" if len(offset) == 5 else offset
        display = f"{dt_local.strftime('%Y-%m-%d %H:%M:%S')}.{rounded_microseconds // 100_000} ({offset_fmt})"
        return display, dt_local
    except Exception:
        return ts, None


def _make_task_callback(
    task_type: str | None, user_id: int, report_id: uuid.UUID | None = None
) -> tuple[Callable[[str, str | None], None], str]:
    """Return a callback that records task updates and the corresponding report ID."""

    report_id = report_id or uuid.uuid4()
    task_label = task_type or "compile_project"

    def _post(message: str, status: str | None = None) -> None:
        """Persist updates safely from both sync and async contexts."""

        def _write() -> None:
            TaskUpdate.objects.create(
                report_id=report_id,
                user_id=user_id,
                task_type=task_label,
                message=message[:1024],
                status=status,
            )

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No running loop: normal sync execution.
            _write()
        else:
            # Running inside an event loop (e.g., pipeline coroutine); schedule
            # database write off the loop to avoid SynchronousOnlyOperation.
            loop.create_task(asyncio.to_thread(_write))

    return _post, str(report_id)



def _audio_repository_dir(language: str) -> Path:
    """Return global audio repository path for a language."""

    lang = slugify((language or "und").replace("_", "-")).replace("-", "_") or "und"
    return Path(settings.MEDIA_ROOT).resolve() / "audio_repository" / lang

def _image_style_dir(project: Project) -> Path:
    return project.artifact_dir() / "images" / "style"


def _persist_image_style_artifacts(
    project: Project,
    style: ProjectImageStyle,
    *,
    request_payload: dict[str, Any] | None = None,
    response_payload: dict[str, Any] | None = None,
) -> None:
    style_dir = _image_style_dir(project)
    style_dir.mkdir(parents=True, exist_ok=True)
    (style_dir / "style_brief.txt").write_text(style.style_brief or "", encoding="utf-8")
    (style_dir / "style_description.txt").write_text(
        style.expanded_style_description or "", encoding="utf-8"
    )
    (style_dir / "representative_excerpt.txt").write_text(
        style.representative_excerpt or "", encoding="utf-8"
    )
    (style_dir / "sample_image_prompt.txt").write_text(
        style.sample_image_prompt or "", encoding="utf-8"
    )
    (style_dir / "sample_image_revised_prompt.txt").write_text(
        style.sample_image_revised_prompt or "", encoding="utf-8"
    )
    (style_dir / "style_status.json").write_text(
        json.dumps(
            {
                "project_id": project.pk,
                "ai_model": style.ai_model,
                "sample_image_model": style.sample_image_model,
                "sample_image_path": style.sample_image_path,
                "status": style.status,
                "updated_at": style.updated_at.isoformat(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    if request_payload is not None:
        (style_dir / "style_expansion_prompt.json").write_text(
            json.dumps(request_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    if response_payload is not None:
        (style_dir / "style_expansion_response.json").write_text(
            json.dumps(response_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def _extract_project_plain_text(project: Project) -> str:
    if (project.source_text or "").strip():
        return project.source_text.strip()

    latest_run = _resolve_run_dir(project)
    if latest_run:
        for stage in ("text_gen", "segmentation_phase_1", "segmentation_phase_2"):
            payload = _load_stage_payload(project, stage, run_dir=latest_run)
            if isinstance(payload, dict):
                surface = (payload.get("surface") or "").strip()
                if surface:
                    return surface
    return (project.description or "").strip()


def _build_style_generation_request(project: Project, style_brief: str) -> dict[str, Any]:
    plain_text = _extract_project_plain_text(project)
    representative_excerpt = plain_text[:1500].strip()
    prompt = "\n".join(
        [
            "You are helping define a consistent illustration style for a language-learning story.",
            "Return JSON with keys: expanded_style_description, representative_excerpt, sample_image_prompt.",
            "expanded_style_description should preserve the user's brief but elaborate it in a way that fits the story content.",
            "representative_excerpt should be a short excerpt or summary snippet from the story most useful for a sample image.",
            "sample_image_prompt should be a detailed prompt for a single sample image that demonstrates the style for this story.",
            "",
            f"Project title: {project.title}",
            f"Project language: {project.language}",
            f"Target language: {project.target_language}",
            f"User style brief: {style_brief}",
            "Project text:",
            plain_text or "[No text available; rely on the description.]",
        ]
    )
    return {
        "style_brief": style_brief,
        "plain_text": plain_text,
        "prompt": prompt,
    }


def _generate_project_image_style(
    project: Project,
    style_brief: str,
    *,
    ai_model: str,
) -> dict[str, Any]:
    request_payload = _build_style_generation_request(project, style_brief)
    client = _build_ai_client(model_name=ai_model)
    response = asyncio.run(client.chat_json(request_payload["prompt"], model=ai_model))

    return {
        "expanded_style_description": (
            response.get("expanded_style_description") or style_brief
        ).strip(),
        "representative_excerpt": (
            response.get("representative_excerpt")
            or request_payload["plain_text"][:800]
        ).strip(),
        "sample_image_prompt": (
            response.get("sample_image_prompt")
            or response.get("expanded_style_description")
            or style_brief
        ).strip(),
        "_request_payload": request_payload,
        "_response_payload": response,
    }


def _generate_project_style_sample_image(
    project: Project,
    style: ProjectImageStyle,
) -> dict[str, Any]:
    prompt = (style.sample_image_prompt or style.expanded_style_description or "").strip()
    if not prompt:
        raise ValueError("Please generate or enter a sample image prompt first.")

    client = _build_ai_client()
    image_result = client.generate_image(prompt, model=style.sample_image_model)
    style_dir = _image_style_dir(project)
    style_dir.mkdir(parents=True, exist_ok=True)
    image_filename = "style_sample_image.png"
    image_path = style_dir / image_filename
    image_path.write_bytes(image_result["bytes"])

    rel_path = image_path.relative_to(project.artifact_dir()).as_posix()
    metadata = {
        "prompt": prompt,
        "revised_prompt": image_result.get("revised_prompt") or "",
        "model": image_result.get("model") or style.sample_image_model,
        "size": image_result.get("size"),
        "quality": image_result.get("quality"),
        "output_format": image_result.get("output_format"),
        "path": rel_path,
    }
    (style_dir / "style_sample_image_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return metadata


def _image_elements_dir(project: Project) -> Path:
    return project.artifact_dir() / "images" / "elements"


def _extract_project_pages(project: Project) -> list[str]:
    latest_run = _resolve_run_dir(project)
    if latest_run:
        seg1 = _load_stage_payload(project, "segmentation_phase_1", run_dir=latest_run)
        if isinstance(seg1, dict):
            pages = seg1.get("pages", [])
            surfaces = [str(page.get("surface", "")).strip() for page in pages if str(page.get("surface", "")).strip()]
            if surfaces:
                return surfaces
    plain_text = _extract_project_plain_text(project)
    if not plain_text:
        return []
    chunks = [chunk.strip() for chunk in plain_text.split("\n\n") if chunk.strip()]
    return chunks or [plain_text]


def _persist_image_elements_artifacts(
    project: Project,
    *,
    request_payload: dict[str, Any] | None = None,
    response_payload: dict[str, Any] | None = None,
) -> None:
    elements_dir = _image_elements_dir(project)
    elements_dir.mkdir(parents=True, exist_ok=True)
    elements_data = list(
        project.image_elements.order_by("name", "id").values(
            "id",
            "name",
            "element_type",
            "page_refs",
            "why_consistency_matters",
            "expanded_description",
            "expanded_prompt",
            "image_model",
            "image_path",
            "image_revised_prompt",
            "is_confirmed",
            "status",
            "ai_model",
            "updated_at",
        )
    )
    (elements_dir / "elements_list.json").write_text(
        json.dumps(elements_data, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    if request_payload is not None:
        (elements_dir / "elements_discovery_prompt.json").write_text(
            json.dumps(request_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    if response_payload is not None:
        (elements_dir / "elements_discovery_response.json").write_text(
            json.dumps(response_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def _discover_project_image_elements(
    project: Project,
    *,
    ai_model: str,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    pages = _extract_project_pages(project)
    style_description = ""
    try:
        style_description = project.image_style.expanded_style_description
    except Exception:
        style_description = ""

    prompt = "\n".join(
        [
            "Identify recurring visual elements that should be rendered consistently.",
            "Return JSON with key 'elements', where each item has keys:",
            "name, type, page_refs, why_consistency_matters.",
            "page_refs should be a list of 1-indexed page numbers.",
            "Only include elements that appear on at least two pages or are central recurring motifs.",
            "",
            f"Project title: {project.title}",
            f"Language: {project.language}",
            f"Approved style description: {style_description or '[none]'}",
            "Pages:",
        ]
    )
    for idx, page_surface in enumerate(pages, start=1):
        prompt += f"\nPage {idx}: {page_surface}"

    request_payload = {
        "pages": pages,
        "style_description": style_description,
        "prompt": prompt,
    }
    client = _build_ai_client(model_name=ai_model)
    response = asyncio.run(client.chat_json(prompt, model=ai_model))
    elements = response.get("elements") or []
    if not isinstance(elements, list):
        elements = []
    normalized: list[dict[str, Any]] = []
    for item in elements:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        refs = item.get("page_refs") or []
        if isinstance(refs, list):
            refs_text = ",".join(str(x) for x in refs if str(x).strip())
        else:
            refs_text = str(refs)
        normalized.append(
            {
                "name": name[:255],
                "element_type": str(item.get("type") or "character")[:64],
                "page_refs": refs_text[:255],
                "why_consistency_matters": str(item.get("why_consistency_matters") or "")[:2000],
            }
        )
    return normalized, request_payload, response


def _expand_project_image_elements(
    project: Project,
    *,
    ai_model: str,
) -> int:
    style_description = ""
    try:
        style_description = project.image_style.expanded_style_description
    except Exception:
        style_description = ""
    full_text = _extract_project_plain_text(project)
    count = 0
    client = _build_ai_client(model_name=ai_model)
    for element in project.image_elements.order_by("name", "id"):
        prompt = "\n".join(
            [
                "Create an expanded visual element description for consistent illustration.",
                "Return JSON with keys: expanded_description, expanded_prompt.",
                "",
                f"Element name: {element.name}",
                f"Element type: {element.element_type}",
                f"Page refs: {element.page_refs}",
                f"Why consistency matters: {element.why_consistency_matters}",
                f"Project style description: {style_description or '[none]'}",
                "Project text:",
                full_text or "[none]",
            ]
        )
        response = asyncio.run(client.chat_json(prompt, model=ai_model))
        element.expanded_description = str(
            response.get("expanded_description") or element.expanded_description or ""
        ).strip()
        element.expanded_prompt = str(
            response.get("expanded_prompt") or element.expanded_description or ""
        ).strip()
        element.ai_model = ai_model
        element.status = ProjectImageElement.STATUS_EXPANDED
        element.save(
            update_fields=[
                "expanded_description",
                "expanded_prompt",
                "ai_model",
                "status",
                "updated_at",
            ]
        )
        count += 1
    return count


def _generate_project_element_images(
    project: Project,
    *,
    image_model: str,
) -> int:
    elements_dir = _image_elements_dir(project)
    elements_dir.mkdir(parents=True, exist_ok=True)
    generated = 0
    elements = list(project.image_elements.order_by("name", "id"))
    work_items: list[tuple[ProjectImageElement, str]] = []
    for element in elements:
        prompt = (element.expanded_prompt or element.expanded_description or element.name).strip()
        if prompt:
            work_items.append((element, prompt))

    if not work_items:
        return 0

    max_workers = min(4, len(work_items))
    logger.info(
        "Generating %s element images with fan-out/fan-in (workers=%s, model=%s) for project %s",
        len(work_items),
        max_workers,
        image_model,
        project.pk,
    )
    results_by_id: dict[int, dict[str, Any]] = {}

    def _generate_one(element_id: int, prompt_text: str) -> tuple[int, dict[str, Any]]:
        client = _build_ai_client()
        return element_id, client.generate_image(prompt_text, model=image_model)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_generate_one, element.id, prompt): (element.id, prompt)
            for element, prompt in work_items
        }
        for future in as_completed(futures):
            element_id, _prompt = futures[future]
            results_by_id[element_id] = future.result()[1]

    for element, prompt in work_items:
        image_result = results_by_id[element.id]
        element_slug = slugify(element.name) or f"element-{element.id}"
        element_dir = elements_dir / element_slug
        element_dir.mkdir(parents=True, exist_ok=True)
        image_path = element_dir / "reference.png"
        image_path.write_bytes(image_result["bytes"])
        rel_path = image_path.relative_to(project.artifact_dir()).as_posix()
        element.image_model = image_model
        element.image_path = rel_path
        element.image_revised_prompt = image_result.get("revised_prompt") or ""
        if element.status != ProjectImageElement.STATUS_CONFIRMED:
            element.status = ProjectImageElement.STATUS_EXPANDED
        element.save(
            update_fields=[
                "image_model",
                "image_path",
                "image_revised_prompt",
                "status",
                "updated_at",
            ]
        )
        (element_dir / "metadata.json").write_text(
            json.dumps(
                {
                    "name": element.name,
                    "prompt": prompt,
                    "model": image_model,
                    "revised_prompt": element.image_revised_prompt,
                    "image_path": rel_path,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        generated += 1

    logger.info(
        "Completed element image generation fan-in for project %s (%s images).",
        project.pk,
        generated,
    )
    return generated


def _image_pages_dir(project: Project) -> Path:
    return project.artifact_dir() / "images" / "pages"


def _page_refs_match(page_refs: str, page_number: int) -> bool:
    refs = [chunk.strip() for chunk in (page_refs or "").split(",") if chunk.strip()]
    return str(page_number) in refs


def _build_page_image_prompt(
    *,
    project: Project,
    style: ProjectImageStyle,
    page_number: int,
    page_text: str,
    full_text: str,
    relevant_elements: list[ProjectImageElement],
) -> str:
    lines = [
        "Create one story illustration page in a consistent style.",
        "Keep visual continuity with the existing style and element references.",
        "",
        f"Project title: {project.title}",
        f"Language: {project.language}",
        f"Page number: {page_number}",
        f"Style description: {style.expanded_style_description or style.style_brief or '[none]'}",
        "Page text:",
        page_text or "[none]",
        "",
        "Full story text for context:",
        full_text or "[none]",
        "",
        "Relevant element references:",
    ]
    if relevant_elements:
        for element in relevant_elements:
            lines.extend(
                [
                    f"- Element: {element.name} ({element.element_type or 'unspecified'})",
                    f"  Description: {element.expanded_description or element.why_consistency_matters or '[none]'}",
                    f"  Prompt: {element.expanded_prompt or '[none]'}",
                    f"  Reference image path: {element.image_path or '[none]'}",
                ]
            )
    else:
        lines.append("- [No relevant elements with image references]")
    return "\n".join(lines)


def _ensure_project_page_rows(project: Project) -> int:
    pages = _extract_project_pages(project)
    existing = {
        row.page_number: row
        for row in ProjectImagePage.objects.filter(project=project)
    }
    for idx, page_text in enumerate(pages, start=1):
        row = existing.get(idx)
        if row:
            if row.page_text != page_text:
                row.page_text = page_text
                row.save(update_fields=["page_text", "updated_at"])
        else:
            ProjectImagePage.objects.create(
                project=project,
                page_number=idx,
                page_text=page_text,
            )
    return len(pages)


def _persist_image_pages_artifacts(project: Project) -> None:
    pages_dir = _image_pages_dir(project)
    pages_dir.mkdir(parents=True, exist_ok=True)
    rows = list(
        project.image_pages.order_by("page_number", "id").values(
            "id",
            "page_number",
            "page_text",
            "generation_prompt",
            "image_model",
            "image_path",
            "image_revised_prompt",
            "status",
            "updated_at",
        )
    )
    (pages_dir / "pages_list.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def _generate_project_page_images(project: Project, *, image_model: str) -> int:
    style = project.image_style
    full_text = _extract_project_plain_text(project)
    pages_dir = _image_pages_dir(project)
    pages_dir.mkdir(parents=True, exist_ok=True)
    page_rows = list(project.image_pages.order_by("page_number", "id"))
    relevant_elements = [
        element
        for element in project.image_elements.order_by("name", "id")
        if element.image_path
    ]
    if not page_rows:
        return 0

    def _generate_one(page_obj: ProjectImagePage) -> tuple[int, str, str]:
        refs = [
            element
            for element in relevant_elements
            if not element.page_refs or _page_refs_match(element.page_refs, page_obj.page_number)
        ]
        prompt = _build_page_image_prompt(
            project=project,
            style=style,
            page_number=page_obj.page_number,
            page_text=page_obj.page_text,
            full_text=full_text,
            relevant_elements=refs,
        )
        client = _build_ai_client()
        image_result = client.generate_image(prompt, model=image_model)
        page_dir = pages_dir / f"page_{page_obj.page_number:03d}"
        page_dir.mkdir(parents=True, exist_ok=True)
        image_path = page_dir / "image.png"
        image_path.write_bytes(image_result["bytes"])
        rel_path = image_path.relative_to(project.artifact_dir()).as_posix()
        metadata = {
            "page_number": page_obj.page_number,
            "prompt": prompt,
            "model": image_model,
            "revised_prompt": image_result.get("revised_prompt") or "",
            "image_path": rel_path,
        }
        (page_dir / "metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return page_obj.pk, rel_path, metadata["revised_prompt"], prompt

    generated = 0
    futures = {}
    with ThreadPoolExecutor(max_workers=min(8, len(page_rows))) as executor:
        for page_obj in page_rows:
            future = executor.submit(_generate_one, page_obj)
            futures[future] = page_obj
        for future in as_completed(futures):
            page_pk, rel_path, revised_prompt, prompt = future.result()
            ProjectImagePage.objects.filter(pk=page_pk).update(
                generation_prompt=prompt,
                image_model=image_model,
                image_path=rel_path,
                image_revised_prompt=revised_prompt,
                status=ProjectImagePage.STATUS_GENERATED,
            )
            generated += 1
    return generated


def register(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            Profile.objects.get_or_create(user=user)
            messages.success(request, "Account created. Please log in.")
            return redirect("login")
    else:
        form = RegistrationForm()
    return render(request, "projects/register.html", {"form": form})


@login_required
def profile(request: HttpRequest) -> HttpResponse:
    profile_obj, _ = Profile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        form = ProfileForm(request.POST, instance=profile_obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile saved.")
            return redirect("profile")
    else:
        form = ProfileForm(instance=profile_obj)

    return render(request, "projects/profile_form.html", {"form": form})


@login_required
def project_image_style(request: HttpRequest, pk: int) -> HttpResponse:
    project = _get_project_for_user(pk=pk, user=request.user, min_role=ProjectCollaborator.ROLE_ANNOTATOR)
    style_obj, _ = ProjectImageStyle.objects.get_or_create(
        project=project,
        defaults={"ai_model": project.ai_model or DEFAULT_MODEL},
    )

    if request.method == "POST":
        action = request.POST.get("action") or "save"
        form = ProjectImageStyleForm(
            request.POST,
            instance=style_obj,
            ai_model_choices=AI_MODEL_CHOICES,
            image_model_choices=IMAGE_MODEL_CHOICES,
        )
        if form.is_valid():
            style_obj = form.save(commit=False)
            request_payload = None
            response_payload = None

            if action == "generate":
                try:
                    generated = _generate_project_image_style(
                        project,
                        style_obj.style_brief,
                        ai_model=style_obj.ai_model,
                    )
                except Exception as exc:
                    logger.exception(
                        "Failed to generate image style for project %s", project.pk
                    )
                    messages.error(request, f"Style generation failed: {exc}")
                else:
                    style_obj.expanded_style_description = generated[
                        "expanded_style_description"
                    ]
                    style_obj.representative_excerpt = generated[
                        "representative_excerpt"
                    ]
                    style_obj.sample_image_prompt = generated["sample_image_prompt"]
                    style_obj.status = ProjectImageStyle.STATUS_GENERATED
                    request_payload = generated["_request_payload"]
                    response_payload = generated["_response_payload"]
                    messages.success(
                        request,
                        f"Style expansion completed with {style_obj.ai_model}: prompt and excerpt are ready for review.",
                    )
            elif action == "generate_image":
                try:
                    metadata = _generate_project_style_sample_image(project, style_obj)
                except Exception as exc:
                    logger.exception(
                        "Failed to generate style sample image for project %s", project.pk
                    )
                    messages.error(request, f"Sample image generation failed: {exc}")
                else:
                    style_obj.sample_image_path = metadata["path"]
                    style_obj.sample_image_revised_prompt = metadata["revised_prompt"]
                    style_obj.status = ProjectImageStyle.STATUS_GENERATED
                    messages.success(
                        request,
                        f"Sample style image generation completed with {metadata.get('model') or style_obj.sample_image_model}.",
                    )
            elif action == "approve":
                style_obj.status = ProjectImageStyle.STATUS_APPROVED
                messages.success(request, "Style marked as approved.")
            else:
                messages.success(request, "Style draft saved.")

            style_obj.save()
            _persist_image_style_artifacts(
                project,
                style_obj,
                request_payload=request_payload,
                response_payload=response_payload,
            )
            return redirect(f"{reverse('project-image-style', args=[project.pk])}?notice=done")
        messages.error(
            request,
            "Could not process the style request. Please review the highlighted form fields.",
        )
    else:
        form = ProjectImageStyleForm(
            instance=style_obj,
            ai_model_choices=AI_MODEL_CHOICES,
            image_model_choices=IMAGE_MODEL_CHOICES,
        )

    return render(
        request,
        "projects/project_image_style.html",
        {
            "project": project,
            "form": form,
            "style": style_obj,
            "style_artifact_dir": _image_style_dir(project),
            "style_image_url": (
                reverse("project-compiled", args=[project.pk, style_obj.sample_image_path])
                if style_obj.sample_image_path
                else None
            ),
            "status_notice": request.GET.get("notice"),
        },
    )


@login_required
def project_image_elements(request: HttpRequest, pk: int) -> HttpResponse:
    project = _get_project_for_user(pk=pk, user=request.user, min_role=ProjectCollaborator.ROLE_ANNOTATOR)
    try:
        style = project.image_style
    except ProjectImageStyle.DoesNotExist:
        messages.error(request, "Please complete the Style step first.")
        return redirect("project-image-style", pk=project.pk)

    queryset = ProjectImageElement.objects.filter(project=project).order_by("name", "id")

    if request.method == "POST":
        action = request.POST.get("action") or "save"
        requested_image_model = (request.POST.get("image_model") or "").strip()
        image_model = requested_image_model or "gpt-image-1"
        invalid_image_model = image_model not in IMAGE_MODEL_CHOICES
        if invalid_image_model:
            image_model = "gpt-image-1"
        formset = ProjectImageElementFormSet(request.POST, queryset=queryset)
        if formset.is_valid():
            if action == "generate_images" and requested_image_model and invalid_image_model:
                messages.warning(
                    request,
                    f"Unknown image model '{requested_image_model}'. Using gpt-image-1 instead.",
                )
            instances = formset.save(commit=False)
            for obj in formset.deleted_objects:
                obj.delete()
            for obj in instances:
                obj.project = project
                obj.ai_model = obj.ai_model or style.ai_model or DEFAULT_MODEL
                if obj.is_confirmed:
                    obj.status = ProjectImageElement.STATUS_CONFIRMED
                obj.save()
            formset.save_m2m()

            if action == "discover":
                messages.info(
                    request,
                    f"Discovering recurring elements with {style.ai_model or DEFAULT_MODEL}.",
                )
                try:
                    discovered, request_payload, response_payload = _discover_project_image_elements(
                        project, ai_model=style.ai_model or DEFAULT_MODEL
                    )
                except Exception as exc:
                    logger.exception("Failed to discover image elements for project %s", project.pk)
                    messages.error(request, f"Element discovery failed: {exc}")
                else:
                    project.image_elements.all().delete()
                    for item in discovered:
                        ProjectImageElement.objects.create(
                            project=project,
                            ai_model=style.ai_model or DEFAULT_MODEL,
                            status=ProjectImageElement.STATUS_PROPOSED,
                            **item,
                        )
                    _persist_image_elements_artifacts(
                        project,
                        request_payload=request_payload,
                        response_payload=response_payload,
                    )
                    messages.success(request, f"Discovered {len(discovered)} recurring elements.")
            elif action == "expand":
                messages.info(
                    request,
                    f"Expanding element prompts with {style.ai_model or DEFAULT_MODEL}.",
                )
                try:
                    expanded = _expand_project_image_elements(
                        project, ai_model=style.ai_model or DEFAULT_MODEL
                    )
                except Exception as exc:
                    logger.exception("Failed to expand image elements for project %s", project.pk)
                    messages.error(request, f"Element expansion failed: {exc}")
                else:
                    _persist_image_elements_artifacts(project)
                    messages.success(request, f"Expanded prompts for {expanded} elements.")
            elif action == "confirm":
                confirmed = 0
                for element in project.image_elements.all():
                    if element.is_confirmed:
                        element.status = ProjectImageElement.STATUS_CONFIRMED
                        element.save(update_fields=["status", "updated_at"])
                        confirmed += 1
                _persist_image_elements_artifacts(project)
                messages.success(request, f"Confirmed {confirmed} elements.")
            elif action == "generate_images":
                try:
                    generated_images = _generate_project_element_images(
                        project, image_model=image_model
                    )
                except Exception as exc:
                    logger.exception("Failed to generate element images for project %s", project.pk)
                    messages.error(request, f"Element image generation failed: {exc}")
                else:
                    _persist_image_elements_artifacts(project)
                    messages.success(
                        request,
                        f"Generated {generated_images} element reference images with {image_model}.",
                    )
            else:
                _persist_image_elements_artifacts(project)
                messages.success(request, "Saved element edits.")
            return redirect(f"{reverse('project-image-elements', args=[project.pk])}?notice=done")
        messages.error(
            request,
            "Could not process the elements request. Please review the form rows for errors.",
        )
    else:
        formset = ProjectImageElementFormSet(queryset=queryset)

    return render(
        request,
        "projects/project_image_elements.html",
        {
            "project": project,
            "style": style,
            "formset": formset,
            "elements_artifact_dir": _image_elements_dir(project),
            "confirmed_count": project.image_elements.filter(is_confirmed=True).count(),
            "image_models": IMAGE_MODEL_CHOICES,
            "selected_image_model": request.GET.get("image_model")
            or project.image_elements.filter(image_model__isnull=False)
            .exclude(image_model="")
            .values_list("image_model", flat=True)
            .first()
            or "gpt-image-1",
            "status_notice": request.GET.get("notice"),
        },
    )


@login_required
def project_image_pages(request: HttpRequest, pk: int) -> HttpResponse:
    project = _get_project_for_user(pk=pk, user=request.user, min_role=ProjectCollaborator.ROLE_ANNOTATOR)
    try:
        style = project.image_style
    except ProjectImageStyle.DoesNotExist:
        messages.error(request, "Please complete the Style step first.")
        return redirect("project-image-style", pk=project.pk)

    _ensure_project_page_rows(project)
    queryset = ProjectImagePage.objects.filter(project=project).order_by("page_number", "id")

    if request.method == "POST":
        action = request.POST.get("action") or "save"
        requested_image_model = (request.POST.get("image_model") or "").strip()
        image_model = requested_image_model or "gpt-image-1"
        if image_model not in IMAGE_MODEL_CHOICES:
            image_model = "gpt-image-1"
        formset = ProjectImagePageFormSet(request.POST, queryset=queryset)
        if formset.is_valid():
            rows = formset.save(commit=False)
            for row in rows:
                row.project = project
                row.save()

            if action == "refresh":
                synced = _ensure_project_page_rows(project)
                messages.success(request, f"Synced {synced} page rows from source text.")
            elif action == "generate_images":
                try:
                    generated = _generate_project_page_images(project, image_model=image_model)
                except Exception as exc:
                    logger.exception("Failed to generate page images for project %s", project.pk)
                    messages.error(request, f"Page image generation failed: {exc}")
                else:
                    messages.success(
                        request,
                        f"Generated {generated} page images with {image_model}.",
                    )
            else:
                messages.success(request, "Saved page image prompt edits.")
            _persist_image_pages_artifacts(project)
            return redirect(f"{reverse('project-image-pages', args=[project.pk])}?notice=done")
        messages.error(
            request,
            "Could not process the page image request. Please review the form rows for errors.",
        )
    else:
        formset = ProjectImagePageFormSet(queryset=queryset)

    return render(
        request,
        "projects/project_image_pages.html",
        {
            "project": project,
            "style": style,
            "formset": formset,
            "pages_artifact_dir": _image_pages_dir(project),
            "image_models": IMAGE_MODEL_CHOICES,
            "selected_image_model": request.GET.get("image_model") or "gpt-image-1",
            "element_count": project.image_elements.count(),
            "confirmed_element_count": project.image_elements.filter(is_confirmed=True).count(),
            "elements_with_images_count": project.image_elements.exclude(image_path="").count(),
            "status_notice": request.GET.get("notice"),
        },
    )


class ProjectListView(LoginRequiredMixin, ListView):
    model = Project
    template_name = "projects/project_list.html"

    def get_queryset(self):  # type: ignore[override]
        return _projects_for_user(self.request.user)


class ProjectDetailView(LoginRequiredMixin, DetailView):
    model = Project
    template_name = "projects/project_detail.html"

    def get_queryset(self):  # type: ignore[override]
        return _projects_for_user(self.request.user)
    def get_context_data(self, **kwargs):  # type: ignore[override]
        context = super().get_context_data(**kwargs)
        project: Project = context["object"]

        stage_files: list[dict[str, Any]] = []
        progress: list[dict[str, Any]] = []

        base = project.artifact_dir().resolve()
        run_dir = _resolve_run_dir(project)
        media_root = Path(settings.MEDIA_ROOT).resolve()
        compiled_uri: str | None = None
        compiled_media_url: str | None = None
        run_media_base: str | None = None

        project_media_base = (
            Path(settings.MEDIA_URL.rstrip("/"))
            / "users"
            / str(project.owner.id)
            / "projects"
            / f"project_{project.id}"
        ).as_posix()

        if project.compiled_path:
            compiled_abs = (base / project.compiled_path).resolve()
            if compiled_abs.exists():
                try:
                    compiled_uri = compiled_abs.as_uri()
                except ValueError:
                    compiled_uri = compiled_abs.as_posix()

            # Always provide a MEDIA_URL-based link so compiled pages and
            # concordances can load without hitting the view indirection.
            compiled_media_url = f"{project_media_base}/{project.compiled_path}"

        try:
            tz_name = self.request.user.profile.timezone
        except Exception:
            tz_name = "UTC"

        if run_dir:
            # Keep the MEDIA-relative run base stable for stage links even if
            # the project was compiled on a different host path.
            run_media_base = f"{project_media_base}/runs/{run_dir.name}"

            stage_dir = run_dir / "stages"
            if stage_dir.exists():
                for path in sorted(stage_dir.glob("*.json"), key=lambda p: p.stat().st_mtime):
                    rel = path.resolve().relative_to(base).as_posix()
                    url = None
                    if run_media_base:
                        try:
                            rel_from_run = path.resolve().relative_to(run_dir).as_posix()
                            url = run_media_base.rstrip("/") + "/" + rel_from_run
                        except Exception:
                            url = None
                    stage_files.append({"path": rel, "url": url})

                progress_path = stage_dir / "progress.jsonl"
                if progress_path.exists():
                    for line in progress_path.read_text(encoding="utf-8").splitlines():
                        try:
                            raw_entry = json.loads(line)
                        except Exception:
                            continue

                        display_ts, dt = _format_timestamp(
                            raw_entry.get("timestamp", ""), tz_name
                        )
                        progress.append(
                            {
                                "stage": raw_entry.get("stage"),
                                "status": raw_entry.get("status"),
                                "timestamp": display_ts,
                                "_dt": dt,
                            }
                        )

                    progress.sort(
                        key=lambda p: p.get("_dt") or p.get("timestamp", "")
                    )

        # Drop helper datetime objects used for sorting before rendering.
        for p in progress:
            p.pop("_dt", None)

        context["stage_files"] = stage_files
        context["progress"] = progress
        context["pipeline_stages"] = PIPELINE_ORDER
        context["default_start_stage"] = (
            "text_gen" if project.input_mode == Project.INPUT_DESCRIPTION else "segmentation_phase_1"
        )
        context["compiled_uri"] = compiled_uri
        context["compiled_media_url"] = compiled_media_url
        context["ai_models"] = AI_MODEL_CHOICES
        context["selected_ai_model"] = project.ai_model or DEFAULT_MODEL
        style_obj = getattr(project, "image_style", None)
        context["style_ready"] = bool(
            style_obj and (style_obj.sample_image_path or style_obj.status == ProjectImageStyle.STATUS_APPROVED)
        )
        context["elements_ready"] = project.image_elements.exclude(image_path="").exists()
        context["pages_ready"] = project.image_pages.exclude(image_path="").exists()
        context["page_image_placement_options"] = PAGE_IMAGE_PLACEMENT_CHOICES
        context["selected_page_image_placement"] = (
            project.page_image_placement
            if project.page_image_placement in PAGE_IMAGE_PLACEMENT_CHOICES
            else "none"
        )
        context["has_segmentation_phase_1"] = _has_segmentation_phase_1_output(project)
        if project.language.lower().startswith("zh"):
            context["segmentation_method_options"] = [("auto", "Jieba (default)"), ("jieba", "Jieba"), ("ai", "AI")]
            context["romanization_method_options"] = [
                ("auto", "pypinyin (default)"),
                ("pypinyin", "pypinyin"),
                ("ai", "AI"),
            ]
        elif project.language.lower().startswith("hi"):
            context["segmentation_method_options"] = [("auto", "AI (default)"), ("ai", "AI")]
            context["romanization_method_options"] = [
                ("auto", "indic_transliteration (default)"),
                ("indic_transliteration", "indic_transliteration"),
                ("ai", "AI"),
            ]
        else:
            context["segmentation_method_options"] = [("auto", "AI (default)"), ("ai", "AI")]
            context["romanization_method_options"] = [("auto", "Not used for this language")]
        context["selected_segmentation_method"] = project.segmentation_method or "auto"
        context["selected_romanization_method"] = project.romanization_method or "auto"
        collaborators = project.collaborators.select_related("user").all()
        context["collaborators"] = collaborators
        context["collaborator_role_choices"] = ProjectCollaborator.ROLE_CHOICES
        context["current_user_role"] = _project_role_for_user(project, self.request.user)
        assigned_ids = {c.user_id for c in collaborators}
        assigned_ids.add(project.owner_id)
        User = get_user_model()
        context["available_collaborator_users"] = User.objects.exclude(id__in=assigned_ids).order_by("username")[:500]
        context["exercise_sets"] = project.exercise_sets.all()[:20]
        return context


class ProjectAnnotationView(ProjectDetailView):
    template_name = "projects/project_annotation.html"


@login_required
def project_images_home(request: HttpRequest, pk: int) -> HttpResponse:
    project = _get_project_for_user(pk=pk, user=request.user, min_role=ProjectCollaborator.ROLE_ANNOTATOR)
    style = getattr(project, "image_style", None)
    elements_with_images = project.image_elements.exclude(image_path="").order_by("name", "id")
    pages_with_images = project.image_pages.exclude(image_path="").order_by("page_number", "id")
    return render(
        request,
        "projects/project_images_home.html",
        {
            "project": project,
            "style": style,
            "elements_with_images_count": elements_with_images.count(),
            "sample_elements_with_images": elements_with_images[:5],
            "pages_with_images_count": pages_with_images.count(),
            "sample_pages_with_images": pages_with_images[:5],
            "has_segmentation_phase_1": _has_segmentation_phase_1_output(project),
            "selected_ai_model": project.ai_model or DEFAULT_MODEL,
            "selected_page_image_placement": (
                project.page_image_placement
                if project.page_image_placement in PAGE_IMAGE_PLACEMENT_CHOICES
                else "none"
            ),
        },
    )


@login_required
def project_exercises_home(request: HttpRequest, pk: int) -> HttpResponse:
    project = _get_project_for_user(pk=pk, user=request.user, min_role=ProjectCollaborator.ROLE_ANNOTATOR)
    role = _project_role_for_user(project, request.user)
    latest_sets: list[ExerciseSet] = []
    for exercise_type, _label in ExerciseSet.TYPE_CHOICES:
        latest_set = (
            project.exercise_sets.filter(exercise_type=exercise_type)
            .order_by("-updated_at", "-id")
            .first()
        )
        if latest_set is not None:
            latest_sets.append(latest_set)

    latest_sets.sort(key=lambda s: s.updated_at, reverse=True)
    return render(
        request,
        "projects/project_exercises_home.html",
        {
            "project": project,
            "exercise_sets": latest_sets,
            "can_publish": role == ProjectCollaborator.ROLE_OWNER or project.owner_id == request.user.id,
        },
    )


class ProjectCreateView(LoginRequiredMixin, CreateView):
    model = Project
    form_class = ProjectForm
    template_name = "projects/project_form.html"

    def form_valid(self, form):  # type: ignore[override]
        form.instance.owner = self.request.user
        messages.info(self.request, "Project created. Compile when ready.")
        response = super().form_valid(form)
        _persist_project_source(self.object)
        return response

    def get_success_url(self):  # type: ignore[override]
        return reverse("project-detail", args=[self.object.pk])


def _build_ai_client(model_name: str | None = None) -> OpenAIClient:
    config = OpenAIConfig(model=model_name or DEFAULT_MODEL)
    return OpenAIClient(config=config)


def _prepare_output_dir(project: Project) -> Path:
    base = project.artifact_dir()
    # Ensure base/source directories exist so future uploads or manual edits have
    # a stable home.
    (base / "source").mkdir(parents=True, exist_ok=True)
    runs_dir = base / "runs"
    timestamp = datetime.utcnow().strftime("run_%Y%m%d_%H%M%S")
    output_dir = runs_dir / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def _persist_project_source(project: Project) -> None:
    """Write the project's current description/source text into ``source/``.

    This keeps the on-disk layout aligned with the documented structure so that
    downstream tooling (and humans) can inspect the inputs that seeded a run.
    Files are written even when blank so the chosen input mode is obvious on disk.
    """

    base = project.artifact_dir()
    source_dir = base / "source"
    source_dir.mkdir(parents=True, exist_ok=True)

    try:
        (source_dir / "description.txt").write_text(project.description or "", encoding="utf-8")
        (source_dir / "source_text.txt").write_text(project.source_text or "", encoding="utf-8")
    except Exception:
        # Best-effort persistence; failures should not block UI flows.
        pass


def _resolve_run_dir(project: Project) -> Path | None:
    base = project.artifact_dir().resolve()
    if project.compiled_path:
        rel = Path(project.compiled_path)
        if len(rel.parts) >= 2 and rel.parts[0] == "runs":
            return (base / rel.parts[0] / rel.parts[1]).resolve()
    runs_root = base / "runs"
    if runs_root.exists():
        try:
            return max(runs_root.iterdir(), key=lambda p: p.stat().st_mtime)
        except ValueError:
            return None
    return None


def _has_segmentation_phase_1_output(project: Project) -> bool:
    run_dir = _resolve_run_dir(project)
    if not run_dir:
        return False
    return (run_dir / "stages" / "segmentation_phase_1.json").exists()



def _write_tree_to_zip(zip_file: zipfile.ZipFile, source_dir: Path, zip_root: Path) -> int:
    """Write all files under ``source_dir`` into ``zip_file`` under ``zip_root``."""

    if not source_dir.exists():
        return 0

    count = 0
    for file_path in source_dir.rglob("*"):
        if not file_path.is_file():
            continue
        rel = file_path.relative_to(source_dir)
        zip_file.write(file_path, arcname=(zip_root / rel).as_posix())
        count += 1
    return count


def _safe_zip_read_json(zf: zipfile.ZipFile, member: str) -> dict[str, Any] | None:
    try:
        with zf.open(member, "r") as fp:
            return json.loads(fp.read().decode("utf-8"))
    except Exception:
        return None


def _build_unique_import_title(user: Any, base_title: str) -> str:
    candidate = (base_title or "Imported project").strip()
    if not candidate:
        candidate = "Imported project"
    if not Project.objects.filter(owner=user, title=candidate).exists():
        return candidate
    for idx in range(2, 200):
        titled = f"{candidate} ({idx})"
        if not Project.objects.filter(owner=user, title=titled).exists():
            return titled
    return f"{candidate} ({uuid.uuid4().hex[:8]})"

def _iter_runs(project: Project) -> list[Path]:
    runs_root = (project.artifact_dir() / "runs").resolve()
    if not runs_root.exists():
        return []
    return sorted(runs_root.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)


def _find_run_with_stage(project: Project, stage: str) -> Path | None:
    for run_dir in _iter_runs(project):
        if (run_dir / "stages" / f"{stage}.json").exists():
            return run_dir
    return None


def _load_stage_payload(
    project: Project, stage: str, run_dir: Path | None = None
) -> dict[str, Any] | None:
    if run_dir is None:
        run_dir = _resolve_run_dir(project)
    if not run_dir:
        return None
    path = run_dir / "stages" / f"{stage}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _copy_run_artifacts(src: Path, dest: Path) -> None:
    """Copy prior run outputs into ``dest`` so partial recompiles have inputs.

    Stages upstream from the chosen start point live in previous run folders.
    Copying those artifacts forward lets later partial runs chain together even
    when the most recent run only contains downstream outputs.
    """

    for item in src.iterdir():
        target = dest / item.name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        elif item.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)


def _run_compile_task(
    project_id: int,
    user_id: int,
    output_dir_str: str,
    project_root_str: str,
    start_stage: str,
    timezone_name: str | None,
    description: str | None,
    text: str | None,
    text_obj: dict[str, Any] | None,
    report_id: str | None = None,
    task_type: str | None = None,
    ai_model: str | None = None,
    end_stage: str | None = None,
    page_image_placement: str | None = None,
    segmentation_method: str | None = None,
    romanization_method: str | None = None,
) -> None:
    project = Project.objects.get(pk=project_id)
    output_dir = Path(output_dir_str)
    project_root = Path(project_root_str)
    stage_dir = output_dir / "stages"
    stage_dir.mkdir(parents=True, exist_ok=True)
    progress_log = stage_dir / "progress.jsonl"

    try:
        profile = Profile.objects.get(user_id=user_id)
        tz_name = profile.timezone or "UTC"
    except Profile.DoesNotExist:
        tz_name = timezone_name or "UTC"

    try:
        report_uuid = uuid.UUID(report_id) if report_id else uuid.uuid4()
    except Exception:
        report_uuid = uuid.uuid4()
    post_update, _ = _make_task_callback(
        task_type or f"compile_project_{project_id}", user_id, report_uuid
    )
    telemetry_log = output_dir / "stages" / "telemetry.jsonl"
    telemetry = _TaskTelemetry(log_path=telemetry_log, post_update=post_update)
    post_update(f"Telemetry log file: {telemetry_log}")
    logger.info("Compile telemetry log file: %s", telemetry_log)

    def progress_cb(stage: str, status: str, timestamp: str) -> None:
        try:
            dt = datetime.fromisoformat(timestamp)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            local_timestamp = dt.astimezone(ZoneInfo(tz_name)).isoformat()
        except Exception:
            local_timestamp = timestamp

        entry = {"stage": stage, "status": status, "timestamp": local_timestamp}
        try:
            with progress_log.open("a", encoding="utf-8") as fp:
                fp.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            logger.exception("Failed to append progress entry; progress_log=%s", progress_log)

        try:
            display_ts, _ = _format_timestamp(local_timestamp, tz_name)
            post_update(f"{stage}: {status} @ {display_ts}")
        except Exception:
            logger.exception(
                "Failed to persist task update; stage=%s status=%s report_id=%s",
                stage,
                status,
                report_id,
            )

    spec = FullPipelineSpec(
        text=text,
        text_obj=text_obj,
        description=description,
        language=project.language,
        target_language=project.target_language,
        output_dir=output_dir,
        audio_cache_dir=_audio_repository_dir(project.language),
        require_real_tts=True,
        persist_intermediates=True,
        progress_callback=progress_cb,
        start_stage=start_stage,
        end_stage=end_stage or "compile_html",
        page_images={},
        segmentation_method=_resolve_segmentation_method(project.language, segmentation_method or project.segmentation_method),
        romanization_method=_resolve_romanization_method(project.language, romanization_method or project.romanization_method),
        telemetry=telemetry,
    )

    placement = (page_image_placement or "none").strip().lower()
    if placement in {"top", "bottom"}:
        page_images: dict[int, dict[str, str]] = {}
        expected_paths: list[str] = []
        for row in project.image_pages.order_by("page_number"):
            if not row.image_path:
                expected_paths.append(f"page {row.page_number}: [no image_path set]")
                continue
            abs_path = (project.artifact_dir() / row.image_path).resolve()
            rel_path = os.path.relpath(abs_path, output_dir / "html").replace("\\", "/")
            expected_paths.append(f"page {row.page_number}: {abs_path} (exists={abs_path.exists()})")
            if abs_path.exists():
                page_images[row.page_number] = {"path": rel_path, "placement": placement}
        spec.page_images = page_images
        if not page_images:
            logger.warning(
                "Page image placement is '%s' but no source images were resolved for compile input. Expected references: %s",
                placement,
                "; ".join(expected_paths) if expected_paths else "[no ProjectImagePage rows found]",
            )
            post_update(
                "Warning: page image placement is enabled but no page images were found for compile input."
            )

    chosen_model = ai_model or project.ai_model or DEFAULT_MODEL
    if chosen_model not in AI_MODEL_CHOICES:
        chosen_model = DEFAULT_MODEL

    client = _build_ai_client(model_name=chosen_model)

    try:
        result = asyncio.run(run_full_pipeline(spec, client=client))
    except Exception as exc:  # pragma: no cover - surfaced through session
        logger.exception("Compile failed for project %s", project_id)
        failure_entry = {
            "stage": "compile",
            "status": "error",
            "timestamp": datetime.now(ZoneInfo(tz_name)).isoformat(),
        }
        try:
            with progress_log.open("a", encoding="utf-8") as fp:
                fp.write(json.dumps(failure_entry, ensure_ascii=False) + "\n")
        except Exception:
            logger.exception(
                "Failed to append compile failure entry; progress_log=%s", progress_log
            )
        post_update(f"Compile failed: {exc}", status="error")
        return

    requested_end_stage = spec.end_stage or "compile_html"
    html_info: dict[str, Any] | None = result.get("html") if isinstance(result, dict) else None
    compiled_rel = ""
    run_root = output_dir
    if html_info:
        run_root = Path(html_info.get("run_root", output_dir)).resolve()
        index_path = html_info.get("index_path") or html_info.get("html_path")
        if index_path:
            html_path = Path(index_path).resolve()
            try:
                compiled_rel = html_path.relative_to(project_root).as_posix()
            except Exception:
                compiled_rel = html_path.as_posix()
        if placement in {"top", "bottom"} and spec.page_images:
            post_update(
                f"Attached {len(spec.page_images)} generated page image reference(s) to compile input ({placement})."
            )
    update_fields = ["artifact_root", "updated_at"]
    if compiled_rel:
        project.compiled_path = compiled_rel.replace("\\", "/")
        update_fields.append("compiled_path")
    elif requested_end_stage == "compile_html":
        # compile_html was requested but no HTML was produced; clear compiled path.
        project.compiled_path = ""
        update_fields.append("compiled_path")
    project.artifact_root = str(project_root).replace("\\", "/")
    project.save(update_fields=update_fields)

    final_status = "success" if (compiled_rel or requested_end_stage != "compile_html") else "error"
    completion_entry = {
        "stage": "compile",
        "status": final_status,
        "timestamp": datetime.now(ZoneInfo(tz_name)).isoformat(),
    }
    try:
        with progress_log.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(completion_entry, ensure_ascii=False) + "\n")
    except Exception:
        logger.exception("Failed to append compile completion entry; progress_log=%s", progress_log)

    if compiled_rel:
        outcome_message = "Project compiled to HTML."
    elif requested_end_stage != "compile_html":
        outcome_message = f"Pipeline finished successfully at stage: {requested_end_stage}."
    else:
        outcome_message = "Compilation finished but no HTML was produced."
    post_update(outcome_message, status="finished" if final_status == "success" else "error")


@login_required
def compile_project(request: HttpRequest, pk: int) -> HttpResponse:
    project = _get_project_for_user(pk=pk, user=request.user, min_role=ProjectCollaborator.ROLE_ANNOTATOR)
    project_root = project.artifact_dir().resolve()
    _persist_project_source(project)
    output_dir = _prepare_output_dir(project).resolve()
    stage_dir = output_dir / "stages"
    stage_dir.mkdir(parents=True, exist_ok=True)

    try:
        profile = request.user.profile
        timezone_name = profile.timezone or "UTC"
    except Profile.DoesNotExist:
        timezone_name = "UTC"

    start_stage = request.POST.get("start_stage") or (
        "text_gen" if project.input_mode == Project.INPUT_DESCRIPTION else "segmentation_phase_1"
    )
    if start_stage not in PIPELINE_ORDER:
        messages.error(request, "Unknown start stage.")
        return redirect("project-detail", pk=project.pk)
    end_stage = request.POST.get("end_stage") or "compile_html"
    if end_stage not in PIPELINE_ORDER:
        messages.error(request, "Unknown end stage.")
        return redirect("project-detail", pk=project.pk)
    if PIPELINE_ORDER.index(end_stage) < PIPELINE_ORDER.index(start_stage):
        messages.error(request, "End stage must come after the selected start stage.")
        return redirect("project-detail", pk=project.pk)

    page_image_placement = (
        request.POST.get("page_image_placement")
        or project.page_image_placement
        or "none"
    ).strip().lower()
    if page_image_placement not in PAGE_IMAGE_PLACEMENT_CHOICES:
        messages.error(request, "Unknown page image placement option.")
        return redirect("project-detail", pk=project.pk)

    ai_model = request.POST.get("ai_model") or project.ai_model or DEFAULT_MODEL
    if ai_model not in AI_MODEL_CHOICES:
        messages.error(request, "Unknown AI model selection.")
        return redirect("project-detail", pk=project.pk)
    if ai_model != project.ai_model:
        project.ai_model = ai_model
        project.save(update_fields=["ai_model", "updated_at"])

    segmentation_method = (request.POST.get("segmentation_method") or project.segmentation_method or "auto").strip().lower()
    romanization_method = (request.POST.get("romanization_method") or project.romanization_method or "auto").strip().lower()
    if segmentation_method not in SEGMENTATION_METHOD_CHOICES:
        messages.error(request, "Unknown segmentation method option.")
        return redirect("project-detail", pk=project.pk)
    if romanization_method not in ROMANIZATION_METHOD_CHOICES:
        messages.error(request, "Unknown romanization method option.")
        return redirect("project-detail", pk=project.pk)
    update_fields: list[str] = []
    if segmentation_method != project.segmentation_method:
        project.segmentation_method = segmentation_method
        update_fields.append("segmentation_method")
    if romanization_method != project.romanization_method:
        project.romanization_method = romanization_method
        update_fields.append("romanization_method")
    if update_fields:
        project.save(update_fields=update_fields + ["updated_at"])

    text: str | None = None
    text_obj: dict[str, Any] | None = None
    # Always define ``description`` so queued tasks receive a predictable
    # argument, avoiding NameError if the start stage skips description entry.
    description: str | None = (project.description or "").strip()

    if start_stage == "text_gen":
        if not description:
            messages.error(request, "Please provide a description to generate text.")
            return redirect("project-detail", pk=project.pk)
    elif start_stage == "segmentation_phase_1":
        text = (project.source_text or "").strip()
        if not text:
            source_run = _find_run_with_stage(project, "text_gen")
            if source_run:
                generated = _load_stage_payload(project, "text_gen", run_dir=source_run)
                if isinstance(generated, dict):
                    text = str(generated.get("surface") or "").strip()
                try:
                    _copy_run_artifacts(source_run, output_dir)
                    progress_log = output_dir / "stages" / "progress.jsonl"
                    if progress_log.exists():
                        progress_log.unlink()
                except Exception:
                    logger.exception("Failed to copy prior run artifacts from %s", source_run)
        if not text:
            messages.error(
                request,
                "Please provide source text to segment, or run text_gen first to create source text.",
            )
            return redirect("project-detail", pk=project.pk)
    else:
        # Start from a persisted intermediate produced by a previous run.
        upstream_index = PIPELINE_ORDER.index(start_stage) - 1
        upstream_stage = PIPELINE_ORDER[upstream_index]
        source_run = _find_run_with_stage(project, upstream_stage)
        if not source_run:
            messages.error(
                request,
                f"Cannot start at {start_stage}: missing upstream stage output ({upstream_stage}).",
            )
            return redirect("project-detail", pk=project.pk)

        text_obj = _load_stage_payload(project, upstream_stage, run_dir=source_run)
        if text_obj is None:
            messages.error(
                request,
                f"Cannot start at {start_stage}: missing upstream stage output ({upstream_stage}).",
            )
            return redirect("project-detail", pk=project.pk)

        try:
            _copy_run_artifacts(source_run, output_dir)
            # Each run gets its own progress trail; start with a clean slate.
            progress_log = output_dir / "stages" / "progress.jsonl"
            if progress_log.exists():
                progress_log.unlink()
        except Exception:
            logger.exception("Failed to copy prior run artifacts from %s", source_run)

    task_type = f"compile_project_{project.pk}"
    report_id = str(uuid.uuid4())

    async_task(
        _run_compile_task,
        project.pk,
        request.user.id,
        str(output_dir),
        str(project_root),
        start_stage,
        timezone_name,
        description,
        text,
        text_obj,
        report_id,
        task_type,
        ai_model,
        end_stage,
        page_image_placement,
        segmentation_method,
        romanization_method,
        q_options={"sync": False},
    )

    return redirect("project-compile-monitor", pk=project.pk, report_id=report_id)


@login_required
def set_page_image_placement(request: HttpRequest, pk: int) -> HttpResponse:
    project = _get_project_for_user(pk=pk, user=request.user, min_role=ProjectCollaborator.ROLE_OWNER)
    placement = (request.POST.get("page_image_placement") or "none").strip().lower()
    if placement not in PAGE_IMAGE_PLACEMENT_CHOICES:
        messages.error(request, "Unknown page image placement option.")
        return redirect("project-detail", pk=project.pk)
    if placement != project.page_image_placement:
        project.page_image_placement = placement
        project.save(update_fields=["page_image_placement", "updated_at"])
    messages.success(request, f"Saved page image placement setting: {placement}.")
    return redirect("project-detail", pk=project.pk)


@login_required
def set_processing_options(request: HttpRequest, pk: int) -> HttpResponse:
    project = _get_project_for_user(pk=pk, user=request.user, min_role=ProjectCollaborator.ROLE_OWNER)
    segmentation_method = (request.POST.get("segmentation_method") or project.segmentation_method or "auto").strip().lower()
    romanization_method = (request.POST.get("romanization_method") or project.romanization_method or "auto").strip().lower()
    if segmentation_method not in SEGMENTATION_METHOD_CHOICES:
        messages.error(request, "Unknown segmentation method option.")
        return redirect("project-detail", pk=project.pk)
    if romanization_method not in ROMANIZATION_METHOD_CHOICES:
        messages.error(request, "Unknown romanization method option.")
        return redirect("project-detail", pk=project.pk)
    update_fields: list[str] = []
    if segmentation_method != project.segmentation_method:
        project.segmentation_method = segmentation_method
        update_fields.append("segmentation_method")
    if romanization_method != project.romanization_method:
        project.romanization_method = romanization_method
        update_fields.append("romanization_method")
    if update_fields:
        project.save(update_fields=update_fields + ["updated_at"])
    messages.success(request, "Saved language-processing options.")
    return redirect("project-detail", pk=project.pk)


@login_required
def compile_monitor(request: HttpRequest, pk: int, report_id: str) -> HttpResponse:
    project = _get_project_for_user(pk=pk, user=request.user, min_role=ProjectCollaborator.ROLE_ANNOTATOR)
    return render(
        request,
        "projects/compile_monitor.html",
        {"project": project, "report_id": report_id},
    )


@login_required
def compile_status(request: HttpRequest, pk: int, report_id: str) -> JsonResponse:
    project = _get_project_for_user(pk=pk, user=request.user, min_role=ProjectCollaborator.ROLE_ANNOTATOR)
    updates = (
        TaskUpdate.objects.filter(report_id=report_id, user=request.user)
        .order_by("timestamp")
        .all()
    )

    unread = [u for u in updates if not u.read]
    messages_out = [u.message for u in unread]
    status = "running"

    for u in unread:
        if u.status == "error":
            status = "error"
            break
        if u.status == "finished":
            status = "finished"

    TaskUpdate.objects.filter(pk__in=[u.pk for u in unread]).update(read=True)

    if status == "running" and unread == []:
        # Check the latest status so the monitor can exit even if all updates
        # have been consumed.
        last = updates.last()
        if last and last.status in {"error", "finished"}:
            status = last.status

    if status in {"error", "finished"} and messages_out:
        level = messages.ERROR if status == "error" else messages.INFO
        # Surface the last update to the project detail page when the monitor
        # redirects after completion.
        messages.add_message(request, level, messages_out[-1])

    return JsonResponse({"messages": messages_out, "status": status, "project": project.pk})



def _compiled_page_one_path(project: Project) -> str | None:
    """Return compiled page_1 path when available."""

    compiled = (project.compiled_path or "").strip()
    if not compiled:
        return None
    compiled_path = Path(compiled)
    page_one = compiled_path.with_name("page_1.html")
    base = Path(project.artifact_root or project.artifact_dir()).resolve()
    if (base / page_one).exists():
        return page_one.as_posix()
    return compiled_path.as_posix()


@login_required
def content_list(request: HttpRequest) -> HttpResponse:
    """Search/browse published projects."""

    title = (request.GET.get("title") or "").strip()
    text_language = (request.GET.get("text_language") or "").strip()
    annotation_language = (request.GET.get("annotation_language") or "").strip()
    date_posted = (request.GET.get("date_posted") or "any").strip()
    if date_posted not in CONTENT_DATE_FILTERS:
        date_posted = "any"

    qs = Project.objects.filter(is_published=True)
    if title:
        qs = qs.filter(title__icontains=title)
    if text_language:
        qs = qs.filter(language__iexact=text_language)
    if annotation_language:
        qs = qs.filter(target_language__iexact=annotation_language)

    window = CONTENT_DATE_FILTERS.get(date_posted)
    if window is not None:
        cutoff = django_timezone.now() - window
        qs = qs.filter(published_at__gte=cutoff)

    projects = list(qs.order_by("-published_at", "-updated_at")[:200])
    return render(
        request,
        "projects/content_list.html",
        {
            "projects": projects,
            "filters": {
                "title": title,
                "text_language": text_language,
                "annotation_language": annotation_language,
                "date_posted": date_posted,
            },
            "date_options": [
                ("any", "Any time"),
                ("last_3_days", "Last 3 days"),
                ("last_month", "Last month"),
                ("last_3_months", "Last 3 months"),
                ("last_year", "Last year"),
            ],
        },
    )


@login_required
def content_detail(request: HttpRequest, pk: int) -> HttpResponse:
    """Show metadata for a published project and link to page 1."""

    project = get_object_or_404(Project, pk=pk, is_published=True)
    Project.objects.filter(pk=project.pk).update(access_count=F("access_count") + 1)

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip().lower()
        if action == "comment":
            body = (request.POST.get("body") or "").strip()
            if body:
                ContentComment.objects.create(project=project, author=request.user, body=body)
                messages.success(request, "Comment posted.")
            else:
                messages.error(request, "Comment cannot be empty.")
        elif action == "rate":
            value = (request.POST.get("value") or "").strip().lower()
            note = (request.POST.get("comment") or "").strip()
            if value in {ContentRating.VALUE_UP, ContentRating.VALUE_DOWN}:
                ContentRating.objects.update_or_create(
                    project=project,
                    author=request.user,
                    defaults={"value": value, "comment": note},
                )
                messages.success(request, "Rating saved.")
            else:
                messages.error(request, "Unknown rating value.")
        return redirect("content-detail", pk=project.pk)

    project.refresh_from_db(fields=["access_count"])
    page_one = _compiled_page_one_path(project)
    comments = project.content_comments.filter(is_hidden=False).select_related("author")[:100]
    ratings = project.content_ratings.all()
    up_count = ratings.filter(value=ContentRating.VALUE_UP).count()
    down_count = ratings.filter(value=ContentRating.VALUE_DOWN).count()
    user_rating = ratings.filter(author=request.user).first()

    return render(
        request,
        "projects/content_detail.html",
        {
            "project": project,
            "page_one_path": page_one,
            "comments": comments,
            "up_count": up_count,
            "down_count": down_count,
            "user_rating": user_rating,
            "published_exercise_sets": project.exercise_sets.filter(is_published=True).order_by("-updated_at"),
        },
    )

@login_required
def toggle_publish(request: HttpRequest, pk: int) -> HttpResponse:
    project = _get_project_for_user(pk=pk, user=request.user, min_role=ProjectCollaborator.ROLE_OWNER)
    project.is_published = not project.is_published
    if project.is_published and project.published_at is None:
        project.published_at = django_timezone.now()
    project.save(update_fields=["is_published", "published_at", "updated_at"])
    state = "published" if project.is_published else "unpublished"
    messages.info(request, f"Project {state}.")
    return redirect("project-detail", pk=project.pk)


@login_required
@xframe_options_sameorigin
def serve_compiled(request: HttpRequest, pk: int, path: str) -> HttpResponse:
    """Serve compiled artifacts from a project's run directory.

    Mirrors the C-LARA behaviour so concordance iframes and relative links work
    without refusing the connection.
    """

    project = get_object_or_404(Project, pk=pk)
    if project.owner != request.user and not project.is_published:
        raise Http404()

    base = Path(project.artifact_root or project.artifact_dir()).resolve()
    safe_path = Path(unquote(path))
    file_path = (base / safe_path).resolve()

    try:
        file_path.relative_to(base)
    except ValueError:
        raise Http404()

    if not file_path.exists():
        raise Http404()

    content_type, _ = mimetypes.guess_type(unquote(str(file_path)))
    with open(file_path, "rb") as fp:
        data = fp.read()
    return HttpResponse(data, content_type=content_type or "application/octet-stream")


def _extract_segment_candidates_for_cloze(run_dir: Path) -> list[dict[str, Any]]:
    stage_names = ["gloss", "lemma", "mwe", "translation", "segmentation_phase_2"]
    payload = None
    for stage in stage_names:
        path = run_dir / "stages" / f"{stage}.json"
        if path.exists():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                break
            except Exception:
                continue
    if not payload:
        return []

    candidates: list[dict[str, Any]] = []
    for page in payload.get("pages", []):
        page_number = page.get("page_number", 1)
        for idx, seg in enumerate(page.get("segments", [])):
            tokens = seg.get("tokens", [])
            words: list[str] = []
            for t in tokens:
                surface = (t.get("surface") or "").strip()
                ann = t.get("annotations", {}) or {}
                if not surface:
                    continue
                if ann.get("mwe_id"):
                    continue
                if any(ch.isalpha() for ch in surface):
                    words.append(surface)
            if words:
                seg_text = "".join(t.get("surface", "") for t in tokens).strip() or seg.get("surface", "")
                candidates.append(
                    {
                        "page_number": page_number,
                        "segment_index": idx,
                        "segment_text": seg_text,
                        "words": words,
                    }
                )
    return candidates


def _extract_token_candidates_for_flashcards(run_dir: Path) -> list[dict[str, Any]]:
    stage_names = ["gloss", "lemma", "mwe", "translation", "segmentation_phase_2"]
    payload = None
    for stage in stage_names:
        path = run_dir / "stages" / f"{stage}.json"
        if path.exists():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                break
            except Exception:
                continue
    if not payload:
        return []

    candidates: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for page in payload.get("pages", []):
        page_number = page.get("page_number", 1)
        for seg_idx, seg in enumerate(page.get("segments", [])):
            tokens = seg.get("tokens", [])
            for tok_idx, token in enumerate(tokens):
                surface = (token.get("surface") or "").strip()
                if not surface or not any(ch.isalpha() for ch in surface):
                    continue
                ann = token.get("annotations", {}) or {}
                if ann.get("mwe_id"):
                    continue
                gloss = str(ann.get("gloss") or "").strip()
                if not gloss:
                    continue
                pair = (surface.lower(), gloss.lower())
                if pair in seen:
                    continue
                seen.add(pair)
                candidates.append(
                    {
                        "page_number": page_number,
                        "segment_index": seg_idx,
                        "token_index": tok_idx,
                        "source_word": surface,
                        "target_gloss": gloss,
                        "segment_text": "".join(t.get("surface", "") for t in tokens).strip() or seg.get("surface", ""),
                    }
                )
    return candidates


async def _generate_cloze_item(
    client: OpenAIClient,
    model: str,
    theme: str,
    candidate: dict[str, Any],
    order_index: int,
) -> dict[str, Any]:
    target_word = candidate["words"][order_index % len(candidate["words"])]
    segment_text = candidate["segment_text"]
    cloze_text = segment_text.replace(target_word, "____", 1)
    prompt = f"""
Create exactly 3 plausible distractors for a cloze exercise.
Theme: {theme}
Segment: {segment_text}
Correct answer: {target_word}
Each distractor must make the sentence clearly incorrect in context.
Do not produce near-synonyms that could still fit.

Return JSON with:
- distractors: array of 3 strings
- rationale: object mapping each distractor string to one short rationale
"""
    try:
        data = await client.chat_json(prompt, model=model)
    except Exception:
        data = {}
    distractors = [str(x).strip() for x in (data.get("distractors") or []) if str(x).strip()]
    distractors = [d for d in distractors if d.lower() != target_word.lower()]
    distractors = distractors[:3]
    while len(distractors) < 3:
        distractors.append(f"{target_word}_{len(distractors)+1}")
    options = [target_word] + distractors
    return {
        "order_index": order_index,
        "page_number": candidate["page_number"],
        "segment_index": candidate["segment_index"],
        "segment_text": segment_text,
        "prompt": cloze_text,
        "answer": target_word,
        "options": options,
        "rationale": data.get("rationale") if isinstance(data.get("rationale"), dict) else {},
    }


async def _generate_flashcard_item(
    client: OpenAIClient,
    model: str,
    theme: str,
    candidate: dict[str, Any],
    order_index: int,
) -> dict[str, Any]:
    source_word = candidate["source_word"]
    correct_gloss = candidate["target_gloss"]
    segment_text = candidate["segment_text"]
    prompt = f"""
Create exactly 3 plausible distractor translations/glosses for a flashcard multiple-choice item.
Theme: {theme}
Source word: {source_word}
Correct gloss: {correct_gloss}
Segment context: {segment_text}
Return JSON with:
- distractors: array of 3 strings
- rationale: object mapping each distractor to a short reason
"""
    try:
        data = await client.chat_json(prompt, model=model)
    except Exception:
        data = {}
    distractors = [str(x).strip() for x in (data.get("distractors") or []) if str(x).strip()]
    distractors = [d for d in distractors if d.lower() != correct_gloss.lower()]
    distractors = distractors[:3]
    while len(distractors) < 3:
        distractors.append(f"{correct_gloss}_{len(distractors)+1}")
    options = [correct_gloss] + distractors
    return {
        "order_index": order_index,
        "page_number": candidate["page_number"],
        "segment_index": candidate["segment_index"],
        "segment_text": segment_text,
        "prompt": f"What is the best gloss/translation for: {source_word}?",
        "answer": correct_gloss,
        "options": options,
        "rationale": data.get("rationale") if isinstance(data.get("rationale"), dict) else {},
    }


@login_required
def generate_cloze_exercises(request: HttpRequest, pk: int) -> HttpResponse:
    project = _get_project_for_user(pk=pk, user=request.user, min_role=ProjectCollaborator.ROLE_ANNOTATOR)
    run_dir = _resolve_run_dir(project)
    if run_dir is None or not run_dir.exists():
        messages.error(request, "Please run the pipeline first to generate stage artifacts.")
        return redirect("project-detail", pk=project.pk)

    if request.method == "POST":
        form = ClozeExerciseSetForm(request.POST, ai_model_choices=AI_MODEL_CHOICES)
        if form.is_valid():
            theme = form.cleaned_data["theme"]
            item_count = form.cleaned_data["item_count"]
            model = form.cleaned_data.get("ai_model") or project.ai_model or DEFAULT_MODEL

            candidates = _extract_segment_candidates_for_cloze(run_dir)
            if not candidates:
                messages.error(request, "Could not find suitable segments/tokens for cloze generation.")
                return redirect("project-detail", pk=project.pk)

            selected = candidates[:item_count]
            ex_set = ExerciseSet.objects.create(
                project=project,
                exercise_type=ExerciseSet.TYPE_CLOZE,
                theme=theme,
                title=f"{project.title} — Cloze ({theme})",
                status=ExerciseSet.STATUS_DRAFT,
                created_by=request.user,
            )

            async def _run() -> list[dict[str, Any]]:
                client = _build_ai_client(model)
                tasks = [
                    _generate_cloze_item(client, model, theme, cand, idx)
                    for idx, cand in enumerate(selected)
                ]
                return await asyncio.gather(*tasks)

            items = asyncio.run(_run())
            ExerciseItem.objects.bulk_create(
                [
                    ExerciseItem(
                        exercise_set=ex_set,
                        order_index=item["order_index"],
                        page_number=item["page_number"],
                        segment_index=item["segment_index"],
                        segment_text=item["segment_text"],
                        prompt=item["prompt"],
                        answer=item["answer"],
                        options=item["options"],
                        rationale=item["rationale"],
                    )
                    for item in items
                ]
            )
            ex_set.status = ExerciseSet.STATUS_READY
            ex_set.save(update_fields=["status", "updated_at"])
            messages.success(request, f"Generated {len(items)} cloze items.")
            return redirect("exercise-set-detail", set_id=ex_set.id)
    else:
        form = ClozeExerciseSetForm(
            initial={"ai_model": project.ai_model or DEFAULT_MODEL},
            ai_model_choices=AI_MODEL_CHOICES,
        )

    return render(
        request,
        "projects/exercise_generate_cloze.html",
        {"project": project, "form": form},
    )


@login_required
def generate_flashcard_exercises(request: HttpRequest, pk: int) -> HttpResponse:
    project = _get_project_for_user(pk=pk, user=request.user, min_role=ProjectCollaborator.ROLE_ANNOTATOR)
    run_dir = _resolve_run_dir(project)
    if run_dir is None or not run_dir.exists():
        messages.error(request, "Please run the pipeline first to generate stage artifacts.")
        return redirect("project-detail", pk=project.pk)

    if request.method == "POST":
        form = FlashcardExerciseSetForm(request.POST, ai_model_choices=AI_MODEL_CHOICES)
        if form.is_valid():
            theme = form.cleaned_data["theme"]
            item_count = form.cleaned_data["item_count"]
            model = form.cleaned_data.get("ai_model") or project.ai_model or DEFAULT_MODEL

            candidates = _extract_token_candidates_for_flashcards(run_dir)
            if not candidates:
                messages.error(
                    request,
                    "Could not find suitable glossed tokens for flashcard generation. Run glossing first.",
                )
                return redirect("project-detail", pk=project.pk)

            selected = candidates[:item_count]
            ex_set = ExerciseSet.objects.create(
                project=project,
                exercise_type=ExerciseSet.TYPE_FLASHCARD,
                theme=theme,
                title=f"{project.title} — Flashcards ({theme})",
                status=ExerciseSet.STATUS_DRAFT,
                created_by=request.user,
            )

            async def _run() -> list[dict[str, Any]]:
                client = _build_ai_client(model)
                tasks = [
                    _generate_flashcard_item(client, model, theme, cand, idx)
                    for idx, cand in enumerate(selected)
                ]
                return await asyncio.gather(*tasks)

            items = asyncio.run(_run())
            ExerciseItem.objects.bulk_create(
                [
                    ExerciseItem(
                        exercise_set=ex_set,
                        order_index=item["order_index"],
                        page_number=item["page_number"],
                        segment_index=item["segment_index"],
                        segment_text=item["segment_text"],
                        prompt=item["prompt"],
                        answer=item["answer"],
                        options=item["options"],
                        rationale=item["rationale"],
                    )
                    for item in items
                ]
            )
            ex_set.status = ExerciseSet.STATUS_READY
            ex_set.save(update_fields=["status", "updated_at"])
            messages.success(request, f"Generated {len(items)} flashcard items.")
            return redirect("exercise-set-detail", set_id=ex_set.id)
    else:
        form = FlashcardExerciseSetForm(
            initial={"ai_model": project.ai_model or DEFAULT_MODEL},
            ai_model_choices=AI_MODEL_CHOICES,
        )

    return render(
        request,
        "projects/exercise_generate_flashcard.html",
        {"project": project, "form": form},
    )


@login_required
def exercise_set_detail(request: HttpRequest, set_id: int) -> HttpResponse:
    ex_set = get_object_or_404(ExerciseSet.objects.select_related("project"), pk=set_id)
    project = ex_set.project
    if project.owner != request.user and not ex_set.is_published:
        raise Http404()
    return render(
        request,
        "projects/exercise_set_detail.html",
        {"exercise_set": ex_set, "items": ex_set.items.all(), "project": project},
    )


@login_required
def exercise_set_play(request: HttpRequest, set_id: int) -> HttpResponse:
    ex_set = get_object_or_404(ExerciseSet.objects.select_related("project"), pk=set_id)
    project = ex_set.project
    if project.owner != request.user and not ex_set.is_published:
        raise Http404()
    items = list(ex_set.items.all())
    if not items:
        return render(request, "projects/exercise_set_play.html", {"exercise_set": ex_set, "project": project, "done": True})

    idx = int(request.GET.get("i", "0") or "0")
    idx = max(0, min(idx, len(items) - 1))
    current = items[idx]
    feedback = None
    selected = None
    if request.method == "POST":
        selected = (request.POST.get("choice") or "").strip()
        feedback = {
            "selected": selected,
            "correct": current.answer,
            "is_correct": selected == current.answer,
        }
    next_index = idx + 1 if idx + 1 < len(items) else None
    return render(
        request,
        "projects/exercise_set_play.html",
        {
            "exercise_set": ex_set,
            "project": project,
            "item": current,
            "index": idx,
            "total": len(items),
            "feedback": feedback,
            "next_index": next_index,
            "done": False,
        },
    )


@login_required
def publish_exercise_set(request: HttpRequest, set_id: int) -> HttpResponse:
    ex_set = get_object_or_404(ExerciseSet.objects.select_related("project"), pk=set_id)
    _get_project_for_user(pk=ex_set.project_id, user=request.user, min_role=ProjectCollaborator.ROLE_OWNER)
    ex_set.is_published = not ex_set.is_published
    ex_set.status = ExerciseSet.STATUS_PUBLISHED if ex_set.is_published else ExerciseSet.STATUS_READY
    ex_set.save(update_fields=["is_published", "status", "updated_at"])
    return redirect("exercise-set-detail", set_id=ex_set.id)


@login_required
def published_exercises_for_project(request: HttpRequest, pk: int) -> HttpResponse:
    project = get_object_or_404(Project, pk=pk, is_published=True)
    sets = project.exercise_sets.filter(is_published=True).order_by("-updated_at")
    return render(request, "projects/published_exercises.html", {"project": project, "exercise_sets": sets})



@login_required
def download_project_bundle(request: HttpRequest, pk: int) -> HttpResponse:
    """Download a self-contained zip with compiled HTML, audio and images."""

    project = _get_project_for_user(pk=pk, user=request.user, min_role=ProjectCollaborator.ROLE_ANNOTATOR)
    run_dir = _resolve_run_dir(project)
    if run_dir is None or not run_dir.exists():
        messages.error(request, "No compiled run is available yet. Please compile the project first.")
        return redirect("project-detail", pk=project.pk)

    artifact_root = project.artifact_dir().resolve()
    images_dir = artifact_root / "images"

    has_html = (run_dir / "html").exists()
    has_images = images_dir.exists()
    if not has_html and not has_images:
        messages.error(
            request,
            "Could not find compiled HTML or generated images to include in a bundle.",
        )
        return redirect("project-detail", pk=project.pk)

    safe_title = slugify(project.title) or f"project-{project.pk}"
    bundle_root = Path(f"{safe_title}-bundle")

    spool = tempfile.SpooledTemporaryFile(max_size=10 * 1024 * 1024, mode="w+b")
    created_at = datetime.now(timezone.utc)
    with zipfile.ZipFile(spool, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        run_file_count = _write_tree_to_zip(
            zf,
            run_dir,
            bundle_root / "runs" / run_dir.name,
        )
        image_file_count = _write_tree_to_zip(zf, images_dir, bundle_root / "images")

        html_dir = run_dir / "html"
        start_page = "page_1.html" if (html_dir / "page_1.html").exists() else "index.html"
        start_page_href = f"runs/{run_dir.name}/html/{start_page}"
        audio_dir = run_dir / "audio"
        audio_file_count = sum(1 for p in audio_dir.rglob("*") if p.is_file()) if audio_dir.exists() else 0

        media_notes: list[str] = []
        if audio_file_count:
            media_notes.append(f"<li>Audio files: {audio_file_count}</li>")
        else:
            media_notes.append("<li>Audio files: none included in this bundle.</li>")

        if image_file_count:
            media_notes.append(f"<li>Image files: {image_file_count}</li>")
        else:
            media_notes.append("<li>Image files: none included in this bundle.</li>")

        readme_html = f"""<!doctype html>
<html lang="en"> 
  <head>
    <meta charset="utf-8" />
    <title>{escape(project.title)} bundle</title>
  </head>
  <body>
    <h1>C-LARA project bundle</h1>
    <p><strong>Project:</strong> {escape(project.title)}</p>
    <p><strong>Project ID:</strong> {project.pk}</p>
    <p><strong>Run:</strong> {escape(run_dir.name)}</p>
    <p><strong>Created (UTC):</strong> {created_at.isoformat(timespec='seconds')}</p>
    <p><strong>Total bundled files:</strong> {run_file_count + image_file_count}</p>

    <p><a href="{escape(start_page_href)}">Open the compiled text (page 1)</a></p>

    <h2>Bundle contents</h2>
    <ul>
      <li><code>runs/&lt;run_id&gt;/html</code>: compiled HTML pages</li>
      <li><code>runs/&lt;run_id&gt;/audio</code>: copied audio files used by the HTML</li>
      <li><code>images</code>: generated image assets (if any)</li>
      {''.join(media_notes)}
    </ul>
  </body>
</html>
"""
        zf.writestr((bundle_root / "README.html").as_posix(), readme_html)

    spool.seek(0)

    filename = f"{safe_title}-{run_dir.name}.zip"
    return FileResponse(spool, as_attachment=True, filename=filename, content_type="application/zip")


@login_required
def download_project_source_bundle(request: HttpRequest, pk: int) -> HttpResponse:
    """Download a source-focused bundle for latest run artifacts."""

    project = _get_project_for_user(pk=pk, user=request.user, min_role=ProjectCollaborator.ROLE_ANNOTATOR)
    run_dir = _resolve_run_dir(project)
    if run_dir is None or not run_dir.exists():
        messages.error(request, "No run is available yet. Please run the pipeline first.")
        return redirect("project-detail", pk=project.pk)

    stages_dir = run_dir / "stages"
    if not stages_dir.exists():
        messages.error(request, "Latest run does not contain stage artifacts to export.")
        return redirect("project-detail", pk=project.pk)

    safe_title = slugify(project.title) or f"project-{project.pk}"
    bundle_root = Path(f"{safe_title}-source-bundle")
    artifact_root = project.artifact_dir().resolve()
    created_at = datetime.now(timezone.utc)
    run_name = run_dir.name

    style = ProjectImageStyle.objects.filter(project=project).first()
    elements = list(ProjectImageElement.objects.filter(project=project).order_by("id").values())
    pages = list(ProjectImagePage.objects.filter(project=project).order_by("page_number", "id").values())

    style_data = None
    if style:
        style_data = {
            "style_brief": style.style_brief,
            "expanded_style_description": style.expanded_style_description,
            "representative_excerpt": style.representative_excerpt,
            "sample_image_prompt": style.sample_image_prompt,
            "sample_image_path": style.sample_image_path,
            "sample_image_revised_prompt": style.sample_image_revised_prompt,
            "sample_image_model": style.sample_image_model,
            "ai_model": style.ai_model,
            "status": style.status,
        }

    image_rel_paths: set[str] = set()
    if style and style.sample_image_path:
        image_rel_paths.add(style.sample_image_path)
    for row in elements:
        if row.get("image_path"):
            image_rel_paths.add(str(row["image_path"]))
    for row in pages:
        if row.get("image_path"):
            image_rel_paths.add(str(row["image_path"]))

    spool = tempfile.SpooledTemporaryFile(max_size=10 * 1024 * 1024, mode="w+b")
    with zipfile.ZipFile(spool, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        manifest = {
            "schema_version": "1.0",
            "created_utc": created_at.isoformat(timespec="seconds"),
            "source_project_id": project.pk,
            "source_project_title": project.title,
            "run_id": run_name,
        }
        zf.writestr((bundle_root / "manifest.json").as_posix(), json.dumps(manifest, ensure_ascii=False, indent=2))

        metadata = {
            "title": project.title,
            "description": project.description,
            "source_text": project.source_text,
            "input_mode": project.input_mode,
            "language": project.language,
            "target_language": project.target_language,
            "ai_model": project.ai_model,
            "page_image_placement": project.page_image_placement,
            "segmentation_method": project.segmentation_method,
            "romanization_method": project.romanization_method,
        }
        zf.writestr((bundle_root / "project" / "metadata.json").as_posix(), json.dumps(metadata, ensure_ascii=False, indent=2))

        pipeline_config = {
            "ai_model": project.ai_model,
            "segmentation_method": project.segmentation_method,
            "romanization_method": project.romanization_method,
            "page_image_placement": project.page_image_placement,
        }
        zf.writestr((bundle_root / "project" / "pipeline_config.json").as_posix(), json.dumps(pipeline_config, ensure_ascii=False, indent=2))

        source_dir = artifact_root / "source"
        if source_dir.exists():
            _write_tree_to_zip(zf, source_dir, bundle_root / "text")
        else:
            zf.writestr((bundle_root / "text" / "source_text.txt").as_posix(), project.source_text or "")
            zf.writestr((bundle_root / "text" / "description.txt").as_posix(), project.description or "")

        _write_tree_to_zip(zf, stages_dir, bundle_root / "stages")
        zf.writestr((bundle_root / "runs" / "latest_run_summary.json").as_posix(), json.dumps({"run_id": run_name}, ensure_ascii=False, indent=2))

        zf.writestr((bundle_root / "images" / "style.json").as_posix(), json.dumps(style_data, ensure_ascii=False, indent=2))
        zf.writestr((bundle_root / "images" / "elements.json").as_posix(), json.dumps(elements, ensure_ascii=False, indent=2))
        zf.writestr((bundle_root / "images" / "pages.json").as_posix(), json.dumps(pages, ensure_ascii=False, indent=2))

        for rel in sorted(image_rel_paths):
            abs_path = (artifact_root / rel).resolve()
            try:
                abs_path.relative_to(artifact_root)
            except ValueError:
                continue
            if abs_path.exists() and abs_path.is_file():
                zf.write(abs_path, arcname=(bundle_root / "assets" / rel).as_posix())

    spool.seek(0)
    filename = f"{safe_title}-source-{run_name}.zip"
    return FileResponse(spool, as_attachment=True, filename=filename, content_type="application/zip")


@login_required
def import_project_source_bundle(request: HttpRequest) -> HttpResponse:
    """Import a source bundle and always create a new project."""

    if request.method != "POST":
        return redirect("project-list")

    upload = request.FILES.get("source_bundle")
    if upload is None:
        messages.error(request, "Please select a ZIP file to import.")
        return redirect("project-list")

    try:
        zf = zipfile.ZipFile(upload)
    except Exception:
        messages.error(request, "Could not read ZIP file.")
        return redirect("project-list")

    with zf:
        names = zf.namelist()
        if not names:
            messages.error(request, "ZIP file is empty.")
            return redirect("project-list")

        root = Path(names[0]).parts[0]
        metadata = _safe_zip_read_json(zf, f"{root}/project/metadata.json")
        if not metadata:
            messages.error(request, "Bundle is missing project metadata.")
            return redirect("project-list")

        title = _build_unique_import_title(request.user, metadata.get("title", "Imported project"))
        project = Project.objects.create(
            owner=request.user,
            title=title,
            description=(metadata.get("description") or "")[:100000],
            source_text=(metadata.get("source_text") or "")[:1000000],
            input_mode=metadata.get("input_mode") if metadata.get("input_mode") in {Project.INPUT_DESCRIPTION, Project.INPUT_SOURCE} else Project.INPUT_SOURCE,
            language=(metadata.get("language") or "en")[:16],
            target_language=(metadata.get("target_language") or "fr")[:16],
            ai_model=(metadata.get("ai_model") or DEFAULT_MODEL)[:64],
            page_image_placement=(metadata.get("page_image_placement") or "none")[:16],
            segmentation_method=(metadata.get("segmentation_method") or "auto")[:32],
            romanization_method=(metadata.get("romanization_method") or "auto")[:32],
        )

        artifact_root = project.artifact_dir().resolve()
        (artifact_root / "source").mkdir(parents=True, exist_ok=True)

        def _safe_write(member_name: str, target: Path) -> None:
            try:
                with zf.open(member_name, "r") as fp:
                    data = fp.read()
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            except KeyError:
                return

        _safe_write(f"{root}/text/source_text.txt", artifact_root / "source" / "source_text.txt")
        _safe_write(f"{root}/text/description.txt", artifact_root / "source" / "description.txt")

        # Restore latest run stages if available.
        run_dir = artifact_root / "runs" / f"run_imported_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        stage_prefix = f"{root}/stages/"
        stage_names = [n for n in names if n.startswith(stage_prefix) and n.endswith(".json")]
        if stage_names:
            for member_name in stage_names:
                rel = Path(member_name).relative_to(stage_prefix)
                target = run_dir / "stages" / rel
                _safe_write(member_name, target)

        # Restore images metadata.
        style_payload = _safe_zip_read_json(zf, f"{root}/images/style.json")
        if isinstance(style_payload, dict) and style_payload:
            ProjectImageStyle.objects.update_or_create(
                project=project,
                defaults={
                    "style_brief": style_payload.get("style_brief", ""),
                    "expanded_style_description": style_payload.get("expanded_style_description", ""),
                    "representative_excerpt": style_payload.get("representative_excerpt", ""),
                    "sample_image_prompt": style_payload.get("sample_image_prompt", ""),
                    "sample_image_path": style_payload.get("sample_image_path", ""),
                    "sample_image_revised_prompt": style_payload.get("sample_image_revised_prompt", ""),
                    "sample_image_model": style_payload.get("sample_image_model", "gpt-image-1"),
                    "ai_model": style_payload.get("ai_model", DEFAULT_MODEL),
                    "status": style_payload.get("status", ProjectImageStyle.STATUS_DRAFT),
                },
            )

        elements_payload = _safe_zip_read_json(zf, f"{root}/images/elements.json")
        if isinstance(elements_payload, list):
            for row in elements_payload:
                if not isinstance(row, dict):
                    continue
                ProjectImageElement.objects.create(
                    project=project,
                    name=(row.get("name") or "Element")[:255],
                    element_type=(row.get("element_type") or "")[:64],
                    page_refs=(row.get("page_refs") or "")[:255],
                    why_consistency_matters=row.get("why_consistency_matters") or "",
                    expanded_description=row.get("expanded_description") or "",
                    expanded_prompt=row.get("expanded_prompt") or "",
                    image_model=(row.get("image_model") or "gpt-image-1")[:64],
                    image_path=(row.get("image_path") or "")[:512],
                    image_revised_prompt=row.get("image_revised_prompt") or "",
                    is_confirmed=bool(row.get("is_confirmed")),
                    ai_model=(row.get("ai_model") or DEFAULT_MODEL)[:64],
                    status=(row.get("status") or ProjectImageElement.STATUS_PROPOSED)[:32],
                )

        pages_payload = _safe_zip_read_json(zf, f"{root}/images/pages.json")
        if isinstance(pages_payload, list):
            for row in pages_payload:
                if not isinstance(row, dict):
                    continue
                page_num = row.get("page_number")
                if not isinstance(page_num, int):
                    continue
                ProjectImagePage.objects.update_or_create(
                    project=project,
                    page_number=page_num,
                    defaults={
                        "page_text": row.get("page_text") or "",
                        "generation_prompt": row.get("generation_prompt") or "",
                        "image_model": (row.get("image_model") or "gpt-image-1")[:64],
                        "image_path": (row.get("image_path") or "")[:512],
                        "image_revised_prompt": row.get("image_revised_prompt") or "",
                        "status": (row.get("status") or ProjectImagePage.STATUS_DRAFT)[:32],
                    },
                )

        # Restore selected image files under their original relative paths.
        asset_prefix = f"{root}/assets/"
        for member_name in names:
            if not member_name.startswith(asset_prefix):
                continue
            rel = Path(member_name).relative_to(asset_prefix)
            target = (artifact_root / rel).resolve()
            try:
                target.relative_to(artifact_root)
            except ValueError:
                continue
            _safe_write(member_name, target)

        _persist_project_source(project)
        messages.success(request, f"Imported source bundle as new project '{project.title}'.")
        return redirect("project-detail", pk=project.pk)


@login_required
def set_project_collaborator(request: HttpRequest, pk: int) -> HttpResponse:
    project = _get_project_for_user(pk=pk, user=request.user, min_role=ProjectCollaborator.ROLE_OWNER)
    if request.method != "POST":
        return redirect("project-detail", pk=project.pk)

    username = (request.POST.get("username") or "").strip()
    role = (request.POST.get("role") or "").strip().lower()
    if role not in {r for r, _ in ProjectCollaborator.ROLE_CHOICES}:
        messages.error(request, "Unknown collaborator role.")
        return redirect("project-detail", pk=project.pk)
    if not username:
        messages.error(request, "Please provide a username.")
        return redirect("project-detail", pk=project.pk)

    User = get_user_model()
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        messages.error(request, f"User '{username}' was not found.")
        return redirect("project-detail", pk=project.pk)

    if user.id == project.owner_id:
        messages.info(request, "Project owner already has OWNER permissions.")
        return redirect("project-detail", pk=project.pk)

    ProjectCollaborator.objects.update_or_create(
        project=project,
        user=user,
        defaults={"role": role},
    )
    messages.success(request, f"Saved collaborator '{username}' with role {role.upper()}.")
    return redirect("project-detail", pk=project.pk)

@login_required
def delete_project(request: HttpRequest, pk: int) -> HttpResponse:
    project = _get_project_for_user(pk=pk, user=request.user, min_role=ProjectCollaborator.ROLE_OWNER)
    if request.method != "POST":
        messages.error(request, "Project deletion must be confirmed.")
        return redirect("project-detail", pk=project.pk)

    artifact_dir = project.artifact_dir()
    project.delete()
    try:
        shutil.rmtree(artifact_dir, ignore_errors=True)
    except Exception:
        pass
    messages.success(request, "Project deleted.")
    return redirect("project-list")
