from __future__ import annotations

import json
import sys
import logging
import os
import random
import shutil
import hashlib
import re
import uuid
import asyncio
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import FileResponse, Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.db.models import Count, F, Max, Q, Sum
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.generic import CreateView, DetailView, ListView
from django_q.tasks import async_task
from django.utils.html import escape
from django.utils.text import slugify
from django.utils import timezone as django_timezone
import mimetypes
import tempfile
import zipfile
import urllib.request
from urllib.parse import unquote
from urllib.parse import quote

from core.config import DEFAULT_MODEL, OpenAIConfig
from core.ai_api import OpenAIClient, normalize_json_text
from core.language_direction import language_direction
from pipeline.full_pipeline import FullPipelineSpec, PIPELINE_ORDER, run_full_pipeline
from pipeline.mwe import normalize_mwes

from .forms import (
    AdminCommunityForm,
    AdminCommunityMembershipForm,
    AdminDeleteCommunityForm,
    AdminAdjustCreditsForm,
    AdminOpenAIPricingForm,
    ClozeExerciseSetForm,
    DeleteCachedWordAudioForm,
    FlashcardExerciseSetForm,
    GrantAdminPrivilegesForm,
    ProfileForm,
    ProjectDiscoveryMetadataForm,
    ProjectForm,
    ProjectImageElementFormSet,
    ProjectImagePageFormSet,
    ProjectImageStyleForm,
    RegistrationForm,
)
from .metadata import update_project_discovery_metadata
from .billing import (
    apply_credit_delta,
    credits_enabled,
    get_user_balance_usd,
    has_minimum_balance_for_compile,
    minimum_compile_balance_usd,
    openai_price_for_model,
    record_openai_usage_and_charge,
)
from .models import (
    Community,
    CommunityImageVote,
    CommunityMembership,
    CommunityOrganiserReview,
    PictureDictionary,
    PictureDictionaryEntry,
    CreditLedgerEntry,
    OpenAIModelPricing,
    Profile,
    Project,
    CommunityMembership,
    ProjectImageElement,
    ProjectImagePage,
    ProjectImagePageVariant,
    ProjectImageStyle,
    TaskUpdate,
    ProjectCollaborator,
    ContentComment,
    ContentRating,
    ExerciseSet,
    ExerciseItem,
    AIUsageCharge,
)
from .picture_dictionary import (
    add_lemma_pos_entries as picture_dictionary_add_lemma_pos_entries,
    add_words as picture_dictionary_add_words,
    compile_picture_dictionary as picture_dictionary_compile,
    ensure_picture_dictionary_for_community,
    remove_entries_by_ids as picture_dictionary_remove_entries_by_ids,
    remove_words as picture_dictionary_remove_words,
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
CONTENT_DATE_ALIASES = {
    "today": "last_3_days",
    "last_7_days": "last_month",
    "week": "last_month",
    "month": "last_month",
    "3_months": "last_3_months",
    "past_year": "last_year",
    "year": "last_year",
}
CEFR_LEVEL_ORDER = ["A1", "A2", "B1", "B2", "C1", "C2"]



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


def _default_start_stage_for_project(project: Project) -> str:
    freshest_stage: str | None = None
    freshest_mtime = float("-inf")
    for stage_name in PIPELINE_ORDER:
        latest = _latest_stage_artifact(project, stage_name)
        if latest is None:
            continue
        _run_dir, _stage_path, mtime = latest
        if mtime > freshest_mtime:
            freshest_mtime = mtime
            freshest_stage = stage_name
    if freshest_stage is None:
        return "text_gen"
    if freshest_stage == "compile_html":
        return "compile_html"
    index = PIPELINE_ORDER.index(freshest_stage)
    return PIPELINE_ORDER[index + 1] if index + 1 < len(PIPELINE_ORDER) else "compile_html"


def _user_community_ids(user) -> list[int]:
    return list(
        CommunityMembership.objects.filter(user=user, community__is_active=True).values_list("community_id", flat=True)
    )


def _published_projects_visible_to_user(user):
    if user.is_staff:
        return Project.objects.filter(is_published=True)
    community_ids = _user_community_ids(user)
    return Project.objects.filter(is_published=True).filter(
        Q(access_scope=Project.ACCESS_PUBLIC)
        | Q(owner=user)
        | Q(collaborators__user=user)
        | Q(access_scope=Project.ACCESS_COMMUNITY, community_id__in=community_ids)
    ).distinct()


def _community_role_for_user(community: Community, user) -> str | None:
    membership = CommunityMembership.objects.filter(community=community, user=user).values_list("role", flat=True).first()
    return str(membership) if membership else None


def _manual_annotation_context(project: Project) -> dict[str, Any]:
    return {
        "has_source_text_for_manual_segmentation": bool(_base_text_for_segmentation_phase_1(project).strip()),
        "has_segmentation_phase_1": _has_segmentation_phase_1_output(project),
        "has_segmentation_phase_2": _find_latest_stage_file(project, "segmentation_phase_2.json") is not None,
        "has_mwe": _find_latest_stage_file(project, "mwe.json") is not None,
        "has_lemma": _find_latest_stage_file(project, "lemma.json") is not None,
        "has_gloss": _find_latest_stage_file(project, "gloss.json") is not None,
        "manual_stage_status": {
            "segmentation_phase_1": _manual_stage_status(project, "segmentation_phase_1"),
            "segmentation_phase_2": _manual_stage_status(project, "segmentation_phase_2"),
            "mwe": _manual_stage_status(project, "mwe"),
            "lemma": _manual_stage_status(project, "lemma"),
            "gloss": _manual_stage_status(project, "gloss"),
            "pinyin": _manual_stage_status(project, "pinyin"),
            "translation": _manual_stage_status(project, "translation"),
        },
    }


def _bootstrap_admin_usernames() -> set[str]:
    configured = getattr(settings, "BOOTSTRAP_ADMIN_USERNAMES", []) or []
    return {str(name).strip() for name in configured if str(name).strip()}


def _ensure_bootstrap_admin(user) -> None:
    if not user or not getattr(user, "is_authenticated", False):
        return
    if user.is_staff:
        return
    if user.username in _bootstrap_admin_usernames():
        user.is_staff = True
        user.save(update_fields=["is_staff"])


def _require_admin(user) -> None:
    _ensure_bootstrap_admin(user)
    if not user.is_staff:
        raise Http404()


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


def _append_style_telemetry(project: Project, record: dict[str, Any]) -> None:
    telemetry_path = _image_style_dir(project) / "telemetry.jsonl"
    telemetry_path.parent.mkdir(parents=True, exist_ok=True)
    entry = dict(record)
    entry["timestamp"] = datetime.now(timezone.utc).isoformat()
    with telemetry_path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _iter_exception_chain(exc: BaseException) -> list[BaseException]:
    chain: list[BaseException] = []
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        chain.append(current)
        seen.add(id(current))
        current = current.__cause__ or current.__context__
    return chain


def _is_timeout_exception(exc: BaseException) -> bool:
    for current in _iter_exception_chain(exc):
        if isinstance(current, (TimeoutError, asyncio.TimeoutError)):
            return True
        if "timeout" in current.__class__.__name__.lower():
            return True
    return False


def _exception_telemetry_fields(exc: BaseException) -> dict[str, Any]:
    return {
        "error": str(exc),
        "error_type": exc.__class__.__name__,
        "is_timeout": _is_timeout_exception(exc),
    }


def _ensure_style_telemetry_file(project: Project) -> Path:
    telemetry_path = _image_style_dir(project) / "telemetry.jsonl"
    telemetry_path.parent.mkdir(parents=True, exist_ok=True)
    if not telemetry_path.exists():
        telemetry_path.write_text("", encoding="utf-8")
    return telemetry_path


def _style_artifact_links(project: Project) -> list[dict[str, str]]:
    style_dir = _image_style_dir(project)
    _ensure_style_telemetry_file(project)
    files = [
        ("style_brief.txt", "Style brief"),
        ("style_expansion_prompt.json", "Style expansion prompt"),
        ("style_expansion_response.json", "Style expansion response"),
        ("style_description.txt", "Expanded style description"),
        ("representative_excerpt.txt", "Representative excerpt"),
        ("sample_image_prompt.txt", "Sample image prompt"),
        ("sample_image_revised_prompt.txt", "Sample image revised prompt"),
        ("style_status.json", "Style status"),
        ("telemetry.jsonl", "Style telemetry"),
    ]
    links: list[dict[str, str]] = []
    for rel_name, label in files:
        path = style_dir / rel_name
        if not path.exists():
            continue
        relpath = os.path.relpath(path, project.artifact_dir()).replace("\\", "/")
        links.append(
            {
                "label": label,
                "url": reverse("project-compiled", args=[project.pk, relpath]),
                "size": str(path.stat().st_size),
            }
        )
    return links


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
    prompt_language = _image_prompt_language(project)
    prompt = "\n".join(
        [
            "You are helping define a consistent illustration style for a language-learning story.",
            "Return JSON with keys: expanded_style_description, representative_excerpt, sample_image_prompt.",
            "expanded_style_description should preserve the user's brief but elaborate it in a way that fits the story content.",
            "expanded_style_description must contain only global style guidance (medium/technique, palette, line/shape language, composition, lighting, overall mood).",
            "Do NOT include named characters, named places, plot events, page-specific actions, or detailed props from this story.",
            "If the user brief contains story-specific details, generalize them into reusable style principles.",
            "Keep expanded_style_description concise (target 600-1000 characters, hard max 1400 characters).",
            "representative_excerpt should be a short excerpt or summary snippet from the story most useful for a sample image.",
            "sample_image_prompt should be a detailed prompt for a single sample image that demonstrates the style for this story.",
            f"Write expanded_style_description, representative_excerpt, and sample_image_prompt in the image prompt language ({prompt_language}).",
            "",
            f"Project title: {project.title}",
            f"Project language (source): {project.language}",
            f"Image prompt language (derived from image text-source setting): {prompt_language}",
            f"Target language: {project.target_language}",
            f"User style brief: {style_brief}",
            (
                "Text policy for final images: Prefer little/no visible text, "
                "but allow short text only when it is clearly required by the story (e.g., a meaningful sign or label)."
                if getattr(project.image_style, "discourage_text_in_images", False)
                else "Text policy for final images: Text is allowed when appropriate for the scene."
            ),
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
    _append_style_telemetry(
        project,
        {
            "type": "event",
            "level": "info",
            "message": "style expansion request start",
            "model": ai_model,
            "prompt": request_payload["prompt"],
            "prompt_length": len(request_payload["prompt"]),
            "prompt_preview": request_payload["prompt"][:400],
        },
    )
    started = datetime.now(timezone.utc)
    usage_events: list[dict[str, Any]] = []
    client = _build_ai_client(
        model_name=ai_model,
        usage_reporter=_collect_usage_event(usage_events),
    )
    try:
        response = asyncio.run(client.chat_json(request_payload["prompt"], model=ai_model))
    except Exception as exc:
        _flush_project_usage_events(
            project=project,
            events=usage_events,
            request_type="image_style_expand",
            default_model=ai_model,
        )
        elapsed_s = (datetime.now(timezone.utc) - started).total_seconds()
        _append_style_telemetry(
            project,
            {
                "type": "event",
                "level": "error",
                "message": "style expansion timeout" if _is_timeout_exception(exc) else "style expansion request failed",
                "model": ai_model,
                "elapsed_s": round(elapsed_s, 3),
                **_exception_telemetry_fields(exc),
            },
        )
        raise
    _flush_project_usage_events(
        project=project,
        events=usage_events,
        request_type="image_style_expand",
        default_model=ai_model,
    )
    elapsed_s = (datetime.now(timezone.utc) - started).total_seconds()
    _append_style_telemetry(
        project,
        {
            "type": "event",
            "level": "info",
            "message": "style expansion response received",
            "model": ai_model,
            "elapsed_s": round(elapsed_s, 3),
            "response_keys": sorted(response.keys()) if isinstance(response, dict) else [],
            "response_preview": str(response)[:400],
        },
    )

    return {
        "expanded_style_description": _compact_style_description_for_prompt(
            str(response.get("expanded_style_description") or style_brief).strip(),
            max_chars=1400,
        ),
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

    _append_style_telemetry(
        project,
        {
            "type": "event",
            "level": "info",
            "message": "style sample image request start",
            "model": style.sample_image_model,
            "prompt": prompt,
            "prompt_length": len(prompt),
            "prompt_preview": prompt[:400],
        },
    )
    started = datetime.now(timezone.utc)
    client = _build_billed_project_ai_client(
        project,
        model_name=style.sample_image_model,
        request_type="image_style_sample",
    )
    try:
        image_result = client.generate_image(prompt, model=style.sample_image_model)
    except Exception as exc:
        elapsed_s = (datetime.now(timezone.utc) - started).total_seconds()
        _append_style_telemetry(
            project,
            {
                "type": "event",
                "level": "error",
                "message": "style sample image timeout" if _is_timeout_exception(exc) else "style sample image request failed",
                "model": style.sample_image_model,
                "elapsed_s": round(elapsed_s, 3),
                **_exception_telemetry_fields(exc),
            },
        )
        raise
    elapsed_s = (datetime.now(timezone.utc) - started).total_seconds()
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
    _append_style_telemetry(
        project,
        {
            "type": "event",
            "level": "info",
            "message": "style sample image response received",
            "elapsed_s": round(elapsed_s, 3),
            **metadata,
        },
    )
    (style_dir / "style_sample_image_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return metadata


def _image_elements_dir(project: Project) -> Path:
    return project.artifact_dir() / "images" / "elements"


def _append_elements_telemetry(project: Project, record: dict[str, Any]) -> None:
    telemetry_path = _image_elements_dir(project) / "telemetry.jsonl"
    telemetry_path.parent.mkdir(parents=True, exist_ok=True)
    entry = dict(record)
    entry["timestamp"] = datetime.now(timezone.utc).isoformat()
    with telemetry_path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _elements_artifact_links(project: Project) -> list[dict[str, str]]:
    elements_dir = _image_elements_dir(project)
    elements_dir.mkdir(parents=True, exist_ok=True)
    telemetry_path = elements_dir / "telemetry.jsonl"
    if not telemetry_path.exists():
        telemetry_path.write_text("", encoding="utf-8")
    files = [
        ("elements_list.json", "Elements list"),
        ("elements_discovery_prompt.json", "Elements discovery prompt"),
        ("elements_discovery_response.json", "Elements discovery response"),
        ("telemetry.jsonl", "Elements telemetry"),
    ]
    links: list[dict[str, str]] = []
    for rel_name, label in files:
        path = elements_dir / rel_name
        if not path.exists():
            continue
        relpath = os.path.relpath(path, project.artifact_dir()).replace("\\", "/")
        links.append(
            {
                "label": label,
                "url": reverse("project-compiled", args=[project.pk, relpath]),
                "size": str(path.stat().st_size),
            }
        )
    billing_path = project.artifact_dir() / "images" / "billing_telemetry.jsonl"
    if billing_path.exists():
        relpath = os.path.relpath(billing_path, project.artifact_dir()).replace("\\", "/")
        links.append(
            {
                "label": "Image billing telemetry",
                "url": reverse("project-compiled", args=[project.pk, relpath]),
                "size": str(billing_path.stat().st_size),
            }
        )
    return links


def _extract_project_pages(project: Project) -> list[str]:
    if project.page_image_text_source == Project.PAGE_IMAGE_TEXT_SOURCE_TRANSLATION:
        translation_pages = _extract_project_pages_from_translation(project)
        if translation_pages:
            return translation_pages
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
    inline_pages = [
        chunk.strip()
        for chunk in re.split(r"(?i)<\s*page\s*/?\s*>", plain_text)
        if chunk and chunk.strip()
    ]
    if len(inline_pages) > 1:
        return inline_pages
    chunks = [chunk.strip() for chunk in plain_text.split("\n\n") if chunk.strip()]
    return chunks or [plain_text]


def _extract_project_pages_from_translation(project: Project) -> list[str]:
    tr_latest = _find_latest_stage_file(project, "translation.json")
    if not tr_latest:
        return []
    tr_payload = _load_stage_payload(project, "translation", run_dir=tr_latest[0])
    if not isinstance(tr_payload, dict):
        return []
    pages = tr_payload.get("pages") or []
    output_pages: list[str] = []
    for page in pages:
        segments = (page or {}).get("segments") or []
        parts: list[str] = []
        for segment in segments:
            text = str((((segment or {}).get("annotations") or {}).get("translation")) or "").strip()
            if text:
                parts.append(text)
        joined = " ".join(parts).strip()
        if joined:
            output_pages.append(joined)
    return output_pages


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
    prompt_language = _image_prompt_language(project)
    pages_block = "\n".join(f"Page {idx}: {surface}" for idx, surface in enumerate(pages, start=1))
    phase1_prompt = "\n".join(
        [
            "Identify concrete recurring visual elements in this story.",
            "Only include reusable visual items: characters, locations, objects, props, motifs.",
            "Do not include style/aesthetic directions.",
            "Return JSON with key 'elements'. Each item should have: name, type.",
            "Keep names concise and concrete.",
            f"Write names and types in the image prompt language ({prompt_language}).",
            "",
            f"Project title: {project.title}",
            f"Language: {project.language}",
            f"Image prompt language: {prompt_language}",
            "Pages:",
            pages_block or "[none]",
        ]
    )
    _append_elements_telemetry(
        project,
        {
            "type": "event",
            "level": "info",
            "message": "elements discovery phase_1 request start",
            "model": ai_model,
            "pages_count": len(pages),
            "prompt": phase1_prompt,
            "prompt_length": len(phase1_prompt),
            "prompt_preview": phase1_prompt[:400],
        },
    )
    phase1_usage_events: list[dict[str, Any]] = []
    phase1_client = _build_ai_client(
        model_name=ai_model,
        usage_reporter=_collect_usage_event(phase1_usage_events),
    )
    started = datetime.now(timezone.utc)
    try:
        phase1_response = asyncio.run(
            phase1_client.chat_json(phase1_prompt, model=ai_model)
        )
    except Exception as exc:
        _flush_project_usage_events(
            project=project,
            events=phase1_usage_events,
            request_type="image_elements_discovery_phase_1",
            default_model=ai_model,
        )
        elapsed_s = (datetime.now(timezone.utc) - started).total_seconds()
        _append_elements_telemetry(
            project,
            {
                "type": "event",
                "level": "error",
                "message": "elements discovery phase_1 timeout" if _is_timeout_exception(exc) else "elements discovery phase_1 failed",
                "model": ai_model,
                "elapsed_s": round(elapsed_s, 3),
                **_exception_telemetry_fields(exc),
            },
        )
        raise
    _flush_project_usage_events(
        project=project,
        events=phase1_usage_events,
        request_type="image_elements_discovery_phase_1",
        default_model=ai_model,
    )
    elapsed_s = (datetime.now(timezone.utc) - started).total_seconds()
    _append_elements_telemetry(
        project,
        {
            "type": "event",
            "level": "info",
            "message": "elements discovery phase_1 response received",
            "model": ai_model,
            "elapsed_s": round(elapsed_s, 3),
            "response_keys": sorted(phase1_response.keys()) if isinstance(phase1_response, dict) else [],
            "response_preview": str(phase1_response)[:400],
        },
    )

    raw_candidates = phase1_response.get("elements") if isinstance(phase1_response, dict) else []
    if not isinstance(raw_candidates, list):
        raw_candidates = []

    candidates: list[dict[str, str]] = []
    for item in raw_candidates:
        if isinstance(item, dict):
            name = str(item.get("name") or "").strip()
            elem_type = str(item.get("type") or "object").strip()
        else:
            name = str(item).strip()
            elem_type = "object"
        if not name:
            continue
        candidates.append({"name": name[:255], "element_type": elem_type[:64] or "object"})

    unique_by_name: dict[str, dict[str, str]] = {}
    for item in candidates:
        key = item["name"].casefold()
        if key not in unique_by_name:
            unique_by_name[key] = item
    candidates = list(unique_by_name.values())

    def _resolve_page_refs(candidate: dict[str, str]) -> dict[str, Any]:
        phase2_prompt = "\n".join(
            [
                "Find where this visual element appears in the story.",
                "Return JSON with keys: page_refs, why_consistency_matters, type.",
                "page_refs must be a list of 1-indexed page numbers where the element appears.",
                "why_consistency_matters should be one concise sentence.",
                f"Write why_consistency_matters and type in the image prompt language ({prompt_language}).",
                "",
                f"Element name: {candidate['name']}",
                f"Proposed type: {candidate['element_type']}",
                "Pages:",
                pages_block or "[none]",
            ]
        )
        _append_elements_telemetry(
            project,
            {
                "type": "event",
                "level": "info",
                "message": "elements discovery phase_2 request start",
                "model": ai_model,
                "element_name": candidate["name"],
                "prompt": phase2_prompt,
                "prompt_length": len(phase2_prompt),
                "prompt_preview": phase2_prompt[:400],
            },
        )
        phase2_usage_events: list[dict[str, Any]] = []
        phase2_client = _build_ai_client(
            model_name=ai_model,
            usage_reporter=_collect_usage_event(phase2_usage_events),
        )
        started_local = datetime.now(timezone.utc)
        try:
            response_local = asyncio.run(
                phase2_client.chat_json(phase2_prompt, model=ai_model)
            )
        except Exception as exc:
            elapsed_local_s = (datetime.now(timezone.utc) - started_local).total_seconds()
            _append_elements_telemetry(
                project,
                {
                    "type": "event",
                    "level": "error",
                    "message": "elements discovery phase_2 timeout" if _is_timeout_exception(exc) else "elements discovery phase_2 failed",
                    "model": ai_model,
                    "element_name": candidate["name"],
                    "elapsed_s": round(elapsed_local_s, 3),
                    **_exception_telemetry_fields(exc),
                },
            )
            raise
        elapsed_local_s = (datetime.now(timezone.utc) - started_local).total_seconds()
        _append_elements_telemetry(
            project,
            {
                "type": "event",
                "level": "info",
                "message": "elements discovery phase_2 response received",
                "model": ai_model,
                "element_name": candidate["name"],
                "elapsed_s": round(elapsed_local_s, 3),
                "response_keys": sorted(response_local.keys()) if isinstance(response_local, dict) else [],
                "response_preview": str(response_local)[:400],
            },
        )
        refs_raw = response_local.get("page_refs") if isinstance(response_local, dict) else []
        refs: list[int] = []
        if isinstance(refs_raw, list):
            for ref in refs_raw:
                try:
                    page_num = int(ref)
                except Exception:
                    continue
                if 1 <= page_num <= len(pages):
                    refs.append(page_num)
        refs = sorted(set(refs))
        return {
            "name": candidate["name"],
            "element_type": str((response_local or {}).get("type") or candidate["element_type"])[:64],
            "page_refs_list": refs,
            "why_consistency_matters": str((response_local or {}).get("why_consistency_matters") or "").strip()[:2000],
            "phase2_response": response_local,
            "phase2_usage_events": phase2_usage_events,
        }

    phase2_items: list[dict[str, Any]] = []
    if candidates:
        max_workers = min(6, max(1, len(candidates)))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(_resolve_page_refs, item) for item in candidates]
            for future in as_completed(futures):
                item = future.result()
                _flush_project_usage_events(
                    project=project,
                    events=item.get("phase2_usage_events", []),
                    request_type="image_elements_discovery_phase_2",
                    default_model=ai_model,
                )
                phase2_items.append(item)

    normalized: list[dict[str, Any]] = []
    min_refs_required = 2 if len(pages) > 1 else 1
    for item in phase2_items:
        refs = item.get("page_refs_list") or []
        if len(refs) < min_refs_required:
            continue
        normalized.append(
            {
                "name": item["name"][:255],
                "element_type": item["element_type"][:64] or "object",
                "page_refs": ",".join(str(x) for x in refs)[:255],
                "why_consistency_matters": item["why_consistency_matters"][:2000],
            }
        )

    diagnostics = {
        "pages_count": len(pages),
        "phase1_candidates": len(candidates),
        "phase2_results": len(phase2_items),
        "normalized_elements_count": len(normalized),
    }
    response_payload = {
        "phase_1": phase1_response,
        "phase_2": [
            {
                "name": row["name"],
                "response": row.get("phase2_response", {}),
                "page_refs": row.get("page_refs_list", []),
            }
            for row in phase2_items
        ],
        "_diagnostics": diagnostics,
    }
    request_payload = {
        "phase_1_prompt": phase1_prompt,
        "phase_2_candidates": [row["name"] for row in candidates],
        "pages_count": len(pages),
    }
    if not normalized:
        logger.warning(
            "Element discovery returned no usable elements for project %s: %s",
            project.pk,
            diagnostics,
        )
    return normalized, request_payload, response_payload


def _compact_style_description_for_prompt(text: str, *, max_chars: int = 1200) -> str:
    value = str(text or "").strip()
    if len(value) <= max_chars:
        return value
    keep = max(0, max_chars - 48)
    return f"{value[:keep]}\n...[style description truncated {len(value) - keep} chars]..."


def _expand_project_image_elements(
    project: Project,
    *,
    ai_model: str,
) -> dict[str, Any]:
    prompt_language = _image_prompt_language(project)
    style_description = ""
    try:
        style_description = project.image_style.expanded_style_description
    except Exception:
        style_description = ""
    style_description = _compact_style_description_for_prompt(style_description, max_chars=1200)
    full_text = _extract_project_plain_text(project)
    expanded_count = 0
    failed_count = 0
    failed_elements: list[dict[str, Any]] = []
    usage_events: list[dict[str, Any]] = []
    client = _build_ai_client(
        model_name=ai_model,
        usage_reporter=_collect_usage_event(usage_events),
    )
    for element in project.image_elements.order_by("name", "id"):
        prompt = "\n".join(
            [
                "Create an expanded visual element description for consistent illustration.",
                "Return JSON with keys: expanded_description, expanded_prompt.",
                f"Write expanded_description and expanded_prompt in the image prompt language ({prompt_language}).",
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
        _append_elements_telemetry(
            project,
            {
                "type": "event",
                "level": "info",
                "message": "element expansion request start",
                "model": ai_model,
                "element_id": element.id,
                "element_name": element.name,
                "prompt": prompt,
                "prompt_length": len(prompt),
                "prompt_preview": prompt[:400],
            },
        )
        started = datetime.now(timezone.utc)
        try:
            response = asyncio.run(client.chat_json(prompt, model=ai_model))
        except Exception as exc:
            elapsed_s = (datetime.now(timezone.utc) - started).total_seconds()
            _append_elements_telemetry(
                project,
                {
                    "type": "event",
                    "level": "error",
                    "message": "element expansion timeout" if _is_timeout_exception(exc) else "element expansion failed",
                    "model": ai_model,
                    "element_id": element.id,
                    "element_name": element.name,
                    "elapsed_s": round(elapsed_s, 3),
                    **_exception_telemetry_fields(exc),
                },
            )
            logger.exception(
                "Element expansion failed for project %s element %s (%s)",
                project.pk,
                element.id,
                element.name,
            )
            _flush_project_usage_events(
                project=project,
                events=usage_events,
                request_type="image_elements_expand",
                default_model=ai_model,
            )
            failed_count += 1
            failed_elements.append(
                {
                    "element_id": element.id,
                    "element_name": element.name,
                    "error": str(exc),
                }
            )
            continue
        _flush_project_usage_events(
            project=project,
            events=usage_events,
            request_type="image_elements_expand",
            default_model=ai_model,
        )
        elapsed_s = (datetime.now(timezone.utc) - started).total_seconds()
        _append_elements_telemetry(
            project,
            {
                "type": "event",
                "level": "info",
                "message": "element expansion response received",
                "model": ai_model,
                "element_id": element.id,
                "element_name": element.name,
                "elapsed_s": round(elapsed_s, 3),
                "response_keys": sorted(response.keys()) if isinstance(response, dict) else [],
                "response_preview": str(response)[:400],
            },
        )
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
        expanded_count += 1

    _append_elements_telemetry(
        project,
        {
            "type": "event",
            "level": "info" if failed_count == 0 else "warning",
            "message": "element expansion completed",
            "model": ai_model,
            "expanded_count": expanded_count,
            "failed_count": failed_count,
            "failed_elements": failed_elements[:10],
        },
    )
    return {
        "expanded_count": expanded_count,
        "failed_count": failed_count,
        "failed_elements": failed_elements,
    }




def _running_tests() -> bool:
    argv = " ".join(sys.argv).lower()
    return "pytest" in argv or "manage.py test" in argv or " test" in argv


def _run_expand_elements_task(project_id: int, user_id: int, ai_model: str, report_id: str) -> None:
    try:
        project = Project.objects.get(pk=project_id)
        user = get_user_model().objects.filter(pk=user_id).first()
        TaskUpdate.objects.create(
            report_id=report_id,
            user=user,
            task_type=f"image_elements_expand_{project_id}",
            message=f"Started element prompt expansion with {ai_model}.",
            status="running",
        )
        expansion_started = datetime.now(timezone.utc)
        _append_elements_telemetry(project, {"type":"event","level":"info","message":"elements expansion run start","ai_model":ai_model,"report_id":report_id})
        expand_result = _expand_project_image_elements(project, ai_model=ai_model)
        elapsed_s = (datetime.now(timezone.utc) - expansion_started).total_seconds()
        _append_elements_telemetry(project, {"type":"event","level":"info","message":"elements expansion run complete","ai_model":ai_model,"elapsed_s":round(elapsed_s,3),"report_id":report_id})
        _persist_image_elements_artifacts(project)
        expanded = int(expand_result.get("expanded_count", 0))
        failed = int(expand_result.get("failed_count", 0))
        status = "done" if failed == 0 else "warning"
        TaskUpdate.objects.create(
            report_id=report_id,
            user=user,
            task_type=f"image_elements_expand_{project_id}",
            message=f"Expanded prompts for {expanded} elements; {failed} failed in {elapsed_s:.1f}s.",
            status=status,
        )
    except Exception as exc:
        logger.exception("Async element expansion failed for project %s", project_id)
        project = Project.objects.filter(pk=project_id).first()
        if project:
            _append_elements_telemetry(project, {"type":"event","level":"error","message":"elements expansion failed","ai_model":ai_model,"report_id":report_id,**_exception_telemetry_fields(exc)})
        user = get_user_model().objects.filter(pk=user_id).first()
        TaskUpdate.objects.create(
            report_id=report_id,
            user=user,
            task_type=f"image_elements_expand_{project_id}",
            message=f"Element expansion failed: {exc}",
            status="error",
        )

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
        _append_elements_telemetry(
            project,
            {
                "type": "event",
                "level": "info",
                "message": "element image request start",
                "model": image_model,
                "element_id": element_id,
                "prompt": prompt_text,
                "prompt_length": len(prompt_text),
                "prompt_preview": prompt_text[:400],
            },
        )
        started = datetime.now(timezone.utc)
        client = _build_billed_project_ai_client(
            project,
            model_name=image_model,
            request_type="image_elements_generate_image",
        )
        try:
            result = client.generate_image(prompt_text, model=image_model)
        except Exception as exc:
            elapsed_s = (datetime.now(timezone.utc) - started).total_seconds()
            _append_elements_telemetry(
                project,
                {
                    "type": "event",
                    "level": "error",
                    "message": "element image timeout" if _is_timeout_exception(exc) else "element image request failed",
                    "model": image_model,
                    "element_id": element_id,
                    "elapsed_s": round(elapsed_s, 3),
                    **_exception_telemetry_fields(exc),
                },
            )
            raise
        elapsed_s = (datetime.now(timezone.utc) - started).total_seconds()
        _append_elements_telemetry(
            project,
            {
                "type": "event",
                "level": "info",
                "message": "element image response received",
                "model": image_model,
                "element_id": element_id,
                "elapsed_s": round(elapsed_s, 3),
            },
        )
        return element_id, result

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
    discourage_text_in_image: bool = False,
    dictionary_entry: PictureDictionaryEntry | None = None,
) -> str:
    language_instructions = {
        "en": ("Create one story illustration page in a consistent style.", "Keep visual continuity with existing style and element references."),
        "fr": ("Crée une illustration de page d’histoire dans un style cohérent.", "Conserve la continuité visuelle avec le style et les références d’éléments."),
        "de": ("Erstelle eine einzelne illustrierte Geschichten-Seite in konsistentem Stil.", "Behalte visuelle Kontinuität mit Stil und Elementreferenzen bei."),
        "es": ("Crea una ilustración de una página de historia con estilo coherente.", "Mantén continuidad visual con el estilo y las referencias de elementos."),
        "it": ("Crea un’illustrazione di una pagina della storia con stile coerente.", "Mantieni continuità visiva con lo stile e i riferimenti degli elementi."),
        "pt": ("Crie uma ilustração de uma página da história em estilo consistente.", "Mantenha continuidade visual com o estilo e as referências dos elementos."),
    }
    language_labels = {
        "en": "English",
        "fr": "French",
        "de": "German",
        "es": "Spanish",
        "it": "Italian",
        "pt": "Portuguese",
        "zh": "Chinese",
        "ja": "Japanese",
        "ko": "Korean",
        "ar": "Arabic",
        "ru": "Russian",
        "hi": "Hindi",
    }
    prompt_language = _image_prompt_language(project)
    if prompt_language not in language_instructions:
        prompt_language = "en"
    line1, line2 = language_instructions.get(prompt_language, language_instructions["en"])
    no_text_line = _discourage_text_guideline_for_language(prompt_language)
    if dictionary_entry is not None:
        lemma = (dictionary_entry.lemma or page_text or "").strip()
        pos = (dictionary_entry.pos or "").strip() or "unspecified"
        return "\n".join(
            [
                "Create one picture-dictionary illustration.",
                f"Target lemma: {lemma}",
                f"Target POS: {pos}",
                f"Prompt language: {language_labels.get(prompt_language, 'English')}",
                f"Language (source): {project.language}",
                f"Style description: {_compact_style_description_for_prompt(style.expanded_style_description or style.style_brief or '[none]', max_chars=1200)}",
                "Render a clear visual scene for the target lemma itself (not a generic story page).",
                "Do not focus on words, captions, typography, book pages, or signage text.",
                f"{no_text_line}",
                "If the lemma is a noun, make the object/animal/person visually central and unambiguous.",
                "If the lemma is a verb, depict the action in progress with clear actors/objects.",
                "If the lemma is an adjective, depict a concrete object/scene where the property is visually obvious.",
            ]
        )
    suppression_block_by_language = {
        "en": [
            "TEXT SUPPRESSION REQUIREMENTS (HIGH PRIORITY):",
            "- Do not render readable words, sentences, subtitles, speech bubbles, labels, captions, or signage text.",
            "- Exception: allow at most 1–3 very short words only when absolutely story-essential (for example: one critical sign or one brief comic-style sound effect).",
            "- If any text is unavoidable, keep it tiny, low-contrast, background-only, and never central.",
        ],
        "fr": [
            "EXIGENCES DE SUPPRESSION DU TEXTE (PRIORITÉ ÉLEVÉE) :",
            "- N’affiche aucun mot lisible, aucune phrase, sous-titre, bulle, étiquette, légende ou texte d’enseigne.",
            "- Exception : autorise au maximum 1 à 3 mots très courts, uniquement si c’est indispensable à l’histoire (par exemple une enseigne critique ou une très brève onomatopée).",
            "- Si du texte est inévitable, il doit rester minuscule, peu contrasté, en arrière-plan, et jamais central.",
        ],
    }
    suppression_block = suppression_block_by_language.get(prompt_language, suppression_block_by_language["en"])
    lines = [
        line1,
        line2,
        "",
    ]
    if discourage_text_in_image:
        lines.extend(suppression_block)
        lines.extend([f"- {no_text_line}", ""])
    lines.extend(
        [
        f"Prompt language: {language_labels.get(prompt_language, 'English')}",
        f"Project title: {project.title}",
        f"Language (source): {project.language}",
        f"Language for image prompt text: {prompt_language}",
        f"Page number: {page_number}",
        f"Style description: {_compact_style_description_for_prompt(style.expanded_style_description or style.style_brief or '[none]', max_chars=1200)}",
        "Page text:",
        page_text or "[none]",
        "",
        "Story context (brief):",
        full_text or "[none]",
        "",
        ]
    )
    lines.append("Relevant element references:")
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


_DISCOURAGE_TEXT_GUIDELINES = {
    "en": "Prefer little or no visible text. Allow short text only when story-essential (e.g., a meaningful sign, or brief comic-style sound effects like 'BANG!' or 'BOOM!').",
    "fr": "Privilégie peu ou pas de texte visible. Autorise un texte court seulement s’il est essentiel à la scène (p. ex. un panneau important, ou une onomatopée brève de style BD comme « BANG! »).",
    "de": "Bevorzuge wenig oder keinen sichtbaren Text. Erlaube kurzen Text nur, wenn er für die Szene wesentlich ist (z. B. ein wichtiges Schild oder ein kurzes Comic-Geräusch wie „BANG!“).",
    "es": "Prefiere poco o ningún texto visible. Permite texto breve solo cuando sea esencial para la escena (p. ej., un letrero importante o una onomatopeya breve estilo cómic como «¡BANG!»).",
    "it": "Preferisci poco o nessun testo visibile. Consenti testo breve solo quando è essenziale per la scena (es. un cartello importante o una breve onomatopea da fumetto come «BANG!»).",
    "pt": "Prefira pouco ou nenhum texto visível. Permita texto curto apenas quando for essencial para a cena (ex.: uma placa importante ou uma onomatopeia curta em estilo quadrinhos como «BANG!»).",
    "nl": "Gebruik bij voorkeur weinig of geen zichtbare tekst. Sta korte tekst alleen toe als die essentieel is voor de scène (bijv. een belangrijk bord of een kort stripachtig geluidseffect zoals ‘BANG!’).",
    "sv": "Använd helst lite eller ingen synlig text. Tillåt kort text bara när den är viktig för scenen (t.ex. en betydelsefull skylt eller en kort serielik ljudeffekt som ”BANG!”).",
    "no": "Bruk helst lite eller ingen synlig tekst. Tillat kort tekst bare når den er viktig for scenen (f.eks. et viktig skilt eller en kort tegneserieaktig lydeffekt som «BANG!»).",
    "da": "Brug helst lidt eller ingen synlig tekst. Tillad kun kort tekst, når den er vigtig for scenen (fx et vigtigt skilt eller en kort tegneserieagtig lydeffekt som »BANG!«).",
    "fi": "Suosi vähän tai ei lainkaan näkyvää tekstiä. Salli lyhyt teksti vain, kun se on kohtaukselle olennainen (esim. tärkeä kyltti tai lyhyt sarjakuvamainen ääniefekti kuten ”BANG!”).",
    "pl": "Preferuj mało lub brak widocznego tekstu. Dopuszczaj krótki tekst tylko wtedy, gdy jest istotny dla sceny (np. ważny znak albo krótka komiksowa onomatopeja typu „BANG!”).",
    "zh": "尽量少用或不用可见文字。只有在剧情确实需要时才使用简短文字（例如关键路牌，或简短漫画拟声词如“BANG!”）。",
    "ja": "基本的に可視テキストは最小限または無しにしてください。物語上どうしても必要な場合のみ、短い文字を許可します（例：重要な看板、短い漫画風効果音「BANG!」）。",
    "ko": "보이는 텍스트는 가능하면 최소화하거나 사용하지 마세요. 장면에 꼭 필요할 때만 짧은 텍스트를 허용하세요(예: 중요한 표지판, 짧은 만화식 효과음 ‘BANG!’).",
    "ar": "يفضَّل تقليل النص الظاهر أو عدم استخدامه. يُسمح بنص قصير فقط عندما يكون ضروريًا للمشهد (مثل لافتة مهمة أو مؤثر صوتي قصير بأسلوب القصص المصورة مثل \"BANG!\").",
    "ru": "Предпочтительно минимум или отсутствие видимого текста. Допускайте короткий текст только если он важен для сцены (например, значимая вывеска или краткая комиксная звукоподражательная вставка вроде «BANG!»).",
    "hi": "दृश्य में टेक्स्ट बहुत कम रखें या न रखें। केवल तब छोटा टेक्स्ट दें जब वह कहानी के लिए ज़रूरी हो (जैसे महत्वपूर्ण साइनबोर्ड या कॉमिक-शैली की छोटी ध्वनि जैसे “BANG!”)।",
}


@lru_cache(maxsize=128)
def _translate_discourage_text_guideline(language_code: str) -> str:
    base = _DISCOURAGE_TEXT_GUIDELINES["en"]
    prompt = "\n".join(
        [
            "Translate the following instruction into the requested language.",
            "Keep meaning and examples intact.",
            "Return only the translated instruction text (no quotes, no markdown).",
            f"Language code: {language_code}",
            f"Instruction: {base}",
        ]
    )
    try:
        translated = asyncio.run(_build_ai_client(model_name="gpt-4o-mini").chat_text(prompt, model="gpt-4o-mini"))
    except Exception:
        return base
    value = str(translated or "").strip()
    return value or base


def _discourage_text_guideline_for_language(language_code: str) -> str:
    code = (language_code or "").strip().lower()
    if not code:
        return _DISCOURAGE_TEXT_GUIDELINES["en"]
    if code in _DISCOURAGE_TEXT_GUIDELINES:
        return _DISCOURAGE_TEXT_GUIDELINES[code]
    return _translate_discourage_text_guideline(code)


def _image_prompt_language(project: Project) -> str:
    if project.page_image_text_source == Project.PAGE_IMAGE_TEXT_SOURCE_TRANSLATION:
        pivot_language = (project.image_generation_pivot_language or "").strip().lower()
        if pivot_language:
            return pivot_language
        return (project.target_language or "en").strip().lower() or "en"
    return (project.language or "en").strip().lower() or "en"


def _truncate_for_prompt(text: str, *, max_chars: int) -> str:
    value = str(text or "")
    if len(value) <= max_chars:
        return value
    head = value[:max(0, max_chars - 48)]
    return f"{head}\n...[truncated {len(value) - len(head)} chars]..."


def _fit_page_image_prompt_to_limit(
    *,
    project: Project,
    style: ProjectImageStyle,
    page_number: int,
    page_text: str,
    full_text: str,
    relevant_elements: list[ProjectImageElement],
    dictionary_entry: PictureDictionaryEntry | None = None,
    discourage_text_in_image: bool = False,
    max_chars: int = 12000,
) -> tuple[str, dict[str, Any]]:
    """Build a page-image prompt and iteratively trim when it exceeds limits."""

    full_text_limit = 1200
    element_desc_limit = 600
    element_prompt_limit = 350
    max_relevant_elements = 3

    def _element_text_for_page(text: str, page_number_value: int) -> str:
        value = str(text or "")
        if not value.strip():
            return value
        kept: list[str] = []
        for line in value.splitlines():
            candidate = line.strip()
            if not candidate:
                kept.append(line)
                continue
            lowered = candidate.lower()
            if "page" not in lowered:
                kept.append(line)
                continue
            page_nums = [int(n) for n in re.findall(r"\b\d+\b", candidate)]
            if not page_nums or page_number_value in page_nums:
                kept.append(line)
        filtered = "\n".join(kept).strip()
        return filtered or value

    def _build_with_limits() -> str:
        trimmed_elements: list[ProjectImageElement] = []
        for element in relevant_elements[:max_relevant_elements]:
            clone = ProjectImageElement(
                name=element.name,
                element_type=element.element_type,
                expanded_description=_truncate_for_prompt(
                    _element_text_for_page(
                        element.expanded_description or element.why_consistency_matters or "",
                        page_number,
                    ),
                    max_chars=element_desc_limit,
                ),
                expanded_prompt=_truncate_for_prompt(
                    _element_text_for_page(element.expanded_prompt or "", page_number),
                    max_chars=element_prompt_limit,
                ),
                image_path=element.image_path,
            )
            trimmed_elements.append(clone)
        return _build_page_image_prompt(
            project=project,
            style=style,
            page_number=page_number,
            page_text=page_text,
            full_text=_truncate_for_prompt(full_text, max_chars=full_text_limit),
            relevant_elements=trimmed_elements,
            dictionary_entry=dictionary_entry,
            discourage_text_in_image=discourage_text_in_image,
        )

    prompt = _build_with_limits()
    strategy = "none"
    if len(prompt) > max_chars:
        full_text_limit = 800
        strategy = "truncate_full_text"
        prompt = _build_with_limits()
    if len(prompt) > max_chars:
        element_desc_limit = 350
        element_prompt_limit = 250
        max_relevant_elements = 2
        strategy = "truncate_elements_350_top2"
        prompt = _build_with_limits()
    if len(prompt) > max_chars:
        element_desc_limit = 200
        element_prompt_limit = 200
        max_relevant_elements = 1
        strategy = "truncate_elements_200"
        prompt = _build_with_limits()
    if len(prompt) > max_chars:
        strategy = "hard_cut"
        prompt = _truncate_for_prompt(prompt, max_chars=max_chars)

    metadata = {
        "max_chars": max_chars,
        "final_length": len(prompt),
        "strategy": strategy,
        "trimmed": strategy != "none",
    }
    return prompt, metadata


def _append_page_image_telemetry(project: Project, record: dict[str, Any]) -> None:
    telemetry_path = _image_pages_dir(project) / "telemetry.jsonl"
    telemetry_path.parent.mkdir(parents=True, exist_ok=True)
    entry = dict(record)
    entry["timestamp"] = datetime.now(timezone.utc).isoformat()
    with telemetry_path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _append_image_billing_telemetry(project: Project, record: dict[str, Any]) -> None:
    telemetry_path = project.artifact_dir() / "images" / "billing_telemetry.jsonl"
    telemetry_path.parent.mkdir(parents=True, exist_ok=True)
    entry = dict(record)
    entry["timestamp"] = datetime.now(timezone.utc).isoformat()
    with telemetry_path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(entry, ensure_ascii=False) + "\n")


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
            "preferred_variant_id",
            "image_revised_prompt",
            "status",
            "updated_at",
        )
    )
    (pages_dir / "pages_list.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    variants = list(
        ProjectImagePageVariant.objects.filter(page__project=project)
        .order_by("page__page_number", "variant_index", "id")
        .values(
            "id",
            "page_id",
            "variant_index",
            "image_model",
            "image_path",
            "generation_prompt",
            "image_revised_prompt",
            "status",
            "updated_at",
        )
    )
    (pages_dir / "variants_list.json").write_text(
        json.dumps(variants, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def _page_artifact_links(project: Project) -> list[dict[str, str]]:
    pages_dir = _image_pages_dir(project)
    pages_dir.mkdir(parents=True, exist_ok=True)
    telemetry_path = pages_dir / "telemetry.jsonl"
    if not telemetry_path.exists():
        telemetry_path.write_text("", encoding="utf-8")
    files = [
        ("pages_list.json", "Pages list"),
        ("variants_list.json", "Variants list"),
        ("telemetry.jsonl", "Page images telemetry"),
    ]
    links: list[dict[str, str]] = []
    for rel_name, label in files:
        path = pages_dir / rel_name
        if not path.exists():
            continue
        relpath = os.path.relpath(path, project.artifact_dir()).replace("\\", "/")
        links.append(
            {
                "label": label,
                "url": reverse("project-compiled", args=[project.pk, relpath]),
                "size": str(path.stat().st_size),
            }
        )
    billing_path = project.artifact_dir() / "images" / "billing_telemetry.jsonl"
    if billing_path.exists():
        relpath = os.path.relpath(billing_path, project.artifact_dir()).replace("\\", "/")
        links.append(
            {
                "label": "Image billing telemetry",
                "url": reverse("project-compiled", args=[project.pk, relpath]),
                "size": str(billing_path.stat().st_size),
            }
        )
    return links


def _set_page_preferred_variant(page: ProjectImagePage, variant: ProjectImagePageVariant) -> None:
    ProjectImagePage.objects.filter(pk=page.pk).update(
        preferred_variant=variant,
        image_path=variant.image_path,
        image_revised_prompt=variant.image_revised_prompt,
        image_model=variant.image_model,
        generation_prompt=variant.generation_prompt,
        status=variant.status,
    )


def _apply_preferred_variant_selection(project: Project, post_data) -> int:
    changed = 0
    pages = list(ProjectImagePage.objects.filter(project=project).order_by("page_number", "id"))
    for page in pages:
        requested = (post_data.get(f"preferred_variant_{page.id}") or "").strip()
        if not requested:
            continue
        try:
            preferred_id = int(requested)
        except ValueError:
            continue
        variant = ProjectImagePageVariant.objects.filter(page=page, pk=preferred_id).first()
        if not variant:
            continue
        if page.preferred_variant_id != variant.id or page.image_path != variant.image_path:
            _set_page_preferred_variant(page, variant)
            changed += 1
    return changed


def _generate_project_page_images(
    project: Project,
    *,
    image_model: str,
    variants_per_page: int = 1,
    discourage_text_in_image: bool = False,
    include_full_text: bool = True,
    include_elements: bool = True,
    missing_only: bool = False,
) -> int:
    style = project.image_style
    dictionary = getattr(project, "picture_dictionary", None)
    dictionary_entry_by_page: dict[int, PictureDictionaryEntry] = {}
    dictionary_entry_by_surface: dict[str, PictureDictionaryEntry] = {}
    if dictionary:
        for entry in dictionary.entries.filter(is_active=True):
            surface_key = (entry.surface or entry.lemma or "").strip().casefold()
            if surface_key and surface_key not in dictionary_entry_by_surface:
                dictionary_entry_by_surface[surface_key] = entry
            if entry.current_page_number and entry.current_page_number not in dictionary_entry_by_page:
                dictionary_entry_by_page[entry.current_page_number] = entry
    full_text = _extract_project_plain_text(project) if include_full_text else ""
    pages_dir = _image_pages_dir(project)
    pages_dir.mkdir(parents=True, exist_ok=True)
    page_rows = list(project.image_pages.order_by("page_number", "id"))
    if missing_only:
        page_rows = [row for row in page_rows if not row.image_path]
    relevant_elements = []
    if include_elements:
        relevant_elements = [
            element
            for element in project.image_elements.order_by("name", "id")
            if element.image_path
        ]
    if not page_rows:
        return 0

    usage_events: list[dict[str, Any]] = []
    usage_reporter = _collect_usage_event(usage_events)

    variants_per_page = max(1, min(8, int(variants_per_page or 1)))
    prompt_by_page: dict[int, str] = {}
    for page_obj in page_rows:
        refs = [
            element
            for element in relevant_elements
            if not element.page_refs or _page_refs_match(element.page_refs, page_obj.page_number)
        ]
        dictionary_entry = dictionary_entry_by_page.get(page_obj.page_number)
        if dictionary_entry is None:
            dictionary_entry = dictionary_entry_by_surface.get((page_obj.page_text or "").strip().casefold())
        prompt, prompt_meta = _fit_page_image_prompt_to_limit(
            project=project,
            style=style,
            page_number=page_obj.page_number,
            page_text=page_obj.page_text,
            full_text=full_text,
            relevant_elements=refs,
            discourage_text_in_image=discourage_text_in_image,
            dictionary_entry=dictionary_entry,
        )
        prompt_by_page[page_obj.pk] = prompt
        _append_page_image_telemetry(
            project,
            {
                "event": "page_image_request",
                "page_number": page_obj.page_number,
                "model": image_model,
                "variants_requested": variants_per_page,
                "prompt": prompt,
                "prompt_length": len(prompt),
                "prompt_meta": prompt_meta,
                "discourage_text_in_image": discourage_text_in_image,
                "relevant_element_count": len(refs),
                "relevant_element_paths": [e.image_path for e in refs if e.image_path],
                "reference_images_sent_in_request": False,
                "dictionary_mode": dictionary_entry is not None,
            },
        )

    def _generate_one_variant(page_obj: ProjectImagePage, variant_index: int) -> tuple[int, int, str, str, str, str]:
        prompt = prompt_by_page[page_obj.pk]
        started = datetime.now(timezone.utc)
        client = _build_ai_client(
            model_name=image_model,
            usage_reporter=usage_reporter,
        )
        page_dir = pages_dir / f"page_{page_obj.page_number:03d}"
        page_dir.mkdir(parents=True, exist_ok=True)
        try:
            image_result = client.generate_image(prompt, model=image_model)
        except Exception as exc:
            elapsed_s = (datetime.now(timezone.utc) - started).total_seconds()
            _append_page_image_telemetry(
                project,
                {
                    "event": "page_image_timeout" if _is_timeout_exception(exc) else "page_image_error",
                    "page_number": page_obj.page_number,
                    "variant_index": variant_index,
                    "model": image_model,
                    "elapsed_s": round(elapsed_s, 3),
                    **_exception_telemetry_fields(exc),
                },
            )
            raise
        image_path = page_dir / f"variant_{variant_index:03d}.png"
        image_path.write_bytes(image_result["bytes"])
        rel_path = image_path.relative_to(project.artifact_dir()).as_posix()
        revised_prompt = image_result.get("revised_prompt") or ""
        metadata = {
            "page_number": page_obj.page_number,
            "variant_index": variant_index,
            "prompt": prompt,
            "model": image_model,
            "revised_prompt": revised_prompt,
            "image_path": rel_path,
        }
        (page_dir / f"metadata_variant_{variant_index:03d}.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        _append_page_image_telemetry(
            project,
            {
                "event": "page_image_response",
                "page_number": page_obj.page_number,
                "variant_index": variant_index,
                "model": image_model,
                "elapsed_s": round((datetime.now(timezone.utc) - started).total_seconds(), 3),
                "revised_prompt": revised_prompt,
                "image_path": rel_path,
            },
        )
        return page_obj.pk, page_obj.page_number, variant_index, rel_path, revised_prompt, prompt

    generated = 0
    outputs_by_page: dict[int, list[tuple[int, str, str, str]]] = {}
    futures = {}
    max_workers = min(24, max(1, len(page_rows) * variants_per_page))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for page_obj in page_rows:
            for variant_index in range(1, variants_per_page + 1):
                future = executor.submit(_generate_one_variant, page_obj, variant_index)
                futures[future] = page_obj.pk
        for future in as_completed(futures):
            page_pk, _page_number, variant_index, rel_path, revised_prompt, prompt = future.result()
            outputs_by_page.setdefault(page_pk, []).append((variant_index, rel_path, revised_prompt, prompt))
            generated += 1

    for page_obj in page_rows:
        outputs = sorted(outputs_by_page.get(page_obj.pk, []), key=lambda tup: tup[0])
        if not outputs:
            continue
        preferred_variant = page_obj.preferred_variant if page_obj.preferred_variant_id else None
        for variant_index, rel_path, revised_prompt, prompt in outputs:
            variant, _ = ProjectImagePageVariant.objects.update_or_create(
                page_id=page_obj.pk,
                variant_index=variant_index,
                defaults={
                    "image_model": image_model,
                    "image_path": rel_path,
                    "image_revised_prompt": revised_prompt,
                    "generation_prompt": prompt,
                    "status": ProjectImagePage.STATUS_GENERATED,
                },
            )
            if preferred_variant is None and variant_index == 1:
                preferred_variant = variant
        if preferred_variant is not None:
            _set_page_preferred_variant(page_obj, preferred_variant)

    billing_reporter = _billing_usage_reporter(
        user_id=project.owner_id,
        project_id=project.id,
        request_type="image_pages_generate_image",
    )
    for event in usage_events:
        billing_reporter(event)

    return generated


def _generate_requested_page_variants(
    *,
    project: Project,
    image_model: str,
    requests: list[tuple[ProjectImagePage, int, str]],
) -> int:
    pages_dir = _image_pages_dir(project)
    pages_dir.mkdir(parents=True, exist_ok=True)
    generated = 0
    page_by_id = {page.id: page for page, _count, _prompt in requests}
    usage_events: list[dict[str, Any]] = []
    usage_reporter = _collect_usage_event(usage_events)

    def _generate_one(page: ProjectImagePage, variant_index: int, prompt: str) -> tuple[int, int, str, str, str]:
        started = datetime.now(timezone.utc)
        client = _build_ai_client(
            model_name=image_model,
            usage_reporter=usage_reporter,
        )
        image_result = client.generate_image(prompt, model=image_model)
        page_dir = pages_dir / f"page_{page.page_number:03d}"
        page_dir.mkdir(parents=True, exist_ok=True)
        image_path = page_dir / f"variant_{variant_index:03d}.png"
        image_path.write_bytes(image_result["bytes"])
        rel_path = image_path.relative_to(project.artifact_dir()).as_posix()
        revised_prompt = image_result.get("revised_prompt") or ""
        _append_page_image_telemetry(
            project,
            {
                "event": "community_variant_response",
                "page_number": page.page_number,
                "variant_index": variant_index,
                "model": image_model,
                "elapsed_s": round((datetime.now(timezone.utc) - started).total_seconds(), 3),
            },
        )
        return page.id, variant_index, rel_path, revised_prompt, prompt

    futures = {}
    max_workers = min(24, max(1, sum(count for _p, count, _prompt in requests)))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for page, count, prompt in requests:
            max_variant = page.variants.aggregate(max_idx=Max("variant_index")).get("max_idx") or 0
            for offset in range(1, count + 1):
                idx = max_variant + offset
                futures[executor.submit(_generate_one, page, idx, prompt)] = page.id
        for future in as_completed(futures):
            page_id, variant_index, rel_path, revised_prompt, prompt = future.result()
            variant, _ = ProjectImagePageVariant.objects.update_or_create(
                page_id=page_id,
                variant_index=variant_index,
                defaults={
                    "image_model": image_model,
                    "image_path": rel_path,
                    "generation_prompt": prompt,
                    "image_revised_prompt": revised_prompt,
                    "status": ProjectImagePageVariant.STATUS_GENERATED,
                },
            )
            page = page_by_id.get(page_id)
            if page is None:
                page = ProjectImagePage.objects.get(pk=page_id)
            if not page.preferred_variant_id:
                _set_page_preferred_variant(page, variant)
            generated += 1

    billing_reporter = _billing_usage_reporter(
        user_id=project.owner_id,
        project_id=project.id,
        request_type="community_generate_image_variant",
    )
    for event in usage_events:
        billing_reporter(event)

    return generated


def register(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            _ensure_bootstrap_admin(user)
            Profile.objects.get_or_create(user=user)
            messages.success(request, "Account created. Please log in.")
            return redirect("login")
    else:
        form = RegistrationForm()
    return render(request, "projects/register.html", {"form": form})


@login_required
def profile(request: HttpRequest) -> HttpResponse:
    _ensure_bootstrap_admin(request.user)
    profile_obj, _ = Profile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        action = (request.POST.get("memory_action") or "").strip().lower()
        if action == "clear":
            profile_obj.dialogue_memory = {}
            profile_obj.save(update_fields=["dialogue_memory", "updated_at"])
            messages.success(request, "Dialogue memory cleared.")
            return redirect("profile")
        form = ProfileForm(request.POST, instance=profile_obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile saved.")
            return redirect("profile")
    else:
        form = ProfileForm(instance=profile_obj)

    return render(request, "projects/profile_form.html", {"form": form})


def _audio_cache_language_choices() -> list[tuple[str, str]]:
    labels = {code: label for code, label in ProjectForm.LANGUAGE_CHOICES}
    root = Path(settings.MEDIA_ROOT).resolve() / "audio_repository"
    known_codes = set(labels.keys())
    if root.exists():
        for child in root.iterdir():
            if child.is_dir():
                known_codes.add(child.name.replace("_", "-"))
    return sorted(
        [(code, f"{labels.get(code, code)} ({code})") for code in known_codes],
        key=lambda item: item[1].lower(),
    )


def _extract_openai_pricing_with_ai(
    *,
    source_url: str,
    models_to_extract: list[str],
    ai_model: str | None = None,
) -> dict[str, dict[str, str]]:
    with urllib.request.urlopen(source_url, timeout=20) as response_fp:
        html = response_fp.read().decode("utf-8", errors="replace")
    html_excerpt = html[:120000]
    model_list = ", ".join(sorted(set(models_to_extract)))
    prompt = (
        "Extract USD token prices per 1M tokens from the supplied OpenAI pricing HTML.\n"
        f"Return only these models if present: {model_list}.\n"
        "Output JSON object with shape:\n"
        '{"prices":[{"model":"...","input_usd_per_1m":"...","output_usd_per_1m":"...","evidence":"..."}]}\n'
        "Use decimal strings. If not found, omit the model.\n\n"
        f"HTML SOURCE URL: {source_url}\n\nHTML:\n{html_excerpt}"
    )
    pricing_model = ai_model or getattr(settings, "OPENAI_PRICING_AI_MODEL", "gpt-5")
    client = _build_ai_client(model_name=pricing_model)
    payload = asyncio.run(client.chat_json(prompt, model=pricing_model))
    rows = payload.get("prices") if isinstance(payload, dict) else []
    result: dict[str, dict[str, str]] = {}
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        model_name = str(row.get("model") or "").strip()
        if not model_name:
            continue
        result[model_name] = {
            "input": str(row.get("input_usd_per_1m") or ""),
            "output": str(row.get("output_usd_per_1m") or ""),
            "evidence": str(row.get("evidence") or ""),
        }
    return result


@login_required
def admin_tools(request: HttpRequest) -> HttpResponse:
    _require_admin(request.user)
    delete_form = DeleteCachedWordAudioForm(language_choices=_audio_cache_language_choices())
    grant_form = GrantAdminPrivilegesForm(
        queryset=get_user_model().objects.filter(is_staff=False).order_by("username")
    )
    community_form = AdminCommunityForm()
    community_membership_form = AdminCommunityMembershipForm()
    delete_community_form = AdminDeleteCommunityForm()
    adjust_credits_form = AdminAdjustCreditsForm()
    pricing_form = AdminOpenAIPricingForm()
    pricing_rows_qs = OpenAIModelPricing.objects.all().order_by("model_name")
    pricing_rows = list(pricing_rows_qs)
    menu_models = sorted(set(AI_MODEL_CHOICES + IMAGE_MODEL_CHOICES))
    now_ts = django_timezone.now()
    pricing_by_model = {row.model_name: row for row in pricing_rows}
    pricing_matrix: list[dict[str, Any]] = []
    for model_name in menu_models:
        row = pricing_by_model.get(model_name)
        age_hours: float | None = None
        stale = True
        if row and row.last_synced_at:
            age_delta = now_ts - row.last_synced_at
            age_hours = round(age_delta.total_seconds() / 3600.0, 1)
            stale = age_delta > timedelta(days=1)
        pricing_matrix.append(
            {
                "model_name": model_name,
                "row": row,
                "input_value": row.input_usd_per_1m if row else "",
                "output_value": row.output_usd_per_1m if row else "",
                "age_hours": age_hours,
                "stale": stale,
            }
        )

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        if action == "delete_audio_cache":
            delete_form = DeleteCachedWordAudioForm(
                request.POST,
                language_choices=_audio_cache_language_choices(),
            )
            if delete_form.is_valid():
                language = delete_form.cleaned_data["language"]
                cache_dir = _audio_repository_dir(language)
                if cache_dir.exists():
                    shutil.rmtree(cache_dir)
                    messages.success(request, f"Deleted cached word audio for {language}.")
                else:
                    messages.info(request, f"No cached word audio found for {language}.")
                return redirect("admin-tools")
        elif action == "grant_admin":
            grant_form = GrantAdminPrivilegesForm(
                request.POST,
                queryset=get_user_model().objects.filter(is_staff=False).order_by("username"),
            )
            if grant_form.is_valid():
                user_obj = grant_form.cleaned_data["user"]
                user_obj.is_staff = True
                user_obj.save(update_fields=["is_staff"])
                messages.success(request, f"{user_obj.username} now has admin privileges.")
                return redirect("admin-tools")
        elif action == "adjust_credits":
            adjust_credits_form = AdminAdjustCreditsForm(request.POST)
            if adjust_credits_form.is_valid():
                user_obj = adjust_credits_form.cleaned_data["user"]
                amount = adjust_credits_form.cleaned_data["amount_usd"]
                reason = (adjust_credits_form.cleaned_data.get("reason") or "Manual admin adjustment").strip()
                entry = apply_credit_delta(
                    user=user_obj,
                    amount_usd=amount,
                    entry_type=CreditLedgerEntry.ENTRY_ADMIN_ADJUST,
                    description=reason,
                    metadata={"admin_user_id": request.user.id},
                )
                messages.success(
                    request,
                    f"Adjusted {user_obj.username} by ${amount:.4f}. New balance: ${entry.balance_after_usd:.4f}.",
                )
                return redirect("admin-tools")
        elif action == "create_community":
            community_form = AdminCommunityForm(request.POST)
            if community_form.is_valid():
                community = community_form.save()
                messages.success(request, f"Created community {community.name}.")
                return redirect("admin-tools")
        elif action == "assign_community_role":
            community_membership_form = AdminCommunityMembershipForm(request.POST)
            if community_membership_form.is_valid():
                community = community_membership_form.cleaned_data["community"]
                user_obj = community_membership_form.cleaned_data["user"]
                role = community_membership_form.cleaned_data["role"]
                membership, created = CommunityMembership.objects.get_or_create(
                    community=community,
                    user=user_obj,
                    defaults={"role": role},
                )
                if not created and membership.role != role:
                    membership.role = role
                    membership.save(update_fields=["role", "updated_at"])
                verb = "Added" if created else "Updated"
                messages.success(request, f"{verb} {user_obj.username} as {role} in {community.name}.")
                return redirect("admin-tools")
        elif action == "delete_community":
            delete_community_form = AdminDeleteCommunityForm(request.POST)
            if delete_community_form.is_valid():
                community = delete_community_form.cleaned_data["community"]
                community_name = community.name
                community.delete()
                messages.success(request, f"Deleted community {community_name}.")
                return redirect("admin-tools")
        elif action == "save_openai_pricing":
            pricing_form = AdminOpenAIPricingForm(request.POST)
            if pricing_form.is_valid():
                pricing_obj, created = OpenAIModelPricing.objects.get_or_create(
                    model_name=pricing_form.cleaned_data["model_name"],
                    defaults={
                        "input_usd_per_1m": pricing_form.cleaned_data["input_usd_per_1m"],
                        "output_usd_per_1m": pricing_form.cleaned_data["output_usd_per_1m"],
                        "source_url": pricing_form.cleaned_data.get("source_url") or "",
                        "status": OpenAIModelPricing.STATUS_HUMAN_REVISED,
                        "last_human_reviewed_at": django_timezone.now(),
                        "notes": pricing_form.cleaned_data.get("notes") or "",
                    },
                )
                if not created:
                    pricing_obj.input_usd_per_1m = pricing_form.cleaned_data["input_usd_per_1m"]
                    pricing_obj.output_usd_per_1m = pricing_form.cleaned_data["output_usd_per_1m"]
                    pricing_obj.source_url = pricing_form.cleaned_data.get("source_url") or pricing_obj.source_url
                    pricing_obj.status = OpenAIModelPricing.STATUS_HUMAN_REVISED
                    pricing_obj.last_human_reviewed_at = django_timezone.now()
                    pricing_obj.notes = pricing_form.cleaned_data.get("notes") or pricing_obj.notes
                    pricing_obj.save(
                        update_fields=[
                            "input_usd_per_1m",
                            "output_usd_per_1m",
                            "source_url",
                            "status",
                            "last_human_reviewed_at",
                            "notes",
                            "updated_at",
                        ]
                    )
                messages.success(request, f"Saved pricing for {pricing_obj.model_name}.")
                return redirect("admin-tools")
        elif action == "sync_openai_pricing_ai":
            source_url = (request.POST.get("source_url") or "https://developers.openai.com/api/docs/pricing").strip()
            models_to_extract = getattr(settings, "OPENAI_PRICING_TRACKED_MODELS", AI_MODEL_CHOICES)
            try:
                extracted = _extract_openai_pricing_with_ai(
                    source_url=source_url,
                    models_to_extract=list(models_to_extract),
                    ai_model=getattr(settings, "OPENAI_PRICING_AI_MODEL", "gpt-5"),
                )
                changed = 0
                now = django_timezone.now()
                for model_name, prices in extracted.items():
                    input_price = prices.get("input")
                    output_price = prices.get("output")
                    if not input_price or not output_price:
                        continue
                    notes = f"AI-parsed evidence: {prices.get('evidence', '')}".strip()
                    obj, _ = OpenAIModelPricing.objects.get_or_create(
                        model_name=model_name,
                        defaults={
                            "input_usd_per_1m": input_price,
                            "output_usd_per_1m": output_price,
                            "source_url": source_url,
                            "status": OpenAIModelPricing.STATUS_AI_PARSED,
                            "last_synced_at": now,
                            "notes": notes,
                        },
                    )
                    obj.input_usd_per_1m = input_price
                    obj.output_usd_per_1m = output_price
                    obj.source_url = source_url
                    obj.status = OpenAIModelPricing.STATUS_AI_PARSED
                    obj.last_synced_at = now
                    if notes:
                        obj.notes = notes
                    obj.save(
                        update_fields=[
                            "input_usd_per_1m",
                            "output_usd_per_1m",
                            "source_url",
                            "status",
                            "last_synced_at",
                            "notes",
                            "updated_at",
                        ]
                    )
                    changed += 1
                messages.success(request, f"AI pricing sync completed: {changed} model row(s) updated.")
            except Exception as exc:
                messages.error(
                    request,
                    f"AI pricing sync failed: {exc}. Please use the manual pricing table below.",
                )
            return redirect("admin-tools")
        elif action == "save_openai_pricing_bulk":
            source_url = (request.POST.get("source_url") or "").strip()
            changed = 0
            for model_name in menu_models:
                input_raw = (request.POST.get(f"bulk_input_{model_name}") or "").strip()
                output_raw = (request.POST.get(f"bulk_output_{model_name}") or "").strip()
                if not input_raw or not output_raw:
                    continue
                row, _ = OpenAIModelPricing.objects.get_or_create(
                    model_name=model_name,
                    defaults={
                        "input_usd_per_1m": input_raw,
                        "output_usd_per_1m": output_raw,
                        "source_url": source_url,
                        "status": OpenAIModelPricing.STATUS_HUMAN_REVISED,
                        "last_human_reviewed_at": django_timezone.now(),
                    },
                )
                row.input_usd_per_1m = input_raw
                row.output_usd_per_1m = output_raw
                if source_url:
                    row.source_url = source_url
                row.status = OpenAIModelPricing.STATUS_HUMAN_REVISED
                row.last_human_reviewed_at = django_timezone.now()
                row.last_synced_at = django_timezone.now()
                row.save(
                    update_fields=[
                        "input_usd_per_1m",
                        "output_usd_per_1m",
                        "source_url",
                        "status",
                        "last_human_reviewed_at",
                        "last_synced_at",
                        "updated_at",
                    ]
                )
                changed += 1
            messages.success(request, f"Saved manual pricing for {changed} model row(s).")
            return redirect("admin-tools")
        elif action == "backfill_project_discovery_keywords":
            force = bool(request.POST.get("force_backfill_keywords"))
            try:
                call_command(
                    "backfill_project_discovery_keywords",
                    admin_username=request.user.username,
                    force=force,
                )
                msg = "Backfill started for discovery keywords (forced)." if force else "Backfill started for missing/stale discovery keywords."
                messages.success(request, msg)
            except Exception as exc:
                messages.error(request, f"Keyword backfill failed: {exc}")
            return redirect("admin-tools")
        else:
            messages.error(request, "Unknown admin action.")

    community_rows: list[dict[str, Any]] = []
    for community in Community.objects.prefetch_related("memberships__user").order_by("name"):
        members = list(community.memberships.all())
        organisers = [m.user.username for m in members if m.role == CommunityMembership.ROLE_ORGANISER]
        all_members = [f"{m.user.username} ({m.role})" for m in members]
        community_rows.append(
            {
                "name": community.name,
                "language": community.language,
                "is_active": community.is_active,
                "organisers_text": ", ".join(organisers) if organisers else "—",
                "members_text": ", ".join(all_members) if all_members else "—",
            }
        )

    return render(
        request,
        "projects/admin_tools.html",
        {
            "delete_audio_form": delete_form,
            "grant_admin_form": grant_form,
            "community_form": community_form,
            "community_membership_form": community_membership_form,
            "delete_community_form": delete_community_form,
            "adjust_credits_form": adjust_credits_form,
            "pricing_form": pricing_form,
            "pricing_rows": pricing_rows,
            "pricing_matrix": pricing_matrix,
            "pricing_source_default": "https://developers.openai.com/api/docs/pricing",
            "bootstrap_admin_usernames": sorted(_bootstrap_admin_usernames()),
            "current_admins": get_user_model().objects.filter(is_staff=True).order_by("username"),
            "community_rows": community_rows,
        },
    )


@login_required
def project_image_style(request: HttpRequest, pk: int) -> HttpResponse:
    project = _get_project_for_user(pk=pk, user=request.user, min_role=ProjectCollaborator.ROLE_ANNOTATOR)
    style_obj, _ = ProjectImageStyle.objects.get_or_create(
        project=project,
        defaults={"ai_model": project.ai_model or DEFAULT_MODEL},
    )

    if request.method == "POST":
        form_data = request.POST.copy()
        if "ai_model" not in form_data:
            form_data["ai_model"] = style_obj.ai_model or project.ai_model or DEFAULT_MODEL
        if "sample_image_model" not in form_data:
            form_data["sample_image_model"] = style_obj.sample_image_model or "gpt-image-1"
        if "status" not in form_data:
            form_data["status"] = style_obj.status or ProjectImageStyle.STATUS_DRAFT
        if "discourage_text_in_images" not in form_data and style_obj.discourage_text_in_images:
            form_data["discourage_text_in_images"] = "on"
        action = (
            form_data.get("action")
            or form_data.get("action_intent")
            or "save"
        ).strip()
        form = ProjectImageStyleForm(
            form_data,
            instance=style_obj,
            ai_model_choices=AI_MODEL_CHOICES,
            image_model_choices=IMAGE_MODEL_CHOICES,
        )
        if form.is_valid():
            style_obj = form.save(commit=False)
            request_payload = None
            response_payload = None
            had_error = False
            _append_style_telemetry(
                project,
                {
                    "type": "event",
                    "level": "info",
                    "message": "style action dispatch",
                    "action": action,
                },
            )

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
                    _append_style_telemetry(
                        project,
                        {
                            "type": "event",
                            "level": "error",
                            "message": "style expansion failed",
                            **_exception_telemetry_fields(exc),
                        },
                    )
                    messages.error(request, f"Style generation failed: {exc}")
                    had_error = True
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
                    if not (style_obj.expanded_style_description or "").strip():
                        messages.warning(
                            request,
                            "Style expansion returned an empty expanded style description. "
                            "Inspect style telemetry/response artifacts for details.",
                        )
                    if not (style_obj.sample_image_prompt or "").strip():
                        messages.warning(
                            request,
                            "Style expansion returned an empty sample image prompt. "
                            "Inspect style telemetry/response artifacts for details.",
                        )
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
                    _append_style_telemetry(
                        project,
                        {
                            "type": "event",
                            "level": "error",
                            "message": "style sample image failed",
                            **_exception_telemetry_fields(exc),
                        },
                    )
                    messages.error(request, f"Sample image generation failed: {exc}")
                    had_error = True
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
            notice = "error" if had_error else "done"
            return redirect(f"{reverse('project-image-style', args=[project.pk])}?notice={notice}")
        error_payload = form.errors.get_json_data(escape_html=True)
        _append_style_telemetry(
            project,
            {
                "type": "event",
                "level": "error",
                "message": "style form invalid",
                "action": action,
                "errors": error_payload,
            },
        )
        for field_name, errors in error_payload.items():
            for err in errors:
                messages.error(
                    request,
                    f"Style form error ({field_name}): {err.get('message', 'Invalid value')}",
                )
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
            "style_artifact_links": _style_artifact_links(project),
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
        action = request.POST.get("action") or request.POST.get("action_intent") or "save"
        requested_ai_model = (request.POST.get("ai_model") or "").strip()
        ai_model = requested_ai_model or style.ai_model or project.ai_model or DEFAULT_MODEL
        invalid_ai_model = ai_model not in AI_MODEL_CHOICES
        if invalid_ai_model:
            ai_model = DEFAULT_MODEL
        if ai_model != style.ai_model:
            style.ai_model = ai_model
            style.save(update_fields=["ai_model", "updated_at"])
        requested_image_model = (request.POST.get("image_model") or "").strip()
        image_model = requested_image_model or style.sample_image_model or "gpt-image-1"
        invalid_image_model = image_model not in IMAGE_MODEL_CHOICES
        if invalid_image_model:
            image_model = "gpt-image-1"
        formset = ProjectImageElementFormSet(request.POST, queryset=queryset)
        if formset.is_valid():
            _append_elements_telemetry(
                project,
                {
                    "type": "event",
                    "level": "info",
                    "message": "elements action dispatch",
                    "action": action,
                    "ai_model": ai_model,
                    "image_model": image_model,
                },
            )
            if action in {"discover", "expand"} and requested_ai_model and invalid_ai_model:
                messages.warning(
                    request,
                    f"Unknown text model '{requested_ai_model}'. Using {ai_model} instead.",
                )
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
                    f"Discovering recurring elements with {ai_model}.",
                )
                try:
                    discovered, request_payload, response_payload = _discover_project_image_elements(
                        project, ai_model=ai_model
                    )
                except Exception as exc:
                    logger.exception("Failed to discover image elements for project %s", project.pk)
                    _append_elements_telemetry(
                        project,
                        {
                            "type": "event",
                            "level": "error",
                            "message": "elements discovery failed",
                            "ai_model": ai_model,
                            **_exception_telemetry_fields(exc),
                        },
                    )
                    messages.error(request, f"Element discovery failed: {exc}")
                else:
                    project.image_elements.all().delete()
                    for item in discovered:
                        ProjectImageElement.objects.create(
                            project=project,
                            ai_model=ai_model,
                            status=ProjectImageElement.STATUS_PROPOSED,
                            **item,
                        )
                    _persist_image_elements_artifacts(
                        project,
                        request_payload=request_payload,
                        response_payload=response_payload,
                    )
                    if discovered:
                        messages.success(request, f"Discovered {len(discovered)} recurring elements.")
                    else:
                        diagnostics = response_payload.get("_diagnostics", {}) if isinstance(response_payload, dict) else {}
                        messages.warning(
                            request,
                            "No recurring elements were discovered. "
                            f"Diagnostics: raw={diagnostics.get('raw_elements_count', 0)}, "
                            f"usable={diagnostics.get('normalized_elements_count', 0)}, "
                            f"pages={diagnostics.get('pages_count', 0)}. "
                            "Inspect images/elements/elements_discovery_prompt.json and "
                            "images/elements/elements_discovery_response.json for details.",
                        )
            elif action == "expand":
                report_id = str(uuid.uuid4())
                async_task(
                    _run_expand_elements_task,
                    project.pk,
                    request.user.id,
                    ai_model,
                    report_id,
                    q_options={"sync": _running_tests()},
                )
                messages.info(
                    request,
                    f"Started element prompt expansion with {ai_model}. Tracking id: {report_id}.",
                )
                messages.info(request, "Refresh this page after a short delay to see completion messages.")
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
            "elements_artifact_links": _elements_artifact_links(project),
            "confirmed_count": project.image_elements.filter(is_confirmed=True).count(),
            "confirmed_with_prompts_count": project.image_elements.filter(is_confirmed=True).exclude(expanded_prompt="").count(),
            "elements_count": project.image_elements.count(),
            "elements_with_prompts_count": project.image_elements.exclude(expanded_prompt="").count(),
            "elements_with_images_count": project.image_elements.exclude(image_path="").count(),
            "ai_models": AI_MODEL_CHOICES,
            "selected_ai_model": style.ai_model or project.ai_model or DEFAULT_MODEL,
            "image_models": IMAGE_MODEL_CHOICES,
            "selected_image_model": request.GET.get("image_model")
            or style.sample_image_model
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
        action = request.POST.get("action") or request.POST.get("action_intent") or "save"
        requested_image_model = (request.POST.get("image_model") or "").strip()
        requested_variants_per_page = request.POST.get("variants_per_page") or "1"
        try:
            variants_per_page = max(1, min(8, int(requested_variants_per_page)))
        except ValueError:
            variants_per_page = 1
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
                    generated = _generate_project_page_images(
                        project,
                        image_model=image_model,
                        variants_per_page=variants_per_page,
                        discourage_text_in_image=bool(style.discourage_text_in_images),
                    )
                except Exception as exc:
                    logger.exception("Failed to generate page images for project %s", project.pk)
                    _append_page_image_telemetry(
                        project,
                        {
                            "event": "page_images_generation_failed",
                            "model": image_model,
                            **_exception_telemetry_fields(exc),
                        },
                    )
                    messages.error(request, f"Page image generation failed: {exc}")
                else:
                    messages.success(
                        request,
                        f"Generated {generated} page image variant(s) with {image_model}.",
                    )
            elif action == "set_preferred":
                changed = _apply_preferred_variant_selection(project, request.POST)
                messages.success(request, f"Updated preferred image for {changed} page(s).")
            else:
                messages.success(request, "Saved page image prompt edits.")
            if action in {"save", "refresh", "generate_images"}:
                changed = _apply_preferred_variant_selection(project, request.POST)
                if changed:
                    messages.success(request, f"Updated preferred image for {changed} page(s).")
            _persist_image_pages_artifacts(project)
            return redirect(f"{reverse('project-image-pages', args=[project.pk])}?notice=done")
        messages.error(
            request,
            "Could not process the page image request. Please review the form rows for errors.",
        )
    else:
        formset = ProjectImagePageFormSet(queryset=queryset)
    for form in formset.forms:
        setattr(form.instance, "variants_for_ui", list(form.instance.variants.order_by("variant_index", "id")))

    return render(
        request,
        "projects/project_image_pages.html",
        {
            "project": project,
            "style": style,
            "formset": formset,
            "pages_artifact_dir": _image_pages_dir(project),
            "pages_artifact_links": _page_artifact_links(project),
            "image_models": IMAGE_MODEL_CHOICES,
            "selected_image_model": request.GET.get("image_model") or "gpt-image-1",
            "default_variants_per_page": 1,
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
        _ensure_bootstrap_admin(self.request.user)
        return _projects_for_user(self.request.user)

    def get_context_data(self, **kwargs):  # type: ignore[override]
        context = super().get_context_data(**kwargs)
        nl_query = (self.request.GET.get("nl_open_query") or "").strip()
        dialogue_language = (self.request.GET.get("dialogue_language") or "").strip()
        if not dialogue_language:
            try:
                dialogue_language = self.request.user.profile.dialogue_language or "en"
            except Exception:
                dialogue_language = "en"
        nl_plan: dict[str, Any] = {}
        suggested_projects: list[Project] = []
        if nl_query:
            prev_query = ""
            prev_plan: dict[str, Any] = {}
            try:
                profile_obj = self.request.user.profile
            except Exception:
                profile_obj = None
            if (
                profile_obj
                and profile_obj.dialogue_memory_enabled
                and isinstance(profile_obj.dialogue_memory, dict)
            ):
                section_payload = _profile_memory_section(profile_obj, "project_open")
                prev_query = str(section_payload.get("last_nl_query") or "")
                prev_plan = section_payload.get("last_nl_plan") if isinstance(section_payload.get("last_nl_plan"), dict) else {}
            nl_plan = _parse_nl_project_open_request(
                nl_query=nl_query,
                dialogue_language=dialogue_language,
                previous_query=prev_query,
                previous_plan=prev_plan,
            )
            queryset = list(context["object_list"])
            title_filter = str(nl_plan.get("title") or "").strip()
            text_language = _normalize_language_filter(str(nl_plan.get("text_language") or ""))
            annotation_language = _normalize_language_filter(str(nl_plan.get("annotation_language") or ""))
            keywords = [str(k).strip().lower() for k in (nl_plan.get("keywords") or []) if str(k).strip()]
            if title_filter:
                queryset = [p for p in queryset if title_filter.lower() in (p.title or "").lower()]
            if text_language:
                queryset = [p for p in queryset if (p.language or "").lower().startswith(text_language)]
            if annotation_language:
                queryset = [p for p in queryset if (p.target_language or "").lower().startswith(annotation_language)]
            if keywords:
                queryset = [
                    p
                    for p in queryset
                    if any(kw in (p.title or "").lower() for kw in keywords)
                    or any(kw in (p.description or "").lower() for kw in keywords)
                    or any(kw in " ".join(p.discovery_keywords or []).lower() for kw in keywords)
                    or any(kw in " ".join(p.discovery_keywords_en or []).lower() for kw in keywords)
                ]
            suggested_projects = queryset[:8]
            if profile_obj and profile_obj.dialogue_memory_enabled:
                _update_profile_memory_section(
                    profile_obj,
                    "project_open",
                    _profile_memory_payload_for_nl(nl_query=nl_query, nl_plan=nl_plan),
                )
        context.update(
            {
                "nl_open_query": nl_query,
                "nl_open_plan": nl_plan,
                "dialogue_language": dialogue_language,
                "suggested_projects": suggested_projects,
                "dialogue_language_choices": ProjectForm.LANGUAGE_CHOICES,
            }
        )
        return context


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
            latest_stage_by_name: dict[str, Path] = {}
            for candidate_run in _iter_runs(project):
                stage_dir = candidate_run / "stages"
                if not stage_dir.exists():
                    continue
                for path in stage_dir.glob("*.json"):
                    current = latest_stage_by_name.get(path.name)
                    if current is None or path.stat().st_mtime > current.stat().st_mtime:
                        latest_stage_by_name[path.name] = path
            for path in sorted(latest_stage_by_name.values(), key=lambda p: p.stat().st_mtime):
                rel = path.resolve().relative_to(base).as_posix()
                url = f"{project_media_base}/{rel}"
                stage_files.append({"path": rel, "url": url})

            telemetry_rel = None
            telemetry_path = run_dir / "stages" / "telemetry.jsonl"
            if telemetry_path.exists():
                telemetry_rel = telemetry_path.resolve().relative_to(base).as_posix()
                stage_files.append(
                    {"path": telemetry_rel, "url": f"{project_media_base}/{telemetry_rel}"}
                )

            # Keep the MEDIA-relative run base stable for progress links.
            run_media_base = f"{project_media_base}/runs/{run_dir.name}"
            stage_dir = run_dir / "stages"
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
        context["default_start_stage"] = _default_start_stage_for_project(project)
        context["compiled_uri"] = compiled_uri
        context["compiled_media_url"] = compiled_media_url
        context["ai_models"] = AI_MODEL_CHOICES
        context["selected_ai_model"] = project.ai_model or DEFAULT_MODEL
        context["detailed_api_trace_default"] = False
        context["language_choices"] = ProjectForm.LANGUAGE_CHOICES
        context["project_text_direction"] = language_direction(project.language)
        context["project_annotation_direction"] = language_direction(project.target_language)
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
        usage_breakdown = (
            AIUsageCharge.objects.filter(project=project, status=AIUsageCharge.STATUS_CHARGED)
            .values("request_type")
            .annotate(total=Sum("cost_usd"))
            .order_by("request_type")
        )
        context["project_total_cost_usd"] = project.total_cost_usd
        context["project_cost_breakdown"] = [
            {"request_type": row["request_type"] or "unspecified", "total": row["total"] or 0}
            for row in usage_breakdown
        ]
        context.update(_manual_annotation_context(project))
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
        if context["current_user_role"] == ProjectCollaborator.ROLE_OWNER:
            context["discovery_metadata_form"] = ProjectDiscoveryMetadataForm(instance=project)
        assigned_ids = {c.user_id for c in collaborators}
        assigned_ids.add(project.owner_id)
        User = get_user_model()
        context["available_collaborator_users"] = User.objects.exclude(id__in=assigned_ids).order_by("username")[:500]
        eligible_communities = Community.objects.filter(
            language__iexact=project.language,
            memberships__user=self.request.user,
            memberships__role=CommunityMembership.ROLE_ORGANISER,
            is_active=True,
        ).order_by("name")
        context["eligible_project_communities"] = eligible_communities
        context["can_assign_project_community"] = bool(self.request.user == project.owner and eligible_communities.exists())
        context["exercise_sets"] = project.exercise_sets.all()[:20]
        return context


class ProjectAnnotationView(ProjectDetailView):
    template_name = "projects/project_annotation.html"

    def get_context_data(self, **kwargs):  # type: ignore[override]
        context = super().get_context_data(**kwargs)
        project: Project = context["object"]
        annotation_home = reverse("project-annotation-home", args=[project.pk])
        seg_review = reverse("manual-segmentation-phase-1", args=[project.pk])
        context["annotation_dialogue_plan"] = _annotation_dialogue_plan(project)
        context["annotation_plain_text"] = _base_text_for_segmentation_phase_1(project).strip()
        context["annotation_segmentation_review_href"] = f"{seg_review}?return_to={quote(annotation_home)}"
        return context


def _annotation_dialogue_plan(project: Project) -> dict[str, Any]:
    annotation_home = reverse("project-annotation-home", args=[project.pk])
    has_plain_text = bool(_base_text_for_segmentation_phase_1(project).strip())
    latest_segmentation = _find_latest_stage_file(project, "segmentation_phase_2.json")
    has_segmented = latest_segmentation is not None
    segmentation_review_href = (
        f"{reverse('manual-segmentation-phase-1', args=[project.pk])}?return_to={quote(annotation_home)}"
    )
    image_workflow_href = reverse("project-images-home", args=[project.pk])
    page_by_page_manual_href = reverse("manual-page-annotation", args=[project.pk])
    compiled_href: str | None = None
    compiled_page = _compiled_page_one_path(project)
    if compiled_page:
        compiled_href = reverse("project-compiled", args=[project.pk, compiled_page])
    has_html = bool(compiled_href) or _find_latest_stage_file(project, "compile_html.json") is not None

    if not has_plain_text:
        return {
            "title": "Suggested next step: create a first plain-text draft",
            "summary": "You do not yet have base text to annotate. I can generate a draft from your description and show it for approval.",
            "choices": [
                {
                    "label": "Generate plain text draft",
                    "description": "Runs text generation only.",
                    "start_stage": "text_gen",
                    "end_stage": "text_gen",
                }
            ],
        }

    if has_plain_text and not has_segmented:
        return {
            "title": "Suggested next step: split into pages/segments or preview HTML",
            "summary": "You already have plain text. Common next actions are segmentation for structured annotation, or a quick HTML preview.",
            "choices": [
                {
                    "label": "Split into pages and segments (recommended)",
                    "description": "Runs segmentation phases to prepare annotation-ready structure.",
                    "start_stage": "segmentation_phase_1",
                    "end_stage": "segmentation_phase_2",
                },
                {
                    "label": "Render HTML preview now",
                    "description": "Compiles to HTML so you can review quickly before detailed annotation.",
                    "start_stage": "segmentation_phase_1",
                    "end_stage": "compile_html",
                },
                {
                    "label": "Open image workflow",
                    "description": "Generate style, elements, and page images.",
                    "href": image_workflow_href,
                },
                {
                    "label": "Show current plain text",
                    "description": "Review the generated/source text before segmentation.",
                    "href": "#plain-text-preview",
                },
            ],
        }

    if has_plain_text and has_segmented and not has_html:
        return {
            "title": "Suggested next step: render HTML or move to images",
            "summary": "You already have segmented text. You can compile to HTML now, or continue to image workflow.",
            "choices": [
                {
                    "label": "Render HTML now (recommended)",
                    "description": "Compile the current annotations into browsable HTML.",
                    "start_stage": "translation",
                    "end_stage": "compile_html",
                },
                {
                    "label": "Open image workflow",
                    "description": "Go to image pages/elements generation controls.",
                    "href": image_workflow_href,
                },
                *(
                    [
                        {
                            "label": "Review/edit segmentation",
                            "description": "Open manual segmentation view to inspect and adjust boundaries.",
                            "href": segmentation_review_href,
                        },
                        {
                            "label": "Open page-by-page manual editor",
                            "description": "Edit translation and word-level annotations page by page.",
                            "href": page_by_page_manual_href,
                        }
                    ]
                    if has_segmented
                    else []
                ),
            ],
        }

    return {
        "title": "HTML is available — review and revise",
        "summary": "You can open the latest HTML now and then request corrections if anything looks wrong.",
        "choices": [
            {
                "label": "Open compiled HTML",
                "description": "View the latest compiled output.",
                "href": compiled_href or reverse("project-detail", args=[project.pk]),
            },
            {
                "label": "Compile HTML now",
                "description": "Run pipeline compilation to refresh HTML using default stage settings.",
                "start_stage": _default_start_stage_for_project(project),
                "end_stage": "compile_html",
            },
            {
                "label": "Open page-by-page manual editor",
                "description": "Edit translation and word-level annotations page by page.",
                "href": page_by_page_manual_href,
            },
            {
                "label": "Open image workflow",
                "description": "Generate style, elements, and page images.",
                "href": image_workflow_href,
            },
            {
                "label": "Open manual annotation editor",
                "description": "Make targeted corrections to segmentation, glosses, lemma, etc.",
                "href": reverse("manual-top-level", args=[project.pk]),
            },
            *(
                [
                    {
                        "label": "Review/edit segmentation",
                        "description": "Open manual segmentation view to inspect and adjust boundaries.",
                        "href": segmentation_review_href,
                    }
                ]
                if has_segmented
                else []
            ),
            {
                "label": "Show current plain text",
                "description": "Review the plain text currently feeding annotation.",
                "href": "#plain-text-preview",
            },
        ],
    }
def _ensure_stage_run_dir(project: Project) -> Path:
    run_dir = _resolve_run_dir(project)
    if run_dir is None:
        run_dir = _prepare_output_dir(project)
    stage_dir = run_dir / "stages"
    stage_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def _base_text_for_segmentation_phase_1(project: Project) -> str:
    source_text = (project.source_text or "").replace("\r\n", "\n")
    if source_text.strip():
        return source_text
    run_dir = _find_run_with_stage(project, "text_gen")
    payload = _load_stage_payload(project, "text_gen", run_dir=run_dir) if run_dir else None
    if isinstance(payload, dict):
        return str(payload.get("surface") or "").replace("\r\n", "\n")
    return ""


def _surface_without_phase1_markers(surface: str) -> str:
    text = str(surface or "").replace("\r\n", "\n")
    marker = "\uFFF0"
    marked = text.replace("<page>", f"{marker}P{marker}").replace("||", f"{marker}S{marker}")
    parts = marked.split(marker)
    out: list[str] = []
    pending_boundary = False
    for part in parts:
        if part in {"P", "S"}:
            pending_boundary = True
            continue
        if part == "":
            continue
        if pending_boundary and out:
            prev = out[-1][-1] if out[-1] else ""
            next_char = part[0]
            if prev and next_char and (not prev.isspace()) and (not next_char.isspace()):
                out.append(" ")
        out.append(part)
        pending_boundary = False
    return "".join(out)


def _phase1_comparison_hash(text: str) -> str:
    """Hash text with tolerant normalization for phase-1 boundary whitespace."""

    normalized = str(text or "").replace("\r\n", "\n")
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return _stable_text_hash(normalized)


def _annotation_return_to(request: HttpRequest, project: Project, *, default_manual: bool = False) -> str:
    default = (
        reverse("manual-top-level", args=[project.pk])
        if default_manual
        else reverse("project-annotation-home", args=[project.pk])
    )
    candidate = str(request.POST.get("return_to") or request.GET.get("return_to") or "").strip()
    if not candidate:
        return default
    if candidate.startswith(f"/projects/{project.pk}/annotation/"):
        return candidate
    return default


def _phase1_surface_from_payload(payload: dict[str, Any]) -> str:
    """Reconstruct editable phase-1 surface from page/segment structure."""

    pages = payload.get("pages") or []
    page_surfaces: list[str] = []
    for page in pages:
        segments = page.get("segments") or []
        seg_surfaces = [str((seg or {}).get("surface") or "") for seg in segments]
        page_surfaces.append("||".join(seg_surfaces))
    return "<page>".join(page_surfaces)


def _build_phase1_payload_from_surface(surface: str, language: str) -> dict[str, Any]:
    pages: list[dict[str, Any]] = []
    for page_raw in surface.split("<page>"):
        if page_raw == "":
            continue
        segments_raw = page_raw.split("||")
        segments = [{"surface": seg} for seg in segments_raw]
        pages.append({"surface": page_raw, "segments": segments, "annotations": {}})
    return {"l2": language, "surface": surface, "pages": pages, "annotations": {}}


def _phase2_preview_from_payload(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    for p_idx, page in enumerate(payload.get("pages", []) or [], start=1):
        lines.append(f"# Page {p_idx}")
        for s_idx, segment in enumerate(page.get("segments", []) or [], start=1):
            token_surfaces = _display_token_surfaces_for_segment(
                str(segment.get("surface") or ""),
                segment.get("tokens") or [],
            )
            if token_surfaces:
                lines.append(f"P{p_idx}S{s_idx}: " + "¦".join(token_surfaces))
            else:
                lines.append(f"P{p_idx}S{s_idx}: {segment.get('surface', '')}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _stable_text_hash(text: str) -> str:
    return hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def _save_versioned_stage_payload(
    *,
    project: Project,
    stage_name: str,
    payload: dict[str, Any],
    metadata: dict[str, Any],
    run_dir: Path | None = None,
) -> None:
    payload = normalize_json_text(payload)
    target_run = run_dir or _ensure_stage_run_dir(project)
    stage_dir = target_run / "stages"
    stage_dir.mkdir(parents=True, exist_ok=True)
    (stage_dir / f"{stage_name}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    versions_dir = stage_dir / "manual_versions"
    versions_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    version_payload = {"saved_at": stamp, "stage": stage_name, "metadata": metadata, "payload": payload}
    (versions_dir / f"{stage_name}_{stamp}.json").write_text(
        json.dumps(version_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _canonicalize_phase1_surface(surface: str) -> str:
    pages: list[str] = []
    for page in str(surface or "").replace("\r\n", "\n").split("<page>"):
        if page == "":
            continue
        segments = page.split("||")
        pages.append("||".join(segments))
    return "<page>".join(pages)


def _phase2_token_bar_rows(seg1_payload: dict[str, Any], seg2_payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for p_idx, (base_page, edited_page) in enumerate(
        zip(seg1_payload.get("pages") or [], seg2_payload.get("pages") or []),
        start=1,
    ):
        for s_idx, (base_segment, edited_segment) in enumerate(
            zip(base_page.get("segments") or [], edited_page.get("segments") or []),
            start=1,
        ):
            segment_text = str(base_segment.get("surface") or "")
            token_surfaces = _display_token_surfaces_for_segment(
                segment_text,
                edited_segment.get("tokens") or [],
            )
            tokenized_text = "¦".join(token_surfaces) if token_surfaces else segment_text
            rows.append(
                {
                    "page_index": p_idx,
                    "segment_index": s_idx,
                    "segment_text": segment_text,
                    "tokenized_text": tokenized_text,
                }
            )
    return rows


def _phase2_payload_from_bar_rows(seg1_payload: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    token_map: dict[tuple[int, int], list[str]] = {}
    for row in rows:
        edited = str(row["tokenized_text"] or "").replace("\r\n", "\n")
        segment_text = str(row["segment_text"] or "").replace("\r\n", "\n")
        tokens = edited.split("¦")
        edited_without_bars = "".join(tokens)
        if edited_without_bars != segment_text:
            reconciled_tokens = _reconcile_outer_whitespace_only_difference(tokens, segment_text)
            if reconciled_tokens is not None:
                tokens = reconciled_tokens
                edited_without_bars = "".join(tokens)
            if edited_without_bars != segment_text:
                mismatch = _describe_text_mismatch(edited_without_bars, segment_text)
                raise ValueError(
                    f"Page {row['page_index']} segment {row['segment_index']} changes text content; "
                    f"only token separators may be inserted or removed. {mismatch}"
                )
        if any(tok == "" for tok in tokens):
            raise ValueError(
                f"Page {row['page_index']} segment {row['segment_index']} contains an empty token "
                "(adjacent/leading/trailing separators are not allowed)."
            )
        token_map[(row["page_index"], row["segment_index"])] = tokens
    edited = json.loads(json.dumps(seg1_payload))
    for p_idx, page in enumerate(edited.get("pages") or [], start=1):
        for s_idx, segment in enumerate(page.get("segments") or [], start=1):
            token_surfaces = token_map.get((p_idx, s_idx))
            if not token_surfaces:
                token_surfaces = [str(segment.get("surface") or "")]
            segment["tokens"] = [{"surface": surface} for surface in token_surfaces]
    return edited


def _describe_text_mismatch(edited_text: str, expected_text: str) -> str:
    mismatch_index: int | None = None
    for idx, (edited_char, expected_char) in enumerate(zip(edited_text, expected_text)):
        if edited_char != expected_char:
            mismatch_index = idx
            break
    if mismatch_index is None and len(edited_text) != len(expected_text):
        mismatch_index = min(len(edited_text), len(expected_text))
    if mismatch_index is None:
        mismatch_index = 0

    edited_char = edited_text[mismatch_index] if mismatch_index < len(edited_text) else ""
    expected_char = expected_text[mismatch_index] if mismatch_index < len(expected_text) else ""

    start = max(0, mismatch_index - 12)
    end = mismatch_index + 13
    edited_context = edited_text[start:end]
    expected_context = expected_text[start:end]

    return (
        f"First mismatch at character {mismatch_index + 1}: "
        f"edited={_format_debug_char(edited_char)}, expected={_format_debug_char(expected_char)}; "
        f"edited_length={len(edited_text)}, expected_length={len(expected_text)}; "
        f"edited_context={edited_context!r}; expected_context={expected_context!r}"
    )


def _reconcile_outer_whitespace_only_difference(tokens: list[str], expected_text: str) -> list[str] | None:
    if not tokens:
        return None
    joined = "".join(tokens)
    if joined.strip() != expected_text.strip():
        return None
    expected_leading = expected_text[: len(expected_text) - len(expected_text.lstrip())]
    expected_trailing = expected_text[len(expected_text.rstrip()) :]

    adjusted_tokens = list(tokens)
    adjusted_tokens[0] = expected_leading + adjusted_tokens[0].lstrip()
    adjusted_tokens[-1] = adjusted_tokens[-1].rstrip() + expected_trailing
    return adjusted_tokens


def _format_debug_char(ch: str) -> str:
    if ch == "":
        return "<end>"
    return f"{ch!r} (U+{ord(ch):04X})"


def _display_token_surfaces_for_segment(segment_text: str, raw_tokens: list[Any]) -> list[str]:
    token_surfaces = [str((tok or {}).get("surface") or "") for tok in raw_tokens if isinstance(tok, dict)]
    if token_surfaces and "".join(token_surfaces) == segment_text and len(token_surfaces) > 1:
        return token_surfaces
    return _default_token_surfaces_for_segment(segment_text)


def _default_token_surfaces_for_segment(segment_text: str) -> list[str]:
    fallback = [m.group(0) for m in re.finditer(r"\w+|\s+|[^\w\s]", segment_text, flags=re.UNICODE)]
    return fallback if fallback else [segment_text]


def _reconcile_phase2_payload_with_seg1(seg1_payload: dict[str, Any], seg2_payload: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    if _validate_phase2_structure(seg1_payload, seg2_payload) is None:
        return seg2_payload, False

    reconciled = _build_phase2_seed_from_seg1(seg1_payload)
    old_pages = seg2_payload.get("pages") or []
    new_pages = reconciled.get("pages") or []
    for pidx, new_page in enumerate(new_pages):
        new_segments = (new_page or {}).get("segments") or []
        old_segments = ((old_pages[pidx] if pidx < len(old_pages) else {}) or {}).get("segments") or []
        for sidx, new_segment in enumerate(new_segments):
            old_segment = (old_segments[sidx] if sidx < len(old_segments) else {}) or {}
            if str(old_segment.get("surface") or "") != str(new_segment.get("surface") or ""):
                continue
            tokens = old_segment.get("tokens") or []
            if not isinstance(tokens, list) or not tokens:
                continue
            rebuilt = "".join(str((tok or {}).get("surface") or "") for tok in tokens if isinstance(tok, dict))
            if rebuilt == str(new_segment.get("surface") or ""):
                new_segment["tokens"] = tokens
    return reconciled, True


def _translation_rows(seg2_payload: dict[str, Any], translation_payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seg2_pages = seg2_payload.get("pages") or []
    tr_pages = translation_payload.get("pages") or []
    for pidx, seg2_page in enumerate(seg2_pages, start=1):
        seg2_segments = seg2_page.get("segments") or []
        tr_segments = ((tr_pages[pidx - 1] if pidx - 1 < len(tr_pages) else {}) or {}).get("segments") or []
        for sidx, seg2_seg in enumerate(seg2_segments, start=1):
            tr_seg = (tr_segments[sidx - 1] if sidx - 1 < len(tr_segments) else {}) or {}
            translation_value = str(((tr_seg.get("annotations") or {}).get("translation")) or "")
            rows.append(
                {
                    "page_index": pidx,
                    "segment_index": sidx,
                    "source_text": str(seg2_seg.get("surface") or ""),
                    "translation_text": translation_value,
                }
            )
    return rows


def _reconcile_translation_payload_with_seg2(
    seg2_payload: dict[str, Any], translation_payload: dict[str, Any]
) -> tuple[dict[str, Any], bool]:
    reconciled = json.loads(json.dumps(seg2_payload))
    changed = False
    tr_pages = translation_payload.get("pages") or []
    for pidx, page in enumerate(reconciled.get("pages") or []):
        segs = page.get("segments") or []
        tr_segs = ((tr_pages[pidx] if pidx < len(tr_pages) else {}) or {}).get("segments") or []
        for sidx, seg in enumerate(segs):
            anns = dict(seg.get("annotations") or {})
            copied = ""
            tr_seg = (tr_segs[sidx] if sidx < len(tr_segs) else {}) or {}
            if str(tr_seg.get("surface") or "") == str(seg.get("surface") or ""):
                copied = str(((tr_seg.get("annotations") or {}).get("translation")) or "")
            if copied != str((seg.get("annotations") or {}).get("translation") or ""):
                changed = True
            anns["translation"] = copied
            seg["annotations"] = anns
    return reconciled, changed


def _translation_payload_from_rows(seg2_payload: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    payload = json.loads(json.dumps(seg2_payload))
    for row in rows:
        page = payload["pages"][row["page_index"] - 1]
        seg = page["segments"][row["segment_index"] - 1]
        if str(seg.get("surface") or "") != str(row["source_text"] or ""):
            raise ValueError("Source segment text changed; only translation text may be edited.")
        annotations = dict(seg.get("annotations") or {})
        annotations["translation"] = str(row["translation_text"] or "")
        seg["annotations"] = annotations
    payload["l1"] = payload.get("l1") or ""
    return payload


def _segment_tokens_match(seg_a: dict[str, Any], seg_b: dict[str, Any]) -> bool:
    tokens_a = seg_a.get("tokens") or []
    tokens_b = seg_b.get("tokens") or []
    if len(tokens_a) != len(tokens_b):
        return False
    for idx, token_a in enumerate(tokens_a):
        token_b = tokens_b[idx] if idx < len(tokens_b) else {}
        if str((token_a or {}).get("surface") or "") != str((token_b or {}).get("surface") or ""):
            return False
    return True


def _rebuild_segment_mwes_from_token_ids(segment: dict[str, Any]) -> None:
    tokens = segment.get("tokens") or []
    seg_annotations = dict(segment.get("annotations") or {})
    existing = seg_annotations.get("mwes") or []
    labels_by_id = {
        str(entry.get("id") or ""): str(entry.get("label") or "")
        for entry in existing
        if isinstance(entry, dict) and entry.get("id")
    }
    id_to_surfaces: dict[str, list[str]] = {}
    for token in tokens:
        token_annotations = (token or {}).get("annotations") or {}
        mwe_id = str(token_annotations.get("mwe_id") or "").strip()
        tok_surface = str((token or {}).get("surface") or "")
        if not mwe_id or not tok_surface.strip():
            continue
        id_to_surfaces.setdefault(mwe_id, []).append(tok_surface)
    seg_annotations["mwes"] = [
        {"id": mwe_id, "tokens": surfaces, "label": labels_by_id.get(mwe_id, "")}
        for mwe_id, surfaces in sorted(id_to_surfaces.items())
        if len(surfaces) >= 2
    ]
    segment["annotations"] = seg_annotations


def _mwe_rows(seg2_payload: dict[str, Any], mwe_payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seg2_pages = seg2_payload.get("pages") or []
    mwe_pages = mwe_payload.get("pages") or []
    for pidx, seg2_page in enumerate(seg2_pages, start=1):
        seg2_segments = seg2_page.get("segments") or []
        mwe_segments = ((mwe_pages[pidx - 1] if pidx - 1 < len(mwe_pages) else {}) or {}).get("segments") or []
        for sidx, seg2_seg in enumerate(seg2_segments, start=1):
            mwe_seg = (mwe_segments[sidx - 1] if sidx - 1 < len(mwe_segments) else {}) or {}
            seg_tokens = seg2_seg.get("tokens") or []
            mwe_tokens = mwe_seg.get("tokens") or []
            token_rows: list[dict[str, Any]] = []
            pending_ws = ""
            for tidx, token in enumerate(seg_tokens, start=1):
                surface = str((token or {}).get("surface") or "")
                if not surface.strip():
                    pending_ws += surface
                    continue
                mwe_token = (mwe_tokens[tidx - 1] if tidx - 1 < len(mwe_tokens) else {}) or {}
                mwe_id = str((((mwe_token.get("annotations") or {}).get("mwe_id")) or ""))
                token_rows.append(
                    {
                        "token_index": tidx,
                        "surface": surface,
                        "leading_ws": pending_ws,
                        "mwe_id": mwe_id,
                    }
                )
                pending_ws = ""
            rows.append(
                {
                    "page_index": pidx,
                    "segment_index": sidx,
                    "source_text": str(seg2_seg.get("surface") or ""),
                    "tokens": token_rows,
                }
            )
    return rows


def _reconcile_mwe_payload_with_seg2(seg2_payload: dict[str, Any], mwe_payload: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    reconciled = json.loads(json.dumps(seg2_payload))
    changed = False
    mwe_pages = mwe_payload.get("pages") or []
    for pidx, page in enumerate(reconciled.get("pages") or []):
        segs = page.get("segments") or []
        mwe_segs = ((mwe_pages[pidx] if pidx < len(mwe_pages) else {}) or {}).get("segments") or []
        for sidx, seg in enumerate(segs):
            mwe_seg = (mwe_segs[sidx] if sidx < len(mwe_segs) else {}) or {}
            if str(mwe_seg.get("surface") or "") != str(seg.get("surface") or ""):
                continue
            if not _segment_tokens_match(seg, mwe_seg):
                has_mwe_data = bool((mwe_seg.get("annotations") or {}).get("mwes"))
                if not has_mwe_data:
                    for tok in (mwe_seg.get("tokens") or []):
                        if ((tok or {}).get("annotations") or {}).get("mwe_id"):
                            has_mwe_data = True
                            break
                if has_mwe_data:
                    changed = True
                continue
            seg_tokens = seg.get("tokens") or []
            mwe_tokens = mwe_seg.get("tokens") or []
            for tidx, token in enumerate(seg_tokens):
                mwe_token = (mwe_tokens[tidx] if tidx < len(mwe_tokens) else {}) or {}
                token_annotations = dict(token.get("annotations") or {})
                old_mwe_id = str((token_annotations.get("mwe_id") or ""))
                new_mwe_id = str((((mwe_token.get("annotations") or {}).get("mwe_id")) or ""))
                if old_mwe_id != new_mwe_id:
                    changed = True
                if new_mwe_id:
                    token_annotations["mwe_id"] = new_mwe_id
                else:
                    token_annotations.pop("mwe_id", None)
                token["annotations"] = token_annotations
            _rebuild_segment_mwes_from_token_ids(seg)
    return normalize_mwes(reconciled), changed


def _mwe_payload_from_rows(seg2_payload: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    payload = json.loads(json.dumps(seg2_payload))
    for row in rows:
        page = payload["pages"][row["page_index"] - 1]
        seg = page["segments"][row["segment_index"] - 1]
        if str(seg.get("surface") or "") != str(row["source_text"] or ""):
            raise ValueError("Source segment text changed; only token MWE ids may be edited.")
        tokens = seg.get("tokens") or []
        edited_tokens = {int(t.get("token_index")): t for t in (row.get("tokens") or []) if t.get("token_index")}
        for idx, token in enumerate(tokens, start=1):
            edited_token = edited_tokens.get(idx)
            if not edited_token:
                continue
            if str((token.get("surface") or "")) != str((edited_token.get("surface") or "")):
                raise ValueError("Token text changed; only token MWE ids may be edited.")
            annotations = dict(token.get("annotations") or {})
            mwe_id = str((edited_token.get("mwe_id") or "")).strip()
            if mwe_id:
                annotations["mwe_id"] = mwe_id
            else:
                annotations.pop("mwe_id", None)
            token["annotations"] = annotations
        _rebuild_segment_mwes_from_token_ids(seg)
    return normalize_mwes(payload)


def _lemma_rows(mwe_payload: dict[str, Any], lemma_payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    mwe_pages = mwe_payload.get("pages") or []
    lemma_pages = lemma_payload.get("pages") or []
    for pidx, mwe_page in enumerate(mwe_pages, start=1):
        mwe_segments = mwe_page.get("segments") or []
        lemma_segments = ((lemma_pages[pidx - 1] if pidx - 1 < len(lemma_pages) else {}) or {}).get("segments") or []
        for sidx, mwe_seg in enumerate(mwe_segments, start=1):
            lemma_seg = (lemma_segments[sidx - 1] if sidx - 1 < len(lemma_segments) else {}) or {}
            mwe_tokens = mwe_seg.get("tokens") or []
            lemma_tokens = lemma_seg.get("tokens") or []
            token_rows: list[dict[str, Any]] = []
            pending_ws = ""
            for tidx, token in enumerate(mwe_tokens, start=1):
                surface = str((token or {}).get("surface") or "")
                if not surface.strip():
                    pending_ws += surface
                    continue
                lemma_token = (lemma_tokens[tidx - 1] if tidx - 1 < len(lemma_tokens) else {}) or {}
                lemma_ann = (lemma_token.get("annotations") or {}) if isinstance(lemma_token, dict) else {}
                token_rows.append(
                    {
                        "token_index": tidx,
                        "surface": surface,
                        "leading_ws": pending_ws,
                        "lemma": str((lemma_ann.get("lemma") or "")),
                        "pos": str((lemma_ann.get("pos") or "")),
                    }
                )
                pending_ws = ""
            rows.append(
                {
                    "page_index": pidx,
                    "segment_index": sidx,
                    "source_text": str(mwe_seg.get("surface") or ""),
                    "tokens": token_rows,
                }
            )
    return rows


def _segment_has_lemma_data(segment: dict[str, Any]) -> bool:
    for token in (segment.get("tokens") or []):
        ann = (token or {}).get("annotations") or {}
        if ann.get("lemma") or ann.get("pos"):
            return True
    return False


def _reconcile_lemma_payload_with_mwe(mwe_payload: dict[str, Any], lemma_payload: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    reconciled = json.loads(json.dumps(mwe_payload))
    changed = False
    lemma_pages = lemma_payload.get("pages") or []
    for pidx, page in enumerate(reconciled.get("pages") or []):
        segs = page.get("segments") or []
        lemma_segs = ((lemma_pages[pidx] if pidx < len(lemma_pages) else {}) or {}).get("segments") or []
        for sidx, seg in enumerate(segs):
            lemma_seg = (lemma_segs[sidx] if sidx < len(lemma_segs) else {}) or {}
            if str(lemma_seg.get("surface") or "") != str(seg.get("surface") or ""):
                continue
            if not _segment_tokens_match(seg, lemma_seg):
                if _segment_has_lemma_data(lemma_seg):
                    changed = True
                continue
            seg_tokens = seg.get("tokens") or []
            lemma_tokens = lemma_seg.get("tokens") or []
            for tidx, token in enumerate(seg_tokens):
                lemma_token = (lemma_tokens[tidx] if tidx < len(lemma_tokens) else {}) or {}
                lemma_ann = (lemma_token.get("annotations") or {}) if isinstance(lemma_token, dict) else {}
                token_annotations = dict(token.get("annotations") or {})
                old_lemma = str(token_annotations.get("lemma") or "")
                old_pos = str(token_annotations.get("pos") or "")
                new_lemma = str(lemma_ann.get("lemma") or "")
                new_pos = str(lemma_ann.get("pos") or "")
                if old_lemma != new_lemma or old_pos != new_pos:
                    changed = True
                if new_lemma:
                    token_annotations["lemma"] = new_lemma
                else:
                    token_annotations.pop("lemma", None)
                if new_pos:
                    token_annotations["pos"] = new_pos
                else:
                    token_annotations.pop("pos", None)
                token["annotations"] = token_annotations
    return reconciled, changed


def _lemma_payload_from_rows(mwe_payload: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    payload = json.loads(json.dumps(mwe_payload))
    for row in rows:
        page = payload["pages"][row["page_index"] - 1]
        seg = page["segments"][row["segment_index"] - 1]
        if str(seg.get("surface") or "") != str(row["source_text"] or ""):
            raise ValueError("Source segment text changed; only token lemma/POS may be edited.")
        tokens = seg.get("tokens") or []
        edited_tokens = {int(t.get("token_index")): t for t in (row.get("tokens") or []) if t.get("token_index")}
        for idx, token in enumerate(tokens, start=1):
            edited_token = edited_tokens.get(idx)
            if not edited_token:
                continue
            if str((token.get("surface") or "")) != str((edited_token.get("surface") or "")):
                raise ValueError("Token text changed; only token lemma/POS may be edited.")
            annotations = dict(token.get("annotations") or {})
            lemma = str((edited_token.get("lemma") or "")).strip()
            pos = str((edited_token.get("pos") or "")).strip()
            if lemma:
                annotations["lemma"] = lemma
            else:
                annotations.pop("lemma", None)
            if pos:
                annotations["pos"] = pos
            else:
                annotations.pop("pos", None)
            token["annotations"] = annotations
    return payload


def _gloss_rows(lemma_payload: dict[str, Any], gloss_payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    lemma_pages = lemma_payload.get("pages") or []
    gloss_pages = gloss_payload.get("pages") or []
    for pidx, lemma_page in enumerate(lemma_pages, start=1):
        lemma_segments = lemma_page.get("segments") or []
        gloss_segments = ((gloss_pages[pidx - 1] if pidx - 1 < len(gloss_pages) else {}) or {}).get("segments") or []
        for sidx, lemma_seg in enumerate(lemma_segments, start=1):
            gloss_seg = (gloss_segments[sidx - 1] if sidx - 1 < len(gloss_segments) else {}) or {}
            lemma_tokens = lemma_seg.get("tokens") or []
            gloss_tokens = gloss_seg.get("tokens") or []
            token_rows: list[dict[str, Any]] = []
            pending_ws = ""
            for tidx, token in enumerate(lemma_tokens, start=1):
                surface = str((token or {}).get("surface") or "")
                if not surface.strip():
                    pending_ws += surface
                    continue
                gloss_token = (gloss_tokens[tidx - 1] if tidx - 1 < len(gloss_tokens) else {}) or {}
                gloss_ann = (gloss_token.get("annotations") or {}) if isinstance(gloss_token, dict) else {}
                token_rows.append(
                    {
                        "token_index": tidx,
                        "surface": surface,
                        "leading_ws": pending_ws,
                        "gloss": str((gloss_ann.get("gloss") or "")),
                    }
                )
                pending_ws = ""
            rows.append(
                {
                    "page_index": pidx,
                    "segment_index": sidx,
                    "source_text": str(lemma_seg.get("surface") or ""),
                    "tokens": token_rows,
                }
            )
    return rows


def _segment_has_gloss_data(segment: dict[str, Any]) -> bool:
    for token in (segment.get("tokens") or []):
        ann = (token or {}).get("annotations") or {}
        if ann.get("gloss"):
            return True
    return False


def _reconcile_gloss_payload_with_lemma(lemma_payload: dict[str, Any], gloss_payload: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    reconciled = json.loads(json.dumps(lemma_payload))
    changed = False
    gloss_pages = gloss_payload.get("pages") or []
    for pidx, page in enumerate(reconciled.get("pages") or []):
        segs = page.get("segments") or []
        gloss_segs = ((gloss_pages[pidx] if pidx < len(gloss_pages) else {}) or {}).get("segments") or []
        for sidx, seg in enumerate(segs):
            gloss_seg = (gloss_segs[sidx] if sidx < len(gloss_segs) else {}) or {}
            if str(gloss_seg.get("surface") or "") != str(seg.get("surface") or ""):
                continue
            if not _segment_tokens_match(seg, gloss_seg):
                if _segment_has_gloss_data(gloss_seg):
                    changed = True
                continue
            seg_tokens = seg.get("tokens") or []
            gloss_tokens = gloss_seg.get("tokens") or []
            for tidx, token in enumerate(seg_tokens):
                gloss_token = (gloss_tokens[tidx] if tidx < len(gloss_tokens) else {}) or {}
                gloss_ann = (gloss_token.get("annotations") or {}) if isinstance(gloss_token, dict) else {}
                token_annotations = dict(token.get("annotations") or {})
                old_gloss = str(token_annotations.get("gloss") or "")
                new_gloss = str(gloss_ann.get("gloss") or "")
                if old_gloss != new_gloss:
                    changed = True
                if new_gloss:
                    token_annotations["gloss"] = new_gloss
                else:
                    token_annotations.pop("gloss", None)
                token["annotations"] = token_annotations
    return reconciled, changed


def _gloss_payload_from_rows(lemma_payload: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    payload = json.loads(json.dumps(lemma_payload))
    for row in rows:
        page = payload["pages"][row["page_index"] - 1]
        seg = page["segments"][row["segment_index"] - 1]
        if str(seg.get("surface") or "") != str(row["source_text"] or ""):
            raise ValueError("Source segment text changed; only token gloss may be edited.")
        tokens = seg.get("tokens") or []
        edited_tokens = {int(t.get("token_index")): t for t in (row.get("tokens") or []) if t.get("token_index")}
        for idx, token in enumerate(tokens, start=1):
            edited_token = edited_tokens.get(idx)
            if not edited_token:
                continue
            if str((token.get("surface") or "")) != str((edited_token.get("surface") or "")):
                raise ValueError("Token text changed; only token gloss may be edited.")
            annotations = dict(token.get("annotations") or {})
            gloss = str((edited_token.get("gloss") or "")).strip()
            if gloss:
                annotations["gloss"] = gloss
            else:
                annotations.pop("gloss", None)
            token["annotations"] = annotations
    return payload


def _pinyin_rows(gloss_payload: dict[str, Any], pinyin_payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    gloss_pages = gloss_payload.get("pages") or []
    pinyin_pages = pinyin_payload.get("pages") or []
    for pidx, gloss_page in enumerate(gloss_pages, start=1):
        gloss_segments = gloss_page.get("segments") or []
        pinyin_segments = ((pinyin_pages[pidx - 1] if pidx - 1 < len(pinyin_pages) else {}) or {}).get("segments") or []
        for sidx, gloss_seg in enumerate(gloss_segments, start=1):
            pinyin_seg = (pinyin_segments[sidx - 1] if sidx - 1 < len(pinyin_segments) else {}) or {}
            gloss_tokens = gloss_seg.get("tokens") or []
            pinyin_tokens = pinyin_seg.get("tokens") or []
            token_rows: list[dict[str, Any]] = []
            pending_ws = ""
            for tidx, token in enumerate(gloss_tokens, start=1):
                surface = str((token or {}).get("surface") or "")
                if not surface.strip():
                    pending_ws += surface
                    continue
                pinyin_token = (pinyin_tokens[tidx - 1] if tidx - 1 < len(pinyin_tokens) else {}) or {}
                pinyin_ann = (pinyin_token.get("annotations") or {}) if isinstance(pinyin_token, dict) else {}
                token_rows.append(
                    {
                        "token_index": tidx,
                        "surface": surface,
                        "leading_ws": pending_ws,
                        "pinyin": str((pinyin_ann.get("pinyin") or "")),
                    }
                )
                pending_ws = ""
            rows.append(
                {
                    "page_index": pidx,
                    "segment_index": sidx,
                    "source_text": str(gloss_seg.get("surface") or ""),
                    "tokens": token_rows,
                }
            )
    return rows


def _segment_has_pinyin_data(segment: dict[str, Any]) -> bool:
    for token in (segment.get("tokens") or []):
        ann = (token or {}).get("annotations") or {}
        if ann.get("pinyin"):
            return True
    return False


def _reconcile_pinyin_payload_with_gloss(gloss_payload: dict[str, Any], pinyin_payload: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    reconciled = json.loads(json.dumps(gloss_payload))
    changed = False
    pinyin_pages = pinyin_payload.get("pages") or []
    for pidx, page in enumerate(reconciled.get("pages") or []):
        segs = page.get("segments") or []
        pinyin_segs = ((pinyin_pages[pidx] if pidx < len(pinyin_pages) else {}) or {}).get("segments") or []
        for sidx, seg in enumerate(segs):
            pinyin_seg = (pinyin_segs[sidx] if sidx < len(pinyin_segs) else {}) or {}
            if str(pinyin_seg.get("surface") or "") != str(seg.get("surface") or ""):
                continue
            if not _segment_tokens_match(seg, pinyin_seg):
                if _segment_has_pinyin_data(pinyin_seg):
                    changed = True
                continue
            seg_tokens = seg.get("tokens") or []
            pinyin_tokens = pinyin_seg.get("tokens") or []
            for tidx, token in enumerate(seg_tokens):
                pinyin_token = (pinyin_tokens[tidx] if tidx < len(pinyin_tokens) else {}) or {}
                pinyin_ann = (pinyin_token.get("annotations") or {}) if isinstance(pinyin_token, dict) else {}
                token_annotations = dict(token.get("annotations") or {})
                old_val = str(token_annotations.get("pinyin") or "")
                new_val = str(pinyin_ann.get("pinyin") or "")
                if old_val != new_val:
                    changed = True
                if new_val:
                    token_annotations["pinyin"] = new_val
                else:
                    token_annotations.pop("pinyin", None)
                token["annotations"] = token_annotations
    return reconciled, changed


def _pinyin_payload_from_rows(gloss_payload: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    payload = json.loads(json.dumps(gloss_payload))
    for row in rows:
        page = payload["pages"][row["page_index"] - 1]
        seg = page["segments"][row["segment_index"] - 1]
        if str(seg.get("surface") or "") != str(row["source_text"] or ""):
            raise ValueError("Source segment text changed; only token pinyin/romanization may be edited.")
        tokens = seg.get("tokens") or []
        edited_tokens = {int(t.get("token_index")): t for t in (row.get("tokens") or []) if t.get("token_index")}
        for idx, token in enumerate(tokens, start=1):
            edited_token = edited_tokens.get(idx)
            if not edited_token:
                continue
            if str((token.get("surface") or "")) != str((edited_token.get("surface") or "")):
                raise ValueError("Token text changed; only token pinyin/romanization may be edited.")
            annotations = dict(token.get("annotations") or {})
            pinyin_value = str((edited_token.get("pinyin") or "")).strip()
            if pinyin_value:
                annotations["pinyin"] = pinyin_value
            else:
                annotations.pop("pinyin", None)
            token["annotations"] = annotations
    return payload


def _page_surface_hashes(payload: dict[str, Any]) -> list[str]:
    hashes: list[str] = []
    for page in payload.get("pages", []) or []:
        hashes.append(_stable_text_hash(str((page or {}).get("surface") or "")))
    return hashes


def _build_phase2_seed_from_seg1(seg1_payload: dict[str, Any]) -> dict[str, Any]:
    seed = json.loads(json.dumps(seg1_payload))
    for page in seed.get("pages", []) or []:
        for segment in page.get("segments", []) or []:
            segment["tokens"] = [{"surface": str(segment.get("surface") or "")}]
    return seed


def _salvage_segmentation_phase_2_for_run(run_dir: Path) -> dict[str, Any] | None:
    seg1_path = run_dir / "stages" / "segmentation_phase_1.json"
    seg2_path = run_dir / "stages" / "segmentation_phase_2.json"
    if not seg1_path.exists() or not seg2_path.exists():
        return None
    try:
        seg1_payload = json.loads(seg1_path.read_text(encoding="utf-8"))
        seg2_payload = json.loads(seg2_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(seg1_payload, dict) or not isinstance(seg2_payload, dict):
        return None

    old_hashes = _page_surface_hashes(seg2_payload)
    new_hashes = _page_surface_hashes(seg1_payload)
    salvaged = _build_phase2_seed_from_seg1(seg1_payload)
    unchanged_pages = 0
    for idx, (old_hash, new_hash) in enumerate(zip(old_hashes, new_hashes)):
        if old_hash != new_hash:
            continue
        old_pages = seg2_payload.get("pages") or []
        new_pages = salvaged.get("pages") or []
        if idx >= len(old_pages) or idx >= len(new_pages):
            continue
        old_segments = (old_pages[idx] or {}).get("segments") or []
        new_segments = (new_pages[idx] or {}).get("segments") or []
        if len(old_segments) != len(new_segments):
            continue
        page_ok = True
        for sidx, old_seg in enumerate(old_segments):
            if str((old_seg or {}).get("surface") or "") != str((new_segments[sidx] or {}).get("surface") or ""):
                page_ok = False
                break
        if not page_ok:
            continue
        for sidx, old_seg in enumerate(old_segments):
            tokens = (old_seg or {}).get("tokens") or []
            if isinstance(tokens, list) and tokens:
                new_segments[sidx]["tokens"] = tokens
        unchanged_pages += 1

    if unchanged_pages == 0:
        return None
    (run_dir / "stages" / "segmentation_phase_2.json").write_text(
        json.dumps(salvaged, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {"unchanged_pages": unchanged_pages, "total_pages": len(new_hashes)}


def _invalidate_downstream_stage_files(run_dir: Path, from_stage: str) -> None:
    if from_stage not in PIPELINE_ORDER:
        return
    from_index = PIPELINE_ORDER.index(from_stage)
    for stage in PIPELINE_ORDER[from_index + 1 :]:
        path = run_dir / "stages" / f"{stage}.json"
        if path.exists():
            path.unlink()


def _manual_stage_status(project: Project, stage: str) -> dict[str, Any]:
    latest = _find_latest_stage_file(project, f"{stage}.json")
    if not latest:
        return {"exists": False, "stage": stage}
    run_dir, stage_path = latest
    stage_mtime = datetime.fromtimestamp(stage_path.stat().st_mtime, tz=timezone.utc)
    manual_dir = run_dir / "stages" / "manual_versions"
    provenance = "pipeline/auto"
    if manual_dir.exists():
        matches = sorted(manual_dir.glob(f"{stage}_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if matches and abs(matches[0].stat().st_mtime - stage_path.stat().st_mtime) < 3:
            provenance = "manual edit"
    note = ""
    if stage == "segmentation_phase_2":
        upstream = _find_latest_stage_file(project, "segmentation_phase_1.json")
        if upstream and upstream[1].stat().st_mtime > stage_path.stat().st_mtime:
            note = "upstream phase 1 is newer"
    elif stage == "mwe":
        upstream = _find_latest_stage_file(project, "segmentation_phase_2.json")
        if upstream and upstream[1].stat().st_mtime > stage_path.stat().st_mtime:
            note = "upstream segmentation phase 2 is newer"
    elif stage == "lemma":
        upstream = _find_latest_stage_file(project, "mwe.json")
        if upstream and upstream[1].stat().st_mtime > stage_path.stat().st_mtime:
            note = "upstream mwe is newer"
    elif stage == "gloss":
        upstream = _find_latest_stage_file(project, "lemma.json")
        if upstream and upstream[1].stat().st_mtime > stage_path.stat().st_mtime:
            note = "upstream lemma is newer"
    elif stage == "pinyin":
        upstream = _find_latest_stage_file(project, "gloss.json")
        if upstream and upstream[1].stat().st_mtime > stage_path.stat().st_mtime:
            note = "upstream gloss is newer"
    return {
        "exists": True,
        "stage": stage,
        "run": run_dir.name,
        "path": stage_path,
        "updated_at": stage_mtime.isoformat(),
        "provenance": provenance,
        "note": note,
    }


def _validate_phase2_structure(seg1_payload: dict[str, Any], edited_payload: dict[str, Any]) -> str | None:
    base_pages = seg1_payload.get("pages") or []
    edited_pages = edited_payload.get("pages") or []
    if len(base_pages) != len(edited_pages):
        return "Edited segmentation phase 2 must keep the same number of pages as segmentation phase 1."
    for p_idx, (base_page, edited_page) in enumerate(zip(base_pages, edited_pages), start=1):
        base_segments = base_page.get("segments") or []
        edited_segments = edited_page.get("segments") or []
        if len(base_segments) != len(edited_segments):
            return f"Page {p_idx} must keep the same number of segments as segmentation phase 1."
        for s_idx, (base_segment, edited_segment) in enumerate(zip(base_segments, edited_segments), start=1):
            base_surface = str(base_segment.get("surface") or "")
            tokens = edited_segment.get("tokens") or []
            if not isinstance(tokens, list) or not tokens:
                return f"Page {p_idx} segment {s_idx} must contain a non-empty token list."
            rebuilt = ""
            for token in tokens:
                if not isinstance(token, dict):
                    return f"Page {p_idx} segment {s_idx} has an invalid token entry."
                rebuilt += str(token.get("surface") or "")
            if rebuilt != base_surface:
                return (
                    f"Page {p_idx} segment {s_idx} changes text content. "
                    "Only content-element boundaries may be edited in segmentation phase 2."
                )
    return None


@login_required
def manual_top_level(request: HttpRequest, pk: int) -> HttpResponse:
    project = _get_project_for_user(pk=pk, user=request.user, min_role=ProjectCollaborator.ROLE_ANNOTATOR)
    context = {"project": project}
    context.update(_manual_annotation_context(project))
    return render(request, "projects/manual_top_level.html", context)


@login_required
def manual_page_annotation(request: HttpRequest, pk: int) -> HttpResponse:
    project = _get_project_for_user(pk=pk, user=request.user, min_role=ProjectCollaborator.ROLE_ANNOTATOR)
    seg1_run = _find_run_with_stage(project, "segmentation_phase_1")
    seg1_payload = _load_stage_payload(project, "segmentation_phase_1", run_dir=seg1_run) if seg1_run else None
    if not seg1_payload:
        base_text = _base_text_for_segmentation_phase_1(project)
        if not base_text.strip():
            messages.error(request, "Page-oriented manual annotation requires source text.")
            return redirect("project-annotation-home", pk=project.pk)
        editable_surface = request.POST.get("editable_surface") if request.method == "POST" else base_text
        editable_surface = _canonicalize_phase1_surface(str(editable_surface or base_text))
        base_hash = _stable_text_hash(base_text)
        if request.method == "POST":
            edited_hash = _stable_text_hash(_surface_without_phase1_markers(editable_surface))
            if edited_hash != base_hash:
                messages.error(request, "Text hash mismatch; only <page> and || separators may be changed.")
            else:
                payload = _build_phase1_payload_from_surface(editable_surface, project.language)
                _save_versioned_stage_payload(
                    project=project,
                    stage_name="segmentation_phase_1",
                    payload=payload,
                    metadata={"before_text_hash": base_hash, "after_text_hash": edited_hash, "mode": "page_oriented"},
                )
                messages.success(request, "Saved segmentation phase 1 from page-oriented editor.")
                return redirect("manual-page-annotation", pk=project.pk)
        return render(
            request,
            "projects/manual_page_annotation.html",
            {"project": project, "mode": "phase1", "editable_surface": editable_surface, "base_hash": base_hash},
        )

    seg2_run = _find_run_with_stage(project, "segmentation_phase_2")
    seg2_payload = _load_stage_payload(project, "segmentation_phase_2", run_dir=seg2_run) if seg2_run else None
    if not seg2_payload:
        seg2_payload = json.loads(json.dumps(seg1_payload))
        for page in seg2_payload.get("pages", []) or []:
            for segment in page.get("segments", []) or []:
                pieces = _default_token_surfaces_for_segment(str(segment.get("surface") or ""))
                segment["tokens"] = [{"surface": piece} for piece in pieces] if pieces else [{"surface": ""}]
        token_rows = _phase2_token_bar_rows(seg1_payload, seg2_payload)
        base_hash = _stable_text_hash(str(seg1_payload.get("surface") or ""))
        if request.method == "POST":
            try:
                for row in token_rows:
                    submitted = request.POST.get(
                        f"tokenized_text_{row['page_index']}_{row['segment_index']}",
                        row["tokenized_text"],
                    )
                    row["tokenized_text"] = str(submitted).replace("|", "¦")
                edited_payload = _phase2_payload_from_bar_rows(seg1_payload, token_rows)
            except ValueError as exc:
                messages.error(request, str(exc))
            else:
                error = _validate_phase2_structure(seg1_payload, edited_payload)
                edited_hash = _stable_text_hash(str(edited_payload.get("surface") or ""))
                if error:
                    messages.error(request, error)
                elif edited_hash != base_hash:
                    messages.error(request, "Text hash mismatch; only content-element boundaries may be changed.")
                else:
                    _save_versioned_stage_payload(
                        project=project,
                        stage_name="segmentation_phase_2",
                        payload=edited_payload,
                        metadata={"before_text_hash": base_hash, "after_text_hash": edited_hash, "mode": "page_oriented"},
                        run_dir=seg1_run,
                    )
                    messages.success(request, "Saved segmentation phase 2 from page-oriented editor.")
                    return redirect("manual-page-annotation", pk=project.pk)
        return render(
            request,
            "projects/manual_page_annotation.html",
            {"project": project, "mode": "phase2", "token_rows": token_rows, "base_hash": base_hash},
        )

    tr_payload = _load_stage_payload(project, "translation", run_dir=_find_run_with_stage(project, "translation")) or {}
    tr_payload, _ = _reconcile_translation_payload_with_seg2(seg2_payload, tr_payload or json.loads(json.dumps(seg2_payload)))
    mwe_payload = _load_stage_payload(project, "mwe", run_dir=_find_run_with_stage(project, "mwe")) or {}
    mwe_payload, _ = _reconcile_mwe_payload_with_seg2(seg2_payload, mwe_payload or json.loads(json.dumps(seg2_payload)))
    lemma_payload = _load_stage_payload(project, "lemma", run_dir=_find_run_with_stage(project, "lemma")) or {}
    lemma_payload, _ = _reconcile_lemma_payload_with_mwe(mwe_payload, lemma_payload or json.loads(json.dumps(mwe_payload)))
    gloss_payload = _load_stage_payload(project, "gloss", run_dir=_find_run_with_stage(project, "gloss")) or {}
    gloss_payload, _ = _reconcile_gloss_payload_with_lemma(lemma_payload, gloss_payload or json.loads(json.dumps(lemma_payload)))
    pinyin_payload = _load_stage_payload(project, "pinyin", run_dir=_find_run_with_stage(project, "pinyin")) or {}
    pinyin_payload, _ = _reconcile_pinyin_payload_with_gloss(gloss_payload, pinyin_payload or json.loads(json.dumps(gloss_payload)))

    image_by_page = {row.page_number: row.image_path for row in project.image_pages.exclude(image_path="")}
    pages_data: list[dict[str, Any]] = []
    for page_index, page in enumerate(seg2_payload.get("pages") or []):
        segments_data: list[dict[str, Any]] = []
        for segment_index, segment in enumerate(page.get("segments") or []):
            tr_segment = (((tr_payload.get("pages") or [])[page_index].get("segments") or [])[segment_index]
                          if page_index < len(tr_payload.get("pages") or []) and segment_index < len((((tr_payload.get("pages") or [])[page_index]).get("segments") or []))
                          else {})
            tokens_data: list[dict[str, Any]] = []
            for token_index, token in enumerate(segment.get("tokens") or []):
                mwe_token = ((((mwe_payload.get("pages") or [])[page_index].get("segments") or [])[segment_index].get("tokens") or [])[token_index]
                             if page_index < len(mwe_payload.get("pages") or []) and segment_index < len((((mwe_payload.get("pages") or [])[page_index]).get("segments") or [])) and token_index < len(((((mwe_payload.get("pages") or [])[page_index].get("segments") or [])[segment_index]).get("tokens") or []))
                             else {})
                lemma_token = ((((lemma_payload.get("pages") or [])[page_index].get("segments") or [])[segment_index].get("tokens") or [])[token_index]
                               if page_index < len(lemma_payload.get("pages") or []) and segment_index < len((((lemma_payload.get("pages") or [])[page_index]).get("segments") or [])) and token_index < len(((((lemma_payload.get("pages") or [])[page_index].get("segments") or [])[segment_index]).get("tokens") or []))
                               else {})
                gloss_token = ((((gloss_payload.get("pages") or [])[page_index].get("segments") or [])[segment_index].get("tokens") or [])[token_index]
                               if page_index < len(gloss_payload.get("pages") or []) and segment_index < len((((gloss_payload.get("pages") or [])[page_index]).get("segments") or [])) and token_index < len(((((gloss_payload.get("pages") or [])[page_index].get("segments") or [])[segment_index]).get("tokens") or []))
                               else {})
                pinyin_token = ((((pinyin_payload.get("pages") or [])[page_index].get("segments") or [])[segment_index].get("tokens") or [])[token_index]
                                if page_index < len(pinyin_payload.get("pages") or []) and segment_index < len((((pinyin_payload.get("pages") or [])[page_index]).get("segments") or [])) and token_index < len(((((pinyin_payload.get("pages") or [])[page_index].get("segments") or [])[segment_index]).get("tokens") or []))
                                else {})
                tokens_data.append(
                    {
                        "token_index": token_index,
                        "surface": str(token.get("surface") or ""),
                        "is_whitespace": not str(token.get("surface") or "").strip(),
                        "mwe_id": str(((mwe_token.get("annotations") or {}).get("mwe_id") or "")),
                        "lemma": str(((lemma_token.get("annotations") or {}).get("lemma") or "")),
                        "pos": str(((lemma_token.get("annotations") or {}).get("pos") or "")),
                        "gloss": str(((gloss_token.get("annotations") or {}).get("gloss") or "")),
                        "pinyin": str(((pinyin_token.get("annotations") or {}).get("pinyin") or "")),
                    }
                )
            segments_data.append(
                {
                    "segment_index": segment_index,
                    "surface": str(segment.get("surface") or ""),
                    "translation_text": str(((tr_segment.get("annotations") or {}).get("translation") or "")),
                    "tokens": tokens_data,
                }
            )
        page_number = page_index + 1
        image_path = image_by_page.get(page_number) or ""
        image_url = reverse("project-compiled", args=[project.pk, image_path]) if image_path else ""
        pages_data.append(
            {
                "page_index": page_index,
                "page_number": page_number,
                "segments": segments_data,
                "image_path": image_path,
                "image_url": image_url,
            }
        )

    base_hash = _stable_text_hash(str(seg2_payload.get("surface") or ""))
    if request.method == "POST":
        for page in pages_data:
            for segment in page["segments"]:
                segment["translation_text"] = request.POST.get(
                    f"translation_text_{page['page_index']}_{segment['segment_index']}",
                    segment["translation_text"],
                )
                for token in segment["tokens"]:
                    key = f"{page['page_index']}_{segment['segment_index']}_{token['token_index']}"
                    token["mwe_id"] = request.POST.get(f"mwe_id_{key}", token["mwe_id"])
                    token["lemma"] = request.POST.get(f"lemma_{key}", token["lemma"])
                    token["pos"] = request.POST.get(f"pos_{key}", token["pos"])
                    token["gloss"] = request.POST.get(f"gloss_{key}", token["gloss"])
                    token["pinyin"] = request.POST.get(f"pinyin_{key}", token["pinyin"])

        edited_translation = json.loads(json.dumps(seg2_payload))
        edited_mwe = json.loads(json.dumps(seg2_payload))
        for page in pages_data:
            for segment in page["segments"]:
                tseg = edited_translation["pages"][page["page_index"]]["segments"][segment["segment_index"]]
                tseg.setdefault("annotations", {})
                tseg["annotations"]["translation"] = segment["translation_text"]
                for token in segment["tokens"]:
                    tkn = edited_mwe["pages"][page["page_index"]]["segments"][segment["segment_index"]]["tokens"][token["token_index"]]
                    tkn.setdefault("annotations", {})
                    tkn["annotations"]["mwe_id"] = token["mwe_id"]

        edited_lemma = json.loads(json.dumps(edited_mwe))
        edited_gloss = json.loads(json.dumps(edited_lemma))
        edited_pinyin = json.loads(json.dumps(edited_gloss))
        for page in pages_data:
            for segment in page["segments"]:
                for token in segment["tokens"]:
                    lt = edited_lemma["pages"][page["page_index"]]["segments"][segment["segment_index"]]["tokens"][token["token_index"]]
                    lt.setdefault("annotations", {})
                    lt["annotations"]["lemma"] = token["lemma"]
                    lt["annotations"]["pos"] = token["pos"]
                    gt = edited_gloss["pages"][page["page_index"]]["segments"][segment["segment_index"]]["tokens"][token["token_index"]]
                    gt.setdefault("annotations", {})
                    gt["annotations"]["gloss"] = token["gloss"]
                    pt = edited_pinyin["pages"][page["page_index"]]["segments"][segment["segment_index"]]["tokens"][token["token_index"]]
                    pt.setdefault("annotations", {})
                    pt["annotations"]["pinyin"] = token["pinyin"]

        payloads_to_save = [
            ("translation", edited_translation),
            ("mwe", edited_mwe),
            ("lemma", edited_lemma),
            ("gloss", edited_gloss),
            ("pinyin", edited_pinyin),
        ]
        for stage_name, payload in payloads_to_save:
            if _stable_text_hash(str(payload.get("surface") or "")) != base_hash:
                messages.error(request, f"Text hash mismatch while saving {stage_name}; structure edits are not allowed.")
                return redirect("manual-page-annotation", pk=project.pk)

        for stage_name, payload in payloads_to_save:
            _save_versioned_stage_payload(
                project=project,
                stage_name=stage_name,
                payload=payload,
                metadata={"before_text_hash": base_hash, "after_text_hash": base_hash, "mode": "page_oriented_manual"},
            )
        target_run = _ensure_stage_run_dir(project)
        _invalidate_downstream_stage_files(target_run, "pinyin")
        messages.success(request, "Saved page-oriented manual annotations (translation, MWE, lemma, gloss, pinyin).")
        return redirect("manual-page-annotation", pk=project.pk)

    return render(
        request,
        "projects/manual_page_annotation.html",
        {
            "project": project,
            "mode": "annotation",
            "pages": pages_data,
            "show_translation_default": True,
            "show_mwe_default": True,
            "show_lemma_default": True,
            "show_gloss_default": True,
            "show_pinyin_default": True,
        },
    )


@login_required
def manual_segmentation_phase_1(request: HttpRequest, pk: int) -> HttpResponse:
    project = _get_project_for_user(pk=pk, user=request.user, min_role=ProjectCollaborator.ROLE_ANNOTATOR)
    return_to = _annotation_return_to(request, project, default_manual=True)
    base_text = _base_text_for_segmentation_phase_1(project)
    if not base_text.strip():
        messages.error(request, "Manual segmentation phase 1 requires source text.")
        return redirect(return_to)

    run_dir = _find_run_with_stage(project, "segmentation_phase_1") or _resolve_run_dir(project)
    current_payload = _load_stage_payload(project, "segmentation_phase_1", run_dir=run_dir) if run_dir else None
    current_surface = _canonicalize_phase1_surface(str((current_payload or {}).get("surface") or base_text))
    base_cmp_hash = _phase1_comparison_hash(base_text)
    if isinstance(current_payload, dict):
        reconstructed = _canonicalize_phase1_surface(_phase1_surface_from_payload(current_payload))
        if reconstructed and _phase1_comparison_hash(_surface_without_phase1_markers(reconstructed)) == base_cmp_hash:
            current_surface = reconstructed
    if _phase1_comparison_hash(_surface_without_phase1_markers(current_surface)) != base_cmp_hash:
        messages.warning(
            request,
            "The existing segmentation output is inconsistent with base text. "
            "Showing boundaries derived from the base text instead.",
        )
        current_surface = base_text

    editable_surface = current_surface
    base_hash = _stable_text_hash(base_text)

    if request.method == "POST":
        editable_surface = _canonicalize_phase1_surface(request.POST.get("editable_surface") or "")
        edited_surface_plain = _surface_without_phase1_markers(editable_surface)
        if _phase1_comparison_hash(edited_surface_plain) != base_cmp_hash:
            messages.error(request, "Text hash mismatch; only <page> and || separators may be changed.")
        else:
            edited_hash = base_hash
            payload = _build_phase1_payload_from_surface(editable_surface, project.language)
            _save_versioned_stage_payload(
                project=project,
                stage_name="segmentation_phase_1",
                payload=payload,
                metadata={
                    "before_text_hash": base_hash,
                    "after_text_hash": edited_hash,
                },
            )
            target_run = _ensure_stage_run_dir(project)
            salvage_info = _salvage_segmentation_phase_2_for_run(target_run)
            _invalidate_downstream_stage_files(target_run, "segmentation_phase_2")
            if salvage_info:
                messages.info(
                    request,
                    f"Salvaged segmentation phase 2 for {salvage_info['unchanged_pages']}/"
                    f"{salvage_info['total_pages']} unchanged pages.",
                )
            messages.success(request, "Saved manual segmentation phase 1.")
            return redirect(f"{reverse('manual-segmentation-phase-1', args=[project.pk])}?return_to={quote(return_to)}")

    return render(
        request,
        "projects/manual_segmentation_phase_1.html",
        {
            "project": project,
            "back_href": return_to,
            "return_to": return_to,
            "read_only_surface": current_surface,
            "editable_surface": editable_surface,
            "base_hash": base_hash,
            "base_text_length": len(base_text),
        },
    )


@login_required
def manual_segmentation_phase_2(request: HttpRequest, pk: int) -> HttpResponse:
    project = _get_project_for_user(pk=pk, user=request.user, min_role=ProjectCollaborator.ROLE_ANNOTATOR)
    seg1_run = _find_run_with_stage(project, "segmentation_phase_1")
    seg1_payload = _load_stage_payload(project, "segmentation_phase_1", run_dir=seg1_run) if seg1_run else None
    if not seg1_payload:
        messages.error(
            request,
            "Manual segmentation phase 2 requires segmentation phase 1 annotated text.",
        )
        return redirect("project-annotation-home", pk=project.pk)

    seg2_run = _find_run_with_stage(project, "segmentation_phase_2") or seg1_run
    seg2_payload = _load_stage_payload(project, "segmentation_phase_2", run_dir=seg2_run) if seg2_run else None
    if not seg2_payload:
        seg2_payload = json.loads(json.dumps(seg1_payload))
        for page in seg2_payload.get("pages", []) or []:
            for segment in page.get("segments", []) or []:
                segment["tokens"] = [{"surface": segment.get("surface", "")}]
    seg2_payload, reconciled = _reconcile_phase2_payload_with_seg1(seg1_payload, seg2_payload)
    if reconciled:
        target_run = _ensure_stage_run_dir(project)
        (target_run / "stages" / "segmentation_phase_2.json").write_text(
            json.dumps(seg2_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        messages.warning(
            request,
            "Segmentation phase 2 was out of sync with phase 1 and has been auto-reconciled; "
            "unchanged aligned segments were preserved.",
        )
    token_rows = _phase2_token_bar_rows(seg1_payload, seg2_payload)
    base_hash = _stable_text_hash(str(seg1_payload.get("surface") or ""))

    if request.method == "POST":
        try:
            for row in token_rows:
                row["tokenized_text"] = request.POST.get(
                    f"tokenized_text_{row['page_index']}_{row['segment_index']}",
                    row["tokenized_text"],
                )
            edited_payload = _phase2_payload_from_bar_rows(seg1_payload, token_rows)
        except ValueError as exc:
            messages.error(request, str(exc))
        else:
            error = _validate_phase2_structure(seg1_payload, edited_payload)
            edited_hash = _stable_text_hash(str(edited_payload.get("surface") or ""))
            if error:
                messages.error(request, error)
            elif edited_hash != base_hash:
                messages.error(request, "Text hash mismatch; only content-element boundaries may be changed.")
            else:
                _save_versioned_stage_payload(
                    project=project,
                    stage_name="segmentation_phase_2",
                    payload=edited_payload,
                    metadata={"before_text_hash": base_hash, "after_text_hash": edited_hash},
                )
                messages.success(request, "Saved manual segmentation phase 2.")
                return redirect("manual-segmentation-phase-2", pk=project.pk)

    return render(
        request,
        "projects/manual_segmentation_phase_2.html",
        {
            "project": project,
            "token_rows": token_rows,
            "base_hash": base_hash,
            "preview": _phase2_preview_from_payload(seg2_payload),
        },
    )


@login_required
def manual_mwe(request: HttpRequest, pk: int) -> HttpResponse:
    project = _get_project_for_user(pk=pk, user=request.user, min_role=ProjectCollaborator.ROLE_ANNOTATOR)
    seg2_run = _find_run_with_stage(project, "segmentation_phase_2")
    seg2_payload = _load_stage_payload(project, "segmentation_phase_2", run_dir=seg2_run) if seg2_run else None
    if not seg2_payload:
        messages.error(request, "Manual MWE editing requires segmentation phase 2 annotated text.")
        return redirect("project-annotation-home", pk=project.pk)

    mwe_run = _find_run_with_stage(project, "mwe") or seg2_run
    mwe_payload = _load_stage_payload(project, "mwe", run_dir=mwe_run) if mwe_run else None
    if not mwe_payload:
        mwe_payload = json.loads(json.dumps(seg2_payload))
    mwe_payload, reconciled = _reconcile_mwe_payload_with_seg2(seg2_payload, mwe_payload)
    if reconciled:
        target_run = _ensure_stage_run_dir(project)
        (target_run / "stages" / "mwe.json").write_text(
            json.dumps(mwe_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        messages.warning(
            request,
            "MWE stage was out of sync with segmentation phase 2 and has been auto-reconciled; "
            "aligned token-level MWE ids were preserved.",
        )

    rows = _mwe_rows(seg2_payload, mwe_payload)
    base_hash = _stable_text_hash(str(seg2_payload.get("surface") or ""))

    if request.method == "POST":
        for row in rows:
            for token in row["tokens"]:
                token["mwe_id"] = request.POST.get(
                    f"mwe_id_{row['page_index']}_{row['segment_index']}_{token['token_index']}",
                    token["mwe_id"],
                )
        try:
            edited_payload = _mwe_payload_from_rows(seg2_payload, rows)
        except ValueError as exc:
            messages.error(request, str(exc))
        else:
            edited_hash = _stable_text_hash(str(edited_payload.get("surface") or ""))
            if edited_hash != base_hash:
                messages.error(request, "Text hash mismatch; only token MWE ids may be changed.")
            else:
                _save_versioned_stage_payload(
                    project=project,
                    stage_name="mwe",
                    payload=edited_payload,
                    metadata={"before_text_hash": base_hash, "after_text_hash": edited_hash},
                )
                target_run = _ensure_stage_run_dir(project)
                _invalidate_downstream_stage_files(target_run, "mwe")
                messages.success(request, "Saved manual MWE annotations.")
                return redirect("manual-mwe", pk=project.pk)

    return render(
        request,
        "projects/manual_mwe.html",
        {"project": project, "rows": rows, "base_hash": base_hash},
    )


@login_required
def manual_lemma(request: HttpRequest, pk: int) -> HttpResponse:
    project = _get_project_for_user(pk=pk, user=request.user, min_role=ProjectCollaborator.ROLE_ANNOTATOR)
    mwe_run = _find_run_with_stage(project, "mwe")
    mwe_payload = _load_stage_payload(project, "mwe", run_dir=mwe_run) if mwe_run else None
    if not mwe_payload:
        messages.error(request, "Manual lemma editing requires MWE annotated text.")
        return redirect("project-annotation-home", pk=project.pk)

    lemma_run = _find_run_with_stage(project, "lemma") or mwe_run
    lemma_payload = _load_stage_payload(project, "lemma", run_dir=lemma_run) if lemma_run else None
    if not lemma_payload:
        lemma_payload = json.loads(json.dumps(mwe_payload))
    lemma_payload, reconciled = _reconcile_lemma_payload_with_mwe(mwe_payload, lemma_payload)
    if reconciled:
        target_run = _ensure_stage_run_dir(project)
        (target_run / "stages" / "lemma.json").write_text(
            json.dumps(lemma_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        messages.warning(
            request,
            "Lemma stage was out of sync with MWE and has been auto-reconciled; "
            "aligned token-level lemma/POS values were preserved.",
        )

    rows = _lemma_rows(mwe_payload, lemma_payload)
    base_hash = _stable_text_hash(str(mwe_payload.get("surface") or ""))

    if request.method == "POST":
        for row in rows:
            for token in row["tokens"]:
                token["lemma"] = request.POST.get(
                    f"lemma_{row['page_index']}_{row['segment_index']}_{token['token_index']}",
                    token["lemma"],
                )
                token["pos"] = request.POST.get(
                    f"pos_{row['page_index']}_{row['segment_index']}_{token['token_index']}",
                    token["pos"],
                )
        try:
            edited_payload = _lemma_payload_from_rows(mwe_payload, rows)
        except ValueError as exc:
            messages.error(request, str(exc))
        else:
            edited_hash = _stable_text_hash(str(edited_payload.get("surface") or ""))
            if edited_hash != base_hash:
                messages.error(request, "Text hash mismatch; only token lemma/POS may be changed.")
            else:
                _save_versioned_stage_payload(
                    project=project,
                    stage_name="lemma",
                    payload=edited_payload,
                    metadata={"before_text_hash": base_hash, "after_text_hash": edited_hash},
                )
                target_run = _ensure_stage_run_dir(project)
                _invalidate_downstream_stage_files(target_run, "lemma")
                messages.success(request, "Saved manual lemma annotations.")
                return redirect("manual-lemma", pk=project.pk)

    return render(
        request,
        "projects/manual_lemma.html",
        {"project": project, "rows": rows, "base_hash": base_hash},
    )


@login_required
def manual_gloss(request: HttpRequest, pk: int) -> HttpResponse:
    project = _get_project_for_user(pk=pk, user=request.user, min_role=ProjectCollaborator.ROLE_ANNOTATOR)
    lemma_run = _find_run_with_stage(project, "lemma")
    lemma_payload = _load_stage_payload(project, "lemma", run_dir=lemma_run) if lemma_run else None
    if not lemma_payload:
        messages.error(request, "Manual gloss editing requires lemma annotated text.")
        return redirect("project-annotation-home", pk=project.pk)

    gloss_run = _find_run_with_stage(project, "gloss") or lemma_run
    gloss_payload = _load_stage_payload(project, "gloss", run_dir=gloss_run) if gloss_run else None
    if not gloss_payload:
        gloss_payload = json.loads(json.dumps(lemma_payload))
    gloss_payload, reconciled = _reconcile_gloss_payload_with_lemma(lemma_payload, gloss_payload)
    if reconciled:
        target_run = _ensure_stage_run_dir(project)
        (target_run / "stages" / "gloss.json").write_text(
            json.dumps(gloss_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        messages.warning(
            request,
            "Gloss stage was out of sync with lemma and has been auto-reconciled; "
            "aligned token-level gloss values were preserved.",
        )

    rows = _gloss_rows(lemma_payload, gloss_payload)
    base_hash = _stable_text_hash(str(lemma_payload.get("surface") or ""))

    if request.method == "POST":
        for row in rows:
            for token in row["tokens"]:
                token["gloss"] = request.POST.get(
                    f"gloss_{row['page_index']}_{row['segment_index']}_{token['token_index']}",
                    token["gloss"],
                )
        try:
            edited_payload = _gloss_payload_from_rows(lemma_payload, rows)
        except ValueError as exc:
            messages.error(request, str(exc))
        else:
            edited_hash = _stable_text_hash(str(edited_payload.get("surface") or ""))
            if edited_hash != base_hash:
                messages.error(request, "Text hash mismatch; only token gloss may be changed.")
            else:
                _save_versioned_stage_payload(
                    project=project,
                    stage_name="gloss",
                    payload=edited_payload,
                    metadata={"before_text_hash": base_hash, "after_text_hash": edited_hash},
                )
                target_run = _ensure_stage_run_dir(project)
                _invalidate_downstream_stage_files(target_run, "gloss")
                messages.success(request, "Saved manual gloss annotations.")
                return redirect("manual-gloss", pk=project.pk)

    return render(
        request,
        "projects/manual_gloss.html",
        {"project": project, "rows": rows, "base_hash": base_hash},
    )


@login_required
def manual_pinyin(request: HttpRequest, pk: int) -> HttpResponse:
    project = _get_project_for_user(pk=pk, user=request.user, min_role=ProjectCollaborator.ROLE_ANNOTATOR)
    gloss_run = _find_run_with_stage(project, "gloss")
    gloss_payload = _load_stage_payload(project, "gloss", run_dir=gloss_run) if gloss_run else None
    if not gloss_payload:
        messages.error(request, "Manual pinyin/romanization editing requires gloss annotated text.")
        return redirect("project-annotation-home", pk=project.pk)

    pinyin_run = _find_run_with_stage(project, "pinyin") or gloss_run
    pinyin_payload = _load_stage_payload(project, "pinyin", run_dir=pinyin_run) if pinyin_run else None
    if not pinyin_payload:
        pinyin_payload = json.loads(json.dumps(gloss_payload))
    pinyin_payload, reconciled = _reconcile_pinyin_payload_with_gloss(gloss_payload, pinyin_payload)
    if reconciled:
        target_run = _ensure_stage_run_dir(project)
        (target_run / "stages" / "pinyin.json").write_text(
            json.dumps(pinyin_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        messages.warning(
            request,
            "Pinyin/romanization stage was out of sync with gloss and has been auto-reconciled; "
            "aligned token-level values were preserved.",
        )

    rows = _pinyin_rows(gloss_payload, pinyin_payload)
    base_hash = _stable_text_hash(str(gloss_payload.get("surface") or ""))

    if request.method == "POST":
        for row in rows:
            for token in row["tokens"]:
                token["pinyin"] = request.POST.get(
                    f"pinyin_{row['page_index']}_{row['segment_index']}_{token['token_index']}",
                    token["pinyin"],
                )
        try:
            edited_payload = _pinyin_payload_from_rows(gloss_payload, rows)
        except ValueError as exc:
            messages.error(request, str(exc))
        else:
            edited_hash = _stable_text_hash(str(edited_payload.get("surface") or ""))
            if edited_hash != base_hash:
                messages.error(request, "Text hash mismatch; only token pinyin/romanization may be changed.")
            else:
                _save_versioned_stage_payload(
                    project=project,
                    stage_name="pinyin",
                    payload=edited_payload,
                    metadata={"before_text_hash": base_hash, "after_text_hash": edited_hash},
                )
                target_run = _ensure_stage_run_dir(project)
                _invalidate_downstream_stage_files(target_run, "pinyin")
                messages.success(request, "Saved manual pinyin/romanization annotations.")
                return redirect("manual-pinyin", pk=project.pk)

    return render(
        request,
        "projects/manual_pinyin.html",
        {"project": project, "rows": rows, "base_hash": base_hash},
    )


@login_required
def manual_translation(request: HttpRequest, pk: int) -> HttpResponse:
    project = _get_project_for_user(pk=pk, user=request.user, min_role=ProjectCollaborator.ROLE_ANNOTATOR)
    seg2_run = _find_run_with_stage(project, "segmentation_phase_2")
    seg2_payload = _load_stage_payload(project, "segmentation_phase_2", run_dir=seg2_run) if seg2_run else None
    if not seg2_payload:
        messages.error(request, "Manual translation requires segmentation phase 2 annotated text.")
        return redirect("project-annotation-home", pk=project.pk)

    tr_run = _find_run_with_stage(project, "translation") or seg2_run
    tr_payload = _load_stage_payload(project, "translation", run_dir=tr_run) if tr_run else None
    if not tr_payload:
        tr_payload = json.loads(json.dumps(seg2_payload))
    tr_payload, reconciled = _reconcile_translation_payload_with_seg2(seg2_payload, tr_payload)
    if reconciled:
        target_run = _ensure_stage_run_dir(project)
        (target_run / "stages" / "translation.json").write_text(
            json.dumps(tr_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        messages.warning(
            request,
            "Translation stage was out of sync with segmentation phase 2 and has been auto-reconciled; "
            "aligned segments were preserved.",
        )

    rows = _translation_rows(seg2_payload, tr_payload)
    base_hash = _stable_text_hash(str(seg2_payload.get("surface") or ""))

    if request.method == "POST":
        for row in rows:
            row["translation_text"] = request.POST.get(
                f"translation_text_{row['page_index']}_{row['segment_index']}",
                row["translation_text"],
            )
        try:
            edited_payload = _translation_payload_from_rows(seg2_payload, rows)
        except ValueError as exc:
            messages.error(request, str(exc))
        else:
            edited_hash = _stable_text_hash(str(edited_payload.get("surface") or ""))
            if edited_hash != base_hash:
                messages.error(request, "Text hash mismatch; only translation annotations may be changed.")
            else:
                _save_versioned_stage_payload(
                    project=project,
                    stage_name="translation",
                    payload=edited_payload,
                    metadata={"before_text_hash": base_hash, "after_text_hash": edited_hash},
                )
                target_run = _ensure_stage_run_dir(project)
                _invalidate_downstream_stage_files(target_run, "translation")
                messages.success(request, "Saved manual translation.")
                return redirect("manual-translation", pk=project.pk)

    return render(
        request,
        "projects/manual_translation.html",
        {"project": project, "rows": rows, "base_hash": base_hash},
    )


@login_required
def project_images_home(request: HttpRequest, pk: int) -> HttpResponse:
    project = _get_project_for_user(pk=pk, user=request.user, min_role=ProjectCollaborator.ROLE_ANNOTATOR)
    style = getattr(project, "image_style", None)
    valid_ai_models = set(AI_MODEL_CHOICES)
    valid_image_models = set(IMAGE_MODEL_CHOICES)
    if request.method == "POST":
        valid_pivot_languages = {code for code, _label in ProjectForm.LANGUAGE_CHOICES}
        requested_style_ai_model = str(request.POST.get("style_ai_model") or (style.ai_model if style else project.ai_model) or "").strip()
        requested_style_image_model = str(
            request.POST.get("style_image_model") or (style.sample_image_model if style else "gpt-image-1") or ""
        ).strip()
        from_translations = (request.POST.get("generate_page_images_from_translations") or "").strip().lower() in {
            "1",
            "true",
            "on",
            "yes",
        }
        discourage_text_in_images = (request.POST.get("discourage_text_in_images") or "").strip().lower() in {
            "1",
            "true",
            "on",
            "yes",
        }
        text_source = (
            Project.PAGE_IMAGE_TEXT_SOURCE_TRANSLATION
            if from_translations
            else Project.PAGE_IMAGE_TEXT_SOURCE_SEGMENTATION
        )
        pivot_language = (
            (project.target_language or "").strip().lower()
            if text_source == Project.PAGE_IMAGE_TEXT_SOURCE_TRANSLATION
            else ""
        )
        allowed_text_sources = {choice[0] for choice in Project.PAGE_IMAGE_TEXT_SOURCE_CHOICES}
        if requested_style_ai_model not in valid_ai_models:
            messages.error(request, "Unknown style AI model.")
        elif requested_style_image_model not in valid_image_models:
            messages.error(request, "Unknown image model.")
        elif text_source not in allowed_text_sources:
            messages.error(request, "Unknown page-image text source option.")
        elif text_source == Project.PAGE_IMAGE_TEXT_SOURCE_TRANSLATION and pivot_language not in valid_pivot_languages:
            messages.error(request, "Unknown pivot language for image generation.")
        else:
            project.page_image_text_source = text_source
            project.image_generation_pivot_language = pivot_language
            project.save(update_fields=["page_image_text_source", "image_generation_pivot_language", "updated_at"])
            if style is None:
                style = ProjectImageStyle.objects.create(
                    project=project,
                    ai_model=requested_style_ai_model or project.ai_model or DEFAULT_MODEL,
                    sample_image_model=requested_style_image_model or "gpt-image-1",
                    discourage_text_in_images=discourage_text_in_images,
                )
            else:
                update_fields: list[str] = []
                if style.discourage_text_in_images != discourage_text_in_images:
                    style.discourage_text_in_images = discourage_text_in_images
                    update_fields.append("discourage_text_in_images")
                if style.ai_model != requested_style_ai_model:
                    style.ai_model = requested_style_ai_model
                    update_fields.append("ai_model")
                if style.sample_image_model != requested_style_image_model:
                    style.sample_image_model = requested_style_image_model
                    update_fields.append("sample_image_model")
                if update_fields:
                    style.save(update_fields=[*update_fields, "updated_at"])
            synced = _ensure_project_page_rows(project)
            messages.success(request, f"Saved image settings and synced {synced} page rows.")
        return redirect("project-images-home", pk=project.pk)
    elements_with_images = project.image_elements.exclude(image_path="").order_by("name", "id")
    pages_with_images = project.image_pages.exclude(image_path="").order_by("page_number", "id")
    style_has_content = bool(
        style
        and (
            (style.style_brief or "").strip()
            or (style.expanded_style_description or "").strip()
            or (style.sample_image_prompt or "").strip()
            or (style.sample_image_path or "").strip()
        )
    )
    style_ready = bool(
        style
        and (
            (style.sample_image_path or "").strip()
            or style.status in {ProjectImageStyle.STATUS_GENERATED, ProjectImageStyle.STATUS_APPROVED}
        )
    )
    return render(
        request,
        "projects/project_images_home.html",
        {
            "project": project,
            "style": style,
            "style_has_content": style_has_content,
            "style_ready": style_ready,
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
            "page_image_text_source_choices": Project.PAGE_IMAGE_TEXT_SOURCE_CHOICES,
            "selected_page_image_text_source": project.page_image_text_source,
            "pivot_language_choices": ProjectForm.LANGUAGE_CHOICES,
            "selected_image_generation_pivot_language": project.image_generation_pivot_language,
            "discourage_text_in_images_default": bool(getattr(style, "discourage_text_in_images", False)),
            "ai_model_choices": AI_MODEL_CHOICES,
            "image_model_choices": IMAGE_MODEL_CHOICES,
            "selected_style_ai_model": (getattr(style, "ai_model", "") or project.ai_model or DEFAULT_MODEL),
            "selected_style_image_model": (getattr(style, "sample_image_model", "") or "gpt-image-1"),
        },
    )


@login_required
def project_exercises_home(request: HttpRequest, pk: int) -> HttpResponse:
    project = _get_project_for_user(pk=pk, user=request.user, min_role=ProjectCollaborator.ROLE_ANNOTATOR)
    role = _project_role_for_user(project, request.user)
    latest_sets: list[ExerciseSet] = []
    # Keep one latest set per cloze type and one per flashcard mode.
    latest_cloze = (
        project.exercise_sets.filter(exercise_type=ExerciseSet.TYPE_CLOZE)
        .order_by("-updated_at", "-id")
        .first()
    )
    if latest_cloze is not None:
        latest_sets.append(latest_cloze)

    for mode, _label in ExerciseSet.FLASHCARD_MODE_CHOICES:
        flashcard_query = project.exercise_sets.filter(exercise_type=ExerciseSet.TYPE_FLASHCARD)
        if mode == ExerciseSet.FLASHCARD_MODE_FORM_TO_MEANING:
            flashcard_query = flashcard_query.filter(Q(flashcard_mode=mode) | Q(flashcard_mode=""))
        else:
            flashcard_query = flashcard_query.filter(flashcard_mode=mode)
        latest_flashcards_for_mode = flashcard_query.order_by("-updated_at", "-id").first()
        if latest_flashcards_for_mode is not None:
            latest_sets.append(latest_flashcards_for_mode)

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
        _reset_project_artifacts(self.object)
        _persist_project_source(self.object)
        if (self.object.language or "").strip().lower() == (self.object.target_language or "").strip().lower():
            messages.warning(
                self.request,
                "Glossing language is currently the same as text language. "
                "This is usually unintended; consider setting it to your interaction language.",
            )
        return response

    def get_success_url(self):  # type: ignore[override]
        return reverse("project-detail", args=[self.object.pk])

    def _resolve_nl_create_plan(self) -> tuple[str, str, dict[str, Any]]:
        cached = getattr(self.request, "_nl_create_plan_cache", None)
        if isinstance(cached, tuple) and len(cached) == 3:
            return cached  # type: ignore[return-value]
        nl_query = (self.request.GET.get("nl_new_query") or "").strip()
        dialogue_language = (self.request.GET.get("dialogue_language") or "").strip()
        if not dialogue_language:
            try:
                dialogue_language = self.request.user.profile.dialogue_language or "en"
            except Exception:
                dialogue_language = "en"
        nl_plan: dict[str, Any] = {}
        if nl_query:
            prev_query = ""
            prev_plan: dict[str, Any] = {}
            try:
                profile_obj = self.request.user.profile
            except Exception:
                profile_obj = None
            if (
                profile_obj
                and profile_obj.dialogue_memory_enabled
                and isinstance(profile_obj.dialogue_memory, dict)
            ):
                section_payload = _profile_memory_section(profile_obj, "project_create")
                prev_query = str(section_payload.get("last_nl_query") or "")
                prev_plan = section_payload.get("last_nl_plan") if isinstance(section_payload.get("last_nl_plan"), dict) else {}
            nl_plan = _parse_nl_project_create_request(
                nl_query=nl_query,
                dialogue_language=dialogue_language,
                previous_query=prev_query,
                previous_plan=prev_plan,
            )
            if profile_obj and profile_obj.dialogue_memory_enabled:
                _update_profile_memory_section(
                    profile_obj,
                    "project_create",
                    _profile_memory_payload_for_nl(nl_query=nl_query, nl_plan=nl_plan),
                )
        result = (nl_query, dialogue_language, nl_plan)
        setattr(self.request, "_nl_create_plan_cache", result)
        return result

    def get_initial(self):  # type: ignore[override]
        initial = super().get_initial()
        nl_query, dialogue_language, nl_plan = self._resolve_nl_create_plan()
        if dialogue_language:
            initial.setdefault("target_language", dialogue_language)
        if nl_query:
            for key in ("title", "language", "target_language", "input_mode", "description", "source_text"):
                value = nl_plan.get(key)
                if value:
                    initial[key] = value
        return initial

    def get_context_data(self, **kwargs):  # type: ignore[override]
        context = super().get_context_data(**kwargs)
        nl_query, dialogue_language, nl_plan = self._resolve_nl_create_plan()
        context.update(
            {
                "nl_new_query": nl_query,
                "nl_new_plan": nl_plan,
                "dialogue_language": dialogue_language,
                "dialogue_language_choices": ProjectForm.LANGUAGE_CHOICES,
            }
        )
        return context


def _build_ai_client(
    model_name: str | None = None,
    usage_reporter: Callable[[dict[str, Any]], None] | None = None,
    detailed_telemetry: bool = False,
) -> OpenAIClient:
    config = OpenAIConfig(
        model=model_name or DEFAULT_MODEL,
        usage_reporter=usage_reporter,
        detailed_telemetry=detailed_telemetry,
    )
    return OpenAIClient(config=config)


def _billing_usage_reporter(*, user_id: int, project_id: int | None, request_type: str) -> Callable[[dict[str, Any]], None]:
    def _report(event: dict[str, Any]) -> None:
        payload = dict(event or {})
        model = str(payload.get("model") or DEFAULT_MODEL)
        operation = str(payload.get("operation") or "chat")
        prompt_tokens = max(0, int(payload.get("prompt_tokens") or 0))
        completion_tokens = max(0, int(payload.get("completion_tokens") or 0))
        total_tokens = max(0, int(payload.get("total_tokens") or 0))
        used_total_tokens_as_completion = False
        if operation == "image_generate" and completion_tokens == 0 and total_tokens > 0:
            completion_tokens = total_tokens
            used_total_tokens_as_completion = True
        # Image API responses often do not expose token usage. We treat one image call as one output-unit.
        fallback_applied = operation == "image_generate" and prompt_tokens == 0 and completion_tokens == 0 and total_tokens == 0
        if fallback_applied:
            completion_tokens = 1_000_000
            total_tokens = 1_000_000
        record_openai_usage_and_charge(
            user_id=user_id,
            project_id=project_id,
            model=model,
            operation=operation,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            request_type=request_type or str(payload.get("request_type") or operation),
        )
        if project_id and "image" in (request_type or operation):
            try:
                project = Project.objects.filter(pk=project_id).first()
                if project is None:
                    return
                usage = AIUsageCharge.objects.filter(user_id=user_id, project_id=project_id).order_by("-created_at", "-id").first()
                user = get_user_model().objects.filter(pk=user_id).first()
                pricing = openai_price_for_model(model)
                _append_image_billing_telemetry(
                    project,
                    {
                        "event": "billing_usage_recorded",
                        "request_type": request_type,
                        "operation": operation,
                        "model": model,
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "total_tokens": total_tokens,
                        "fallback_applied": fallback_applied,
                        "used_total_tokens_as_completion": used_total_tokens_as_completion,
                        "price_input_usd_per_1m": str(pricing["input"]),
                        "price_output_usd_per_1m": str(pricing["output"]),
                        "usage_charge_id": usage.id if usage else None,
                        "usage_status": usage.status if usage else None,
                        "usage_cost_usd": str(usage.cost_usd) if usage else None,
                        "balance_after_usd": str(get_user_balance_usd(user)) if user is not None else None,
                    },
                )
            except Exception:
                logger.exception("Failed to append image billing telemetry")

    return _report


def _build_billed_project_ai_client(
    project: Project,
    *,
    model_name: str | None = None,
    request_type: str,
) -> OpenAIClient:
    return _build_ai_client(
        model_name=model_name,
        usage_reporter=_billing_usage_reporter(
            user_id=project.owner_id,
            project_id=project.id,
            request_type=request_type,
        ),
    )


def _collect_usage_event(
    events: list[dict[str, Any]],
) -> Callable[[dict[str, Any]], None]:
    def _report(event: dict[str, Any]) -> None:
        events.append(dict(event or {}))

    return _report


def _flush_project_usage_events(
    *,
    project: Project,
    events: list[dict[str, Any]],
    request_type: str,
    default_model: str,
) -> None:
    for event in events:
        record_openai_usage_and_charge(
            user_id=project.owner_id,
            project_id=project.id,
            model=str(event.get("model") or default_model),
            operation=str(event.get("operation") or "chat"),
            prompt_tokens=max(0, int(event.get("prompt_tokens") or 0)),
            completion_tokens=max(0, int(event.get("completion_tokens") or 0)),
            total_tokens=max(0, int(event.get("total_tokens") or 0)),
            request_type=request_type,
        )
    events.clear()


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


def _reset_project_artifacts(project: Project) -> None:
    """Remove stale artifacts when a freshly-created project reuses an old id.

    In local/dev environments it's common to recreate the database without
    cleaning MEDIA_ROOT. If ids restart from 1, a new project can inherit
    previous run artifacts from an unrelated historical project.
    """

    base = project.artifact_dir()
    if not base.exists():
        return
    try:
        shutil.rmtree(base)
    except Exception:
        logger.exception("Failed to clear stale artifact directory for new project %s", project.pk)


def _resolve_run_dir(project: Project) -> Path | None:
    base = project.artifact_dir().resolve()
    compiled_run_dir: Path | None = None
    if project.compiled_path:
        rel = Path(project.compiled_path)
        if len(rel.parts) >= 2 and rel.parts[0] == "runs":
            candidate = (base / rel.parts[0] / rel.parts[1]).resolve()
            if candidate.exists():
                compiled_run_dir = candidate
    runs_root = base / "runs"
    latest_run_dir: Path | None = None
    if runs_root.exists():
        try:
            latest_run_dir = max(runs_root.iterdir(), key=lambda p: p.stat().st_mtime)
        except ValueError:
            latest_run_dir = None

    if compiled_run_dir and latest_run_dir:
        return latest_run_dir if latest_run_dir.stat().st_mtime >= compiled_run_dir.stat().st_mtime else compiled_run_dir
    return latest_run_dir or compiled_run_dir


def _has_segmentation_phase_1_output(project: Project) -> bool:
    return _find_latest_stage_file(project, "segmentation_phase_1.json") is not None



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


def _find_latest_stage_file(project: Project, stage_filename: str) -> tuple[Path, Path] | None:
    newest: tuple[Path, Path] | None = None
    newest_mtime = float("-inf")
    for run_dir in _iter_runs(project):
        candidate = run_dir / "stages" / stage_filename
        if not candidate.exists():
            continue
        try:
            mtime = candidate.stat().st_mtime
        except Exception:
            continue
        if mtime > newest_mtime:
            newest = (run_dir, candidate)
            newest_mtime = mtime
    return newest


def _find_run_with_stage(project: Project, stage: str) -> Path | None:
    latest = _find_latest_stage_file(project, f"{stage}.json")
    return latest[0] if latest else None


def _load_stage_payload(
    project: Project, stage: str, run_dir: Path | None = None
) -> dict[str, Any] | None:
    if run_dir is None:
        run_dir = _find_run_with_stage(project, stage) or _resolve_run_dir(project)
    if not run_dir:
        return None
    path = run_dir / "stages" / f"{stage}.json"
    if not path.exists():
        return None
    try:
        return normalize_json_text(json.loads(path.read_text(encoding="utf-8")))
    except Exception:
        return None


def _copy_run_artifacts(src: Path, dest: Path) -> None:
    """Copy prior run outputs into ``dest`` so partial recompiles have inputs.

    Stages upstream from the chosen start point live in previous run folders.
    Copying those artifacts forward lets later partial runs chain together even
    when the most recent run only contains downstream outputs.

    Important: only stage artifacts are copied. Runtime output directories like
    ``audio/`` and ``html/`` are intentionally not copied because they can
    contain stale files from older runs, which may cause filename collisions and
    mismatched audio references during recompilation.
    """

    stage_src = src / "stages"
    if stage_src.exists():
        shutil.copytree(stage_src, dest / "stages", dirs_exist_ok=True)


def _latest_stage_artifact(project: Project, stage: str) -> tuple[Path, Path, float] | None:
    run_dir = _find_run_with_stage(project, stage)
    if run_dir is None:
        return None
    stage_path = run_dir / "stages" / f"{stage}.json"
    if not stage_path.exists():
        return None
    try:
        mtime = stage_path.stat().st_mtime
    except Exception:
        return None
    return run_dir, stage_path, mtime


def _stage_payload_with_meta(project: Project, stage: str) -> dict[str, Any] | None:
    latest = _latest_stage_artifact(project, stage)
    if latest is None:
        return None
    run_dir, stage_path, mtime = latest
    payload = _load_stage_payload(project, stage, run_dir=run_dir)
    if payload is None:
        return None
    return {"stage": stage, "run": run_dir.name, "path": stage_path, "mtime": mtime, "payload": payload}


def _segments_are_compatible(base_payload: dict[str, Any], candidate_payload: dict[str, Any]) -> bool:
    base_pages = base_payload.get("pages") or []
    cand_pages = candidate_payload.get("pages") or []
    if len(base_pages) != len(cand_pages):
        return False
    for base_page, cand_page in zip(base_pages, cand_pages):
        base_segments = base_page.get("segments") or []
        cand_segments = cand_page.get("segments") or []
        if len(base_segments) != len(cand_segments):
            return False
        for base_seg, cand_seg in zip(base_segments, cand_segments):
            if str(base_seg.get("surface") or "") != str(cand_seg.get("surface") or ""):
                return False
    return True


def _tokens_are_compatible(base_payload: dict[str, Any], candidate_payload: dict[str, Any]) -> bool:
    if not _segments_are_compatible(base_payload, candidate_payload):
        return False
    base_pages = base_payload.get("pages") or []
    cand_pages = candidate_payload.get("pages") or []
    for base_page, cand_page in zip(base_pages, cand_pages):
        for base_seg, cand_seg in zip(base_page.get("segments") or [], cand_page.get("segments") or []):
            base_tokens = base_seg.get("tokens") or []
            cand_tokens = cand_seg.get("tokens") or []
            if len(base_tokens) != len(cand_tokens):
                return False
            for base_tok, cand_tok in zip(base_tokens, cand_tokens):
                if str(base_tok.get("surface") or "") != str(cand_tok.get("surface") or ""):
                    return False
    return True


def _apply_segment_annotation(
    base_payload: dict[str, Any], candidate_payload: dict[str, Any], *, key: str
) -> int:
    applied = 0
    for base_page, cand_page in zip(base_payload.get("pages") or [], candidate_payload.get("pages") or []):
        for base_seg, cand_seg in zip(base_page.get("segments") or [], cand_page.get("segments") or []):
            cand_annotations = cand_seg.get("annotations") or {}
            if key not in cand_annotations:
                continue
            base_annotations = dict(base_seg.get("annotations") or {})
            base_annotations[key] = cand_annotations[key]
            base_seg["annotations"] = base_annotations
            applied += 1
    return applied


def _apply_token_annotation(
    base_payload: dict[str, Any], candidate_payload: dict[str, Any], *, key: str
) -> int:
    applied = 0
    for base_page, cand_page in zip(base_payload.get("pages") or [], candidate_payload.get("pages") or []):
        for base_seg, cand_seg in zip(base_page.get("segments") or [], cand_page.get("segments") or []):
            for base_tok, cand_tok in zip(base_seg.get("tokens") or [], cand_seg.get("tokens") or []):
                cand_annotations = cand_tok.get("annotations") or {}
                if key not in cand_annotations:
                    continue
                base_annotations = dict(base_tok.get("annotations") or {})
                base_annotations[key] = cand_annotations[key]
                base_tok["annotations"] = base_annotations
                applied += 1
    return applied


def _compose_latest_compile_payload(project: Project) -> tuple[dict[str, Any] | None, list[str]]:
    """Build a compile-ready payload by composing latest compatible stage outputs."""

    stage_meta: dict[str, dict[str, Any]] = {}
    for stage_name in ["segmentation_phase_2", "translation", "mwe", "lemma", "gloss", "pinyin", "audio"]:
        meta = _stage_payload_with_meta(project, stage_name)
        if meta is not None:
            stage_meta[stage_name] = meta

    base_stage = None
    for candidate in ["audio", "pinyin", "gloss", "lemma", "mwe", "translation", "segmentation_phase_2"]:
        if candidate in stage_meta:
            base_stage = candidate
            break
    if base_stage is None:
        return None, ["no upstream stage payloads found"]

    composed = json.loads(json.dumps(stage_meta[base_stage]["payload"]))
    plan: list[str] = [f"base={base_stage}@{stage_meta[base_stage]['run']}"]

    now_ts = datetime.now(timezone.utc).timestamp()

    def _age_minutes(meta: dict[str, Any]) -> int:
        return max(0, int((now_ts - float(meta["mtime"])) / 60))

    def _add_plan(stage_name: str, note: str) -> None:
        meta = stage_meta[stage_name]
        plan.append(f"{stage_name}@{meta['run']} ({_age_minutes(meta)}m old): {note}")

    if "translation" in stage_meta and _segments_are_compatible(composed, stage_meta["translation"]["payload"]):
        n = _apply_segment_annotation(composed, stage_meta["translation"]["payload"], key="translation")
        _add_plan("translation", f"applied segment translation to {n} segment(s)")

    if "mwe" in stage_meta and _tokens_are_compatible(composed, stage_meta["mwe"]["payload"]):
        n1 = _apply_segment_annotation(composed, stage_meta["mwe"]["payload"], key="mwes")
        n2 = _apply_token_annotation(composed, stage_meta["mwe"]["payload"], key="mwe_id")
        _add_plan("mwe", f"applied mwes/mwe_id to {n1 + n2} field(s)")

    if "lemma" in stage_meta and _tokens_are_compatible(composed, stage_meta["lemma"]["payload"]):
        n1 = _apply_token_annotation(composed, stage_meta["lemma"]["payload"], key="lemma")
        n2 = _apply_token_annotation(composed, stage_meta["lemma"]["payload"], key="pos")
        _add_plan("lemma", f"applied lemma/pos to {n1 + n2} token field(s)")

    if "gloss" in stage_meta and _tokens_are_compatible(composed, stage_meta["gloss"]["payload"]):
        n = _apply_token_annotation(composed, stage_meta["gloss"]["payload"], key="gloss")
        _add_plan("gloss", f"applied gloss to {n} token(s)")

    if "pinyin" in stage_meta and _tokens_are_compatible(composed, stage_meta["pinyin"]["payload"]):
        n = _apply_token_annotation(composed, stage_meta["pinyin"]["payload"], key="pinyin")
        _add_plan("pinyin", f"applied pinyin to {n} token(s)")

    if "audio" in stage_meta and _tokens_are_compatible(composed, stage_meta["audio"]["payload"]):
        n1 = _apply_token_annotation(composed, stage_meta["audio"]["payload"], key="audio")
        n2 = _apply_segment_annotation(composed, stage_meta["audio"]["payload"], key="audio")
        _add_plan("audio", f"applied audio annotations to {n1 + n2} node(s)")

    return normalize_json_text(composed), plan


def _build_picture_glosses_for_compile(*, project: Project, output_dir: Path) -> dict[str, dict[str, str]]:
    if not project.community_id:
        return {}
    picture_glosses: dict[str, dict[str, str]] = {}
    picture_gloss_dir = output_dir / "html" / "picture_glosses"
    picture_gloss_dir.mkdir(parents=True, exist_ok=True)
    dictionary = (
        PictureDictionary.objects.select_related("project")
        .filter(community_id=project.community_id, is_active=True)
        .first()
    )
    if not dictionary:
        return {}
    for entry in PictureDictionaryEntry.objects.filter(
        dictionary=dictionary,
        is_active=True,
    ):
        lemma_key = (entry.lemma or entry.surface or "").strip().casefold()
        if not lemma_key or lemma_key in picture_glosses:
            continue
        resolved_image_path = (entry.image_path or "").strip()
        if not resolved_image_path:
            page_qs = ProjectImagePage.objects.select_related("preferred_variant").filter(project=dictionary.project)
            if entry.current_page_number:
                page = page_qs.filter(page_number=entry.current_page_number).first()
            else:
                page = page_qs.filter(page_text=entry.surface).order_by("page_number").first()
            if page:
                resolved_image_path = (page.image_path or "").strip()
                if not resolved_image_path and page.preferred_variant_id and page.preferred_variant:
                    resolved_image_path = (page.preferred_variant.image_path or "").strip()
            if resolved_image_path:
                entry.image_path = resolved_image_path
                entry.save(update_fields=["image_path", "updated_at"])
        if not resolved_image_path:
            continue
        abs_path = (dictionary.project.artifact_dir() / resolved_image_path).resolve()
        if not abs_path.exists():
            continue
        if dictionary.project_id == project.id:
            rel_path = os.path.relpath(abs_path, output_dir / "html").replace("\\", "/")
        else:
            digest = hashlib.sha1(
                f"{dictionary.project_id}:{entry.id}:{abs_path}".encode("utf-8")
            ).hexdigest()[:12]
            safe_lemma = re.sub(r"[^a-z0-9_-]+", "_", lemma_key).strip("_") or "lemma"
            suffix = abs_path.suffix or ".png"
            staged_path = picture_gloss_dir / f"{safe_lemma}_{digest}{suffix}"
            if not staged_path.exists():
                shutil.copy2(abs_path, staged_path)
            rel_path = os.path.relpath(staged_path, output_dir / "html").replace("\\", "/")
        picture_glosses[lemma_key] = {
            "image_path": rel_path,
            "surface": entry.surface or entry.lemma or "",
        }
    return picture_glosses


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
    detailed_api_trace: bool = False,
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
    post_update, _ = _make_task_callback(task_type or f"compile_project_{project_id}", user_id, report_uuid)
    telemetry_log = output_dir / "stages" / "telemetry.jsonl"
    telemetry = _TaskTelemetry(log_path=telemetry_log, post_update=post_update)
    post_update(f"Telemetry log file: {telemetry_log}")

    def progress_cb(stage: str, status: str, timestamp: str) -> None:
        try:
            dt = datetime.fromisoformat(timestamp)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            local_timestamp = dt.astimezone(ZoneInfo(tz_name)).isoformat()
        except Exception:
            local_timestamp = timestamp
        entry = {"stage": stage, "status": status, "timestamp": local_timestamp}
        logger.info(
            "Compile progress project=%s stage=%s status=%s timestamp=%s",
            project_id,
            stage,
            status,
            local_timestamp,
        )
        try:
            with progress_log.open("a", encoding="utf-8") as fp:
                fp.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            logger.exception("Failed to append progress entry; progress_log=%s", progress_log)
        try:
            display_ts, _ = _format_timestamp(local_timestamp, tz_name)
            post_update(f"{stage}: {status} @ {display_ts}")
        except Exception:
            logger.exception("Failed to persist task update; stage=%s status=%s report_id=%s", stage, status, report_id)

    current_request_type: dict[str, str] = {"value": start_stage}

    def tracked_progress_cb(stage: str, status: str, timestamp: str) -> None:
        current_request_type["value"] = stage or current_request_type["value"]
        progress_cb(stage, status, timestamp)

    try:
        post_update(
            "Compile task started. "
            f"start_stage={start_stage}, end_stage={end_stage or 'compile_html'}, output_dir={output_dir}"
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
            progress_callback=tracked_progress_cb,
            start_stage=start_stage,
            end_stage=end_stage or "compile_html",
            page_images={},
            picture_glosses={},
            segmentation_method=_resolve_segmentation_method(project.language, segmentation_method or project.segmentation_method),
            romanization_method=_resolve_romanization_method(project.language, romanization_method or project.romanization_method),
            telemetry=telemetry,
        )
        post_update("Pipeline spec initialized.")
        try:
            spec.picture_glosses = _build_picture_glosses_for_compile(project=project, output_dir=output_dir)
            post_update(f"Prepared picture gloss map: {len(spec.picture_glosses)} lemma image(s).")
        except Exception as gloss_exc:
            logger.exception("Failed to build picture gloss map for project %s; continuing without picture glosses", project_id)
            spec.picture_glosses = {}
            post_update(f"Warning: picture gloss map build failed ({gloss_exc}). Continuing without picture glosses.")

        placement = (page_image_placement or "none").strip().lower()
        if placement in {"top", "bottom"}:
            page_images: dict[int, dict[str, str]] = {}
            expected_paths: list[str] = []
            for row in project.image_pages.select_related("preferred_variant").order_by("page_number"):
                resolved_image_path = row.image_path or (
                    row.preferred_variant.image_path if row.preferred_variant_id and row.preferred_variant else ""
                )
                if not resolved_image_path:
                    expected_paths.append(f"page {row.page_number}: [no image_path set]")
                    continue
                abs_path = (project.artifact_dir() / resolved_image_path).resolve()
                rel_path = os.path.relpath(abs_path, output_dir / "html").replace("\\", "/")
                expected_paths.append(f"page {row.page_number}: {abs_path} (exists={abs_path.exists()})")
                if abs_path.exists():
                    page_images[row.page_number] = {"path": rel_path, "placement": placement}
            spec.page_images = page_images
            post_update(f"Resolved compile page images: {len(page_images)} page image reference(s).")
            if not page_images:
                logger.warning(
                    "Page image placement is '%s' but no source images were resolved for compile input. Expected references: %s",
                    placement,
                    "; ".join(expected_paths) if expected_paths else "[no ProjectImagePage rows found]",
                )
                post_update("Warning: page image placement is enabled but no page images were found for compile input.")

        chosen_model = ai_model or project.ai_model or DEFAULT_MODEL
        if chosen_model not in AI_MODEL_CHOICES:
            chosen_model = DEFAULT_MODEL
        usage_events: list[dict[str, Any]] = []
        model_pricing = openai_price_for_model(chosen_model)

        def usage_reporter(event: dict[str, Any]) -> None:
            event_copy = dict(event or {})
            usage_events.append(event_copy)
            if not detailed_api_trace:
                return
            prompt_tokens = max(0, int(event_copy.get("prompt_tokens") or 0))
            completion_tokens = max(0, int(event_copy.get("completion_tokens") or 0))
            input_cost_usd = (model_pricing["input"] * prompt_tokens) / 1_000_000
            output_cost_usd = (model_pricing["output"] * completion_tokens) / 1_000_000
            total_cost_usd = input_cost_usd + output_cost_usd
            telemetry.event(
                str(event_copy.get("request_type") or current_request_type["value"] or "unknown"),
                "info",
                "openai.usage trace",
                {
                    "model": str(event_copy.get("model") or chosen_model),
                    "operation": str(event_copy.get("operation") or "chat"),
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": max(0, int(event_copy.get("total_tokens") or 0)),
                    "assumed_input_usd_per_1m_tokens": str(model_pricing["input"]),
                    "assumed_output_usd_per_1m_tokens": str(model_pricing["output"]),
                    "assumed_input_cost_usd": str(round(input_cost_usd, 6)),
                    "assumed_output_cost_usd": str(round(output_cost_usd, 6)),
                    "assumed_total_cost_usd": str(round(total_cost_usd, 6)),
                },
            )

        def flush_usage_events() -> None:
            for event in usage_events:
                try:
                    record_openai_usage_and_charge(
                        user_id=user_id,
                        project_id=project_id,
                        model=str(event.get("model") or chosen_model),
                        operation=str(event.get("operation") or "chat"),
                        prompt_tokens=int(event.get("prompt_tokens") or 0),
                        completion_tokens=int(event.get("completion_tokens") or 0),
                        total_tokens=int(event.get("total_tokens") or 0),
                        request_type=str(event.get("request_type") or current_request_type["value"] or "unknown"),
                    )
                except Exception:
                    logger.exception("Failed to record OpenAI usage charge for project=%s", project_id)

        def _finalize_usage_events() -> None:
            try:
                flush_usage_events()
            except Exception:
                logger.exception("Unexpected failure while finalizing usage events for project=%s", project_id)

        post_update(f"Building AI client: model={chosen_model}.")
        client = _build_ai_client(
            model_name=chosen_model,
            usage_reporter=usage_reporter,
            detailed_telemetry=detailed_api_trace,
        )
        post_update("Running full pipeline.")
        try:
            result = asyncio.run(run_full_pipeline(spec, client=client))
        except Exception as exc:
            _finalize_usage_events()
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
                logger.exception("Failed to append compile failure entry; progress_log=%s", progress_log)
            post_update(f"Compile failed: {exc}", status="error")
            return
        _finalize_usage_events()
        post_update("Pipeline returned; finalizing compile outputs.")

        requested_end_stage = spec.end_stage or "compile_html"
        if requested_end_stage == "segmentation_phase_1":
            salvage_info = _salvage_segmentation_phase_2_for_run(output_dir)
            _invalidate_downstream_stage_files(output_dir, "segmentation_phase_2")
            if salvage_info:
                post_update(
                    "Salvaged segmentation_phase_2 for "
                    f"{salvage_info['unchanged_pages']}/{salvage_info['total_pages']} unchanged pages."
                )
        html_info: dict[str, Any] | None = result.get("html") if isinstance(result, dict) else None
        compiled_rel = ""
        if html_info:
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
    except Exception as exc:
        logger.exception("Unhandled compile task exception for project %s", project_id)
        try:
            post_update(f"Compile task crashed unexpectedly: {exc}", status="error")
        except Exception:
            logger.exception("Failed to post unexpected-crash update for project %s", project_id)


def _run_picture_dictionary_compile_task(dictionary_id: int, user_id: int, report_id: str) -> None:
    task_type = f"picture_dictionary_compile_{dictionary_id}"
    try:
        report_uuid = uuid.UUID(report_id)
    except Exception:
        report_uuid = uuid.uuid4()
    post_update, _ = _make_task_callback(task_type, user_id, report_uuid)
    try:
        dictionary = (
            PictureDictionary.objects.select_related("project")
            .filter(pk=dictionary_id, is_active=True)
            .first()
        )
        if not dictionary:
            post_update("Picture dictionary compile failed: dictionary not found.", status="error")
            return

        post_update("Picture dictionary compilation started.", status="running")
        result = picture_dictionary_compile(
            dictionary=dictionary,
            progress_callback=lambda message: post_update(message, status="running"),
            compile_task_report_id=report_id,
            compile_task_user_id=user_id,
            compile_task_type=task_type,
        )
        post_update(
            "Compiled picture dictionary: "
            f"pages={result['pages']}, page rows synced={result['page_rows_synced']}, "
            f"annotation pipeline={result.get('annotation_run')}, generated images={result.get('generated_images', 0)}.",
            status="running",
        )
        if result.get("annotation_error"):
            post_update(f"Annotation pipeline failed: {result.get('annotation_error')}", status="running")
        if result.get("image_generation_note"):
            post_update(str(result.get("image_generation_note")), status="running")
        post_update("Picture dictionary compilation complete.", status="finished")
    except Exception as exc:
        logger.exception("Unhandled picture dictionary compile task exception for dictionary %s", dictionary_id)
        post_update(f"Picture dictionary compile task crashed unexpectedly: {exc}", status="error")


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
    return_to = (request.POST.get("return_to") or "").strip()
    if not return_to.startswith("/"):
        return_to = reverse("project-detail", args=[project.pk])

    start_stage = request.POST.get("start_stage") or _default_start_stage_for_project(project)
    requested_start_stage = start_stage
    if start_stage not in PIPELINE_ORDER:
        messages.error(request, "Unknown start stage.")
        return redirect(return_to)
    end_stage = request.POST.get("end_stage") or "compile_html"
    if end_stage not in PIPELINE_ORDER:
        messages.error(request, "Unknown end stage.")
        return redirect(return_to)
    if PIPELINE_ORDER.index(end_stage) < PIPELINE_ORDER.index(start_stage):
        messages.error(request, "End stage must come after the selected start stage.")
        return redirect(return_to)
    detailed_api_trace = (request.POST.get("detailed_api_trace") or "").strip().lower() in {
        "1",
        "true",
        "on",
        "yes",
    }
    compose_latest_upstream = True
    confirm_compose_latest = True

    page_image_placement = (
        request.POST.get("page_image_placement")
        or project.page_image_placement
        or "none"
    ).strip().lower()
    if page_image_placement not in PAGE_IMAGE_PLACEMENT_CHOICES:
        messages.error(request, "Unknown page image placement option.")
        return redirect(return_to)

    ai_model = request.POST.get("ai_model") or project.ai_model or DEFAULT_MODEL
    if ai_model not in AI_MODEL_CHOICES:
        messages.error(request, "Unknown AI model selection.")
        return redirect(return_to)
    if ai_model != project.ai_model:
        project.ai_model = ai_model
        project.save(update_fields=["ai_model", "updated_at"])

    segmentation_method = (request.POST.get("segmentation_method") or project.segmentation_method or "auto").strip().lower()
    romanization_method = (request.POST.get("romanization_method") or project.romanization_method or "auto").strip().lower()
    if segmentation_method not in SEGMENTATION_METHOD_CHOICES:
        messages.error(request, "Unknown segmentation method option.")
        return redirect(return_to)
    if romanization_method not in ROMANIZATION_METHOD_CHOICES:
        messages.error(request, "Unknown romanization method option.")
        return redirect(return_to)
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

    if start_stage == "compile_html" and compose_latest_upstream:
        composed_payload, compose_plan = _compose_latest_compile_payload(project)
        if composed_payload is None:
            messages.error(
                request,
                "Unable to compose compile input from latest upstream stage files. "
                "Run from an earlier stage instead.",
            )
            return redirect(return_to)
        if not confirm_compose_latest:
            messages.warning(
                request,
                "Compose-latest mode found a merge plan, but confirmation is required. "
                "Re-run with 'Confirm composed input' checked."
            )
            for entry in compose_plan[:10]:
                messages.info(request, f"Compose plan: {entry}")
            return redirect(return_to)
        text = None
        text_obj = composed_payload
        messages.info(request, "Compose-latest mode confirmed; compiling from merged upstream artifacts.")
        for entry in compose_plan[:10]:
            messages.info(request, f"Compose plan: {entry}")
    elif start_stage == "text_gen":
        if not description:
            messages.error(request, "Please provide a description to generate text.")
            return redirect(return_to)
    elif start_stage == "segmentation_phase_1":
        text = (project.source_text or "").strip()
        source_run = _resolve_run_dir(project)
        if source_run:
            try:
                _copy_run_artifacts(source_run, output_dir)
                progress_log = output_dir / "stages" / "progress.jsonl"
                if progress_log.exists():
                    progress_log.unlink()
            except Exception:
                logger.exception("Failed to copy prior run artifacts from %s", source_run)
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
            return redirect(return_to)
    else:
        # Start from a persisted intermediate produced by previous runs.
        # We choose the *freshest* upstream artifact across stages before the
        # requested start stage, then rerun forward from the next stage. This
        # prevents stale downstream stages (e.g. old audio) from masking newer
        # edits in earlier stages (e.g. translation/gloss).
        requested_start_index = PIPELINE_ORDER.index(start_stage)
        upstream_stages = PIPELINE_ORDER[:requested_start_index]

        freshest: tuple[str, Path, float] | None = None
        for stage_name in upstream_stages:
            latest = _latest_stage_artifact(project, stage_name)
            if latest is None:
                continue
            run_dir, _stage_path, mtime = latest
            if freshest is None or mtime > freshest[2]:
                freshest = (stage_name, run_dir, mtime)

        if freshest is None:
            messages.error(
                request,
                f"Cannot start at {start_stage}: no upstream stage outputs were found.",
            )
            return redirect(return_to)

        freshest_stage, source_run, _freshest_mtime = freshest
        freshest_payload = _load_stage_payload(project, freshest_stage, run_dir=source_run)
        if freshest_payload is None:
            messages.error(
                request,
                f"Cannot start at {start_stage}: failed to load upstream stage output ({freshest_stage}).",
            )
            return redirect(return_to)

        effective_start_stage = PIPELINE_ORDER[PIPELINE_ORDER.index(freshest_stage) + 1]
        if PIPELINE_ORDER.index(effective_start_stage) > requested_start_index:
            effective_start_stage = requested_start_stage
        if effective_start_stage != requested_start_stage:
            messages.info(
                request,
                f"Using fresher upstream stage '{freshest_stage}', so recompilation will start at '{effective_start_stage}'.",
            )
        start_stage = effective_start_stage

        if start_stage == "segmentation_phase_1":
            text = str((freshest_payload or {}).get("surface") or "").strip()
            if not text:
                messages.error(
                    request,
                    "Cannot start at segmentation_phase_1: missing text surface in upstream stage output.",
                )
                return redirect(return_to)
            text_obj = None
        else:
            text_obj = freshest_payload

        try:
            _copy_run_artifacts(source_run, output_dir)
            # Each run gets its own progress trail; start with a clean slate.
            progress_log = output_dir / "stages" / "progress.jsonl"
            if progress_log.exists():
                progress_log.unlink()
        except Exception:
            logger.exception("Failed to copy prior run artifacts from %s", source_run)

    if credits_enabled() and not has_minimum_balance_for_compile(request.user):
        min_required = minimum_compile_balance_usd()
        current_balance = get_user_balance_usd(request.user)
        messages.error(
            request,
            f"Insufficient credits to start compile. Current balance: ${current_balance:.4f}; "
            f"minimum required: ${min_required:.4f}. Please contact an administrator for recharge.",
        )
        return redirect(return_to)

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
        detailed_api_trace,
        q_options={"sync": False},
    )

    monitor_url = reverse("project-compile-monitor", args=[project.pk, report_id])
    return redirect(f"{monitor_url}?next={quote(return_to, safe='/')}")


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
    return_url = request.GET.get("next") or reverse("project-detail", args=[project.pk])
    return render(
        request,
        "projects/compile_monitor.html",
        {"project": project, "report_id": report_id, "return_url": return_url},
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


def _parse_nl_content_request(
    *,
    nl_query: str,
    dialogue_language: str,
    previous_query: str = "",
    previous_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    prev_plan = previous_plan or {}
    prompt = (
        f"User language for this request: {dialogue_language}. "
        "Convert the user request into JSON filters for published content discovery, using prior turn context if relevant. "
        "If the user asks to change language/topic, update or clear previous filters accordingly. "
        "Return only a JSON object with keys: title, text_language, annotation_language, date_posted, level, keywords, max_results. "
        "date_posted must be one of: any, last_3_days, last_month, last_3_months, last_year. "
        "keywords must be an array of short strings. If unknown, use empty strings/arrays.\n\n"
        f"Previous user request: {previous_query}\n"
        f"Previous interpreted filters: {prev_plan}\n\n"
        f"Current user request: {nl_query}"
    )
    try:
        client = _build_ai_client(model_name="gpt-4o-mini")
        payload = asyncio.run(client.chat_json(prompt, model="gpt-4o-mini"))
    except Exception:
        logger.exception("NL content parsing failed; falling back to plain filters")
        return {}
    if not isinstance(payload, dict):
        return {}
    raw_title = str(payload.get("title") or "").strip()
    title = _sanitize_nl_title_hint(raw_title)
    return {
        "title": title,
        "text_language": str(payload.get("text_language") or "").strip(),
        "annotation_language": str(payload.get("annotation_language") or "").strip(),
        "date_posted": _normalize_date_posted_filter(str(payload.get("date_posted") or "").strip()),
        "level": _normalize_cefr_level_expression(str(payload.get("level") or "").strip(), max_levels=3),
        "keywords": [str(item).strip() for item in (payload.get("keywords") or []) if str(item).strip()],
        "max_results": int(payload.get("max_results") or 12),
    }


def _parse_nl_project_open_request(
    *,
    nl_query: str,
    dialogue_language: str,
    previous_query: str = "",
    previous_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    prev_plan = previous_plan or {}
    prompt = (
        f"User language for this request: {dialogue_language}. "
        "Interpret the request for opening an existing project. "
        "Return only JSON keys: title, text_language, annotation_language, keywords. "
        "Language mentions (e.g., German, Old Norse, French) usually refer to text_language, not title. "
        "Use prior turn context if relevant and use empty strings/arrays for unknown values.\n\n"
        f"Previous user request: {previous_query}\n"
        f"Previous interpreted filters: {prev_plan}\n\n"
        f"Current user request: {nl_query}"
    )
    try:
        client = _build_ai_client(model_name="gpt-4o-mini")
        payload = asyncio.run(client.chat_json(prompt, model="gpt-4o-mini"))
    except Exception:
        logger.exception("NL project-open parsing failed")
        return {}
    if not isinstance(payload, dict):
        return {}
    parsed = {
        "title": str(payload.get("title") or "").strip(),
        "text_language": _normalize_language_filter(str(payload.get("text_language") or "")),
        "annotation_language": _normalize_language_filter(str(payload.get("annotation_language") or "")),
        "keywords": [str(k).strip().lower() for k in (payload.get("keywords") or []) if str(k).strip()],
    }
    return _postprocess_project_open_plan(nl_query=nl_query, parsed=parsed)


def _parse_nl_project_create_request(
    *,
    nl_query: str,
    dialogue_language: str,
    previous_query: str = "",
    previous_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    prev_plan = previous_plan or {}
    prompt = (
        f"User language for this request: {dialogue_language}. "
        "Interpret this as a new-project setup request. "
        "Return only JSON keys: title, language, target_language, input_mode, description, source_text, keywords. "
        "input_mode must be one of: description, source_text. "
        "Default target_language to the user language unless the user explicitly requests a different glossing/annotation language. "
        "Use prior turn context if relevant. Use empty strings/arrays for unknown values.\n\n"
        f"Previous user request: {previous_query}\n"
        f"Previous interpreted setup: {prev_plan}\n\n"
        f"Current user request: {nl_query}"
    )
    try:
        client = _build_ai_client(model_name="gpt-4o-mini")
        payload = asyncio.run(client.chat_json(prompt, model="gpt-4o-mini"))
    except Exception:
        logger.exception("NL project-create parsing failed")
        return {}
    if not isinstance(payload, dict):
        return {}
    input_mode = str(payload.get("input_mode") or "").strip().lower()
    if input_mode not in {Project.INPUT_DESCRIPTION, Project.INPUT_SOURCE}:
        input_mode = ""
    language = _normalize_language_filter(str(payload.get("language") or ""))
    target_language = _normalize_language_filter(str(payload.get("target_language") or ""))
    dialogue_lang = _normalize_language_filter(dialogue_language)
    if not target_language:
        target_language = dialogue_lang
    if (
        language
        and target_language
        and language == target_language
        and dialogue_lang
        and dialogue_lang != language
        and not re.search(r"\b(same|identical|monolingual)\b", nl_query.lower())
    ):
        target_language = dialogue_lang
    return {
        "title": str(payload.get("title") or "").strip(),
        "language": language,
        "target_language": target_language,
        "input_mode": input_mode,
        "description": str(payload.get("description") or "").strip(),
        "source_text": str(payload.get("source_text") or "").strip(),
        "keywords": [str(k).strip().lower() for k in (payload.get("keywords") or []) if str(k).strip()],
    }


def _sanitize_nl_title_hint(raw_title: str) -> str:
    """Drop generic/non-specific NL title hints so they don't over-filter results."""
    value = (raw_title or "").strip()
    if not value:
        return ""
    generic = {
        "story",
        "stories",
        "text",
        "texts",
        "article",
        "articles",
        "book",
        "books",
        "content",
        "something",
        "anything",
    }
    if value.lower() in generic:
        return ""
    return value


def _language_mentions_in_text(text: str) -> list[str]:
    lowered = (text or "").lower()
    mentions: list[str] = []
    for code, label in ProjectForm.LANGUAGE_CHOICES:
        if re.search(rf"\b{re.escape(str(code).lower())}\b", lowered) or re.search(
            rf"\b{re.escape(str(label).lower())}\b",
            lowered,
        ):
            mentions.append(str(code))
    return mentions


def _postprocess_project_open_plan(*, nl_query: str, parsed: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(parsed)
    mentions = _language_mentions_in_text(nl_query)
    if mentions:
        normalized["text_language"] = mentions[0]
    title = str(normalized.get("title") or "").strip()
    lowered = title.lower()
    if "project" in lowered and (len(title.split()) <= 3 or mentions):
        normalized["title"] = ""
    return normalized


def _normalize_language_filter(raw: str) -> str:
    value = (raw or "").strip().lower()
    if not value:
        return ""
    by_label = {label.lower(): code for code, label in ProjectForm.LANGUAGE_CHOICES}
    return by_label.get(value, value)


def _normalize_date_posted_filter(raw: str) -> str:
    value = (raw or "").strip().lower()
    if not value:
        return "any"
    if value in CONTENT_DATE_FILTERS:
        return value
    return CONTENT_DATE_ALIASES.get(value, "any")


def _normalize_cefr_level_expression(raw: str, *, max_levels: int = 3) -> str:
    value = (raw or "").strip().upper()
    if not value:
        return ""
    aliases = {
        "BEGINNER": "A1/A2",
        "ELEMENTARY": "A1/A2",
        "INTERMEDIATE": "B1/B2",
        "UPPER INTERMEDIATE": "B2/C1",
        "ADVANCED": "C1/C2",
    }
    if value in aliases:
        value = aliases[value]
    tokens = re.findall(r"[ABC][12]", value.replace("-", "/"))
    if not tokens:
        return ""
    deduped: list[str] = []
    for token in tokens:
        if token in CEFR_LEVEL_ORDER and token not in deduped:
            deduped.append(token)
    if not deduped:
        return ""
    indices = sorted(CEFR_LEVEL_ORDER.index(token) for token in deduped[:max_levels])
    return "/".join(CEFR_LEVEL_ORDER[idx] for idx in indices)


def _cefr_overlap(project_level: str, requested_level: str) -> bool:
    project_levels = set(_normalize_cefr_level_expression(project_level, max_levels=2).split("/")) - {""}
    requested_levels = set(_normalize_cefr_level_expression(requested_level, max_levels=3).split("/")) - {""}
    if not requested_levels:
        return False
    return bool(project_levels.intersection(requested_levels))


def _profile_memory_payload_for_nl(*, nl_query: str, nl_plan: dict[str, Any]) -> dict[str, Any]:
    compact_plan = {
        "title": str(nl_plan.get("title") or "").strip(),
        "text_language": str(nl_plan.get("text_language") or "").strip(),
        "annotation_language": str(nl_plan.get("annotation_language") or "").strip(),
        "date_posted": str(nl_plan.get("date_posted") or "").strip(),
        "level": str(nl_plan.get("level") or "").strip(),
        "keywords": [str(k).strip() for k in (nl_plan.get("keywords") or []) if str(k).strip()][:8],
    }
    return {
        "last_nl_query": (nl_query or "").strip()[:500],
        "last_nl_plan": compact_plan,
        "updated_at": django_timezone.now().isoformat(),
    }


def _profile_memory_section(profile: Profile, section: str) -> dict[str, Any]:
    memory = profile.dialogue_memory if isinstance(profile.dialogue_memory, dict) else {}
    payload = memory.get(section) or {}
    return payload if isinstance(payload, dict) else {}


def _update_profile_memory_section(profile: Profile, section: str, payload: dict[str, Any]) -> None:
    memory = profile.dialogue_memory if isinstance(profile.dialogue_memory, dict) else {}
    merged = dict(memory)
    merged[section] = dict(payload)
    profile.dialogue_memory = merged
    profile.save(update_fields=["dialogue_memory", "updated_at"])


@login_required
def content_list(request: HttpRequest) -> HttpResponse:
    """Search/browse published projects, with optional natural-language discovery."""

    manual_title = (request.GET.get("title") or "").strip()
    manual_text_language = _normalize_language_filter(request.GET.get("text_language") or "")
    manual_annotation_language = _normalize_language_filter(request.GET.get("annotation_language") or "")
    manual_date_posted = _normalize_date_posted_filter(request.GET.get("date_posted") or "any")

    nl_query = (request.GET.get("nl_query") or "").strip()
    dialogue_language = (request.GET.get("dialogue_language") or "").strip()
    if not dialogue_language:
        try:
            dialogue_language = request.user.profile.dialogue_language or "en"
        except Exception:
            dialogue_language = "en"

    nl_plan: dict[str, Any] = {}
    if nl_query:
        profile_obj: Profile | None = None
        try:
            profile_obj = request.user.profile
        except Exception:
            profile_obj = None
        prev_query = str(request.session.get("content_nl_last_query") or "")
        prev_plan = request.session.get("content_nl_last_plan") or {}
        if (
            profile_obj
            and profile_obj.dialogue_memory_enabled
            and isinstance(profile_obj.dialogue_memory, dict)
        ):
            section_payload = _profile_memory_section(profile_obj, "content_search")
            mem_prev_query = str(section_payload.get("last_nl_query") or "")
            mem_prev_plan = section_payload.get("last_nl_plan") or {}
            if mem_prev_query:
                prev_query = mem_prev_query
            if isinstance(mem_prev_plan, dict) and mem_prev_plan:
                prev_plan = mem_prev_plan
        if not isinstance(prev_plan, dict):
            prev_plan = {}
        nl_plan = _parse_nl_content_request(
            nl_query=nl_query,
            dialogue_language=dialogue_language,
            previous_query=prev_query,
            previous_plan=prev_plan,
        )
        request.session["content_nl_last_query"] = nl_query
        request.session["content_nl_last_plan"] = nl_plan
        if profile_obj and profile_obj.dialogue_memory_enabled:
            _update_profile_memory_section(
                profile_obj,
                "content_search",
                _profile_memory_payload_for_nl(
                nl_query=nl_query,
                nl_plan=nl_plan,
                ),
            )

    if nl_query:
        title = str(nl_plan.get("title") or "").strip()
        text_language = _normalize_language_filter(str(nl_plan.get("text_language") or ""))
        annotation_language = _normalize_language_filter(str(nl_plan.get("annotation_language") or ""))
        date_posted = _normalize_date_posted_filter(str(nl_plan.get("date_posted") or "any"))
    else:
        title = manual_title
        text_language = manual_text_language
        annotation_language = manual_annotation_language
        date_posted = manual_date_posted

    qs = _published_projects_visible_to_user(request.user)
    title_hard_filter = manual_title if nl_query else title
    if title_hard_filter:
        qs = qs.filter(title__icontains=title_hard_filter)
    if text_language:
        qs = qs.filter(language__iexact=text_language)
    if annotation_language:
        qs = qs.filter(target_language__iexact=annotation_language)

    window = CONTENT_DATE_FILTERS.get(date_posted)
    if window is not None:
        cutoff = django_timezone.now() - window
        qs = qs.filter(published_at__gte=cutoff)

    projects = list(qs.order_by("-published_at", "-updated_at")[:300])
    if text_language:
        projects = [p for p in projects if (p.language or "").lower().startswith(text_language)]
    if annotation_language:
        projects = [p for p in projects if (p.target_language or "").lower().startswith(annotation_language)]
    result_rows: list[dict[str, Any]] = []
    if nl_query:
        requested_keywords = [str(k).strip().lower() for k in (nl_plan.get("keywords") or []) if str(k).strip()]
        requested_level = _normalize_cefr_level_expression(str(nl_plan.get("level") or "").strip(), max_levels=3)
        scored: list[tuple[int, list[str], Project]] = []
        for project in projects:
            score = 0
            reasons: list[str] = []
            searchable = " ".join(
                [
                    project.title or "",
                    project.discovery_summary or "",
                    " ".join(project.discovery_keywords or []),
                    " ".join(project.discovery_keywords_en or []),
                ]
            ).lower()
            for kw in requested_keywords:
                if kw and kw in searchable:
                    score += 2
                    reasons.append(f"Keyword '{kw}' matched metadata keywords.")
            if requested_level and _cefr_overlap(project.discovery_level or "", requested_level):
                score += 3
                reasons.append(f"Level matched ({project.discovery_level}).")
            if not reasons and (manual_title or manual_text_language or manual_annotation_language):
                reasons.append("Matched structured filters.")
            scored.append((score, reasons, project))

        scored.sort(key=lambda tup: (tup[0], tup[2].published_at or tup[2].updated_at), reverse=True)
        max_results = max(1, min(50, int(nl_plan.get("max_results") or 12)))
        for score, reasons, project in scored[:max_results]:
            if score == 0 and (requested_keywords or requested_level or title):
                continue
            result_rows.append({"project": project, "score": score, "reasons": reasons[:3]})
    else:
        result_rows = [{"project": p, "score": 0, "reasons": []} for p in projects[:200]]

    return render(
        request,
        "projects/content_list.html",
        {
            "projects": [row["project"] for row in result_rows],
            "result_rows": result_rows,
            "filters": {
                "title": title,
                "text_language": text_language,
                "annotation_language": annotation_language,
                "date_posted": date_posted,
                "nl_query": nl_query,
                "dialogue_language": dialogue_language,
            },
            "nl_plan": nl_plan,
            "dialogue_language_choices": ProjectForm.LANGUAGE_CHOICES,
            "language_choices": ProjectForm.LANGUAGE_CHOICES,
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

    project = get_object_or_404(_published_projects_visible_to_user(request.user), pk=pk)
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
def community_home(request: HttpRequest) -> HttpResponse:
    memberships = list(
        CommunityMembership.objects.filter(user=request.user, community__is_active=True)
        .select_related("community")
        .order_by("community__name")
    )
    if not memberships:
        raise Http404()
    if len(memberships) == 1:
        return redirect("community-member-home", community_id=memberships[0].community_id)
    return render(request, "projects/community_home.html", {"memberships": memberships})


def _require_community_member(community_id: int, user):
    membership = (
        CommunityMembership.objects.filter(community_id=community_id, community__is_active=True, user=user)
        .select_related("community")
        .first()
    )
    if not membership:
        raise Http404()
    return membership


@login_required
def community_member_home(request: HttpRequest, community_id: int) -> HttpResponse:
    membership = _require_community_member(community_id, request.user)
    projects = list(
        Project.objects.filter(community_id=community_id).order_by("-updated_at")
    )
    judged_by_project = {
        row["project_id"]: row["count"]
        for row in CommunityImageVote.objects.filter(community_id=community_id, user=request.user)
        .values("project_id")
        .annotate(count=Count("id"))
    }
    project_rows = [
        {"project": project, "judged_count": judged_by_project.get(project.id, 0)} for project in projects
    ]
    return render(
        request,
        "projects/community_member_home.html",
        {
            "community": membership.community,
            "membership": membership,
            "project_rows": project_rows,
        },
    )


@login_required
def community_member_judge_project(request: HttpRequest, community_id: int, project_id: int) -> HttpResponse:
    membership = _require_community_member(community_id, request.user)
    project = get_object_or_404(Project, pk=project_id, community_id=community_id)
    pages = list(ProjectImagePage.objects.filter(project=project).order_by("page_number").prefetch_related("variants"))
    if request.method == "POST":
        saved = 0
        for page in pages:
            for variant in page.variants.all():
                value = (request.POST.get(f"vote_{variant.id}") or "").strip().lower()
                note = (request.POST.get(f"note_{variant.id}") or "").strip()
                if value not in {CommunityImageVote.VALUE_UP, CommunityImageVote.VALUE_DOWN}:
                    continue
                CommunityImageVote.objects.update_or_create(
                    community_id=community_id,
                    project=project,
                    page=page,
                    variant=variant,
                    user=request.user,
                    defaults={"value": value, "note": note},
                )
                saved += 1
        messages.success(request, f"Saved {saved} image judgement(s).")
        return redirect("community-member-judge-project", community_id=community_id, project_id=project.id)

    existing_votes = {
        vote.variant_id: vote
        for vote in CommunityImageVote.objects.filter(community_id=community_id, project=project, user=request.user)
    }
    page_rows = [
        {
            "page": page,
            "variant_rows": [{"variant": variant, "vote": existing_votes.get(variant.id)} for variant in page.variants.all()],
        }
        for page in pages
    ]
    return render(
        request,
        "projects/community_member_judge_project.html",
        {
            "community": membership.community,
            "membership": membership,
            "project": project,
            "page_rows": page_rows,
        },
    )


@login_required
def community_organiser_home(request: HttpRequest, community_id: int) -> HttpResponse:
    membership = _require_community_member(community_id, request.user)
    if membership.role != CommunityMembership.ROLE_ORGANISER:
        raise Http404()
    community = membership.community
    projects = list(Project.objects.filter(community_id=community_id).order_by("-updated_at"))
    picture_dictionary = (
        PictureDictionary.objects.select_related("project")
        .filter(community_id=community_id, is_active=True)
        .first()
    )
    dictionary_entries = list(
        picture_dictionary.entries.filter(is_active=True).order_by("id") if picture_dictionary else []
    )
    picture_dictionary_compile_info: dict[str, Any] | None = None
    picture_dictionary_style_brief = ""
    if picture_dictionary:
        style = getattr(picture_dictionary.project, "image_style", None)
        picture_dictionary_style_brief = ((style.style_brief or "").strip() if style else "")
        seg1_path = picture_dictionary.project.artifact_dir() / "runs" / "run_picture_dictionary" / "stages" / "segmentation_phase_1.json"
        if seg1_path.exists():
            try:
                payload = json.loads(seg1_path.read_text(encoding="utf-8"))
            except Exception:
                payload = {}
            picture_dictionary_compile_info = {
                "updated_at": datetime.fromtimestamp(seg1_path.stat().st_mtime, tz=timezone.utc).isoformat(),
                "entry_count": int(((payload.get("metadata") or {}).get("entry_count") or 0)),
            }

    if request.method == "POST":
        action = (request.POST.get("picture_dictionary_action") or "").strip()
        if action:
            try:
                picture_dictionary = ensure_picture_dictionary_for_community(
                    community=community,
                    organiser=request.user,
                )
            except PermissionDenied:
                raise Http404()

            words_raw = str(request.POST.get("picture_dictionary_words") or "")
            words = [word.strip() for word in re.split(r"[,\n]", words_raw) if word.strip()]

            if action == "ensure":
                messages.success(request, "Picture dictionary is ready.")
            elif action == "compile":
                compile_updates: list[str] = []

                def _record_compile_update(message: str) -> None:
                    compile_updates.append(message)

                style = getattr(picture_dictionary.project, "image_style", None)
                style_usable = bool(
                    style
                    and (
                        (style.style_brief or "").strip()
                        or (style.expanded_style_description or "").strip()
                    )
                    and style.status in {ProjectImageStyle.STATUS_GENERATED, ProjectImageStyle.STATUS_APPROVED}
                )
                if not style_usable:
                    style_brief = (request.POST.get("picture_dictionary_style_brief") or "").strip()
                    if not style_brief:
                        messages.error(
                            request,
                            "Style is missing. Enter a style brief and compile again.",
                        )
                        return redirect("community-organiser-home", community_id=community_id)
                    style, _ = ProjectImageStyle.objects.get_or_create(
                        project=picture_dictionary.project,
                        defaults={"ai_model": picture_dictionary.project.ai_model or DEFAULT_MODEL},
                    )
                    style.style_brief = style_brief
                    try:
                        generated = _generate_project_image_style(
                            picture_dictionary.project,
                            style_brief,
                            ai_model=style.ai_model or picture_dictionary.project.ai_model or DEFAULT_MODEL,
                        )
                    except Exception as exc:
                        logger.exception(
                            "Failed to generate fallback style for picture dictionary compile on project %s",
                            picture_dictionary.project_id,
                        )
                        messages.error(
                            request,
                            f"Could not generate style from brief: {exc}",
                        )
                        return redirect("community-organiser-home", community_id=community_id)
                    style.expanded_style_description = generated.get("expanded_style_description", "")
                    style.representative_excerpt = generated.get("representative_excerpt", "")
                    style.sample_image_prompt = generated.get("sample_image_prompt", "")
                    style.status = ProjectImageStyle.STATUS_GENERATED
                    style.save()
                    _persist_image_style_artifacts(
                        picture_dictionary.project,
                        style,
                        request_payload=generated.get("_request_payload"),
                        response_payload=generated.get("_response_payload"),
                    )
                    messages.success(request, "Created dictionary image style from the provided style brief.")
                report_id = str(uuid.uuid4())
                async_task(
                    _run_picture_dictionary_compile_task,
                    picture_dictionary.id,
                    request.user.id,
                    report_id,
                    q_options={"sync": False},
                )
                messages.info(request, "Picture dictionary compilation started. Opening live status monitor.")
                monitor_url = reverse("project-compile-monitor", args=[picture_dictionary.project.id, report_id])
                return_to = reverse("community-organiser-home", args=[community_id])
                return redirect(f"{monitor_url}?next={quote(return_to, safe='/')}")
            elif action == "add":
                added = picture_dictionary_add_words(dictionary=picture_dictionary, words=words)
                messages.success(request, f"Added {added} word(s) to picture dictionary.")
            elif action == "remove":
                removed = picture_dictionary_remove_words(dictionary=picture_dictionary, words=words)
                messages.success(request, f"Removed {removed} word(s) from picture dictionary.")
            elif action == "remove_selected":
                selected_ids = [int(value) for value in request.POST.getlist("remove_entry") if str(value).isdigit()]
                removed = picture_dictionary_remove_entries_by_ids(
                    dictionary=picture_dictionary,
                    entry_ids=selected_ids,
                )
                messages.success(request, f"Removed {removed} selected dictionary entr{'y' if removed == 1 else 'ies'}.")
            elif action == "add_from_text":
                source_project_id_raw = (request.POST.get("source_project_id") or "").strip()
                try:
                    source_project_id = int(source_project_id_raw)
                except ValueError:
                    source_project_id = 0
                source_project = next((row for row in projects if row.id == source_project_id), None)
                if not source_project:
                    messages.error(request, "Please choose a valid community project for add-from-text.")
                else:
                    lemma_run = _find_run_with_stage(source_project, "lemma")
                    lemma_payload = _load_stage_payload(source_project, "lemma", run_dir=lemma_run) if lemma_run else None
                    if not lemma_payload:
                        messages.error(
                            request,
                            "Add from text requires lemma annotations. Run the source project through the lemma stage first.",
                        )
                        return redirect("community-organiser-home", community_id=community_id)
                    lemma_pos_pairs: list[tuple[str, str]] = []
                    seen_pairs: set[tuple[str, str]] = set()
                    for page in lemma_payload.get("pages") or []:
                        for segment in page.get("segments") or []:
                            for token in segment.get("tokens") or []:
                                ann = token.get("annotations") or {}
                                lemma = str(ann.get("lemma") or "").strip()
                                pos = str(ann.get("pos") or "").strip().upper()
                                if not lemma:
                                    continue
                                key = (lemma.casefold(), pos)
                                if key in seen_pairs:
                                    continue
                                seen_pairs.add(key)
                                lemma_pos_pairs.append((lemma, pos))
                    added = picture_dictionary_add_lemma_pos_entries(
                        dictionary=picture_dictionary,
                        lemma_pos_pairs=lemma_pos_pairs,
                    )
                    messages.success(
                        request,
                        f"Added {added} lemma/POS entr{'y' if added == 1 else 'ies'} from project “{source_project.title}”.",
                    )
            else:
                messages.error(request, f"Unknown picture dictionary action: {action}")
            return redirect("community-organiser-home", community_id=community_id)

    review_by_project = {
        row.project_id: row
        for row in CommunityOrganiserReview.objects.filter(
            community_id=community_id,
            organiser=request.user,
        )
    }
    summary_rows: list[dict[str, Any]] = []
    for project in projects:
        latest_vote = (
            CommunityImageVote.objects.filter(community_id=community_id, project=project)
            .order_by("-updated_at")
            .first()
        )
        review = review_by_project.get(project.id)
        up_to_date = bool(review and (latest_vote is None or review.updated_at >= latest_vote.updated_at))
        summary_rows.append(
            {"project": project, "review": review, "latest_vote": latest_vote, "up_to_date": up_to_date}
        )
    return render(
        request,
        "projects/community_organiser_home.html",
        {
            "community": community,
            "membership": membership,
            "summary_rows": summary_rows,
            "picture_dictionary": picture_dictionary,
            "dictionary_entries": dictionary_entries,
            "picture_dictionary_compile_info": picture_dictionary_compile_info,
            "picture_dictionary_style_brief": picture_dictionary_style_brief,
            "community_projects": projects,
        },
    )


@login_required
def community_organiser_review_project(request: HttpRequest, community_id: int, project_id: int) -> HttpResponse:
    membership = _require_community_member(community_id, request.user)
    if membership.role != CommunityMembership.ROLE_ORGANISER:
        raise Http404()
    project = get_object_or_404(Project, pk=project_id, community_id=community_id)
    pages = list(ProjectImagePage.objects.filter(project=project).order_by("page_number").prefetch_related("variants"))

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        if action == "mark_reviewed":
            note = (request.POST.get("review_note") or "").strip()
            CommunityOrganiserReview.objects.update_or_create(
                community_id=community_id,
                project=project,
                organiser=request.user,
                defaults={"note": note},
            )
            messages.success(request, "Marked review as up to date.")
            return redirect("community-organiser-review-project", community_id=community_id, project_id=project.id)
        if action == "generate_requested":
            requested: list[tuple[ProjectImagePage, int, str]] = []
            image_model = (request.POST.get("image_model") or "gpt-image-1").strip()
            if image_model not in IMAGE_MODEL_CHOICES:
                image_model = "gpt-image-1"
            for page in pages:
                count_raw = (request.POST.get(f"request_count_{page.id}") or "").strip()
                prompt_update = (request.POST.get(f"request_prompt_{page.id}") or "").strip()
                try:
                    count = int(count_raw or "0")
                except ValueError:
                    count = 0
                count = max(0, min(8, count))
                if count <= 0:
                    continue
                base_prompt = page.generation_prompt or page.page_text
                final_prompt = f"{base_prompt}\n\nCommunity organiser request: {prompt_update}" if prompt_update else base_prompt
                requested.append((page, count, final_prompt))
            if not requested:
                messages.info(request, "No generation requests were specified.")
                return redirect("community-organiser-review-project", community_id=community_id, project_id=project.id)
            requested_count = sum(count for _page, count, _prompt in requested)
            messages.info(request, f"Generating {requested_count} requested variant(s). Please wait…")
            generated = _generate_requested_page_variants(project=project, image_model=image_model, requests=requested)
            _persist_image_pages_artifacts(project)
            messages.success(request, f"Generated {generated} new variant(s) from organiser requests.")
            return redirect("community-organiser-review-project", community_id=community_id, project_id=project.id)

    vote_rows: list[dict[str, Any]] = []
    for page in pages:
        for variant in page.variants.order_by("variant_index"):
            votes = list(
                CommunityImageVote.objects.filter(community_id=community_id, project=project, variant=variant)
                .select_related("user")
                .order_by("-updated_at")
            )
            up = sum(1 for vote in votes if vote.value == CommunityImageVote.VALUE_UP)
            down = sum(1 for vote in votes if vote.value == CommunityImageVote.VALUE_DOWN)
            vote_rows.append({"page": page, "variant": variant, "votes": votes, "up": up, "down": down})
    review = CommunityOrganiserReview.objects.filter(
        community_id=community_id, project=project, organiser=request.user
    ).first()
    return render(
        request,
        "projects/community_organiser_review_project.html",
        {
            "community": membership.community,
            "membership": membership,
            "project": project,
            "pages": pages,
            "vote_rows": vote_rows,
            "review": review,
            "image_models": IMAGE_MODEL_CHOICES,
        },
    )

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
    return_url = request.GET.get("next") or reverse("project-detail", args=[project.pk])
    return render(
        request,
        "projects/compile_monitor.html",
        {"project": project, "report_id": report_id, "return_url": return_url},
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
    """Search/browse published projects, with optional natural-language discovery."""

    manual_title = (request.GET.get("title") or "").strip()
    manual_text_language = _normalize_language_filter(request.GET.get("text_language") or "")
    manual_annotation_language = _normalize_language_filter(request.GET.get("annotation_language") or "")
    manual_date_posted = _normalize_date_posted_filter(request.GET.get("date_posted") or "any")

    nl_query = (request.GET.get("nl_query") or "").strip()
    dialogue_language = (request.GET.get("dialogue_language") or "").strip()
    if not dialogue_language:
        try:
            dialogue_language = request.user.profile.dialogue_language or "en"
        except Exception:
            dialogue_language = "en"

    nl_plan: dict[str, Any] = {}
    if nl_query:
        profile_obj: Profile | None = None
        try:
            profile_obj = request.user.profile
        except Exception:
            profile_obj = None
        prev_query = str(request.session.get("content_nl_last_query") or "")
        prev_plan = request.session.get("content_nl_last_plan") or {}
        if (
            profile_obj
            and profile_obj.dialogue_memory_enabled
            and isinstance(profile_obj.dialogue_memory, dict)
        ):
            section_payload = _profile_memory_section(profile_obj, "content_search")
            mem_prev_query = str(section_payload.get("last_nl_query") or "")
            mem_prev_plan = section_payload.get("last_nl_plan") or {}
            if mem_prev_query:
                prev_query = mem_prev_query
            if isinstance(mem_prev_plan, dict) and mem_prev_plan:
                prev_plan = mem_prev_plan
        if not isinstance(prev_plan, dict):
            prev_plan = {}
        nl_plan = _parse_nl_content_request(
            nl_query=nl_query,
            dialogue_language=dialogue_language,
            previous_query=prev_query,
            previous_plan=prev_plan,
        )
        request.session["content_nl_last_query"] = nl_query
        request.session["content_nl_last_plan"] = nl_plan
        if profile_obj and profile_obj.dialogue_memory_enabled:
            _update_profile_memory_section(
                profile_obj,
                "content_search",
                _profile_memory_payload_for_nl(
                nl_query=nl_query,
                nl_plan=nl_plan,
                ),
            )

    if nl_query:
        title = str(nl_plan.get("title") or "").strip()
        text_language = _normalize_language_filter(str(nl_plan.get("text_language") or ""))
        annotation_language = _normalize_language_filter(str(nl_plan.get("annotation_language") or ""))
        date_posted = _normalize_date_posted_filter(str(nl_plan.get("date_posted") or "any"))
    else:
        title = manual_title
        text_language = manual_text_language
        annotation_language = manual_annotation_language
        date_posted = manual_date_posted

    qs = _published_projects_visible_to_user(request.user)
    title_hard_filter = manual_title if nl_query else title
    if title_hard_filter:
        qs = qs.filter(title__icontains=title_hard_filter)
    if text_language:
        qs = qs.filter(language__iexact=text_language)
    if annotation_language:
        qs = qs.filter(target_language__iexact=annotation_language)

    window = CONTENT_DATE_FILTERS.get(date_posted)
    if window is not None:
        cutoff = django_timezone.now() - window
        qs = qs.filter(published_at__gte=cutoff)

    projects = list(qs.order_by("-published_at", "-updated_at")[:300])
    if text_language:
        projects = [p for p in projects if (p.language or "").lower().startswith(text_language)]
    if annotation_language:
        projects = [p for p in projects if (p.target_language or "").lower().startswith(annotation_language)]
    result_rows: list[dict[str, Any]] = []
    if nl_query:
        requested_keywords = [str(k).strip().lower() for k in (nl_plan.get("keywords") or []) if str(k).strip()]
        requested_level = _normalize_cefr_level_expression(str(nl_plan.get("level") or "").strip(), max_levels=3)
        scored: list[tuple[int, list[str], Project]] = []
        for project in projects:
            score = 0
            reasons: list[str] = []
            searchable = " ".join(
                [
                    project.title or "",
                    project.discovery_summary or "",
                    " ".join(project.discovery_keywords or []),
                    " ".join(project.discovery_keywords_en or []),
                ]
            ).lower()
            for kw in requested_keywords:
                if kw and kw in searchable:
                    score += 2
                    reasons.append(f"Keyword '{kw}' matched metadata keywords.")
            if requested_level and _cefr_overlap(project.discovery_level or "", requested_level):
                score += 3
                reasons.append(f"Level matched ({project.discovery_level}).")
            if not reasons and (manual_title or manual_text_language or manual_annotation_language):
                reasons.append("Matched structured filters.")
            scored.append((score, reasons, project))

        scored.sort(key=lambda tup: (tup[0], tup[2].published_at or tup[2].updated_at), reverse=True)
        max_results = max(1, min(50, int(nl_plan.get("max_results") or 12)))
        for score, reasons, project in scored[:max_results]:
            if score == 0 and (requested_keywords or requested_level or title):
                continue
            result_rows.append({"project": project, "score": score, "reasons": reasons[:3]})
    else:
        result_rows = [{"project": p, "score": 0, "reasons": []} for p in projects[:200]]

    return render(
        request,
        "projects/content_list.html",
        {
            "projects": [row["project"] for row in result_rows],
            "result_rows": result_rows,
            "filters": {
                "title": title,
                "text_language": text_language,
                "annotation_language": annotation_language,
                "date_posted": date_posted,
                "nl_query": nl_query,
                "dialogue_language": dialogue_language,
            },
            "nl_plan": nl_plan,
            "dialogue_language_choices": ProjectForm.LANGUAGE_CHOICES,
            "language_choices": ProjectForm.LANGUAGE_CHOICES,
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

    project = get_object_or_404(_published_projects_visible_to_user(request.user), pk=pk)
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
    metadata_updated = False
    if project.is_published:
        metadata_updated = update_project_discovery_metadata(project, force=False)
    state = "published" if project.is_published else "unpublished"
    if metadata_updated:
        messages.info(request, f"Project {state}. Discovery metadata generated.")
    else:
        messages.info(request, f"Project {state}.")
    return redirect("project-detail", pk=project.pk)


@login_required
def set_project_discovery_metadata(request: HttpRequest, pk: int) -> HttpResponse:
    project = _get_project_for_user(pk=pk, user=request.user, min_role=ProjectCollaborator.ROLE_OWNER)
    if request.method != "POST":
        return redirect("project-detail", pk=project.pk)
    action = (request.POST.get("action") or "save").strip().lower()
    if action == "regenerate":
        update_project_discovery_metadata(project, force=True)
        messages.success(request, "Regenerated discovery metadata.")
        return redirect("project-detail", pk=project.pk)
    form = ProjectDiscoveryMetadataForm(request.POST, instance=project)
    if form.is_valid():
        updated = form.save(commit=False)
        updated.discovery_level = _normalize_cefr_level_expression(updated.discovery_level or "", max_levels=2)
        updated.discovery_metadata_updated_at = django_timezone.now()
        updated.save(update_fields=["discovery_summary", "discovery_keywords", "discovery_keywords_en", "discovery_level", "discovery_word_count", "discovery_metadata_updated_at", "updated_at"])
        messages.success(request, "Saved discovery metadata.")
    else:
        messages.error(request, "Could not save discovery metadata. Please review the fields.")
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
    flashcard_mode: str,
) -> dict[str, Any]:
    source_word = candidate["source_word"]
    correct_gloss = candidate["target_gloss"]
    segment_text = candidate["segment_text"]
    if flashcard_mode == "meaning_to_form":
        prompt = f"""
Create exactly 3 WRONG distractor source-language words for a flashcard multiple-choice item.
Theme: {theme}
Gloss-language prompt: {correct_gloss}
Correct source-language answer: {source_word}
Segment context: {segment_text}
Hard constraints:
- Every distractor must be incorrect for this prompt.
- Do NOT return the correct answer.
- Do NOT return close variants/spellings/morphological forms of the answer.
- Do NOT return the gloss-language word.
Return JSON with:
- distractors: array of 3 strings
- rationale: object mapping each distractor to a short reason it is clearly wrong
"""
    else:
        prompt = f"""
Create exactly 3 WRONG distractor glosses/translations for a flashcard multiple-choice item.
Theme: {theme}
Source word: {source_word}
Correct gloss: {correct_gloss}
Segment context: {segment_text}
Hard constraints:
- Every distractor must be incorrect for this source word in this context.
- Do NOT return the source word itself.
- Do NOT return the correct gloss.
- Do NOT return close variants/spellings/morphological forms of the correct gloss.
Return JSON with:
- distractors: array of 3 strings
- rationale: object mapping each distractor to a short reason it is clearly wrong
"""
    try:
        data = await client.chat_json(prompt, model=model)
    except Exception:
        data = {}
    distractors = [str(x).strip() for x in (data.get("distractors") or []) if str(x).strip()]
    if flashcard_mode == "meaning_to_form":
        distractors = [
            d
            for d in distractors
            if d.lower() != source_word.lower() and d.lower() != correct_gloss.lower()
        ]
    else:
        distractors = [
            d
            for d in distractors
            if d.lower() != correct_gloss.lower() and d.lower() != source_word.lower()
        ]
    distractors = distractors[:3]
    while len(distractors) < 3:
        filler_base = source_word if flashcard_mode == "meaning_to_form" else correct_gloss
        distractors.append(f"{filler_base}_{len(distractors)+1}")

    answer = source_word if flashcard_mode == "meaning_to_form" else correct_gloss
    prompt_text = (
        f"What is the best source-language word for: {correct_gloss}?"
        if flashcard_mode == "meaning_to_form"
        else f"What is the best gloss/translation for: {source_word}?"
    )
    options = [answer] + distractors
    random.Random(f"{source_word}|{correct_gloss}|{order_index}|{flashcard_mode}").shuffle(options)
    if options and options[0] == answer and len(options) > 1:
        options[0], options[1] = options[1], options[0]
    return {
        "order_index": order_index,
        "page_number": candidate["page_number"],
        "segment_index": candidate["segment_index"],
        "segment_text": segment_text,
        "prompt": prompt_text,
        "answer": answer,
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
                client = _build_billed_project_ai_client(
                    project,
                    model_name=model,
                    request_type="exercise_cloze_generation",
                )
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
            flashcard_mode = form.cleaned_data["flashcard_mode"]
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
                flashcard_mode=flashcard_mode,
                theme=theme,
                title=f"{project.title} — Flashcards ({flashcard_mode}, {theme})",
                status=ExerciseSet.STATUS_DRAFT,
                created_by=request.user,
            )

            async def _run() -> list[dict[str, Any]]:
                client = _build_billed_project_ai_client(
                    project,
                    model_name=model,
                    request_type="exercise_flashcard_generation",
                )
                tasks = [
                    _generate_flashcard_item(client, model, theme, cand, idx, flashcard_mode)
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
    page_variants = list(
        ProjectImagePageVariant.objects.filter(page__project=project)
        .order_by("page__page_number", "variant_index", "id")
        .values()
    )

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
    for row in page_variants:
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
            "text_direction": language_direction(project.language),
            "target_language": project.target_language,
            "annotation_direction": language_direction(project.target_language),
            "ai_model": project.ai_model,
            "page_image_placement": project.page_image_placement,
            "image_generation_pivot_language": project.image_generation_pivot_language,
            "page_image_text_source": project.page_image_text_source,
            "segmentation_method": project.segmentation_method,
            "romanization_method": project.romanization_method,
        }
        zf.writestr((bundle_root / "project" / "metadata.json").as_posix(), json.dumps(metadata, ensure_ascii=False, indent=2))

        pipeline_config = {
            "ai_model": project.ai_model,
            "segmentation_method": project.segmentation_method,
            "romanization_method": project.romanization_method,
            "page_image_placement": project.page_image_placement,
            "image_generation_pivot_language": project.image_generation_pivot_language,
            "page_image_text_source": project.page_image_text_source,
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
        zf.writestr(
            (bundle_root / "images" / "elements.json").as_posix(),
            json.dumps(elements, ensure_ascii=False, indent=2, default=str),
        )
        zf.writestr(
            (bundle_root / "images" / "pages.json").as_posix(),
            json.dumps(pages, ensure_ascii=False, indent=2, default=str),
        )
        zf.writestr(
            (bundle_root / "images" / "page_variants.json").as_posix(),
            json.dumps(page_variants, ensure_ascii=False, indent=2, default=str),
        )

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
        valid_pivot_languages = {code for code, _label in ProjectForm.LANGUAGE_CHOICES}
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
            image_generation_pivot_language=(
                (metadata.get("image_generation_pivot_language") or "")
                if (metadata.get("image_generation_pivot_language") or "") in valid_pivot_languages
                else ""
            )[:16],
            page_image_text_source=(
                metadata.get("page_image_text_source")
                if metadata.get("page_image_text_source") in {c[0] for c in Project.PAGE_IMAGE_TEXT_SOURCE_CHOICES}
                else Project.PAGE_IMAGE_TEXT_SOURCE_SEGMENTATION
            )[:32],
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
        page_pk_map: dict[int, int] = {}
        if isinstance(pages_payload, list):
            for row in pages_payload:
                if not isinstance(row, dict):
                    continue
                page_num = row.get("page_number")
                if not isinstance(page_num, int):
                    continue
                page_obj, _ = ProjectImagePage.objects.update_or_create(
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
                raw_id = row.get("id")
                if isinstance(raw_id, int):
                    page_pk_map[raw_id] = page_obj.pk

        variants_payload = _safe_zip_read_json(zf, f"{root}/images/page_variants.json")
        variant_pk_map: dict[int, int] = {}
        if isinstance(variants_payload, list):
            for row in variants_payload:
                if not isinstance(row, dict):
                    continue
                source_page_id = row.get("page_id")
                variant_index = row.get("variant_index")
                if not isinstance(source_page_id, int) or not isinstance(variant_index, int):
                    continue
                target_page_id = page_pk_map.get(source_page_id)
                if not target_page_id:
                    continue
                variant_obj, _ = ProjectImagePageVariant.objects.update_or_create(
                    page_id=target_page_id,
                    variant_index=variant_index,
                    defaults={
                        "image_model": (row.get("image_model") or "gpt-image-1")[:64],
                        "image_path": (row.get("image_path") or "")[:512],
                        "generation_prompt": row.get("generation_prompt") or "",
                        "image_revised_prompt": row.get("image_revised_prompt") or "",
                        "status": (row.get("status") or ProjectImagePageVariant.STATUS_DRAFT)[:32],
                    },
                )
                raw_variant_id = row.get("id")
                if isinstance(raw_variant_id, int):
                    variant_pk_map[raw_variant_id] = variant_obj.pk
        if isinstance(pages_payload, list):
            for row in pages_payload:
                if not isinstance(row, dict):
                    continue
                source_page_id = row.get("id")
                preferred_variant_id = row.get("preferred_variant_id")
                if not isinstance(source_page_id, int) or not isinstance(preferred_variant_id, int):
                    continue
                target_page_id = page_pk_map.get(source_page_id)
                target_variant_id = variant_pk_map.get(preferred_variant_id)
                if target_page_id and target_variant_id:
                    ProjectImagePage.objects.filter(pk=target_page_id).update(preferred_variant_id=target_variant_id)

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
def set_project_community(request: HttpRequest, pk: int) -> HttpResponse:
    project = _get_project_for_user(pk=pk, user=request.user, min_role=ProjectCollaborator.ROLE_OWNER)
    if request.method != "POST":
        return redirect("project-detail", pk=project.pk)

    action = (request.POST.get("action") or "").strip()
    if action == "clear":
        project.community = None
        if project.access_scope == Project.ACCESS_COMMUNITY:
            project.access_scope = Project.ACCESS_PRIVATE
            project.save(update_fields=["community", "access_scope", "updated_at"])
        else:
            project.save(update_fields=["community", "updated_at"])
        messages.success(request, "Project is no longer assigned to a community.")
        return redirect("project-detail", pk=project.pk)

    community_id = request.POST.get("community_id")
    try:
        community_id_int = int(community_id or "")
    except ValueError:
        messages.error(request, "Unknown community.")
        return redirect("project-detail", pk=project.pk)

    community = Community.objects.filter(pk=community_id_int, is_active=True).first()
    if not community:
        messages.error(request, "Unknown community.")
        return redirect("project-detail", pk=project.pk)
    if (community.language or "").lower() != (project.language or "").lower():
        messages.error(request, "Project language must match community language.")
        return redirect("project-detail", pk=project.pk)
    role = _community_role_for_user(community, request.user)
    if role != CommunityMembership.ROLE_ORGANISER:
        messages.error(request, "You must be a community organiser to assign this project.")
        return redirect("project-detail", pk=project.pk)

    project.community = community
    project.access_scope = Project.ACCESS_COMMUNITY
    project.save(update_fields=["community", "access_scope", "updated_at"])
    messages.success(request, f"Assigned project to community {community.name}.")
    return redirect("project-detail", pk=project.pk)


def _copy_latest_run_files(source_project: Project, target_project: Project) -> int:
    latest_by_rel: dict[str, Path] = {}
    latest_mtime: dict[str, float] = {}
    for run_dir in _iter_runs(source_project):
        for path in run_dir.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(run_dir).as_posix()
            try:
                mtime = path.stat().st_mtime
            except Exception:
                continue
            if rel not in latest_by_rel or mtime > latest_mtime[rel]:
                latest_by_rel[rel] = path
                latest_mtime[rel] = mtime

    if not latest_by_rel:
        return 0

    target_run = _prepare_output_dir(target_project)
    copied = 0
    for rel, src in latest_by_rel.items():
        dest = target_run / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        copied += 1

    source_compiled = Path(source_project.compiled_path or "")
    if len(source_compiled.parts) >= 3 and source_compiled.parts[0] == "runs":
        tail = Path(*source_compiled.parts[2:])
        candidate = target_run / tail
        if candidate.exists():
            target_project.compiled_path = f"runs/{target_run.name}/{tail.as_posix()}"
            target_project.save(update_fields=["compiled_path", "updated_at"])
    return copied


def _copy_image_assets_and_rows(source_project: Project, target_project: Project) -> None:
    source_images = source_project.artifact_dir() / "images"
    target_images = target_project.artifact_dir() / "images"
    if source_images.exists():
        shutil.copytree(source_images, target_images, dirs_exist_ok=True)

    source_style = getattr(source_project, "image_style", None)
    if source_style:
        ProjectImageStyle.objects.update_or_create(
            project=target_project,
            defaults={
                "style_brief": source_style.style_brief,
                "expanded_style_description": source_style.expanded_style_description,
                "representative_excerpt": source_style.representative_excerpt,
                "sample_image_prompt": source_style.sample_image_prompt,
                "sample_image_path": source_style.sample_image_path,
                "sample_image_revised_prompt": source_style.sample_image_revised_prompt,
                "sample_image_model": source_style.sample_image_model,
                "ai_model": source_style.ai_model,
                "status": source_style.status,
            },
        )

    target_project.image_elements.all().delete()
    for element in source_project.image_elements.order_by("id"):
        ProjectImageElement.objects.create(
            project=target_project,
            name=element.name,
            element_type=element.element_type,
            page_refs=element.page_refs,
            why_consistency_matters=element.why_consistency_matters,
            expanded_description=element.expanded_description,
            expanded_prompt=element.expanded_prompt,
            image_model=element.image_model,
            image_path=element.image_path,
            image_revised_prompt=element.image_revised_prompt,
            is_confirmed=element.is_confirmed,
            ai_model=element.ai_model,
            status=element.status,
        )

    target_project.image_pages.all().delete()
    page_pk_map: dict[int, int] = {}
    for page in source_project.image_pages.order_by("page_number", "id"):
        created_page = ProjectImagePage.objects.create(
            project=target_project,
            page_number=page.page_number,
            page_text=page.page_text,
            generation_prompt=page.generation_prompt,
            image_model=page.image_model,
            image_path=page.image_path,
            image_revised_prompt=page.image_revised_prompt,
            status=page.status,
        )
        page_pk_map[page.pk] = created_page.pk
    variant_pk_map: dict[int, int] = {}
    for variant in ProjectImagePageVariant.objects.filter(page__project=source_project).order_by("page_id", "variant_index", "id"):
        target_page_id = page_pk_map.get(variant.page_id)
        if not target_page_id:
            continue
        created_variant = ProjectImagePageVariant.objects.create(
            page_id=target_page_id,
            variant_index=variant.variant_index,
            image_model=variant.image_model,
            image_path=variant.image_path,
            generation_prompt=variant.generation_prompt,
            image_revised_prompt=variant.image_revised_prompt,
            status=variant.status,
        )
        variant_pk_map[variant.pk] = created_variant.pk
    for source_page in source_project.image_pages.order_by("page_number", "id"):
        target_page_id = page_pk_map.get(source_page.pk)
        if not target_page_id:
            continue
        target_variant_id = (
            variant_pk_map.get(source_page.preferred_variant_id) if source_page.preferred_variant_id else None
        )
        if target_variant_id:
            ProjectImagePage.objects.filter(pk=target_page_id).update(preferred_variant_id=target_variant_id)


@login_required
def clone_project(request: HttpRequest, pk: int) -> HttpResponse:
    source_project = _get_project_for_user(pk=pk, user=request.user, min_role=ProjectCollaborator.ROLE_OWNER)
    if request.method != "POST":
        return redirect("project-detail", pk=source_project.pk)

    requested_title = (request.POST.get("clone_title") or "").strip()
    requested_target_language = (request.POST.get("clone_target_language") or "").strip()
    allowed_target_languages = {code for code, _label in ProjectForm.LANGUAGE_CHOICES}
    if requested_target_language and requested_target_language not in allowed_target_languages:
        messages.error(request, "Unknown glossing language for clone.")
        return redirect("project-detail", pk=source_project.pk)
    default_title = f"{source_project.title} (Clone)"
    clone_title = _build_unique_import_title(request.user, requested_title or default_title)
    clone_target_language = requested_target_language or source_project.target_language
    clone = Project.objects.create(
        owner=request.user,
        title=clone_title,
        description=source_project.description,
        source_text=source_project.source_text,
        input_mode=source_project.input_mode,
        language=source_project.language,
        target_language=clone_target_language,
        ai_model=source_project.ai_model,
        page_image_placement=source_project.page_image_placement,
        page_image_text_source=source_project.page_image_text_source,
        segmentation_method=source_project.segmentation_method,
        romanization_method=source_project.romanization_method,
    )
    _persist_project_source(clone)
    copied_files = _copy_latest_run_files(source_project, clone)
    _copy_image_assets_and_rows(source_project, clone)
    messages.success(
        request,
        f"Cloned project '{source_project.title}' to '{clone.title}' ({copied_files} run file(s) copied).",
    )
    return redirect("project-detail", pk=clone.pk)


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
