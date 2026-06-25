from __future__ import annotations

from dataclasses import asdict, replace
import getpass
import json
import sys
import logging
import os

if sys.platform == "win32":
    pwd = None
else:
    import pwd
import signal
import subprocess
import threading
import random
import shutil
import hashlib
import re
import uuid
import asyncio
import unicodedata
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.staticfiles import finders
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
from django.utils.safestring import mark_safe
from django.utils.text import slugify
from django.utils import timezone as django_timezone
import mimetypes
import tempfile
import zipfile
import urllib.error
import urllib.request
from urllib.parse import unquote
from urllib.parse import quote

from core.config import DEFAULT_MODEL, OpenAIConfig
from core.ai_api import OpenAIClient, normalize_json_text
from core.project_understanding import answer_project_understanding_question_with_codex_exec
from core.language_direction import language_direction
from pipeline.full_pipeline import FullPipelineSpec, PIPELINE_ORDER, run_full_pipeline
from pipeline.mwe import normalize_mwes
from pipeline.stage_artifacts import read_stage_artifact, stage_artifact_path, write_stage_artifact

from .forms import (
    AdminCommunityForm,
    AdminCommunityMembershipForm,
    CommunityOrganiserMembershipForm,
    AdminDeleteCommunityForm,
    AdminAdjustCreditsForm,
    AdminOpenAIPricingForm,
    ProjectUnderstandingForm,
    CreditTransferForm,
    ClozeExerciseSetForm,
    CrosswordExerciseSetForm,
    DeleteCachedWordAudioForm,
    FlashcardExerciseSetForm,
    GrantAdminPrivilegesForm,
    WordScrambleExerciseSetForm,
    ProfileForm,
    IssueSuggestionForm,
    IssueUpdateSuggestionForm,
    ProjectDiscoveryMetadataForm,
    ProjectForm,
    ProjectImageElementFormSet,
    ProjectImagePageFormSet,
    ProjectImageStyleForm,
    RegistrationForm,
)
from .metadata import update_project_discovery_metadata
from .legacy_clara_import import (
    LegacyClaraImportError,
    find_legacy_clara_bundle_root,
    import_legacy_clara_bundle,
    import_legacy_clara_project_dir_bundle,
    is_legacy_clara_project_dir_bundle,
    legacy_clara_bundle_title,
    legacy_clara_project_dir_bundle_title,
)
from .billing import (
    apply_credit_delta,
    credits_enabled,
    get_user_balance_usd,
    has_minimum_balance_for_compile,
    minimum_compile_balance_usd,
    openai_price_for_model,
    record_openai_total_token_upper_bound_usage_and_charge,
    record_openai_usage_and_charge,
    transfer_credits_between_users,
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
    IssueSuggestion,
    IssueUpdateSuggestion,
)
from .picture_dictionary import (
    NON_AI_ENABLED_LANGUAGES,
    _manual_rows_from_entries,
    _refresh_dictionary_placeholder_stages,
    _sync_entry_image_paths_from_pages,
    create_or_update_picture_dictionary_subset,
    get_picture_dictionary_subset,
    list_picture_dictionary_subsets,
    picture_dictionary_subset_project_ids,
    add_lemma_pos_entries as picture_dictionary_add_lemma_pos_entries,
    add_manual_rows as picture_dictionary_add_manual_rows,
    add_words as picture_dictionary_add_words,
    clear_entries as picture_dictionary_clear_entries,
    compile_picture_dictionary as picture_dictionary_compile,
    ensure_picture_dictionary_for_community,
    import_project_as_picture_dictionary,
    remove_entries_by_ids as picture_dictionary_remove_entries_by_ids,
    update_entry_metadata as picture_dictionary_update_entry_metadata,
    remove_words as picture_dictionary_remove_words,
)

logger = logging.getLogger(__name__)

ISSUES_OVERVIEW_URL = "https://github.com/mannyrayner/C-LARA-2/blob/main/docs/issues/overview.md"
SOURCE_BUNDLE_REQUIRED_STAGES = [
    "segmentation_phase_1",
    "segmentation_phase_2",
    "translation",
    "mwe",
    "lemma",
    "gloss",
    "pinyin",
    "audio",
    "compile_html",
]
SOURCE_BUNDLE_REGEN_START_STAGE = "audio"
SOURCE_BUNDLE_REGEN_UPSTREAM_STAGES = SOURCE_BUNDLE_REQUIRED_STAGES[
    : SOURCE_BUNDLE_REQUIRED_STAGES.index(SOURCE_BUNDLE_REGEN_START_STAGE)
]


def _issue_registry_choices() -> tuple[list[tuple[str, str]], str]:
    """Return issue choices and a source label.

    Prefer canonical GitHub main-branch issue JSON files; fall back to local checkout
    when remote fetch is unavailable.
    """
    remote_listing_url = "https://api.github.com/repos/mannyrayner/C-LARA-2/contents/docs/issues/issues?ref=main"
    remote_raw_base = "https://raw.githubusercontent.com/mannyrayner/C-LARA-2/main/docs/issues/issues"

    try:
        with urllib.request.urlopen(remote_listing_url, timeout=10) as response_fp:
            listing = json.loads(response_fp.read().decode("utf-8"))
        issue_items = [item for item in listing if str(item.get("name", "")).startswith("ISSUE-")]
        choices: list[tuple[str, str]] = []
        for item in sorted(issue_items, key=lambda entry: str(entry.get("name", ""))):
            filename = str(item.get("name", ""))
            if not filename.endswith(".json"):
                continue
            raw_url = f"{remote_raw_base}/{filename}"
            with urllib.request.urlopen(raw_url, timeout=10) as issue_fp:
                data = json.loads(issue_fp.read().decode("utf-8"))
            issue_id = data.get("issue_id") or filename.removesuffix(".json")
            title = data.get("title") or "Untitled issue"
            choices.append((issue_id, f"{issue_id}: {title}"))
        if choices:
            return choices, "GitHub main branch (docs/issues/issues @ ref main)"
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, TypeError, ValueError) as exc:
        logger.warning("Falling back to local issue registry choices: %s", exc)

    issues_dir = settings.ROOT_DIR / "docs" / "issues" / "issues"
    choices = []
    for path in sorted(issues_dir.glob("ISSUE-*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        issue_id = data.get("issue_id") or path.stem
        title = data.get("title") or "Untitled issue"
        choices.append((issue_id, f"{issue_id}: {title}"))
    return choices, "Local checkout fallback"


AI_MODEL_CHOICES = [
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-5",
]

IMAGE_MODEL_CHOICES = [
    "gpt-image-1",
    "gpt-image-2",
]

PAGE_IMAGE_PLACEMENT_CHOICES = ["none", "top", "bottom"]
SEGMENTATION_METHOD_CHOICES = ["auto", "jieba", "ai"]
ROMANIZATION_METHOD_CHOICES = ["auto", "pypinyin", "indic_transliteration", "ai"]
LEGACY_IMPORT_PROCESSING_METHOD = "legacy_clara_import"
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


def _project_list_content_summary(projects: list[Project]) -> dict[str, int]:
    """Return corpus/image totals for the projects currently visible in the list."""

    totals = {
        "project_count": len(projects),
        "page_count": 0,
        "segment_count": 0,
        "non_space_content_element_count": 0,
        "image_count": 0,
    }
    project_ids = [project.pk for project in projects if project.pk]
    if not project_ids:
        return totals

    image_paths: set[str] = set()
    for path in ProjectImageStyle.objects.filter(project_id__in=project_ids).values_list("sample_image_path", flat=True):
        if str(path or "").strip():
            image_paths.add(str(path))
    for path in ProjectImageElement.objects.filter(project_id__in=project_ids).values_list("image_path", flat=True):
        if str(path or "").strip():
            image_paths.add(str(path))
    for path in ProjectImagePage.objects.filter(project_id__in=project_ids).values_list("image_path", flat=True):
        if str(path or "").strip():
            image_paths.add(str(path))
    for path in ProjectImagePageVariant.objects.filter(page__project_id__in=project_ids).values_list(
        "image_path", flat=True
    ):
        if str(path or "").strip():
            image_paths.add(str(path))
    totals["image_count"] = len(image_paths)

    for project in projects:
        stage_meta = _stage_payload_with_meta(project, "segmentation_phase_2") or _stage_payload_with_meta(
            project, "segmentation_phase_1"
        )
        payload = stage_meta.get("payload") if stage_meta else None
        pages = payload.get("pages") if isinstance(payload, dict) else None
        if not isinstance(pages, list):
            continue
        totals["page_count"] += len(pages)
        for page in pages:
            if not isinstance(page, dict):
                continue
            segments = page.get("segments") or []
            if not isinstance(segments, list):
                continue
            totals["segment_count"] += len(segments)
            for segment in segments:
                if not isinstance(segment, dict):
                    continue
                tokens = segment.get("tokens") or []
                if isinstance(tokens, list) and tokens:
                    totals["non_space_content_element_count"] += sum(
                        1
                        for token in tokens
                        if isinstance(token, dict) and str(token.get("surface") or "").strip()
                    )
                elif str(segment.get("surface") or "").strip():
                    totals["non_space_content_element_count"] += 1
    return totals


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
    if not getattr(user, "is_authenticated", False):
        return Project.objects.filter(is_published=True, access_scope=Project.ACCESS_PUBLIC)
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
    has_segmentation_phase_1 = _has_segmentation_phase_1_output(project)
    return {
        "has_source_text_for_manual_segmentation": (
            bool(_base_text_for_segmentation_phase_1(project).strip()) or has_segmentation_phase_1
        ),
        "has_segmentation_phase_1": has_segmentation_phase_1,
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



def _parse_stage_parameters(raw: str | None) -> tuple[dict[str, dict[str, Any]], str | None]:
    text = (raw or "").strip()
    if not text:
        return {}, None
    try:
        parsed = json.loads(text)
    except Exception as exc:
        return {}, f"Stage parameters must be valid JSON: {exc}"
    if not isinstance(parsed, dict):
        return {}, "Stage parameters must be a JSON object keyed by stage name."
    allowed_stages = set(PIPELINE_ORDER)
    normalized: dict[str, dict[str, Any]] = {}
    for stage, params in parsed.items():
        stage_name = str(stage).strip()
        if stage_name not in allowed_stages:
            return {}, f"Unknown stage in stage parameters: {stage_name}"
        if not isinstance(params, dict):
            return {}, f"Stage parameters for {stage_name} must be a JSON object."
        normalized[stage_name] = params
    return normalized, None


def _normalize_processing_method_choice(method: str | None, valid_choices: list[str]) -> str:
    """Normalize stored processing options while preserving validation for bad user input."""

    normalized = (method or "auto").strip().lower()
    if normalized == LEGACY_IMPORT_PROCESSING_METHOD:
        return "auto"
    if normalized in valid_choices:
        return normalized
    return normalized


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


def _is_moderation_blocked_exception(exc: BaseException) -> bool:
    text = str(exc or "").lower()
    return "moderation_blocked" in text or "rejected by the safety system" in text


def _extract_request_id_from_exception(exc: BaseException) -> str:
    text = str(exc or "")
    match = re.search(r"\breq_[A-Za-z0-9]+\b", text)
    return match.group(0) if match else ""


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
                "Text policy for final images: Do not include visible/readable text."
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
    return _extract_project_source_pages(project)


def _extract_project_source_pages(project: Project) -> list[str]:
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
        status = "finished"
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
    disallow_text_in_image: bool = False,
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
        "ht": "Haitian Creole (Krèol)",
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
        "da": "Danish",
        "nl": "Dutch",
        "no": "Norwegian",
        "pl": "Polish",
        "sv": "Swedish",
    }
    prompt_language = _image_prompt_language(project)
    if prompt_language not in language_instructions:
        prompt_language = "en"
    line1, line2 = language_instructions.get(prompt_language, language_instructions["en"])
    discourage_text_line = _discourage_text_guideline_for_language(prompt_language)
    disallow_text_line = _disallow_text_guideline_for_language(prompt_language)
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
                f"{disallow_text_line if disallow_text_in_image else discourage_text_line}",
                "If the lemma is a noun, make the object/animal/person visually central and unambiguous.",
                "If the lemma is a verb, depict the action in progress with clear actors/objects.",
                "If the lemma is an adjective, depict a concrete object/scene where the property is visually obvious.",
            ]
        )
    suppression_block_by_language = {
        "en": [
            "TEXT SUPPRESSION REQUIREMENTS (HIGH PRIORITY):",
            "- Do not render readable words, sentences, subtitles, speech bubbles, labels, captions, or signage text.",
            "- No exceptions: do not render any readable words, numbers, symbols, labels, captions, signs, or speech bubbles.",
            "- If accidental text appears in a draft, regenerate until the image is text-free.",
        ],
        "fr": [
            "EXIGENCES DE SUPPRESSION DU TEXTE (PRIORITÉ ÉLEVÉE) :",
            "- N’affiche aucun mot lisible, aucune phrase, sous-titre, bulle, étiquette, légende ou texte d’enseigne.",
            "- Aucune exception : n’affiche aucun mot, nombre, symbole, étiquette, légende, enseigne ni bulle lisibles.",
            "- Si du texte apparaît accidentellement, régénère l’image jusqu’à obtenir une image sans texte.",
        ],
    }
    suppression_block = suppression_block_by_language.get(prompt_language, suppression_block_by_language["en"])
    lines = [
        line1,
        line2,
        "",
    ]
    if disallow_text_in_image:
        lines.extend(suppression_block)
        lines.extend([f"- {disallow_text_line}", ""])
    elif discourage_text_in_image:
        lines.extend(suppression_block)
        lines.extend([f"- {discourage_text_line}", ""])
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
    "en": "Do not include visible/readable text in the image. Avoid words, letters, numbers, labels, captions, signs, speech bubbles, and onomatopoeic text.",
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

_DISALLOW_TEXT_GUIDELINES = {
    "en": "Do not include visible/readable text in the image. Avoid words, letters, numbers, labels, captions, signs, speech bubbles, and onomatopoeic text.",
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


def _disallow_text_guideline_for_language(language_code: str) -> str:
    code = (language_code or "").strip().lower()
    if not code:
        return _DISALLOW_TEXT_GUIDELINES["en"]
    return _DISALLOW_TEXT_GUIDELINES.get(code, _DISALLOW_TEXT_GUIDELINES["en"])


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
    disallow_text_in_image: bool = False,
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
            disallow_text_in_image=disallow_text_in_image,
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


def _build_page_prompt_construction_request(
    *,
    project: Project,
    page_obj: ProjectImagePage,
    base_prompt: str,
    full_text: str,
    summary_text: str,
    previous_page_text: str,
    next_page_text: str,
    relevant_elements: list[ProjectImageElement],
    current_page_text: str | None = None,
) -> tuple[str, dict[str, Any]]:
    payload = {
        "project_title": project.title,
        "source_language": project.language,
        "target_language": project.target_language,
        "page_number": page_obj.page_number,
        "summary_text": summary_text,
        "current_page_text": str(current_page_text if current_page_text is not None else page_obj.page_text),
        "previous_page_text": previous_page_text,
        "next_page_text": next_page_text,
        "full_text_excerpt": _truncate_for_prompt(full_text, max_chars=1800),
        "relevant_elements": [
            {
                "name": element.name,
                "element_type": element.element_type,
                "description": element.expanded_description or element.why_consistency_matters or "",
                "prompt_text": element.expanded_prompt or "",
                "image_path": element.image_path or "",
            }
            for element in relevant_elements
        ],
        "base_prompt": base_prompt,
    }
    instruction = "\n".join(
        [
            "You are constructing a final image-generation prompt for a single story page illustration.",
            "Use the JSON context below.",
            "Return only the final prompt text, no markdown, no JSON.",
            "Preserve important style and element continuity details.",
            "Focus on current-page content while staying globally consistent.",
            "Do not include unresolved file references like local image paths in the final prompt.",
            "",
            json.dumps(payload, ensure_ascii=False, indent=2),
        ]
    )
    return instruction, payload


def _normalize_constructed_page_prompt(
    raw_prompt: str,
    *,
    fallback_prompt: str,
    relevant_elements: list[ProjectImageElement],
) -> str:
    prompt = str(raw_prompt or "").strip()
    if not prompt:
        return fallback_prompt
    lines = [line for line in prompt.splitlines() if "image_path" not in line]
    cleaned = "\n".join(lines).strip()
    if not cleaned:
        cleaned = fallback_prompt

    element_refs = [element for element in relevant_elements if (element.image_path or "").strip()]
    if not element_refs:
        return cleaned
    if "Reference image path:" in cleaned:
        return cleaned

    ref_lines = ["", "Relevant element references (must preserve identity/continuity):"]
    for element in element_refs:
        ref_lines.extend(
            [
                f"- Element: {element.name}",
                f"  Reference image path: {element.image_path}",
            ]
        )
    return cleaned.rstrip() + "\n" + "\n".join(ref_lines)


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


def _apply_community_vote_preferred_variants(*, project: Project, community_id: int) -> int:
    """Promote each page's highest positively rated community variant to preferred."""

    changed = 0
    pages = list(
        ProjectImagePage.objects.filter(project=project)
        .select_related("preferred_variant")
        .prefetch_related("variants")
        .order_by("page_number", "id")
    )
    votes_by_variant: dict[int, dict[str, int]] = {}
    for vote in CommunityImageVote.objects.filter(community_id=community_id, project=project):
        counts = votes_by_variant.setdefault(vote.variant_id, {"up": 0, "down": 0})
        if vote.value == CommunityImageVote.VALUE_UP:
            counts["up"] += 1
        elif vote.value == CommunityImageVote.VALUE_DOWN:
            counts["down"] += 1

    for page in pages:
        ranked_variants: list[tuple[int, int, int, int, ProjectImagePageVariant]] = []
        for variant in page.variants.all():
            counts = votes_by_variant.get(variant.id, {"up": 0, "down": 0})
            up = counts["up"]
            down = counts["down"]
            if up <= 0:
                continue
            ranked_variants.append((up - down, up, -down, -variant.variant_index, variant))
        if not ranked_variants:
            continue
        ranked_variants.sort(reverse=True)
        selected = ranked_variants[0][4]
        if page.preferred_variant_id != selected.id or page.image_path != selected.image_path:
            _set_page_preferred_variant(page, selected)
            changed += 1
    return changed


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
    disallow_text_in_image: bool = False,
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
    text_model = (project.ai_model or DEFAULT_MODEL).strip()
    if text_model not in AI_MODEL_CHOICES:
        text_model = DEFAULT_MODEL

    variants_per_page = max(1, min(8, int(variants_per_page or 1)))
    summary_text = _truncate_for_prompt(full_text, max_chars=700) if full_text else ""
    prompt_by_page: dict[int, str] = {}
    prompt_construction_by_page: dict[int, dict[str, Any]] = {}
    page_texts_by_number = {row.page_number: (row.page_text or "") for row in page_rows}
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
            disallow_text_in_image=disallow_text_in_image,
            dictionary_entry=dictionary_entry,
        )
        previous_page_text = page_texts_by_number.get(page_obj.page_number - 1, "")
        next_page_text = page_texts_by_number.get(page_obj.page_number + 1, "")
        constructor_prompt, constructor_payload = _build_page_prompt_construction_request(
            project=project,
            page_obj=page_obj,
            base_prompt=prompt,
            full_text=full_text,
            summary_text=summary_text,
            previous_page_text=previous_page_text,
            next_page_text=next_page_text,
            relevant_elements=refs,
        )
        prompt_construction_by_page[page_obj.pk] = {
            "request_prompt": constructor_prompt,
            "request_payload": constructor_payload,
            "relevant_elements": refs,
            "prompt_meta": prompt_meta,
            "relevant_element_count": len(refs),
            "relevant_element_paths": [e.image_path for e in refs if e.image_path],
            "dictionary_mode": dictionary_entry is not None,
        }
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
        fallback_prompt = prompt_by_page[page_obj.pk]
        started = datetime.now(timezone.utc)
        image_client = _build_ai_client(
            model_name=image_model,
            usage_reporter=usage_reporter,
        )
        text_client = _build_ai_client(
            model_name=text_model,
            usage_reporter=usage_reporter,
        )
        page_dir = pages_dir / f"page_{page_obj.page_number:03d}"
        page_dir.mkdir(parents=True, exist_ok=True)
        construction = prompt_construction_by_page[page_obj.pk]
        constructed_raw = asyncio.run(text_client.chat_text(construction["request_prompt"]))
        prompt = _normalize_constructed_page_prompt(
            constructed_raw,
            fallback_prompt=fallback_prompt,
            relevant_elements=construction["relevant_elements"],
        )
        _append_page_image_telemetry(
            project,
            {
                "event": "page_image_prompt_construction",
                "page_number": page_obj.page_number,
                "variant_index": variant_index,
                "model": image_model,
                "constructor_model": text_model,
                "request_payload": construction["request_payload"],
                "request_prompt": construction["request_prompt"],
                "response_prompt_raw": str(constructed_raw or ""),
                "response_prompt_final": prompt,
            },
        )
        image_prompt_attempts = [prompt]
        retry_prompt = (
            "Create a neutral, non-graphic, family-friendly scene with no violence, no harm, and no sensitive content.\n\n"
            + _truncate_for_prompt(prompt, max_chars=7000)
        )
        if retry_prompt != prompt:
            image_prompt_attempts.append(retry_prompt)
        image_result = None
        last_exc: Exception | None = None
        for attempt_index, attempt_prompt in enumerate(image_prompt_attempts, start=1):
            try:
                image_result = image_client.generate_image(attempt_prompt, model=image_model)
                if attempt_index > 1:
                    _append_page_image_telemetry(
                        project,
                        {
                            "event": "page_image_retry_success",
                            "page_number": page_obj.page_number,
                            "variant_index": variant_index,
                            "model": image_model,
                            "attempt": attempt_index,
                        },
                    )
                prompt = attempt_prompt
                break
            except Exception as exc:
                last_exc = exc
                elapsed_s = (datetime.now(timezone.utc) - started).total_seconds()
                blocked = _is_moderation_blocked_exception(exc)
                _append_page_image_telemetry(
                    project,
                    {
                        "event": (
                            "page_image_moderation_blocked"
                            if blocked
                            else ("page_image_timeout" if _is_timeout_exception(exc) else "page_image_error")
                        ),
                        "page_number": page_obj.page_number,
                        "variant_index": variant_index,
                        "model": image_model,
                        "attempt": attempt_index,
                        "elapsed_s": round(elapsed_s, 3),
                        "request_id": _extract_request_id_from_exception(exc),
                        **_exception_telemetry_fields(exc),
                    },
                )
                if not blocked or attempt_index >= len(image_prompt_attempts):
                    break
        if image_result is None and last_exc is not None:
            request_id = _extract_request_id_from_exception(last_exc)
            error_message = f"{type(last_exc).__name__}: {last_exc}"
            if request_id:
                error_message += f" [request_id={request_id}]"
            return (
                page_obj.pk,
                page_obj.page_number,
                variant_index,
                "",
                f"ERROR: {error_message}",
                prompt,
            )
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
            if rel_path:
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
                    "status": (
                        ProjectImagePage.STATUS_GENERATED
                        if rel_path
                        else ProjectImagePage.STATUS_DRAFT
                    ),
                },
            )
            if preferred_variant is None and variant_index == 1:
                preferred_variant = variant if rel_path else None
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
    progress_callback: Callable[[int, int], None] | None = None,
) -> int:
    pages_dir = _image_pages_dir(project)
    pages_dir.mkdir(parents=True, exist_ok=True)
    generated = 0
    page_by_id = {page.id: page for page, _count, _prompt in requests}
    usage_events: list[dict[str, Any]] = []
    usage_reporter = _collect_usage_event(usage_events)
    style = project.image_style
    full_text = _extract_project_plain_text(project)
    summary_text = _truncate_for_prompt(full_text, max_chars=700) if full_text else ""
    project_pages = list(ProjectImagePage.objects.filter(project=project).order_by("page_number", "id"))
    page_context_rows = _page_review_context_rows(project, project_pages)
    page_text_by_id: dict[int, str] = {}
    page_texts_by_number: dict[int, str] = {}
    for row in project_pages:
        context = page_context_rows.get(row.id, {})
        preferred_text = (
            context.get("translation_text", "")
            if project.page_image_text_source == Project.PAGE_IMAGE_TEXT_SOURCE_TRANSLATION
            else context.get("source_text", "")
        )
        resolved_text = str(preferred_text or row.page_text or "").strip()
        page_text_by_id[row.id] = resolved_text
        page_texts_by_number[row.page_number] = resolved_text
    relevant_elements = [
        element for element in project.image_elements.order_by("name", "id") if element.image_path
    ]
    text_model = (project.ai_model or DEFAULT_MODEL).strip()
    if text_model not in AI_MODEL_CHOICES:
        text_model = DEFAULT_MODEL

    def _build_requested_prompt(page: ProjectImagePage, prompt_update: str) -> str:
        page_text_for_prompt = page_text_by_id.get(page.id, page.page_text or "")
        refs = [
            element for element in relevant_elements
            if not element.page_refs or _page_refs_match(element.page_refs, page.page_number)
        ]
        base_prompt, _meta = _fit_page_image_prompt_to_limit(
            project=project,
            style=style,
            page_number=page.page_number,
            page_text=page_text_for_prompt,
            full_text=full_text,
            relevant_elements=refs,
            discourage_text_in_image=bool(getattr(style, "discourage_text_in_images", False)),
            disallow_text_in_image=bool(getattr(style, "disallow_text_in_images", False)),
            dictionary_entry=None,
        )
        if prompt_update:
            base_prompt = f"{base_prompt}\n\nCommunity organiser request: {prompt_update}"
        constructor_prompt, constructor_payload = _build_page_prompt_construction_request(
            project=project,
            page_obj=page,
            base_prompt=base_prompt,
            full_text=full_text,
            summary_text=summary_text,
            previous_page_text=page_texts_by_number.get(page.page_number - 1, ""),
            next_page_text=page_texts_by_number.get(page.page_number + 1, ""),
            relevant_elements=refs,
            current_page_text=page_text_for_prompt,
        )
        text_client = _build_ai_client(model_name=text_model, usage_reporter=usage_reporter)
        constructed_raw = asyncio.run(text_client.chat_text(constructor_prompt))
        final_prompt = _normalize_constructed_page_prompt(
            constructed_raw,
            fallback_prompt=base_prompt,
            relevant_elements=refs,
        )
        _append_page_image_telemetry(project, {
            "event": "community_prompt_construction",
            "page_number": page.page_number,
            "constructor_model": text_model,
            "request_payload": constructor_payload,
            "request_prompt": constructor_prompt,
            "response_prompt_raw": str(constructed_raw or ""),
            "response_prompt_final": final_prompt,
        })
        return final_prompt

    def _prepare_request(request_tuple: tuple[ProjectImagePage, int, str]) -> tuple[ProjectImagePage, int, str]:
        page, count, prompt_update = request_tuple
        return page, count, _build_requested_prompt(page, prompt_update)

    prepared_requests: list[tuple[ProjectImagePage, int, str]] = []
    if requests:
        max_prompt_workers = min(12, len(requests))
        with ThreadPoolExecutor(max_workers=max_prompt_workers) as executor:
            futures = [executor.submit(_prepare_request, request_tuple) for request_tuple in requests]
            for future in as_completed(futures):
                prepared_requests.append(future.result())
        prepared_requests.sort(key=lambda request_tuple: (request_tuple[0].page_number, request_tuple[0].id))

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
    total_variants = sum(count for _p, count, _prompt in prepared_requests)
    completed_variants = 0
    max_workers = min(24, max(1, total_variants))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for page, count, prompt in prepared_requests:
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
            completed_variants += 1
            if progress_callback:
                progress_callback(completed_variants, total_variants)

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

    transfer_form = CreditTransferForm(sender=request.user)
    if request.method == "POST":
        action = (request.POST.get("memory_action") or "").strip().lower()
        credit_action = (request.POST.get("credit_action") or "").strip().lower()
        if action == "clear":
            profile_obj.dialogue_memory = {}
            profile_obj.save(update_fields=["dialogue_memory", "updated_at"])
            messages.success(request, "Dialogue memory cleared.")
            return redirect("profile")
        if credit_action == "transfer":
            transfer_form = CreditTransferForm(request.POST, sender=request.user)
            if transfer_form.is_valid():
                recipient = transfer_form.cleaned_data["recipient"]
                amount = transfer_form.cleaned_data["amount_usd"]
                note = (transfer_form.cleaned_data.get("note") or "").strip()
                description = note or f"Credit transfer from {request.user.username}"
                try:
                    sender_entry, _ = transfer_credits_between_users(
                        sender=request.user,
                        recipient=recipient,
                        amount_usd=amount,
                        description=description,
                    )
                except ValueError as exc:
                    transfer_form.add_error(None, str(exc))
                else:
                    messages.success(
                        request,
                        f"Transferred ${amount:.4f} to {recipient.username}. "
                        f"Your new balance is ${sender_entry.balance_after_usd:.4f}.",
                    )
                    return redirect("profile")
            form = ProfileForm(instance=profile_obj)
            return render(
                request,
                "projects/profile_form.html",
                {"form": form, "credit_transfer_form": transfer_form},
            )
        form = ProfileForm(request.POST, instance=profile_obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile saved.")
            return redirect("profile")
    else:
        form = ProfileForm(instance=profile_obj)

    return render(request, "projects/profile_form.html", {"form": form, "credit_transfer_form": transfer_form})


@login_required
def issues_home(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "projects/issues_home.html",
        {"issues_overview_url": ISSUES_OVERVIEW_URL},
    )


def favicon(request: HttpRequest) -> HttpResponse:
    favicon_path = finders.find("projects/favicon.svg")
    if not favicon_path:
        raise Http404("favicon not found")
    return FileResponse(open(favicon_path, "rb"), content_type="image/svg+xml")


@login_required
def submit_issue_update_suggestion(request: HttpRequest) -> HttpResponse:
    issue_choices, _ = _issue_registry_choices()
    issue_title_by_id = {
        issue_id: label.removeprefix(f"{issue_id}: ") for issue_id, label in issue_choices
    }
    if request.method == "POST":
        form = IssueUpdateSuggestionForm(request.POST, issue_choices=issue_choices)
        if form.is_valid():
            update_suggestion = form.save(commit=False)
            update_suggestion.submitter = request.user
            update_suggestion.issue_title = issue_title_by_id.get(update_suggestion.issue_id, "")
            update_suggestion.save()
            messages.success(request, "Thanks — your issue update suggestion has been submitted.")
            return redirect("issues-home")
    else:
        form = IssueUpdateSuggestionForm(issue_choices=issue_choices)
    return render(request, "projects/issue_update_suggestion_submit.html", {"form": form})


@login_required
def submit_issue_suggestion(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = IssueSuggestionForm(request.POST)
        if form.is_valid():
            suggestion = form.save(commit=False)
            suggestion.submitter = request.user
            suggestion.save()
            messages.success(request, "Thanks — your issue suggestion has been submitted.")
            return redirect("issue-suggestion-submit")
    else:
        form = IssueSuggestionForm()
    return render(request, "projects/issue_suggestion_submit.html", {"form": form})


@login_required
def admin_issue_suggestions(request: HttpRequest) -> HttpResponse:
    _require_admin(request.user)
    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        if action == "remove_displayed_issue_suggestions":
            new_issue_count, _ = IssueSuggestion.objects.all().delete()
            update_count, _ = IssueUpdateSuggestion.objects.all().delete()
            total_count = new_issue_count + update_count
            messages.success(
                request,
                f"Removed {total_count} issue suggestion{'s' if total_count != 1 else ''}.",
            )
            return redirect("admin-issue-suggestions")
    suggestions = list(IssueSuggestion.objects.select_related("submitter").order_by("-submitted_at", "-id"))
    issue_choices, issue_choices_source = _issue_registry_choices()
    update_suggestions = list(
        IssueUpdateSuggestion.objects.select_related("submitter").order_by("-submitted_at", "-id")
    )
    intro_lines = [
        "Please process the following human issue suggestions collected in the C-LARA-2 platform admin UI.",
        "These suggestions come from user submissions stored at /admin-tools/issue-suggestions/.",
        "Follow guidance in docs/roadmap/issue-tracking-and-human-suggestions.md.",
        "In particular, follow the section 'Overview file guidance (docs/issues/overview.md)' in that roadmap file.",
        "Use your best judgement to decide how each item should be handled.",
        "Assign a priority to each new-issue suggestion (including very low if a suggestion seems unimportant, incorrect, or out of scope).",
        "If a new-issue suggestion appears well grounded, generally rewrite and clarify it based on your understanding of the docs and codebase.",
        "For update suggestions, update the referenced docs/issues entry or related index/overview files as appropriate.",
        "Prepare output intended for docs/issues; in some cases updating existing docs/issues files may be preferable to adding a new file.",
        "Also regenerate docs/issues/overview.md in the new canonical format: timestamp, recent progress, near-term priorities, notes/risks, and a final complete issue inventory for all issues with status.",
        "Validate that issue statuses in overview.md match docs/issues/issues/*.json before finishing.",
        f"Issue registry context source for existing issues: {issue_choices_source}.",
    ]
    suggestion_lines: list[str] = []
    if issue_choices:
        suggestion_lines.append("\nCurrent existing issues (for update-vs-new decisions)")
        for idx, (_, issue_label) in enumerate(issue_choices, start=1):
            suggestion_lines.append(f"{idx}. {issue_label}")
    if suggestions:
        suggestion_lines.append("\nNew issue suggestions")
    for index, suggestion in enumerate(suggestions, start=1):
        suggestion_lines.extend(
            [
                "",
                f"New issue suggestion {index}",
                f"- id: {suggestion.id}",
                f"- submitted_at: {suggestion.submitted_at.isoformat()}",
                f"- submitter: {suggestion.submitter.username}",
                f"- status: {suggestion.status} ({suggestion.get_status_display()})",
                f"- title: {suggestion.title}",
                "- description:",
                suggestion.description.strip() or "(empty)",
            ]
        )
    if update_suggestions:
        suggestion_lines.append("\nExisting issue update suggestions")
    for index, update_suggestion in enumerate(update_suggestions, start=1):
        issue_label = update_suggestion.issue_id
        if update_suggestion.issue_title:
            issue_label = f"{issue_label}: {update_suggestion.issue_title}"
        suggestion_lines.extend(
            [
                "",
                f"Existing issue update suggestion {index}",
                f"- id: {update_suggestion.id}",
                f"- submitted_at: {update_suggestion.submitted_at.isoformat()}",
                f"- submitter: {update_suggestion.submitter.username}",
                f"- status: {update_suggestion.status} ({update_suggestion.get_status_display()})",
                f"- issue: {issue_label}",
                "- requested_update:",
                update_suggestion.update_description.strip() or "(empty)",
            ]
        )
    codex_prompt_text = "\n".join(intro_lines + suggestion_lines)
    return render(
        request,
        "projects/admin_issue_suggestions.html",
        {
            "suggestions": suggestions,
            "update_suggestions": update_suggestions,
            "codex_prompt_text": codex_prompt_text,
        },
    )


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


PROJECT_UNDERSTANDING_TASK_TYPE = "admin_project_understanding"


_MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
_MARKDOWN_CODE_RE = re.compile(r"`([^`]+)`")
_WINDOWS_ABSOLUTE_LINK_RE = re.compile(r"^/?[A-Za-z]:[\\/]")


def _normalise_project_understanding_path_link(raw_href: str) -> str:
    """Convert Codex file-path links inside the configured checkout to GitHub blob URLs."""

    href = unquote(raw_href.strip()).replace("\\", "/")
    if href.lower().startswith("file:///"):
        href = href[8:]
    if href.startswith("/") and len(href) > 2 and href[2] == ":":
        href = href[1:]

    line_fragment = ""
    line_match = re.match(r"^(?P<path>.+\.[A-Za-z0-9_+-]+):(?P<line>\d+)$", href)
    if line_match:
        href = line_match.group("path")
        line_fragment = f"#L{line_match.group('line')}"

    repo_root = str(getattr(settings, "PROJECT_UNDERSTANDING_REPOSITORY_PATH", settings.ROOT_DIR)).replace("\\", "/").rstrip("/")
    if repo_root.startswith("/") and len(repo_root) > 2 and repo_root[2] == ":":
        repo_root = repo_root[1:]

    href_lower = href.lower()
    repo_lower = repo_root.lower()
    relative_path = ""
    if repo_lower and href_lower == repo_lower:
        relative_path = ""
    elif repo_lower and href_lower.startswith(repo_lower + "/"):
        relative_path = href[len(repo_root) + 1 :]
    elif "/c-lara-2/" in href_lower:
        # Be tolerant of Codex returning an absolute path from an equivalent
        # checkout spelling (for example a Windows/Cygwin path) that does not
        # exactly match the configured repository root string.
        marker_index = href_lower.rindex("/c-lara-2/")
        relative_path = href[marker_index + len("/c-lara-2/") :]
    elif not re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", href) and not href.startswith("/"):
        relative_path = href.lstrip("./")
    else:
        return ""

    if not relative_path:
        return getattr(settings, "PROJECT_UNDERSTANDING_GITHUB_BLOB_BASE_URL", "").rstrip("/")
    if relative_path.startswith("../") or "/../" in relative_path:
        return ""
    base_url = str(getattr(settings, "PROJECT_UNDERSTANDING_GITHUB_BLOB_BASE_URL", "")).rstrip("/")
    if not base_url.lower().startswith(("http://", "https://")):
        return ""
    return f"{base_url}/{quote(relative_path, safe='/')}{line_fragment}"


def _normalise_project_understanding_link_href(raw_href: str) -> str:
    """Return a safe href for Codex answer links, mapping repository files to GitHub."""

    href = raw_href.strip()
    if href.lower().startswith(("http://", "https://")):
        return href
    github_href = _normalise_project_understanding_path_link(href)
    if github_href:
        return github_href
    if href.startswith("/") and not _WINDOWS_ABSOLUTE_LINK_RE.match(href):
        return href
    return ""


def _render_project_understanding_inline_markdown(text: str) -> str:
    """Render a small safe subset of inline Markdown used by Codex answers."""

    def _render_code(match: re.Match[str]) -> str:
        return f"<code>{escape(match.group(1))}</code>"

    def _render_links(chunk: str) -> str:
        parts: list[str] = []
        last = 0
        for match in _MARKDOWN_LINK_RE.finditer(chunk):
            parts.append(escape(chunk[last:match.start()]))
            label = escape(match.group(1))
            href = _normalise_project_understanding_link_href(match.group(2))
            if href:
                safe_href = escape(href)
                parts.append(f'<a href="{safe_href}" target="_blank" rel="noopener noreferrer">{label}</a>')
            else:
                parts.append(escape(match.group(0)))
            last = match.end()
        parts.append(escape(chunk[last:]))
        return "".join(parts)

    rendered_parts: list[str] = []
    last = 0
    for match in _MARKDOWN_CODE_RE.finditer(text):
        rendered_parts.append(_render_links(text[last:match.start()]))
        rendered_parts.append(_render_code(match))
        last = match.end()
    rendered_parts.append(_render_links(text[last:]))
    return "".join(rendered_parts)


def render_project_understanding_answer_html(answer: str) -> str:
    """Render Codex Markdown-ish answers as safe human-readable HTML."""

    lines = (answer or "").splitlines()
    html: list[str] = []
    in_list = False
    paragraph: list[str] = []

    def flush_paragraph() -> None:
        if paragraph:
            html.append(f"<p>{'<br>'.join(paragraph)}</p>")
            paragraph.clear()

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            html.append("</ul>")
            in_list = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            flush_paragraph()
            close_list()
            continue
        if stripped.startswith("- "):
            flush_paragraph()
            if not in_list:
                html.append("<ul>")
                in_list = True
            html.append(f"<li>{_render_project_understanding_inline_markdown(stripped[2:])}</li>")
            continue
        close_list()
        paragraph.append(_render_project_understanding_inline_markdown(stripped))
    flush_paragraph()
    close_list()
    return "\n".join(html)


def _project_understanding_run_dir() -> Path:
    directory = Path(settings.MEDIA_ROOT) / "admin_project_understanding"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _project_understanding_result_path(report_id: str | uuid.UUID) -> Path:
    return _project_understanding_run_dir() / f"{report_id}.json"


def _project_understanding_request_path(report_id: str | uuid.UUID) -> Path:
    return _project_understanding_run_dir() / f"{report_id}.request.json"


def _write_project_understanding_request(
    report_id: str | uuid.UUID,
    question: str,
    *,
    user_id: int | None = None,
    username: str = "",
    visibility: str = "private",
    status: str = "queued",
) -> None:
    now = django_timezone.now().isoformat()
    _project_understanding_request_path(report_id).write_text(
        json.dumps(
            {
                "question": question,
                "visibility": visibility if visibility in {"private", "public"} else "private",
                "user_id": user_id,
                "username": username,
                "submitted_at": now,
                "queue_status": status,
                "queued_at": now if status == "queued" else "",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _write_project_understanding_request_payload(report_id: str | uuid.UUID, payload: dict[str, Any]) -> None:
    _project_understanding_request_path(report_id).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _update_project_understanding_request_state(
    report_id: str | uuid.UUID,
    queue_status: str,
    **fields: Any,
) -> dict[str, Any]:
    payload = _read_project_understanding_request(report_id)
    payload["queue_status"] = queue_status
    timestamp_field = {
        "queued": "queued_at",
        "running": "claimed_at",
        "succeeded": "finished_at",
        "failed": "finished_at",
    }.get(queue_status)
    if timestamp_field and not fields.get(timestamp_field):
        fields[timestamp_field] = django_timezone.now().isoformat()
    payload.update(fields)
    _write_project_understanding_request_payload(report_id, payload)
    return payload


def _project_understanding_lock_path(report_id: str | uuid.UUID) -> Path:
    return _project_understanding_run_dir() / f"{report_id}.request.lock"


def _release_project_understanding_request_lock(report_id: str | uuid.UUID) -> None:
    try:
        _project_understanding_lock_path(report_id).unlink()
    except FileNotFoundError:
        pass
    except Exception:
        logger.exception("Failed to release project-understanding request lock for %s", report_id)


def _claim_next_project_understanding_request(worker_id: str) -> tuple[str, dict[str, Any]] | None:
    for request_path in sorted(_project_understanding_run_dir().glob("*.request.json")):
        report_id = request_path.name.removesuffix(".request.json")
        payload = _read_project_understanding_request(report_id)
        if str(payload.get("queue_status") or "queued") != "queued":
            continue
        lock_path = _project_understanding_lock_path(report_id)
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            continue
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as lock_file:
                lock_file.write(json.dumps({"worker_id": worker_id, "locked_at": django_timezone.now().isoformat()}))
            payload = _read_project_understanding_request(report_id)
            if str(payload.get("queue_status") or "queued") != "queued":
                _release_project_understanding_request_lock(report_id)
                continue
            payload = _update_project_understanding_request_state(
                report_id,
                "running",
                worker_id=worker_id,
            )
            return report_id, payload
        except Exception:
            _release_project_understanding_request_lock(report_id)
            logger.exception("Failed to claim project-understanding request %s", report_id)
    return None


def _count_queued_project_understanding_requests() -> int:
    count = 0
    for request_path in _project_understanding_run_dir().glob("*.request.json"):
        report_id = request_path.name.removesuffix(".request.json")
        payload = _read_project_understanding_request(report_id)
        if str(payload.get("queue_status") or "queued") == "queued":
            count += 1
    return count


def _read_project_understanding_request(report_id: str | uuid.UUID) -> dict[str, Any]:
    request_path = _project_understanding_request_path(report_id)
    if request_path.exists():
        try:
            payload = json.loads(request_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                return payload
        except Exception:
            logger.exception("Failed to read project-understanding request %s", request_path)
    result = _read_project_understanding_result(report_id)
    if result:
        return {"question": str(result.get("question") or "").strip(), "visibility": "private"}
    return {}


def _read_project_understanding_question(report_id: str | uuid.UUID) -> str:
    return str(_read_project_understanding_request(report_id).get("question") or "").strip()


def _can_access_project_understanding_turn(user, report_id: str | uuid.UUID) -> bool:
    payload = _read_project_understanding_request(report_id)
    visibility = str(payload.get("visibility") or "private")
    owner_id = payload.get("user_id")
    return visibility == "public" or owner_id == getattr(user, "id", None)


def _list_project_understanding_turns(user) -> list[dict[str, Any]]:
    turns: list[dict[str, Any]] = []
    for request_path in _project_understanding_run_dir().glob("*.request.json"):
        report_id = request_path.name.removesuffix(".request.json")
        request_payload = _read_project_understanding_request(report_id)
        visibility = str(request_payload.get("visibility") or "private")
        if not _can_access_project_understanding_turn(user, report_id):
            continue
        result = _read_project_understanding_result(report_id)
        latest_update = TaskUpdate.objects.filter(report_id=report_id).order_by("-timestamp").first()
        turns.append(
            {
                "report_id": report_id,
                "question": str(request_payload.get("question") or ""),
                "visibility": visibility,
                "username": str(request_payload.get("username") or ""),
                "user_id": request_payload.get("user_id"),
                "submitted_at": str(request_payload.get("submitted_at") or ""),
                "status": latest_update.status if latest_update and latest_update.status else ("finished" if result else "running"),
                "tokens_used": result.get("tokens_used") if result else None,
                "elapsed_seconds": result.get("elapsed_seconds") if result else None,
            }
        )
    return sorted(turns, key=lambda turn: turn.get("submitted_at") or turn["report_id"], reverse=True)


def _filter_project_understanding_turns(turns: list[dict[str, Any]], filters: dict[str, str]) -> list[dict[str, Any]]:
    query = filters.get("q", "").strip().lower()
    date_from = filters.get("date_from", "").strip()
    date_to = filters.get("date_to", "").strip()
    user_id = filters.get("user_id", "").strip()
    visibility = filters.get("visibility", "").strip()
    status = filters.get("status", "").strip()

    filtered: list[dict[str, Any]] = []
    for turn in turns:
        submitted_date = str(turn.get("submitted_at") or "")[:10]
        if query:
            haystack = " ".join(
                str(turn.get(field) or "")
                for field in ("question", "username", "report_id", "status", "visibility")
            ).lower()
            if query not in haystack:
                continue
        if date_from and (not submitted_date or submitted_date < date_from):
            continue
        if date_to and (not submitted_date or submitted_date > date_to):
            continue
        if user_id and str(turn.get("user_id") or "") != user_id:
            continue
        if visibility and str(turn.get("visibility") or "") != visibility:
            continue
        if status and str(turn.get("status") or "") != status:
            continue
        filtered.append(turn)
    return filtered


def _write_project_understanding_result(report_id: str | uuid.UUID, result) -> None:
    payload = asdict(result)
    _project_understanding_result_path(report_id).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _read_project_understanding_result(report_id: str | uuid.UUID) -> dict[str, Any] | None:
    path = _project_understanding_result_path(report_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("Failed to read project-understanding result %s", path)
        return None




def _project_understanding_process_security_summary() -> str:
    """Return non-secret Linux process security details for Codex sandbox diagnosis."""

    status_fields = {"NoNewPrivs", "Seccomp", "Seccomp_filters", "CapEff"}
    parts: list[str] = []
    status_path = Path("/proc/self/status")
    try:
        for line in status_path.read_text(encoding="utf-8", errors="replace").splitlines():
            name, separator, value = line.partition(":")
            if separator and name in status_fields:
                parts.append(f"{name}={value.strip()}")
    except Exception:
        pass

    try:
        cgroup_lines = Path("/proc/self/cgroup").read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        cgroup_lines = []
    if cgroup_lines:
        parts.append(f"cgroup={cgroup_lines[0][-160:]}")

    return "; ".join(parts) if parts else "security=(unavailable)"



def _project_understanding_runtime_summary() -> str:
    """Return non-secret runtime details useful for diagnosing Codex worker setup."""

    try:
        effective_uid = os.geteuid() if hasattr(os, "geteuid") else None
    except Exception:
        effective_uid = None
    try:
        username = pwd.getpwuid(effective_uid).pw_name if effective_uid is not None and pwd is not None else getpass.getuser()
    except Exception:
        try:
            username = getpass.getuser()
        except Exception:
            username = "unknown"
    path_value = os.environ.get("PATH") or ""
    bwrap_path = shutil.which("bwrap", path=path_value) if path_value else None
    return (
        f"worker user={username}"
        + (f" uid={effective_uid}" if effective_uid is not None else "")
        + f"; HOME={os.environ.get('HOME') or os.environ.get('USERPROFILE') or '(not set)'}"
        + f"; CODEX_HOME={os.environ.get('CODEX_HOME') or '(not set)'}"
        + f"; PATH={path_value or '(not set)'}"
        + f"; bwrap={bwrap_path or '(not found)'}"
        + f"; codex={getattr(settings, 'PROJECT_UNDERSTANDING_CODEX_EXECUTABLE', 'codex')}"
        + f"; {_project_understanding_process_security_summary()}"
    )


def _record_project_understanding_update(
    *,
    report_id: str | uuid.UUID,
    user_id: int,
    message: str,
    status: str | None = "running",
) -> None:
    TaskUpdate.objects.create(
        report_id=report_id,
        user_id=user_id,
        task_type=PROJECT_UNDERSTANDING_TASK_TYPE,
        message=message[:1024],
        status=status,
    )


def _run_project_understanding_task(question: str, user_id: int, report_id: str) -> None:
    stop_heartbeat = threading.Event()

    def _heartbeat() -> None:
        tick = 0
        while not stop_heartbeat.wait(10):
            tick += 10
            try:
                _record_project_understanding_update(
                    report_id=report_id,
                    user_id=user_id,
                    message=f"Codex is still inspecting the repository ({tick}s elapsed).",
                    status="running",
                )
            except Exception:
                logger.exception("Project-understanding heartbeat failed for report %s", report_id)

    heartbeat_thread = threading.Thread(target=_heartbeat, daemon=True)
    logger.info("Project-understanding worker starting for report %s", report_id)
    try:
        _record_project_understanding_update(
            report_id=report_id,
            user_id=user_id,
            message=f"Background worker picked up request; launching Codex ({_project_understanding_runtime_summary()}).",
            status="running",
        )
        heartbeat_thread.start()
        result = answer_project_understanding_question_with_codex_exec(
            question,
            repository_path=getattr(settings, "PROJECT_UNDERSTANDING_REPOSITORY_PATH", settings.ROOT_DIR),
            codex_executable=getattr(settings, "PROJECT_UNDERSTANDING_CODEX_EXECUTABLE", "codex"),
            model=getattr(settings, "PROJECT_UNDERSTANDING_MODEL", "gpt-5.3-codex"),
            timeout_seconds=float(getattr(settings, "PROJECT_UNDERSTANDING_TIMEOUT_SECONDS", 300)),
            openai_api_key=getattr(settings, "OPENAI_API_KEY", ""),
        )
        if result.tokens_used is not None:
            estimated_cost = record_openai_total_token_upper_bound_usage_and_charge(
                user_id=user_id,
                model=result.model,
                operation="project_understanding",
                total_tokens=result.tokens_used,
                request_type="codex_exec_project_understanding",
            )
            result = replace(
                result,
                estimated_cost_usd=f"{estimated_cost:.6f}",
                cost_basis="Conservative upper-bound estimate: Codex reports total tokens only, so all reported tokens are priced at the output-token rate; actual OpenAI Usage charges may be lower.",
            )
        _write_project_understanding_result(report_id, result)
        _update_project_understanding_request_state(report_id, "succeeded")
        elapsed = f"{result.elapsed_seconds:.1f}s" if result.elapsed_seconds is not None else "unknown time"
        tokens = result.tokens_used if result.tokens_used is not None else "unknown"
        _record_project_understanding_update(
            report_id=report_id,
            user_id=user_id,
            message=f"Codex project-understanding answer completed in {elapsed}; tokens used: {tokens}.",
            status="finished",
        )
    except Exception as exc:
        logger.exception("Project-understanding Codex task failed for report %s", report_id)
        _update_project_understanding_request_state(report_id, "failed", error=str(exc)[:1000])
        _record_project_understanding_update(
            report_id=report_id,
            user_id=user_id,
            message=f"Codex project-understanding call failed: {exc}",
            status="error",
        )
    finally:
        stop_heartbeat.set()



@login_required
def project_understanding(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = ProjectUnderstandingForm(request.POST)
        if form.is_valid():
            report_id = uuid.uuid4()
            question = form.cleaned_data["question"]
            _write_project_understanding_request(
                report_id,
                question,
                user_id=request.user.id,
                username=request.user.username,
                visibility=form.cleaned_data["visibility"],
            )
            _record_project_understanding_update(
                report_id=report_id,
                user_id=request.user.id,
                message="Project-understanding request queued.",
                status="running",
            )
            logger.info("Queued project-understanding request %s for dedicated worker", report_id)
            _record_project_understanding_update(
                report_id=report_id,
                user_id=request.user.id,
                message="Project-understanding request is waiting for the dedicated Codex worker.",
                status="running",
            )
            messages.info(request, "Codex project-understanding request queued for the dedicated worker. Opening live status monitor.")
            return redirect("project-understanding-monitor", report_id=report_id)
    else:
        form = ProjectUnderstandingForm()
    return render(
        request,
        "projects/project_understanding.html",
        {
            "form": form,
            "result": None,
            "result_answer_html": "",
            "initial_updates": [],
            "report_id": None,
            "status_url": None,
            "repository_path": getattr(settings, "PROJECT_UNDERSTANDING_REPOSITORY_PATH", settings.ROOT_DIR),
            "codex_model": getattr(settings, "PROJECT_UNDERSTANDING_MODEL", "gpt-5.3-codex"),
            "timeout_seconds": getattr(settings, "PROJECT_UNDERSTANDING_TIMEOUT_SECONDS", 300),
        },
    )


@login_required
def project_understanding_turns(request: HttpRequest) -> HttpResponse:
    filters = {
        "q": request.GET.get("q", ""),
        "date_from": request.GET.get("date_from", ""),
        "date_to": request.GET.get("date_to", ""),
        "user_id": request.GET.get("user_id", ""),
        "visibility": request.GET.get("visibility", ""),
        "status": request.GET.get("status", ""),
    }
    all_visible_turns = _list_project_understanding_turns(request.user)
    turns = _filter_project_understanding_turns(all_visible_turns, filters)[:100]
    return render(
        request,
        "projects/project_understanding_turns.html",
        {
            "turns": turns,
            "filters": filters,
            "visible_turn_count": len(all_visible_turns),
            "filtered_turn_count": len(turns),
        },
    )


@login_required
def project_understanding_monitor(request: HttpRequest, report_id: str) -> HttpResponse:
    if not _can_access_project_understanding_turn(request.user, report_id):
        raise Http404()
    current_request = _read_project_understanding_request(report_id)
    current_question = str(current_request.get("question") or "").strip()
    current_visibility = str(current_request.get("visibility") or "private")
    result = _read_project_understanding_result(report_id)
    initial_updates = TaskUpdate.objects.filter(
        report_id=report_id,
        user=request.user,
        task_type=PROJECT_UNDERSTANDING_TASK_TYPE,
    ).order_by("timestamp")
    return render(
        request,
        "projects/project_understanding.html",
        {
            "form": ProjectUnderstandingForm(initial={"question": current_question, "visibility": current_visibility}),
            "result": result,
            "result_answer_html": mark_safe(render_project_understanding_answer_html(str(result.get("answer") or ""))) if result else "",
            "initial_updates": initial_updates,
            "report_id": report_id,
            "status_url": reverse("project-understanding-status", args=[report_id]),
            "repository_path": getattr(settings, "PROJECT_UNDERSTANDING_REPOSITORY_PATH", settings.ROOT_DIR),
            "codex_model": getattr(settings, "PROJECT_UNDERSTANDING_MODEL", "gpt-5.3-codex"),
            "timeout_seconds": getattr(settings, "PROJECT_UNDERSTANDING_TIMEOUT_SECONDS", 300),
        },
    )


@login_required
def project_understanding_status(request: HttpRequest, report_id: str) -> JsonResponse:
    if not _can_access_project_understanding_turn(request.user, report_id):
        raise Http404()
    updates_qs = TaskUpdate.objects.filter(
        report_id=report_id,
        user=request.user,
        task_type=PROJECT_UNDERSTANDING_TASK_TYPE,
    ).order_by("timestamp")
    updates = list(updates_qs)
    unread = [u for u in updates if not u.read]
    messages_out = [u.message for u in unread]
    status = "running"
    for update in unread:
        if update.status == "error":
            status = "error"
            break
        if update.status == "finished":
            status = "finished"
    TaskUpdate.objects.filter(pk__in=[u.pk for u in unread]).update(read=True)
    last = updates[-1] if updates else None
    if status == "running" and not unread and last and last.status in {"error", "finished"}:
        status = last.status

    request_payload = _read_project_understanding_request(report_id)
    queue_status = str(request_payload.get("queue_status") or "queued")
    result = _read_project_understanding_result(report_id)
    if result and status == "running":
        status = "finished"
    if status != "finished":
        result = None

    if status == "running" and not unread:
        if last:
            age_seconds = int((django_timezone.now() - last.timestamp).total_seconds())
            if age_seconds >= 30:
                if queue_status == "queued":
                    messages_out.append(
                        "Project-understanding request is still queued; no dedicated Codex worker has claimed it yet. "
                        "On a development laptop, start one with "
                        "`python manage.py process_project_understanding_queue --once` for a single request, "
                        "or `python manage.py process_project_understanding_queue` for a long-running worker. "
                        f"Latest update was {age_seconds}s ago: {last.message}."
                    )
                elif queue_status == "running":
                    worker_id = str(request_payload.get("worker_id") or "unknown worker")
                    messages_out.append(
                        "Project-understanding request has been claimed by the dedicated Codex worker "
                        f"({worker_id}), but no new progress update has arrived for {age_seconds}s "
                        f"(latest update: {last.message})."
                    )
                else:
                    messages_out.append(
                        "Waiting for the next Codex progress update "
                        f"(queue status {queue_status}; latest update {age_seconds}s ago: {last.message})."
                    )
        else:
            messages_out.append(
                "No TaskUpdate rows exist yet for this report. Check whether the request was enqueued successfully."
            )

    if result:
        result["answer_html"] = render_project_understanding_answer_html(str(result.get("answer") or ""))
    return JsonResponse({
        "messages": messages_out,
        "status": status,
        "queue_status": queue_status,
        "worker_id": request_payload.get("worker_id") or "",
        "claimed_at": request_payload.get("claimed_at") or "",
        "result": result,
        "question": _read_project_understanding_question(report_id),
        "update_count": len(updates),
        "last_update_at": last.timestamp.isoformat() if last else "",
    })


def _process_has_manage_command(args: str, command: str) -> bool:
    arg_tokens = args.split()
    return any(
        Path(token).name == "manage.py"
        and idx + 1 < len(arg_tokens)
        and arg_tokens[idx + 1] == command
        for idx, token in enumerate(arg_tokens)
    )


def _process_snapshot() -> list[dict[str, Any]]:
    try:
        output = subprocess.check_output(
            ["ps", "-eo", "pid=,ppid=,args="],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        return []

    rows: list[dict[str, Any]] = []
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        parts = stripped.split(None, 2)
        if len(parts) < 3:
            continue
        try:
            pid = int(parts[0])
            ppid = int(parts[1])
        except ValueError:
            continue
        rows.append({"pid": pid, "ppid": ppid, "args": parts[2]})
    return rows


def _find_manage_py_processes(command: str, *, process_rows: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    current_pid = os.getpid()
    matches: list[dict[str, Any]] = []
    for row in process_rows if process_rows is not None else _process_snapshot():
        pid = int(row["pid"])
        args = str(row.get("args") or "")
        if command != "runserver" and pid == current_pid:
            continue
        if not _process_has_manage_command(args, command):
            continue
        if command != "runserver" and "runserver" in args.split():
            continue
        matches.append({**row, "command": command})
    return matches


def _find_django_q_processes() -> list[dict[str, Any]]:
    return _find_manage_py_processes("qcluster")


def _find_django_server_processes() -> list[dict[str, Any]]:
    return _find_manage_py_processes("runserver")


def _descendant_processes(process_rows: list[dict[str, Any]], root_pids: set[int]) -> list[dict[str, Any]]:
    children_by_ppid: dict[int, list[dict[str, Any]]] = {}
    for row in process_rows:
        children_by_ppid.setdefault(int(row["ppid"]), []).append(row)

    descendants: list[dict[str, Any]] = []
    queue = list(root_pids)
    seen = set(root_pids)
    while queue:
        parent_pid = queue.pop(0)
        for child in children_by_ppid.get(parent_pid, []):
            child_pid = int(child["pid"])
            if child_pid in seen:
                continue
            seen.add(child_pid)
            descendants.append({**child, "command": "child"})
            queue.append(child_pid)
    return descendants


def _terminate_processes(processes: list[dict[str, Any]], *, status: str) -> list[dict[str, Any]]:
    stopped: list[dict[str, Any]] = []
    seen_pids: set[int] = set()
    for proc in processes:
        pid = int(proc["pid"])
        if pid in seen_pids:
            continue
        seen_pids.add(pid)
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            continue
        except PermissionError as exc:
            stopped.append({**proc, "status": "permission_denied", "error": str(exc)})
        else:
            stopped.append({**proc, "status": status})
    return stopped


def _shutdown_django_q_processes() -> list[dict[str, Any]]:
    return _terminate_processes(_find_django_q_processes(), status="sigterm_sent")


def _django_stack_targets() -> list[dict[str, Any]]:
    process_rows = _process_snapshot()
    direct_targets = _find_manage_py_processes("qcluster", process_rows=process_rows) + _find_manage_py_processes(
        "runserver", process_rows=process_rows
    )
    direct_pids = {int(proc["pid"]) for proc in direct_targets}
    target_by_pid: dict[int, dict[str, Any]] = {int(proc["pid"]): proc for proc in direct_targets}
    for proc in _descendant_processes(process_rows, direct_pids):
        target_by_pid.setdefault(int(proc["pid"]), proc)
    return list(target_by_pid.values())


def _schedule_sigterm_for_pids(pids: list[int], *, delay_seconds: float) -> None:
    if not pids:
        return
    helper = (
        "import os, signal, sys, time\n"
        "delay = float(sys.argv[1])\n"
        "pids = [int(pid) for pid in sys.argv[2].split(',') if pid]\n"
        "time.sleep(delay)\n"
        "for pid in pids:\n"
        "    try:\n"
        "        os.kill(pid, signal.SIGTERM)\n"
        "    except ProcessLookupError:\n"
        "        pass\n"
        "    except PermissionError:\n"
        "        pass\n"
    )
    subprocess.Popen(
        [sys.executable, "-c", helper, str(delay_seconds), ",".join(str(pid) for pid in pids)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        start_new_session=True,
    )


def _shutdown_django_stack_processes(delay_seconds: float = 0.5) -> list[dict[str, Any]]:
    targets_by_pid: dict[int, dict[str, Any]] = {int(proc["pid"]): proc for proc in _django_stack_targets()}
    targets = list(targets_by_pid.values())
    if not targets:
        return []

    current_pid = os.getpid()
    ordered_pids = sorted(
        targets_by_pid,
        key=lambda pid: (pid == current_pid, int(targets_by_pid[pid].get("ppid", 0)) != current_pid, pid),
    )
    _schedule_sigterm_for_pids(ordered_pids, delay_seconds=delay_seconds)
    return [{**proc, "status": "sigterm_scheduled"} for proc in targets]


@login_required
def project_understanding_legacy_redirect(request: HttpRequest) -> HttpResponse:
    return redirect("project-understanding")


@login_required
def project_understanding_turns_legacy_redirect(request: HttpRequest) -> HttpResponse:
    return redirect("project-understanding-turns")


@login_required
def project_understanding_monitor_legacy_redirect(request: HttpRequest, report_id: str) -> HttpResponse:
    return redirect("project-understanding-monitor", report_id=report_id)


@login_required
def project_understanding_status_legacy_redirect(request: HttpRequest, report_id: str) -> HttpResponse:
    return redirect("project-understanding-status", report_id=report_id)


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
    menu_models = sorted(
        set(AI_MODEL_CHOICES + IMAGE_MODEL_CHOICES + list(getattr(settings, "OPENAI_PRICING_TRACKED_MODELS", [])))
    )
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
        if action in {"shutdown_django_stack", "shutdown_django_q"}:
            stopped = (
                _shutdown_django_stack_processes()
                if action == "shutdown_django_stack"
                else _shutdown_django_q_processes()
            )
            successful = [
                proc for proc in stopped if proc.get("status") in {"sigterm_sent", "sigterm_scheduled"}
            ]
            denied = [proc for proc in stopped if proc.get("status") == "permission_denied"]
            label = "Django server/Q process" if action == "shutdown_django_stack" else "Django Q qcluster process"
            if successful:
                pids = ", ".join(str(proc["pid"]) for proc in successful)
                verb = "Scheduled SIGTERM for" if action == "shutdown_django_stack" else "Sent SIGTERM to"
                messages.success(request, f"{verb} {label}(es): {pids}.")
            if denied:
                pids = ", ".join(str(proc["pid"]) for proc in denied)
                messages.error(request, f"Could not stop {label}(es) due to permissions: {pids}.")
            if not stopped:
                messages.info(request, f"No {label} was found.")
            return redirect("admin-tools")
        elif action == "delete_audio_cache":
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

    status_notice = request.GET.get("notice")
    report_id = (request.GET.get("report_id") or "").strip()

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
            "status_notice": status_notice,
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
                messages.info(request, "Expansion is running in the background; this page will refresh automatically.")
                return redirect(f"{reverse('project-image-elements', args=[project.pk])}?notice=running&report_id={report_id}")
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

    status_notice = request.GET.get("notice")
    report_id = (request.GET.get("report_id") or "").strip()
    if report_id:
        latest = TaskUpdate.objects.filter(report_id=report_id, user=request.user).order_by("-timestamp").first()
        if latest and latest.status == "finished":
            status_notice = "done"
        elif latest and latest.status == "error":
            status_notice = "error"

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
            "status_notice": status_notice,
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
                        disallow_text_in_image=bool(getattr(style, "disallow_text_in_images", False)),
                    )
                except Exception as exc:
                    logger.exception("Failed to generate page images for project %s", project.pk)
                    moderation_blocked = _is_moderation_blocked_exception(exc)
                    request_id = _extract_request_id_from_exception(exc)
                    _append_page_image_telemetry(
                        project,
                        {
                            "event": "page_images_generation_failed",
                            "model": image_model,
                            "moderation_blocked": moderation_blocked,
                            "request_id": request_id,
                            **_exception_telemetry_fields(exc),
                        },
                    )
                    if moderation_blocked:
                        details = "The request was blocked by safety moderation."
                        if request_id:
                            details += f" Request id: {request_id}."
                        details += " The system retried once with a safer prompt variant; adjust page text/style context if it keeps failing."
                        messages.error(request, f"Page image generation failed: {details}")
                    else:
                        messages.error(request, f"Page image generation failed: {exc}")
                else:
                    messages.success(
                        request,
                        f"Generated {generated} page image variant(s) with {image_model}.",
                    )
            elif action == "set_preferred":
                changed = _apply_preferred_variant_selection(project, request.POST)
                messages.success(request, f"Updated preferred image for {changed} page(s).")
            elif action == "clear_generated":
                cleared_pages = 0
                cleared_variants = ProjectImagePageVariant.objects.filter(page__project=project).count()
                ProjectImagePageVariant.objects.filter(page__project=project).delete()
                for page in ProjectImagePage.objects.filter(project=project):
                    had_generated = bool(
                        page.image_path
                        or page.generation_prompt
                        or page.image_revised_prompt
                        or page.preferred_variant_id
                    )
                    if had_generated:
                        cleared_pages += 1
                    page.image_path = ""
                    page.generation_prompt = ""
                    page.image_revised_prompt = ""
                    page.preferred_variant_id = None
                    page.status = ProjectImagePage.STATUS_DRAFT
                    page.save(
                        update_fields=[
                            "image_path",
                            "generation_prompt",
                            "image_revised_prompt",
                            "preferred_variant",
                            "status",
                            "updated_at",
                        ]
                    )
                messages.success(
                    request,
                    f"Cleared generated page images/prompts for {cleared_pages} page(s) and removed {cleared_variants} variant(s).",
                )
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

    status_notice = request.GET.get("notice")
    report_id = (request.GET.get("report_id") or "").strip()

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
            "status_notice": status_notice,
            "expansion_report_id": report_id,
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
        text_language_filter = _normalize_language_filter(str(self.request.GET.get("text_language") or ""))
        gloss_language_filter = _normalize_language_filter(str(self.request.GET.get("gloss_language") or ""))
        title_substring_filter = str(self.request.GET.get("title_substring") or "").strip()
        filtered_projects = list(context["object_list"])
        if text_language_filter:
            filtered_projects = [p for p in filtered_projects if (p.language or "").lower().startswith(text_language_filter)]
        if gloss_language_filter:
            filtered_projects = [
                p for p in filtered_projects if (p.target_language or "").lower().startswith(gloss_language_filter)
            ]
        if title_substring_filter:
            needle = title_substring_filter.casefold()
            filtered_projects = [p for p in filtered_projects if needle in (p.title or "").casefold()]
        context["object_list"] = filtered_projects

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
                "text_language_filter": text_language_filter,
                "gloss_language_filter": gloss_language_filter,
                "title_substring_filter": title_substring_filter,
                "project_language_choices": ProjectForm.LANGUAGE_CHOICES,
                "project_list_summary": _project_list_content_summary(filtered_projects),
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
        context["stage_parameters_example"] = json.dumps(
            {
                "segmentation_phase_1": {"prioritise_sentences": True},
                "segmentation_phase_2": {
                    "mechanism": "boundary_first",
                    "variant": "clitic_compound",
                    "fewshot_count": "all",
                },
            },
            indent=2,
        )
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
            if project.page_image_placement in {"top", "bottom"}
            else "top"
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
        context["audio_mode_options"] = Project.AUDIO_MODE_CHOICES
        context["selected_audio_mode"] = project.audio_mode or Project.AUDIO_MODE_TTS
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
    write_stage_artifact(target_run, stage_name, payload)
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
    if not stage_artifact_path(run_dir, "segmentation_phase_1").exists() or not stage_artifact_path(run_dir, "segmentation_phase_2").exists():
        return None
    try:
        seg1_payload = read_stage_artifact(run_dir, "segmentation_phase_1")
        seg2_payload = read_stage_artifact(run_dir, "segmentation_phase_2")
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
    write_stage_artifact(run_dir, "segmentation_phase_2", salvaged)
    return {"unchanged_pages": unchanged_pages, "total_pages": len(new_hashes)}


def _invalidate_downstream_stage_files(run_dir: Path, from_stage: str) -> None:
    if from_stage not in PIPELINE_ORDER:
        return
    from_index = PIPELINE_ORDER.index(from_stage)
    for stage in PIPELINE_ORDER[from_index + 1 :]:
        path = stage_artifact_path(run_dir, stage)
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
    run_dir = _find_run_with_stage(project, "segmentation_phase_1") or _resolve_run_dir(project)
    current_payload = _load_stage_payload(project, "segmentation_phase_1", run_dir=run_dir) if run_dir else None
    base_text = _base_text_for_segmentation_phase_1(project)
    if not base_text.strip() and isinstance(current_payload, dict):
        base_text = _surface_without_phase1_markers(_phase1_surface_from_payload(current_payload)).strip()
    if not base_text.strip():
        messages.error(request, "Manual segmentation phase 1 requires source text or an existing segmentation phase 1 artifact.")
        return redirect(return_to)

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
        write_stage_artifact(target_run, "segmentation_phase_2", seg2_payload)
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
        write_stage_artifact(target_run, "mwe", mwe_payload)
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
        write_stage_artifact(target_run, "lemma", lemma_payload)
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
        write_stage_artifact(target_run, "gloss", gloss_payload)
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
        write_stage_artifact(target_run, "pinyin", pinyin_payload)
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
        write_stage_artifact(target_run, "translation", tr_payload)
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
        disallow_text_in_images = (request.POST.get("disallow_text_in_images") or "").strip().lower() in {
            "1",
            "true",
            "on",
            "yes",
        }
        if disallow_text_in_images:
            discourage_text_in_images = False
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
                    disallow_text_in_images=disallow_text_in_images,
                )
            else:
                update_fields: list[str] = []
                if style.discourage_text_in_images != discourage_text_in_images:
                    style.discourage_text_in_images = discourage_text_in_images
                    update_fields.append("discourage_text_in_images")
                if bool(getattr(style, "disallow_text_in_images", False)) != disallow_text_in_images:
                    style.disallow_text_in_images = disallow_text_in_images
                    update_fields.append("disallow_text_in_images")
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
                else "top"
            ),
            "page_image_text_source_choices": Project.PAGE_IMAGE_TEXT_SOURCE_CHOICES,
            "selected_page_image_text_source": project.page_image_text_source,
            "pivot_language_choices": ProjectForm.LANGUAGE_CHOICES,
            "selected_image_generation_pivot_language": project.image_generation_pivot_language,
            "discourage_text_in_images_default": bool(getattr(style, "discourage_text_in_images", False)),
            "disallow_text_in_images_default": bool(getattr(style, "disallow_text_in_images", False)),
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

    latest_word_scramble = (
        project.exercise_sets.filter(exercise_type=ExerciseSet.TYPE_WORD_SCRAMBLE)
        .order_by("-updated_at", "-id")
        .first()
    )
    if latest_word_scramble is not None:
        latest_sets.append(latest_word_scramble)

    latest_crossword = (
        project.exercise_sets.filter(exercise_type=ExerciseSet.TYPE_CROSSWORD)
        .order_by("-updated_at", "-id")
        .first()
    )
    if latest_crossword is not None:
        latest_sets.append(latest_crossword)

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
    user: Any | None = None,
    model_name: str | None = None,
    usage_reporter: Callable[[dict[str, Any]], None] | None = None,
    detailed_telemetry: bool = False,
) -> OpenAIClient:
    api_key = None
    if user is not None:
        profile_obj = getattr(user, "profile", None)
        if profile_obj and getattr(profile_obj, "use_personal_openai_key", False):
            api_key = (getattr(profile_obj, "openai_api_key", "") or "").strip() or None
    config = OpenAIConfig(
        api_key=api_key,
        model=model_name or DEFAULT_MODEL,
        usage_reporter=usage_reporter,
        detailed_telemetry=detailed_telemetry,
    )
    return OpenAIClient(config=config)


def _user_has_byok_enabled(user: Any | None) -> bool:
    if user is None:
        return False
    profile_obj = getattr(user, "profile", None)
    return bool(
        profile_obj
        and getattr(profile_obj, "use_personal_openai_key", False)
        and (getattr(profile_obj, "openai_api_key", "") or "").strip()
    )


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
        user = get_user_model().objects.filter(pk=user_id).first()
        if user is None:
            return
        byok_enabled = _user_has_byok_enabled(user)
        if not byok_enabled:
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
                        "usage_status": "byok" if byok_enabled else (usage.status if usage else None),
                        "usage_cost_usd": str(usage.cost_usd) if usage else None,
                        "balance_after_usd": str(get_user_balance_usd(user)) if user is not None else None,
                        "byok_enabled": byok_enabled,
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
        user=project.owner,
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
    byok_enabled = _user_has_byok_enabled(getattr(project, "owner", None))
    for event in events:
        if not byok_enabled:
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


def _missing_source_bundle_stages(stages_dir: Path) -> list[str]:
    return [
        stage
        for stage in SOURCE_BUNDLE_REQUIRED_STAGES
        if not (stages_dir / f"{stage}.json").exists()
    ]


def _missing_source_bundle_zip_stages(names: list[str], stage_prefix: str) -> list[str]:
    available = {
        Path(name).name.removesuffix(".json")
        for name in names
        if name.startswith(stage_prefix) and name.endswith(".json")
    }
    return [stage for stage in SOURCE_BUNDLE_REQUIRED_STAGES if stage not in available]


def _refresh_source_bundle_stages_for_export(
    *, project: Project, user: Any, current_run_dir: Path, missing_stages: list[str]
) -> tuple[Path | None, str | None]:
    source_run = _find_run_with_stage(project, "pinyin")
    if source_run is None:
        return (
            None,
            "Source bundle export needs complete stage artifacts, but no pinyin stage was found. "
            "Run linguistic annotation through pinyin/audio/compile_html before exporting.",
        )

    upstream_missing = [
        stage
        for stage in SOURCE_BUNDLE_REGEN_UPSTREAM_STAGES
        if not (source_run / "stages" / f"{stage}.json").exists()
    ]
    if upstream_missing:
        return (
            None,
            "Source bundle export cannot auto-regenerate missing stage artifacts because "
            f"the latest upstream run ({source_run.name}) is missing: {', '.join(upstream_missing)}. "
            "Run the full linguistic annotation pipeline before exporting.",
        )

    pinyin_payload = _load_stage_payload(project, "pinyin", run_dir=source_run)
    if pinyin_payload is None:
        return (
            None,
            "Source bundle export found a pinyin stage, but could not read it. "
            "Run linguistic annotation from pinyin or earlier before exporting.",
        )

    output_dir = _prepare_output_dir(project).resolve()
    try:
        _copy_run_artifacts(source_run, output_dir)
        progress_log = output_dir / "stages" / "progress.jsonl"
        if progress_log.exists():
            progress_log.unlink()
    except Exception:
        logger.exception("Failed to copy source-bundle upstream artifacts from %s", source_run)
        return (None, "Could not prepare prior stage artifacts for source bundle export.")

    report_id = str(uuid.uuid4())
    _run_compile_task(
        project.pk,
        user.id,
        str(output_dir),
        str(project.artifact_dir().resolve()),
        SOURCE_BUNDLE_REGEN_START_STAGE,
        None,
        project.description or "",
        None,
        pinyin_payload,
        report_id,
        f"source_bundle_refresh_{project.pk}",
        project.ai_model or DEFAULT_MODEL,
        "compile_html",
        project.page_image_placement,
        project.segmentation_method,
        project.romanization_method,
        False,
    )

    remaining_missing = _missing_source_bundle_stages(output_dir / "stages")
    if remaining_missing:
        return (
            None,
            "Automatic source bundle stage regeneration did not produce all required stages. "
            f"Still missing: {', '.join(remaining_missing)}.",
        )
    logger.info(
        "Refreshed source bundle stages for project=%s current_run=%s output_run=%s initially_missing=%s",
        project.pk,
        current_run_dir,
        output_dir,
        missing_stages,
    )
    return (output_dir, None)


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
    path = stage_artifact_path(run_dir, stage)
    if not path.exists():
        return None
    try:
        return normalize_json_text(read_stage_artifact(run_dir, stage))
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
    stage_path = stage_artifact_path(run_dir, stage)
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


def _build_picture_glosses_for_compile(
    *,
    project: Project,
    output_dir: Path,
    diagnostics: list[str] | None = None,
) -> dict[str, dict[str, str]]:
    def _record(message: str) -> None:
        if diagnostics is not None:
            diagnostics.append(message)

    if not project.community_id:
        _record("Picture gloss diagnostics: project has no community; no dictionary lookup attempted.")
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
        _record(f"Picture gloss diagnostics: no active picture dictionary for community_id={project.community_id}.")
        return {}

    entries = list(
        PictureDictionaryEntry.objects.filter(
            dictionary=dictionary,
            is_active=True,
        ).order_by("id")
    )
    entry_image_path_count = sum(1 for entry in entries if (entry.image_path or "").strip())
    entry_page_number_count = sum(1 for entry in entries if entry.current_page_number)
    dictionary_pages = list(
        ProjectImagePage.objects.select_related("preferred_variant")
        .filter(project=dictionary.project)
        .order_by("page_number", "id")
    )
    page_image_path_count = sum(1 for page in dictionary_pages if (page.image_path or "").strip())
    page_preferred_variant_count = sum(1 for page in dictionary_pages if page.preferred_variant_id)
    page_preferred_variant_image_count = sum(
        1
        for page in dictionary_pages
        if page.preferred_variant_id and page.preferred_variant and (page.preferred_variant.image_path or "").strip()
    )
    page_by_number = {page.page_number: page for page in dictionary_pages}
    page_by_text: dict[str, ProjectImagePage] = {}
    for page in dictionary_pages:
        page_text_key = (page.page_text or "").strip().casefold()
        if page_text_key and page_text_key not in page_by_text:
            page_by_text[page_text_key] = page
    missing_lemma: list[str] = []
    duplicate_lemma: list[str] = []
    missing_image_path: list[str] = []
    missing_image_file: list[str] = []
    mapped_samples: list[str] = []
    page_fallback_count = 0
    for entry in entries:
        lemma_key = (entry.lemma or entry.surface or "").strip().casefold()
        label = f"entry_id={entry.id}, surface={entry.surface!r}, lemma={entry.lemma!r}, page={entry.current_page_number}"
        if not lemma_key:
            missing_lemma.append(label)
            continue
        if lemma_key in picture_glosses:
            duplicate_lemma.append(label)
            continue
        resolved_image_path = (entry.image_path or "").strip()
        if not resolved_image_path:
            page = None
            if entry.current_page_number:
                page = page_by_number.get(entry.current_page_number)
            if page is None:
                page = page_by_text.get((entry.surface or "").strip().casefold())
            if page:
                resolved_image_path = (page.image_path or "").strip()
                if not resolved_image_path and page.preferred_variant_id and page.preferred_variant:
                    resolved_image_path = (page.preferred_variant.image_path or "").strip()
            if resolved_image_path:
                page_fallback_count += 1
                entry.image_path = resolved_image_path
                entry.save(update_fields=["image_path", "updated_at"])
        if not resolved_image_path:
            missing_image_path.append(label)
            continue
        abs_path = (dictionary.project.artifact_dir() / resolved_image_path).resolve()
        if not abs_path.exists():
            missing_image_file.append(f"{label}, image_path={resolved_image_path!r}, abs={abs_path}")
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
        if len(mapped_samples) < 5:
            mapped_samples.append(f"{lemma_key}->{rel_path}")

    _record(
        "Picture gloss diagnostics: "
        f"community_id={project.community_id}, dictionary_id={dictionary.id}, "
        f"dictionary_project_id={dictionary.project_id}, active_entries={len(entries)}, "
        f"entry_image_paths_before_fallback={entry_image_path_count}, entry_page_numbers={entry_page_number_count}, "
        f"dictionary_pages={len(dictionary_pages)}, page_image_paths={page_image_path_count}, "
        f"page_preferred_variants={page_preferred_variant_count}, "
        f"page_preferred_variant_images={page_preferred_variant_image_count}, "
        f"entry_image_paths_after_fallback={entry_image_path_count + page_fallback_count}, "
        f"mapped={len(picture_glosses)}, page_fallbacks={page_fallback_count}, "
        f"missing_lemma={len(missing_lemma)}, duplicate_lemma={len(duplicate_lemma)}, "
        f"missing_image_path={len(missing_image_path)}, missing_image_file={len(missing_image_file)}."
    )

    def _sample(label: str, values: list[str]) -> None:
        if values:
            _record(f"Picture gloss diagnostics {label} sample: " + "; ".join(values[:5]))

    _sample("mapped", mapped_samples)
    _sample("missing_lemma", missing_lemma)
    _sample("duplicate_lemma", duplicate_lemma)
    _sample("missing_image_path", missing_image_path)
    _sample("missing_image_file", missing_image_file)
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
    stage_parameters: dict[str, dict[str, Any]] | None = None,
) -> None:
    project = Project.objects.get(pk=project_id)
    user = get_user_model().objects.filter(pk=user_id).first()
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
        if stage_parameters:
            post_update(f"Stage parameters: {json.dumps(stage_parameters, ensure_ascii=False)}")
        if user is None:
            post_update(f"Compile failed: no user found for user_id={user_id}", status="error")
            logger.error("Compile task aborted: missing user record for user_id=%s project_id=%s", user_id, project_id)
            return
        audio_mode = (
            project.audio_mode
            if project.audio_mode in {Project.AUDIO_MODE_TTS, Project.AUDIO_MODE_NONE}
            else Project.AUDIO_MODE_TTS
        )
        if audio_mode == Project.AUDIO_MODE_NONE:
            post_update("Audio mode is 'No audio / skip TTS'; the audio stage will not call TTS and compiled HTML will omit audio controls.")

        spec = FullPipelineSpec(
            text=text,
            text_obj=text_obj,
            description=description,
            language=project.language,
            target_language=project.target_language,
            output_dir=output_dir,
            audio_cache_dir=_audio_repository_dir(project.language),
            require_real_tts=audio_mode != Project.AUDIO_MODE_NONE,
            audio_mode=audio_mode,
            persist_intermediates=True,
            progress_callback=tracked_progress_cb,
            start_stage=start_stage,
            end_stage=end_stage or "compile_html",
            page_images={},
            picture_glosses={},
            segmentation_method=_resolve_segmentation_method(project.language, segmentation_method or project.segmentation_method),
            romanization_method=_resolve_romanization_method(project.language, romanization_method or project.romanization_method),
            telemetry=telemetry,
            stage_parameters=stage_parameters or {},
        )
        post_update("Pipeline spec initialized.")
        try:
            picture_gloss_diagnostics: list[str] = []
            spec.picture_glosses = _build_picture_glosses_for_compile(
                project=project,
                output_dir=output_dir,
                diagnostics=picture_gloss_diagnostics,
            )
            post_update(f"Prepared picture gloss map: {len(spec.picture_glosses)} lemma image(s).")
            for diagnostic in picture_gloss_diagnostics:
                post_update(diagnostic)
        except Exception as gloss_exc:
            logger.exception("Failed to build picture gloss map for project %s; continuing without picture glosses", project_id)
            spec.picture_glosses = {}
            post_update(f"Warning: picture gloss map build failed ({gloss_exc}). Continuing without picture glosses.")

        placement = (page_image_placement or "none").strip().lower()
        if placement in {"top", "bottom"}:
            page_images: dict[int, dict[str, str]] = {}
            expected_paths: list[str] = []
            missing_preferred_pages: list[int] = []
            missing_fallback_pages: list[int] = []
            for row in project.image_pages.select_related("preferred_variant").order_by("page_number"):
                resolved_image_path = ""
                source_label = "none"
                if row.preferred_variant_id and row.preferred_variant:
                    resolved_image_path = row.preferred_variant.image_path or ""
                    source_label = "preferred variant"
                elif row.image_path:
                    resolved_image_path = row.image_path
                    source_label = "page image fallback"

                if not resolved_image_path:
                    expected_paths.append(f"page {row.page_number}: [no usable preferred or fallback image_path set]")
                    if row.preferred_variant_id:
                        missing_preferred_pages.append(row.page_number)
                    else:
                        missing_fallback_pages.append(row.page_number)
                    continue

                abs_path = (project.artifact_dir() / resolved_image_path).resolve()
                rel_path = os.path.relpath(abs_path, output_dir / "html").replace("\\", "/")
                expected_paths.append(
                    f"page {row.page_number}: {abs_path} ({source_label}, exists={abs_path.exists()})"
                )
                if abs_path.exists():
                    page_images[row.page_number] = {"path": rel_path, "placement": placement}
                elif row.preferred_variant_id:
                    missing_preferred_pages.append(row.page_number)
                else:
                    missing_fallback_pages.append(row.page_number)
            spec.page_images = page_images
            post_update(f"Resolved compile page images: {len(page_images)} page image reference(s).")
            if missing_preferred_pages:
                post_update(
                    "Warning: preferred page images missing for page(s): "
                    + ", ".join(str(page) for page in missing_preferred_pages)
                    + ". Those pages will compile without page images."
                )
            if missing_fallback_pages:
                post_update(
                    "Warning: fallback page images missing for page(s): "
                    + ", ".join(str(page) for page in missing_fallback_pages)
                    + ". Those pages will compile without page images."
                )
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
            byok_enabled = _user_has_byok_enabled(user)
            if detailed_api_trace:
                telemetry.event(
                    str(current_request_type["value"] or "compile"),
                    "info",
                    "billing mode",
                    {"byok_enabled": byok_enabled, "user_id": user_id, "project_id": project_id},
                )
            for event in usage_events:
                try:
                    if not byok_enabled:
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
            user=user,
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


def _run_picture_dictionary_compile_task(
    dictionary_id: int,
    user_id: int,
    report_id: str,
    low_resource_mode: bool = False,
) -> None:
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
            low_resource_mode=low_resource_mode,
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
    stage_parameters, stage_parameters_error = _parse_stage_parameters(request.POST.get("stage_parameters"))
    if stage_parameters_error:
        messages.error(request, stage_parameters_error)
        return redirect(return_to)
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

    segmentation_method = _normalize_processing_method_choice(
        request.POST.get("segmentation_method") or project.segmentation_method, SEGMENTATION_METHOD_CHOICES
    )
    romanization_method = _normalize_processing_method_choice(
        request.POST.get("romanization_method") or project.romanization_method, ROMANIZATION_METHOD_CHOICES
    )
    audio_mode = (request.POST.get("audio_mode") or project.audio_mode or Project.AUDIO_MODE_TTS).strip().lower()
    if segmentation_method not in SEGMENTATION_METHOD_CHOICES:
        messages.error(request, "Unknown segmentation method option.")
        return redirect(return_to)
    if romanization_method not in ROMANIZATION_METHOD_CHOICES:
        messages.error(request, "Unknown romanization method option.")
        return redirect(return_to)
    if audio_mode not in {Project.AUDIO_MODE_TTS, Project.AUDIO_MODE_NONE}:
        messages.error(request, "Unknown audio mode option.")
        return redirect(return_to)
    update_fields: list[str] = []
    if segmentation_method != project.segmentation_method:
        project.segmentation_method = segmentation_method
        update_fields.append("segmentation_method")
    if romanization_method != project.romanization_method:
        project.romanization_method = romanization_method
        update_fields.append("romanization_method")
    if audio_mode != project.audio_mode:
        project.audio_mode = audio_mode
        update_fields.append("audio_mode")
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
        stage_parameters,
        q_options={"sync": False},
    )

    monitor_url = reverse("project-compile-monitor", args=[project.pk, report_id])
    return redirect(f"{monitor_url}?next={quote(return_to, safe='/')}")


@login_required
def set_page_image_placement(request: HttpRequest, pk: int) -> HttpResponse:
    project = _get_project_for_user(pk=pk, user=request.user, min_role=ProjectCollaborator.ROLE_OWNER)
    placement = (request.POST.get("page_image_placement") or "top").strip().lower()
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
    return_to = (request.POST.get("return_to") or "").strip()
    if not return_to.startswith("/"):
        return_to = reverse("project-detail", args=[project.pk])
    segmentation_method = _normalize_processing_method_choice(
        request.POST.get("segmentation_method") or project.segmentation_method, SEGMENTATION_METHOD_CHOICES
    )
    romanization_method = _normalize_processing_method_choice(
        request.POST.get("romanization_method") or project.romanization_method, ROMANIZATION_METHOD_CHOICES
    )
    audio_mode = (request.POST.get("audio_mode") or project.audio_mode or Project.AUDIO_MODE_TTS).strip().lower()
    if segmentation_method not in SEGMENTATION_METHOD_CHOICES:
        messages.error(request, "Unknown segmentation method option.")
        return redirect(return_to)
    if romanization_method not in ROMANIZATION_METHOD_CHOICES:
        messages.error(request, "Unknown romanization method option.")
        return redirect(return_to)
    if audio_mode not in {Project.AUDIO_MODE_TTS, Project.AUDIO_MODE_NONE}:
        messages.error(request, "Unknown audio mode option.")
        return redirect(return_to)
    update_fields: list[str] = []
    if segmentation_method != project.segmentation_method:
        project.segmentation_method = segmentation_method
        update_fields.append("segmentation_method")
    if romanization_method != project.romanization_method:
        project.romanization_method = romanization_method
        update_fields.append("romanization_method")
    if audio_mode != project.audio_mode:
        project.audio_mode = audio_mode
        update_fields.append("audio_mode")
    if update_fields:
        project.save(update_fields=update_fields + ["updated_at"])
    messages.success(request, "Saved language-processing options.")
    return redirect(return_to)


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
        "Only set 'level' when the user explicitly requests a CEFR level (A1, A2, B1, B2, C1, C2, beginner/intermediate/advanced). "
        "If level is not explicitly requested in the current query, return level as an empty string unless the user clearly asks to keep a previous level. "
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


def content_list(request: HttpRequest) -> HttpResponse:
    """Search/browse published projects, with optional natural-language discovery."""

    manual_title = (request.GET.get("title") or "").strip()
    manual_text_language = _normalize_language_filter(request.GET.get("text_language") or "")
    manual_annotation_language = _normalize_language_filter(request.GET.get("annotation_language") or "")
    manual_date_posted = _normalize_date_posted_filter(request.GET.get("date_posted") or "any")
    manual_level = _normalize_cefr_level_expression(request.GET.get("level") or "", max_levels=3)

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
        level = _normalize_cefr_level_expression(str(nl_plan.get("level") or "").strip(), max_levels=3)
    else:
        title = manual_title
        text_language = manual_text_language
        annotation_language = manual_annotation_language
        date_posted = manual_date_posted
        level = manual_level

    qs = _published_projects_visible_to_user(request.user)
    title_hard_filter = title
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
        requested_level = level
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
            "nl_filters": {
                "nl_query": nl_query,
                "dialogue_language": dialogue_language,
                "level": level,
            },
            "simple_filters": {
                "title": manual_title,
                "text_language": manual_text_language,
                "annotation_language": manual_annotation_language,
                "date_posted": manual_date_posted,
                "level": manual_level,
            },
            "simple_filters": {
                "title": manual_title,
                "text_language": manual_text_language,
                "annotation_language": manual_annotation_language,
                "date_posted": manual_date_posted,
                "level": manual_level,
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
            "level_options": [
                ("", "Any level"),
                ("A1/A2", "A1/A2"),
                ("B1/B2", "B1/B2"),
                ("C1/C2", "C1/C2"),
            ],
        },
    )


def content_detail(request: HttpRequest, pk: int) -> HttpResponse:
    """Show metadata for a published project and link to page 1."""

    project = get_object_or_404(_published_projects_visible_to_user(request.user), pk=pk)
    Project.objects.filter(pk=project.pk).update(access_count=F("access_count") + 1)

    if request.method == "POST":
        if not request.user.is_authenticated:
            messages.error(request, "Please sign in to post comments or ratings.")
            return redirect("login")
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


def _latest_exercise_sets_for_project(project: Project | None) -> list[ExerciseSet]:
    if project is None:
        return []
    latest_sets: list[ExerciseSet] = []
    for exercise_type in [
        ExerciseSet.TYPE_FLASHCARD,
        ExerciseSet.TYPE_WORD_SCRAMBLE,
        ExerciseSet.TYPE_CROSSWORD,
        ExerciseSet.TYPE_CLOZE,
    ]:
        latest = project.exercise_sets.filter(exercise_type=exercise_type).order_by("-updated_at", "-id").first()
        if latest is not None:
            latest_sets.append(latest)
    latest_sets.sort(key=lambda exercise_set: exercise_set.updated_at, reverse=True)
    return latest_sets


def _safe_exercise_back_url(request: HttpRequest) -> str:
    back_url = str(request.GET.get("next") or "").strip()
    if back_url.startswith("/") and not back_url.startswith("//"):
        return back_url
    return ""

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
    picture_dictionary = (
        PictureDictionary.objects.select_related("project")
        .filter(community_id=community_id, is_active=True)
        .first()
    )
    picture_dictionary_exercise_sets = _latest_exercise_sets_for_project(picture_dictionary.project if picture_dictionary else None)
    picture_dictionary_subsets = list_picture_dictionary_subsets(picture_dictionary) if picture_dictionary else []
    for subset in picture_dictionary_subsets:
        subset["exercise_sets"] = _latest_exercise_sets_for_project(subset.get("project"))
    picture_dictionary_has_exercise_sets = bool(picture_dictionary_exercise_sets) or any(
        bool(subset.get("exercise_sets")) for subset in picture_dictionary_subsets
    )
    community_back_url = reverse("community-member-home", args=[community_id])
    return render(
        request,
        "projects/community_member_home.html",
        {
            "community": membership.community,
            "membership": membership,
            "project_rows": project_rows,
            "picture_dictionary": picture_dictionary,
            "picture_dictionary_exercise_sets": picture_dictionary_exercise_sets,
            "picture_dictionary_subsets": picture_dictionary_subsets,
            "picture_dictionary_has_exercise_sets": picture_dictionary_has_exercise_sets,
            "community_back_url": community_back_url,
        },
    )


def _project_language_label(language_code: str) -> str:
    labels = {code: label for code, label in ProjectForm.LANGUAGE_CHOICES}
    code = (language_code or "").strip().lower()
    return labels.get(code, code or "unknown")


def _ai_available_for_user(user: Any | None = None) -> bool:
    if (getattr(settings, "OPENAI_API_KEY", "") or os.environ.get("OPENAI_API_KEY")):
        return True
    return _user_has_byok_enabled(user)


def _normalise_picture_dictionary_mixup_warnings(payload: Any, *, rows_by_number: dict[int, dict[str, str]]) -> list[dict[str, str]]:
    if not isinstance(payload, dict):
        return []
    raw_warnings = payload.get("warnings") or []
    if not isinstance(raw_warnings, list):
        return []
    warnings: list[dict[str, str]] = []
    seen: set[int] = set()
    for raw in raw_warnings:
        if not isinstance(raw, dict):
            continue
        try:
            row_number = int(raw.get("row_number") or raw.get("row") or 0)
        except (TypeError, ValueError):
            row_number = 0
        if row_number not in rows_by_number or row_number in seen:
            continue
        row = rows_by_number[row_number]
        confidence = str(raw.get("confidence") or "").strip().lower()
        if confidence and confidence not in {"medium", "high"}:
            continue
        reason = str(raw.get("reason") or "").strip()
        warnings.append(
            {
                "row_number": str(row_number),
                "surface": row["surface"],
                "translation": row["translation"],
                "reason": reason or "The surface form appears to be in the translation/gloss language rather than the text language.",
                "confidence": confidence or "medium",
            }
        )
        seen.add(row_number)
    return warnings



def _coerce_ai_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "y", "1", "english", "gloss_language"}:
            return True
        if normalized in {"false", "no", "n", "0", "not_english", "not_gloss_language"}:
            return False
    return None


def _normalise_ai_confidence(value: Any) -> str:
    confidence = str(value or "").strip().lower()
    return confidence if confidence in {"low", "medium", "high"} else "unknown"


def _picture_dictionary_language_trace_label(is_gloss_language: bool | None, *, gloss_language_label: str) -> str:
    label = (gloss_language_label or "gloss language").strip()
    if label.lower().startswith("unknown"):
        label = "gloss language"
    if is_gloss_language is True:
        return label
    if is_gloss_language is False:
        return f"not {label}"
    return "uncertain"


def _picture_dictionary_single_mixup_result_from_payload(
    payload: Any,
    *,
    row_number: int,
    surface: str,
    translation: str,
    translation_language: str = "",
    gloss_language_label: str = "gloss language",
) -> tuple[dict[str, str] | None, dict[str, str]]:
    rows_by_number = {row_number: {"surface": surface, "translation": translation}}
    payload_dict = payload if isinstance(payload, dict) else {}
    text_is_gloss_language = _coerce_ai_bool(
        payload_dict.get("text_is_gloss_language")
        if "text_is_gloss_language" in payload_dict
        else payload_dict.get("surface_is_gloss_language")
    )
    translation_is_gloss_language = _coerce_ai_bool(payload_dict.get("translation_is_gloss_language"))
    trace_reason = str(payload_dict.get("reason") or "").strip()
    trace = {
        "row_number": str(row_number),
        "surface": surface,
        "translation": translation,
        "text_language_id": _picture_dictionary_language_trace_label(
            text_is_gloss_language,
            gloss_language_label=gloss_language_label,
        ),
        "text_language_confidence": _normalise_ai_confidence(
            payload_dict.get("text_language_confidence") or payload_dict.get("surface_language_confidence")
        ),
        "gloss_language_id": _picture_dictionary_language_trace_label(
            translation_is_gloss_language,
            gloss_language_label=gloss_language_label,
        ),
        "gloss_language_confidence": _normalise_ai_confidence(
            payload_dict.get("translation_language_confidence") or payload_dict.get("gloss_language_confidence")
        ),
        "reason": trace_reason,
    }
    if isinstance(payload, dict) and isinstance(payload.get("warnings"), list):
        warnings = _normalise_picture_dictionary_mixup_warnings(payload, rows_by_number=rows_by_number)
        return (warnings[0] if warnings else None), trace
    if not isinstance(payload, dict):
        return None, trace
    if translation_is_gloss_language is True:
        return None, trace
    warning_value = payload.get("warning")
    is_warning = _coerce_ai_bool(warning_value)
    if is_warning is None:
        is_warning = translation_is_gloss_language is False
    confidence = str(payload.get("confidence") or "").strip().lower()
    if not is_warning or (confidence and confidence not in {"medium", "high"}):
        return None, trace
    reason = trace_reason
    warning = {
        "row_number": str(row_number),
        "surface": surface,
        "translation": translation,
        "reason": reason or "The translation/gloss does not appear to be in the gloss language, so the row may have swapped word/gloss fields.",
        "confidence": confidence or "medium",
        "text_language_id": trace["text_language_id"],
        "gloss_language_id": trace["gloss_language_id"],
    }
    return warning, trace


def _picture_dictionary_single_mixup_warning_from_payload(
    payload: Any,
    *,
    row_number: int,
    surface: str,
    translation: str,
    translation_language: str = "",
) -> dict[str, str] | None:
    warning, _trace = _picture_dictionary_single_mixup_result_from_payload(
        payload,
        row_number=row_number,
        surface=surface,
        translation=translation,
        translation_language=translation_language,
        gloss_language_label=_project_language_label(translation_language) if translation_language not in {"", "inferred"} else "gloss language",
    )
    return warning


def _picture_dictionary_language_id_cache_key(
    *,
    translation_language: str,
    text: str,
) -> str:
    payload = {
        "version": 3,
        "translation_language": translation_language,
        "text": text.strip().casefold(),
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    return f"picture_dictionary_language_id:{digest}"


def _picture_dictionary_language_id_prompt(
    *,
    translation_language: str,
    translation_label: str,
    field_label: str,
    text: str,
) -> str:
    return (
        "You are doing a language-ID check for ONE isolated picture-dictionary field. "
        "Classify only whether this single text is in the translation/gloss language. "
        "Do not infer or name any low-resource/source language; if it does not look like the gloss language, simply classify it as not in the gloss language. "
        "Treat short dictionary glosses, comma-separated gloss lists, explanatory paraphrases, and minor typos in the gloss language as being in the gloss language. "
        "For example, for English glosses, 'mouth', 'sky', 'small, little', 'non protein food, vegetable food source', and 'ire, firewood' should count as English/gloss-language. "
        "Return only JSON with keys is_gloss_language (boolean), confidence ('low', 'medium', or 'high'), and reason (string).\n\n"
        f"Translation/gloss language: {translation_label} ({translation_language})\n"
        f"Item: {json.dumps({'field': field_label, 'text': text}, ensure_ascii=False)}"
    )


def _picture_dictionary_normalise_language_id_payload(payload: Any) -> dict[str, Any]:
    payload_dict = payload if isinstance(payload, dict) else {}
    is_gloss_language = _coerce_ai_bool(
        payload_dict.get("is_gloss_language")
        if "is_gloss_language" in payload_dict
        else payload_dict.get("text_is_gloss_language")
    )
    return {
        "is_gloss_language": is_gloss_language,
        "confidence": _normalise_ai_confidence(payload_dict.get("confidence") or payload_dict.get("language_confidence")),
        "reason": str(payload_dict.get("reason") or "").strip(),
    }


def _picture_dictionary_mixup_result_from_language_ids(
    *,
    row_number: int,
    surface: str,
    translation: str,
    text_result: dict[str, Any],
    translation_result: dict[str, Any],
    gloss_language_label: str,
) -> tuple[dict[str, str] | None, dict[str, str]]:
    text_is_gloss_language = text_result.get("is_gloss_language")
    translation_is_gloss_language = translation_result.get("is_gloss_language")
    trace = {
        "row_number": str(row_number),
        "surface": surface,
        "translation": translation,
        "text_language_id": _picture_dictionary_language_trace_label(
            text_is_gloss_language,
            gloss_language_label=gloss_language_label,
        ),
        "text_language_confidence": str(text_result.get("confidence") or "unknown"),
        "gloss_language_id": _picture_dictionary_language_trace_label(
            translation_is_gloss_language,
            gloss_language_label=gloss_language_label,
        ),
        "gloss_language_confidence": str(translation_result.get("confidence") or "unknown"),
        "reason": "; ".join(
            reason
            for reason in [str(text_result.get("reason") or ""), str(translation_result.get("reason") or "")]
            if reason
        ),
    }
    if translation_is_gloss_language is not False:
        return None, trace

    text_label = _picture_dictionary_language_trace_label(
        True,
        gloss_language_label=gloss_language_label,
    )
    not_text_label = _picture_dictionary_language_trace_label(
        False,
        gloss_language_label=gloss_language_label,
    )
    if text_is_gloss_language is True:
        reason = (
            f"The word appears to be in {text_label}, but the gloss/translation does not look like {text_label}. "
            "This may mean the word and gloss were swapped, or that the gloss/translation needs correction."
        )
        confidence = str(text_result.get("confidence") or "medium")
    else:
        reason = (
            f"The gloss/translation does not look like {text_label}. It was classified as {not_text_label}, "
            "so image generation may not be able to use it; please check this row."
        )
        confidence = str(translation_result.get("confidence") or "medium")
    if confidence not in {"medium", "high"}:
        confidence = "medium"
    warning = {
        "row_number": str(row_number),
        "surface": surface,
        "translation": translation,
        "reason": reason,
        "confidence": confidence,
        "text_language_id": trace["text_language_id"],
        "gloss_language_id": trace["gloss_language_id"],
    }
    return warning, trace


def _picture_dictionary_surface_translation_mixup_diagnostics(
    *,
    dictionary: PictureDictionary,
    rows: list[dict[str, str]],
    user: Any | None = None,
    max_rows: int | None = None,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Use per-row AI language checks to find likely surface/gloss swaps plus trace rows."""

    if not rows or not _ai_available_for_user(user):
        return [], []
    source_language = dictionary.language or dictionary.project.language
    configured_translation_language = dictionary.project.target_language or ""
    if configured_translation_language and configured_translation_language != source_language:
        translation_label = _project_language_label(configured_translation_language)
        translation_language_for_prompt = configured_translation_language
    else:
        translation_label = "unknown; infer it from the gloss value (usually English or French in this workflow)"
        translation_language_for_prompt = "inferred"
    candidate_rows: list[dict[str, Any]] = []
    for idx, row in enumerate(rows, start=1):
        surface = str(row.get("surface") or "").strip()
        translation = str(row.get("translation") or row.get("gloss") or "").strip()
        if not surface or not translation:
            continue
        candidate_rows.append(
            {
                "row_number": idx,
                "surface": surface,
                "lemma": str(row.get("lemma") or "").strip(),
                "pos": str(row.get("pos") or "").strip(),
                "translation": translation,
            }
        )
        if max_rows is not None and len(candidate_rows) >= max_rows:
            break
    if not candidate_rows:
        return [], []

    def _classify_field(text_value: str, *, field_label: str) -> dict[str, Any]:
        cache_key = _picture_dictionary_language_id_cache_key(
            translation_language=translation_language_for_prompt,
            text=text_value,
        )
        cached = cache.get(cache_key)
        if isinstance(cached, dict) and "is_gloss_language" in cached:
            logger.info(
                "Picture-dictionary language-ID cache hit field=%s is_gloss_language=%s text=%r",
                field_label,
                cached.get("is_gloss_language"),
                text_value,
            )
            return cached
        prompt = _picture_dictionary_language_id_prompt(
            translation_language=translation_language_for_prompt,
            translation_label=translation_label,
            field_label=field_label,
            text=text_value,
        )
        client = _build_ai_client(user=user, model_name="gpt-4o-mini")
        payload = asyncio.run(client.chat_json(prompt, model="gpt-4o-mini"))
        result = _picture_dictionary_normalise_language_id_payload(payload)
        cache.set(cache_key, result, timeout=7 * 24 * 60 * 60)
        logger.info(
            "Picture-dictionary language-ID check field=%s is_gloss_language=%s confidence=%s text=%r reason=%r",
            field_label,
            result.get("is_gloss_language"),
            result.get("confidence"),
            text_value,
            result.get("reason"),
        )
        return result

    def _check_candidate(candidate: dict[str, Any]) -> tuple[dict[str, str] | None, dict[str, str]]:
        row_number = int(candidate["row_number"])
        surface = str(candidate["surface"])
        translation = str(candidate["translation"])
        gloss_language_label = "English" if translation_language_for_prompt == "inferred" else translation_label
        try:
            text_result = _classify_field(surface, field_label="word/page text")
            translation_result = _classify_field(translation, field_label="gloss/translation")
            warning, trace = _picture_dictionary_mixup_result_from_language_ids(
                row_number=row_number,
                surface=surface,
                translation=translation,
                text_result=text_result,
                translation_result=translation_result,
                gloss_language_label=gloss_language_label,
            )
            logger.info(
                "Picture-dictionary mix-up check row %s: warning=%s confidence=%s surface=%r translation=%r text_id=%s gloss_id=%s",
                row_number,
                bool(warning),
                (warning or {}).get("confidence"),
                surface,
                translation,
                trace.get("text_language_id"),
                trace.get("gloss_language_id"),
            )
            return warning, trace
        except Exception:
            logger.exception(
                "Picture-dictionary surface/translation mix-up check failed for dictionary %s row %s",
                dictionary.id,
                row_number,
            )
            trace = {
                "row_number": str(row_number),
                "surface": surface,
                "translation": translation,
                "text_language_id": "error",
                "text_language_confidence": "unknown",
                "gloss_language_id": "error",
                "gloss_language_confidence": "unknown",
                "reason": "AI language check failed; see server logs.",
            }
            return None, trace

    warnings: list[dict[str, str]] = []
    traces: list[dict[str, str]] = []
    max_workers = min(8, len(candidate_rows))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_check_candidate, candidate): candidate for candidate in candidate_rows}
        for future in as_completed(futures):
            warning, trace = future.result()
            traces.append(trace)
            if warning is not None:
                warnings.append(warning)
    warnings.sort(key=lambda item: int(item["row_number"]))
    traces.sort(key=lambda item: int(item["row_number"]) if str(item.get("row_number", "")).isdigit() else 0)
    return warnings, traces




def _picture_dictionary_subset_selection_prompt(
    *,
    subset_description: str,
    source_language_label: str,
    translation_language_label: str,
    row: dict[str, str],
) -> str:
    payload = {
        "subset_description": subset_description,
        "source_language": source_language_label,
        "translation_or_gloss_language": translation_language_label,
        "candidate": row,
    }
    return (
        "You are helping a community organiser build a smaller picture-dictionary subset.\n"
        "Decide whether the candidate dictionary entry belongs in the requested subset.\n"
        "For low-resource languages, rely primarily on the gloss/translation field, because the source word may be opaque.\n"
        "Be inclusive when the candidate is a clear semantic match; do not include unrelated entries.\n"
        "Return only JSON with keys include (boolean), confidence (low|medium|high), and reason (short string).\n\n"
        "Subset candidate:\n"
        f"{json.dumps(payload, ensure_ascii=False)}"
    )


def _normalise_subset_selection_payload(payload: Any) -> dict[str, Any]:
    data = payload if isinstance(payload, dict) else {}
    include = _coerce_ai_bool(data.get("include") if "include" in data else data.get("selected"))
    return {
        "include": bool(include),
        "confidence": _normalise_ai_confidence(data.get("confidence")),
        "reason": str(data.get("reason") or "").strip(),
    }


def _picture_dictionary_ai_subset_suggestions(
    *,
    dictionary: PictureDictionary,
    entries: list[PictureDictionaryEntry],
    subset_description: str,
    user: Any | None = None,
) -> tuple[list[int], list[dict[str, str]]]:
    """Use per-entry AI checks to suggest entries for a described dictionary subset."""

    description = str(subset_description or "").strip()
    if not description or not entries or not _ai_available_for_user(user):
        return [], []
    rows = _manual_rows_from_entries(dictionary, entries)
    source_language_label = _project_language_label(dictionary.language or dictionary.project.language)
    translation_language = (dictionary.project.target_language or "").strip()
    translation_language_label = _project_language_label(translation_language) if translation_language else "translation/gloss language"
    candidates: list[dict[str, Any]] = []
    for entry, row in zip(entries, rows, strict=False):
        candidates.append(
            {
                "entry_id": entry.id,
                "surface": str(row.get("surface") or entry.surface or ""),
                "lemma": str(row.get("lemma") or entry.lemma or entry.surface or ""),
                "pos": str(row.get("pos") or entry.pos or ""),
                "gloss": str(row.get("gloss") or ""),
                "translation": str(row.get("translation") or row.get("gloss") or ""),
            }
        )

    def _check_candidate(candidate: dict[str, Any]) -> dict[str, str]:
        prompt = _picture_dictionary_subset_selection_prompt(
            subset_description=description,
            source_language_label=source_language_label,
            translation_language_label=translation_language_label,
            row={
                "surface": candidate["surface"],
                "lemma": candidate["lemma"],
                "pos": candidate["pos"],
                "gloss": candidate["gloss"],
                "translation": candidate["translation"],
            },
        )
        try:
            client = _build_ai_client(user=user, model_name="gpt-4o-mini")
            payload = asyncio.run(client.chat_json(prompt, model="gpt-4o-mini"))
            result = _normalise_subset_selection_payload(payload)
        except Exception:
            logger.exception(
                "Picture-dictionary subset suggestion failed for dictionary %s entry %s",
                dictionary.id,
                candidate["entry_id"],
            )
            result = {"include": False, "confidence": "unknown", "reason": "AI subset suggestion failed; see server logs."}
        return {
            "entry_id": str(candidate["entry_id"]),
            "surface": candidate["surface"],
            "translation": candidate["translation"],
            "include": "1" if result["include"] else "0",
            "confidence": str(result.get("confidence") or "unknown"),
            "reason": str(result.get("reason") or ""),
        }

    traces: list[dict[str, str]] = []
    max_workers = min(8, len(candidates))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_check_candidate, candidate): candidate for candidate in candidates}
        for future in as_completed(futures):
            traces.append(future.result())
    traces.sort(key=lambda row: int(row["entry_id"]) if row.get("entry_id", "").isdigit() else 0)
    selected_ids = [int(row["entry_id"]) for row in traces if row.get("include") == "1"]
    return selected_ids, traces

def _picture_dictionary_surface_translation_mixup_warnings(
    *,
    dictionary: PictureDictionary,
    rows: list[dict[str, str]],
    user: Any | None = None,
    max_rows: int | None = None,
) -> list[dict[str, str]]:
    warnings, _traces = _picture_dictionary_surface_translation_mixup_diagnostics(
        dictionary=dictionary,
        rows=rows,
        user=user,
        max_rows=max_rows,
    )
    return warnings


def _picture_dictionary_existing_mixup_diagnostics(
    *,
    dictionary: PictureDictionary | None,
    user: Any | None = None,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    if dictionary is None:
        return [], []
    try:
        entries = list(dictionary.entries.filter(is_active=True).order_by("id"))
        rows = _manual_rows_from_entries(dictionary, entries)
    except Exception:
        logger.exception("Could not prepare picture-dictionary rows for mix-up check")
        return [], []
    return _picture_dictionary_surface_translation_mixup_diagnostics(dictionary=dictionary, rows=rows, user=user)


def _picture_dictionary_existing_mixup_warnings(
    *,
    dictionary: PictureDictionary | None,
    user: Any | None = None,
) -> list[dict[str, str]]:
    warnings, _traces = _picture_dictionary_existing_mixup_diagnostics(dictionary=dictionary, user=user)
    return warnings



def _default_picture_dictionary_prompt_language(dictionary: PictureDictionary) -> str:
    source_language = (dictionary.language or dictionary.project.language or dictionary.community.language or "").strip()
    if source_language and source_language not in NON_AI_ENABLED_LANGUAGES:
        return source_language
    return (dictionary.project.target_language or source_language or "en").strip()


def _picture_dictionary_workspace_metadata_path(dictionary: PictureDictionary) -> Path:
    return dictionary.project.artifact_dir() / "picture_dictionary_workspace.json"


def _read_picture_dictionary_workspace_metadata(dictionary: PictureDictionary) -> dict[str, Any]:
    path = _picture_dictionary_workspace_metadata_path(dictionary)
    if not path.exists():
        return {"background_information": "", "translation_language": dictionary.project.target_language or "", "generation_prompt_language": _default_picture_dictionary_prompt_language(dictionary), "entry_suggestions": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.exception("Could not read picture dictionary workspace metadata for dictionary %s", dictionary.pk)
        return {"background_information": "", "translation_language": dictionary.project.target_language or "", "generation_prompt_language": _default_picture_dictionary_prompt_language(dictionary), "entry_suggestions": {}}
    if not isinstance(payload, dict):
        return {"background_information": "", "translation_language": dictionary.project.target_language or "", "generation_prompt_language": _default_picture_dictionary_prompt_language(dictionary), "entry_suggestions": {}}
    suggestions = payload.get("entry_suggestions")
    if not isinstance(suggestions, dict):
        suggestions = {}
    return {
        "background_information": str(payload.get("background_information") or ""),
        "translation_language": str(payload.get("translation_language") or dictionary.project.target_language or ""),
        "generation_prompt_language": str(payload.get("generation_prompt_language") or _default_picture_dictionary_prompt_language(dictionary)),
        "entry_suggestions": {str(key): str(value or "") for key, value in suggestions.items()},
    }


def _write_picture_dictionary_workspace_metadata(
    dictionary: PictureDictionary,
    *,
    background_information: str,
    translation_language: str,
    generation_prompt_language: str,
    entry_suggestions: dict[int, str],
) -> None:
    path = _picture_dictionary_workspace_metadata_path(dictionary)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "background_information": str(background_information or "").strip(),
        "translation_language": str(translation_language or "").strip(),
        "generation_prompt_language": str(generation_prompt_language or "").strip(),
        "entry_suggestions": {str(key): str(value or "").strip() for key, value in entry_suggestions.items()},
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")



def _missing_picture_dictionary_info_request(
    *,
    dictionary: PictureDictionary,
    surface: str,
    lemma: str,
    pos: str,
    gloss: str,
    background_information: str,
) -> str:
    payload = {
        "source_language": dictionary.language or dictionary.project.language or dictionary.community.language,
        "gloss_language": dictionary.project.target_language,
        "gloss_language_label": _project_language_label(dictionary.project.target_language),
        "surface_word": surface,
        "current_lemma": lemma,
        "current_pos": pos,
        "current_translation_or_gloss": gloss,
        "background_information": background_information,
    }
    return "\n".join(
        [
            "Fill missing lexical metadata for one picture-dictionary entry.",
            "Return JSON only with string keys: lemma, pos, translation.",
            "Preserve any non-empty current values unless they are clearly malformed.",
            "Use a concise universal POS tag such as NOUN, VERB, ADJ, ADV, PRON, PROPN, NUM, ADP, DET, or INTJ.",
            "If you are not confident, return the best cautious value rather than an explanation.",
            "",
            json.dumps(payload, ensure_ascii=False, indent=2),
        ]
    )


def _generate_missing_picture_dictionary_info(
    *,
    dictionary: PictureDictionary,
    surface: str,
    lemma: str,
    pos: str,
    gloss: str,
    background_information: str,
    user=None,
) -> dict[str, str]:
    request_prompt = _missing_picture_dictionary_info_request(
        dictionary=dictionary,
        surface=surface,
        lemma=lemma,
        pos=pos,
        gloss=gloss,
        background_information=background_information,
    )
    model_name = (dictionary.project.ai_model or DEFAULT_MODEL).strip()
    if model_name not in AI_MODEL_CHOICES:
        model_name = DEFAULT_MODEL
    client = _build_ai_client(model_name=model_name, user=user)
    if hasattr(client, "chat_json"):
        payload = asyncio.run(client.chat_json(request_prompt))
    else:
        raw = asyncio.run(client.chat_text(request_prompt))
        payload = json.loads(normalize_json_text(str(raw or "{}")))
    if not isinstance(payload, dict):
        payload = {}
    return {
        "lemma": str(payload.get("lemma") or lemma or surface).strip(),
        "pos": str(payload.get("pos") or pos or "").strip().upper(),
        "gloss": str(payload.get("translation") or payload.get("gloss") or gloss or "").strip(),
    }



def _picture_dictionary_translation_request(
    *,
    dictionary: PictureDictionary,
    surface: str,
    lemma: str,
    pos: str,
    background_information: str,
) -> str:
    payload = {
        "source_language": dictionary.language or dictionary.project.language or dictionary.community.language,
        "translation_language": dictionary.project.target_language,
        "translation_language_label": _project_language_label(dictionary.project.target_language),
        "surface_word": surface,
        "lemma": lemma,
        "pos": pos,
        "background_information": background_information,
    }
    return "\n".join(
        [
            "Translate one picture-dictionary entry into the requested translation/gloss language.",
            "Use the lemma and POS to disambiguate the surface word. If POS=ADJ, translate the adjectival meaning; if POS=NOUN, translate the noun meaning.",
            "Return JSON only with a single string key: translation.",
            "Return only a concise dictionary-style gloss/translation, not a sentence or explanation.",
            "If the source word is already in the translation language, still return the best translation/gloss in the requested translation language.",
            "",
            json.dumps(payload, ensure_ascii=False, indent=2),
        ]
    )


def _generate_picture_dictionary_translation(
    *,
    dictionary: PictureDictionary,
    surface: str,
    lemma: str,
    pos: str,
    background_information: str,
    user=None,
) -> str:
    request_prompt = _picture_dictionary_translation_request(
        dictionary=dictionary,
        surface=surface,
        lemma=lemma,
        pos=pos,
        background_information=background_information,
    )
    model_name = (dictionary.project.ai_model or DEFAULT_MODEL).strip()
    if model_name not in AI_MODEL_CHOICES:
        model_name = DEFAULT_MODEL
    client = _build_ai_client(model_name=model_name, user=user)
    if hasattr(client, "chat_json"):
        payload = asyncio.run(client.chat_json(request_prompt))
        if isinstance(payload, dict):
            translation = payload.get("translation") or payload.get("gloss")
        else:
            translation = ""
    else:
        translation = asyncio.run(client.chat_text(request_prompt))
    translation_text = str(translation or "").strip()
    if not translation_text:
        raise ValueError("AI translation generation returned an empty translation.")
    return translation_text


def _run_picture_dictionary_fanout(items: list[Any], worker: Callable[[Any], Any], *, max_workers: int = 8) -> list[Any]:
    if not items:
        return []
    workers = max(1, min(max_workers, len(items)))
    if workers == 1:
        return [worker(item) for item in items]
    results: list[Any] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(worker, item) for item in items]
        for future in as_completed(futures):
            results.append(future.result())
    return results

def _unified_picture_dictionary_prompt_request(
    *,
    dictionary: PictureDictionary,
    entry: PictureDictionaryEntry,
    gloss: str,
    suggestion: str,
    background_information: str,
    style_brief: str,
    prompt_language: str,
) -> str:
    prompt_language_label = _project_language_label(prompt_language) if prompt_language else "the requested prompt language"
    payload = {
        "community": dictionary.community.name,
        "source_language": dictionary.language or dictionary.project.language or dictionary.community.language,
        "gloss_language": dictionary.project.target_language,
        "gloss_language_label": _project_language_label(dictionary.project.target_language),
        "surface_word": (entry.surface or "").strip(),
        "lemma": (entry.lemma or "").strip(),
        "pos": (entry.pos or "").strip(),
        "gloss_or_translation": str(gloss or "").strip(),
        "organiser_suggestion": str(suggestion or "").strip(),
        "background_information": str(background_information or "").strip(),
        "style_brief": str(style_brief or "").strip(),
        "generation_prompt_language": prompt_language,
        "generation_prompt_language_label": prompt_language_label,
    }
    return "\n".join(
        [
            "You are writing the final image-generation prompt for one entry in a picture dictionary.",
            "Use the JSON context below to create a concrete, editable prompt that tells the image model what to draw.",
            "The output must be a vivid but concise prompt, not a restatement of the metadata.",
            "Make concrete choices about the scene, subject, pose, and visual focus when the metadata allows it.",
            "Use POS and gloss/translation to disambiguate the surface word; for example, if the word is an adjective meaning pink, depict the colour pink rather than a rose flower.",
            "Do not invent culturally specific details that are not supplied in the context.",
            "The image must contain no written words, labels, captions, letters, numbers, or readable text.",
            f"Write the final image-generation prompt in {prompt_language_label}. Use that same language consistently across all selected rows.",
            "Return only the final prompt text, with no markdown, no JSON, and no explanation.",
            "",
            json.dumps(payload, ensure_ascii=False, indent=2),
        ]
    )


def _build_unified_picture_dictionary_prompt(
    *,
    dictionary: PictureDictionary,
    entry: PictureDictionaryEntry,
    gloss: str,
    suggestion: str,
    background_information: str,
    style_brief: str,
    prompt_language: str = "",
    user=None,
) -> str:
    request_prompt = _unified_picture_dictionary_prompt_request(
        dictionary=dictionary,
        entry=entry,
        gloss=gloss,
        suggestion=suggestion,
        background_information=background_information,
        style_brief=style_brief,
        prompt_language=prompt_language or _default_picture_dictionary_prompt_language(dictionary),
    )
    model_name = (dictionary.project.ai_model or DEFAULT_MODEL).strip()
    if model_name not in AI_MODEL_CHOICES:
        model_name = DEFAULT_MODEL
    client = _build_ai_client(model_name=model_name, user=user)
    generated = asyncio.run(client.chat_text(request_prompt))
    prompt = str(generated or "").strip()
    if not prompt:
        raise ValueError("AI prompt construction returned an empty prompt.")
    return prompt


def _select_latest_generated_variants_for_pages(pages: list[ProjectImagePage]) -> int:
    selected = 0
    for page in pages:
        latest_variant = page.variants.exclude(image_path="").order_by("-variant_index", "-id").first()
        if not latest_variant:
            continue
        _set_page_preferred_variant(page, latest_variant)
        selected += 1
    return selected


def _page_review_context_rows(project: Project, pages: list[ProjectImagePage]) -> dict[int, dict[str, str]]:
    source_pages = _extract_project_source_pages(project)
    translation_pages = _extract_project_pages_from_translation(project)
    context_by_page: dict[int, dict[str, str]] = {}
    for page in pages:
        source_text = source_pages[page.page_number - 1] if page.page_number <= len(source_pages) else ""
        translation_text = translation_pages[page.page_number - 1] if page.page_number <= len(translation_pages) else ""
        if not source_text and project.page_image_text_source != Project.PAGE_IMAGE_TEXT_SOURCE_TRANSLATION:
            source_text = page.page_text
        # Do not mirror page_text into translation_text when translation stage is empty.
        # In translation-driven workflows (e.g. low-resource dictionaries), page_text may
        # already hold source or prompt text and mirroring it here makes the review UI
        # misleading by showing source==translation.
        context_by_page[page.id] = {
            "source_text": source_text,
            "translation_text": translation_text,
        }
    return context_by_page


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
    page_context = _page_review_context_rows(project, pages)
    page_rows = [
        {
            "page": page,
            "source_text": page_context.get(page.id, {}).get("source_text", ""),
            "translation_text": page_context.get(page.id, {}).get("translation_text", ""),
            "variant_rows": [{"variant": variant, "vote": existing_votes.get(variant.id)} for variant in page.variants.all()],
        }
        for page in pages
    ]
    show_mode = (request.GET.get("show") or "unjudged").strip().lower()
    if show_mode not in {"all", "unjudged"}:
        show_mode = "unjudged"
    unjudged_count = 0
    for row in page_rows:
        row_unjudged = 0
        for vr in row["variant_rows"]:
            if not vr["vote"] or vr["vote"].value not in {CommunityImageVote.VALUE_UP, CommunityImageVote.VALUE_DOWN}:
                row_unjudged += 1
        row["unjudged_count"] = row_unjudged
        if row_unjudged > 0:
            unjudged_count += 1
    if show_mode == "unjudged":
        page_rows = [row for row in page_rows if row.get("unjudged_count", 0) > 0]
    return render(
        request,
        "projects/community_member_judge_project.html",
        {
            "community": membership.community,
            "membership": membership,
            "project": project,
            "page_rows": page_rows,
            "show_mode": show_mode,
            "unjudged_page_count": unjudged_count,
            "total_page_count": len(pages),
        },
    )


@login_required
def community_organiser_home(request: HttpRequest, community_id: int) -> HttpResponse:
    membership = _require_community_member(community_id, request.user)
    if membership.role != CommunityMembership.ROLE_ORGANISER:
        raise Http404()
    community = membership.community
    projects = list(Project.objects.filter(community_id=community_id).order_by("-updated_at"))
    community_memberships = list(
        CommunityMembership.objects.filter(community_id=community_id)
        .select_related("user")
        .order_by("role", "user__username")
    )
    community_membership_form = CommunityOrganiserMembershipForm(community=community)
    picture_dictionary = (
        PictureDictionary.objects.select_related("project")
        .filter(community_id=community_id, is_active=True)
        .first()
    )
    if picture_dictionary is None:
        picture_dictionary = ensure_picture_dictionary_for_community(community=community, organiser=request.user)
    dictionary_entries: list[PictureDictionaryEntry] = []
    picture_dictionary_entry_count = 0
    picture_dictionary_subsets: list[dict[str, Any]] = []
    picture_dictionary_subset_project_id_set: set[int] = set()
    picture_dictionary_background_information = ""
    picture_dictionary_entry_suggestions: dict[str, str] = {}
    picture_dictionary_translation_language = ""
    picture_dictionary_generation_prompt_language = ""
    if picture_dictionary:
        workspace_metadata = _read_picture_dictionary_workspace_metadata(picture_dictionary)
        picture_dictionary_background_information = workspace_metadata["background_information"]
        picture_dictionary_entry_suggestions = workspace_metadata["entry_suggestions"]
        picture_dictionary_translation_language = workspace_metadata.get("translation_language") or picture_dictionary.project.target_language or ""
        picture_dictionary_generation_prompt_language = workspace_metadata.get("generation_prompt_language") or _default_picture_dictionary_prompt_language(picture_dictionary)
    subset_edit_session_key = f"community:{community_id}:picture_dictionary_subset_edit"
    subset_draft_session_key = f"community:{community_id}:picture_dictionary_subset_draft"
    subset_edit_id = str(request.session.get(subset_edit_session_key) or "")
    subset_draft = request.session.get(subset_draft_session_key)
    if not isinstance(subset_draft, dict):
        subset_draft = {}
    picture_dictionary_subset_edit: dict[str, Any] | None = None
    picture_dictionary_subset_selected_entry_ids: set[int] = {
        int(entry_id)
        for entry_id in subset_draft.get("selected_entry_ids", [])
        if str(entry_id).isdigit()
    }
    picture_dictionary_subset_form = {
        "title": str(subset_draft.get("title") or ""),
        "description": str(subset_draft.get("description") or ""),
        "selection_note": str(subset_draft.get("selection_note") or ""),
    }
    if picture_dictionary:
        picture_dictionary_subsets = list_picture_dictionary_subsets(picture_dictionary)
        picture_dictionary_subset_project_id_set = {
            int(row["project_id"])
            for row in picture_dictionary_subsets
            if row.get("project_id")
        }
        if subset_edit_id:
            picture_dictionary_subset_edit = get_picture_dictionary_subset(picture_dictionary, subset_edit_id)
            if picture_dictionary_subset_edit:
                picture_dictionary_subset_selected_entry_ids = {
                    int(entry_id)
                    for entry_id in picture_dictionary_subset_edit.get("entry_ids", [])
                    if str(entry_id).isdigit()
                }
                picture_dictionary_subset_form = {
                    "title": str(picture_dictionary_subset_edit.get("title") or ""),
                    "description": str(picture_dictionary_subset_edit.get("description") or ""),
                    "selection_note": str(picture_dictionary_subset_edit.get("selection_note") or ""),
                }
            else:
                request.session.pop(subset_edit_session_key, None)
                subset_edit_id = ""
    if picture_dictionary:
        dictionary_entries = list(picture_dictionary.entries.filter(is_active=True))
        dictionary_entries.sort(
            key=lambda entry: (
                str(entry.surface or "").casefold(),
                str(entry.lemma or "").casefold(),
                str(entry.pos or "").casefold(),
                entry.id,
            )
        )
        rows_by_entry_id = {
            entry.id: row
            for entry, row in zip(dictionary_entries, _manual_rows_from_entries(picture_dictionary, dictionary_entries), strict=False)
        }
        image_pages_by_number = {
            page.page_number: page
            for page in picture_dictionary.project.image_pages.order_by("page_number", "id")
        }
        for entry in dictionary_entries:
            lemma = (entry.lemma or entry.surface or "").strip()
            pos = (entry.pos or "UNSPECIFIED").strip().upper()
            entry.display_label = f"{(entry.surface or '').strip()} (lemma: {lemma}) [{pos}]"
            row = rows_by_entry_id.get(entry.id, {})
            entry.subset_translation_label = str(row.get("translation") or row.get("gloss") or "").strip()
            page = image_pages_by_number.get(entry.current_page_number or 0)
            entry.unified_surface = str(row.get("surface") or entry.surface or "").strip()
            entry.unified_lemma = str(row.get("lemma") or entry.lemma or entry.surface or "").strip()
            entry.unified_pos = str(row.get("pos") or entry.pos or "").strip()
            entry.unified_gloss = str(row.get("gloss") or row.get("translation") or "").strip()
            entry.unified_prompt = str(getattr(page, "generation_prompt", "") or entry.surface or "").strip()
            entry.unified_suggestion = picture_dictionary_entry_suggestions.get(str(entry.id), "")
            entry.unified_image_path = str((entry.image_path or getattr(page, "image_path", "") or "")).strip()
            prompt_is_missing = not entry.unified_prompt
            if not entry.unified_image_path and entry.unified_prompt.casefold() == entry.unified_surface.casefold():
                prompt_is_missing = True
            entry.unified_incomplete = not (
                entry.unified_lemma
                and entry.unified_pos
                and entry.unified_gloss
                and not prompt_is_missing
                and entry.unified_image_path
            )
    picture_dictionary_entry_count = len(dictionary_entries)
    picture_dictionary_exercise_sets = _latest_exercise_sets_for_project(picture_dictionary.project if picture_dictionary else None)
    if picture_dictionary_subsets:
        entries_by_id = {entry.id: entry for entry in dictionary_entries}
        for subset in picture_dictionary_subsets:
            subset["exercise_sets"] = _latest_exercise_sets_for_project(subset.get("project"))
            preview_entries = []
            for entry_id in subset.get("entry_ids", []):
                entry = entries_by_id.get(int(entry_id)) if str(entry_id).isdigit() else None
                if not entry:
                    continue
                preview_entries.append(
                    {
                        "surface": entry.unified_surface,
                        "gloss": entry.unified_gloss,
                        "image_path": entry.unified_image_path,
                    }
                )
            subset["preview_entries"] = preview_entries
    picture_dictionary_has_exercise_sets = bool(picture_dictionary_exercise_sets) or any(
        bool(subset.get("exercise_sets")) for subset in picture_dictionary_subsets
    )

    picture_dictionary_compile_info: dict[str, Any] | None = None
    picture_dictionary_style_brief = ""
    if picture_dictionary:
        style = getattr(picture_dictionary.project, "image_style", None)
        picture_dictionary_style_brief = ((style.style_brief or "").strip() if style else "")
        seg1_run = picture_dictionary.project.artifact_dir() / "runs" / "run_picture_dictionary"
        seg1_path = stage_artifact_path(seg1_run, "segmentation_phase_1")
        if seg1_path.exists():
            try:
                payload = read_stage_artifact(seg1_run, "segmentation_phase_1")
            except Exception:
                payload = {}
            picture_dictionary_compile_info = {
                "updated_at": datetime.fromtimestamp(seg1_path.stat().st_mtime, tz=timezone.utc).isoformat(),
                "entry_count": int(((payload.get("metadata") or {}).get("entry_count") or 0)),
            }

    low_resource_languages = {"xkk", "iai", "dre"}
    low_resource_mode_recommended = (community.language or "").strip().lower() in low_resource_languages
    low_resource_missing_rows = 0
    low_resource_missing_row_details: list[str] = []
    picture_dictionary_pending_image_count = 0
    low_resource_pending_session_key = f"community:{community_id}:pending_low_resource_rows"
    pending_low_resource_rows = request.session.get(low_resource_pending_session_key)
    if not isinstance(pending_low_resource_rows, list):
        pending_low_resource_rows = []
    low_resource_source_label = _project_language_label(community.language)
    low_resource_gloss_label = ""
    if picture_dictionary:
        low_resource_source_label = _project_language_label(
            picture_dictionary.language or picture_dictionary.project.language or community.language
        )
        target_language = (picture_dictionary.project.target_language or "").strip()
        if target_language and target_language != (picture_dictionary.project.language or "").strip():
            low_resource_gloss_label = _project_language_label(target_language)
        else:
            low_resource_gloss_label = ""
    low_resource_entry_rows = []
    display_rows = pending_low_resource_rows[:]
    display_row_count = max(8, len(display_rows))
    for idx in range(display_row_count):
        row = display_rows[idx] if idx < len(display_rows) and isinstance(display_rows[idx], dict) else {}
        low_resource_entry_rows.append(
            {
                "row_number": idx + 1,
                "surface": str(row.get("surface") or ""),
                "lemma": str(row.get("lemma") or ""),
                "pos": str(row.get("pos") or ""),
                "gloss": str(row.get("gloss") or ""),
            }
        )
    low_resource_mixup_confirmation_required = bool(pending_low_resource_rows)
    if picture_dictionary:
        image_path_by_page_number = {
            row.page_number: (row.image_path or "").strip()
            for row in picture_dictionary.project.image_pages.order_by("page_number", "id")
        }
        picture_dictionary_pending_image_count = 0
        for idx, entry in enumerate(dictionary_entries, start=1):
            entry_image_path = (entry.image_path or "").strip()
            page_image_path = image_path_by_page_number.get(entry.current_page_number or idx, "")
            if not entry_image_path and not page_image_path:
                picture_dictionary_pending_image_count += 1
        try:
            _rows = _manual_rows_from_entries(picture_dictionary, dictionary_entries)
            for idx, row in enumerate(_rows, start=1):
                gloss = str(row.get("gloss") or "").strip()
                translation = str(row.get("translation") or "").strip()
                if gloss and translation:
                    continue
                low_resource_missing_rows += 1
                low_resource_missing_row_details.append(
                    f"row={idx} surface='{str(row.get('surface') or '').strip()}' "
                    f"lemma='{str(row.get('lemma') or '').strip()}' pos='{str(row.get('pos') or '').strip()}' "
                    f"missing={'gloss' if not gloss else ''}{'+' if (not gloss and not translation) else ''}{'translation' if not translation else ''} "
                    f"gloss='{gloss}' translation='{translation}'"
                )
        except Exception:
            low_resource_missing_rows = 0
            low_resource_missing_row_details = []

    if request.method == "POST":
        membership_action = (request.POST.get("community_membership_action") or "").strip()
        if membership_action == "add_member":
            community_membership_form = CommunityOrganiserMembershipForm(request.POST, community=community)
            if community_membership_form.is_valid():
                user_obj = community_membership_form.cleaned_data["user"]
                membership_obj, created = CommunityMembership.objects.get_or_create(
                    community=community,
                    user=user_obj,
                    defaults={"role": CommunityMembership.ROLE_MEMBER},
                )
                if created:
                    messages.success(request, f"Added {user_obj.username} as a member of {community.name}.")
                else:
                    messages.info(request, f"{user_obj.username} is already in {community.name} as {membership_obj.role}.")
                return redirect("community-organiser-home", community_id=community_id)
        elif membership_action == "remove_member":
            membership_id_raw = (request.POST.get("membership_id") or "").strip()
            try:
                membership_id = int(membership_id_raw)
            except ValueError:
                membership_id = 0
            target_membership = (
                CommunityMembership.objects.filter(id=membership_id, community=community)
                .select_related("user")
                .first()
            )
            if not target_membership:
                messages.error(request, "Please choose a valid community member to remove.")
            elif target_membership.user_id == request.user.id:
                messages.error(request, "You cannot remove your own organiser membership.")
            elif target_membership.role == CommunityMembership.ROLE_ORGANISER:
                messages.error(request, "Organiser memberships can only be changed by platform admins.")
            else:
                username = target_membership.user.username
                target_membership.delete()
                messages.success(request, f"Removed {username} from {community.name}.")
                return redirect("community-organiser-home", community_id=community_id)

        action = (request.POST.get("picture_dictionary_action") or "").strip()
        if action:
            if action == "import_from_project":
                source_project_id_raw = (request.POST.get("source_project_id") or "").strip()
                try:
                    source_project_id = int(source_project_id_raw)
                except ValueError:
                    source_project_id = 0
                source_project = next((row for row in projects if row.id == source_project_id), None)
                if not source_project:
                    messages.error(request, "Please choose a valid community project to import as a picture dictionary.")
                else:
                    try:
                        picture_dictionary, summary = import_project_as_picture_dictionary(
                            community=community,
                            organiser=request.user,
                            source_project=source_project,
                        )
                    except ValueError as exc:
                        messages.error(request, str(exc))
                    except PermissionDenied:
                        raise Http404()
                    else:
                        messages.success(
                            request,
                            "Imported “%s” as a picture dictionary copy with %s entr%s."
                            % (
                                source_project.title,
                                summary.get("entries_created", 0),
                                "y" if summary.get("entries_created") == 1 else "ies",
                            ),
                        )
                        for diagnostic in summary.get("diagnostics", []):
                            messages.info(request, str(diagnostic))
                return redirect("community-organiser-home", community_id=community_id)

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
            elif action == "sync_placeholders":
                _refresh_dictionary_placeholder_stages(picture_dictionary)
                messages.success(
                    request,
                    "Dictionary stages synced. Existing annotations were preserved; placeholders were added only for new/missing entries.",
                )
            elif action == "load_subset":
                selected_subset_id = (request.POST.get("subset_id") or "").strip()
                subset = get_picture_dictionary_subset(picture_dictionary, selected_subset_id)
                if not subset:
                    messages.error(request, "Please choose a saved subset project to edit.")
                else:
                    request.session[subset_edit_session_key] = selected_subset_id
                    request.session.pop(subset_draft_session_key, None)
                    request.session.modified = True
                    messages.info(request, f"Loaded subset “{subset['title']}” for editing.")
            elif action == "clear_subset_edit":
                request.session.pop(subset_edit_session_key, None)
                request.session.pop(subset_draft_session_key, None)
                messages.info(request, "Cleared subset edit selection.")
            elif action == "suggest_subset":
                subset_title = (request.POST.get("subset_title") or "").strip()
                subset_description = (request.POST.get("subset_description") or "").strip()
                subset_note = (request.POST.get("subset_selection_note") or "").strip()
                selection_description = subset_note or subset_description or subset_title
                if not selection_description:
                    messages.error(request, "Enter a subset description or selection note before asking AI to suggest entries.")
                elif not _ai_available_for_user(request.user):
                    messages.error(request, "AI subset suggestions need an OpenAI API key or a user profile API key.")
                else:
                    selected_ids, traces = _picture_dictionary_ai_subset_suggestions(
                        dictionary=picture_dictionary,
                        entries=dictionary_entries,
                        subset_description=selection_description,
                        user=request.user,
                    )
                    request.session.pop(subset_edit_session_key, None)
                    request.session[subset_draft_session_key] = {
                        "title": subset_title,
                        "description": subset_description,
                        "selection_note": subset_note,
                        "selected_entry_ids": selected_ids,
                    }
                    request.session.modified = True
                    messages.success(
                        request,
                        f"AI subset prefill complete: suggested {len(selected_ids)} dictionary entr{'y' if len(selected_ids) == 1 else 'ies'} for the subset. Please review the checked entries before saving.",
                    )
                    for trace in traces[:12]:
                        if trace.get("include") == "1":
                            messages.info(
                                request,
                                "Subset suggestion: selected ‘%(surface)s’ (%(translation)s), confidence=%(confidence)s. %(reason)s"
                                % {
                                    "surface": trace.get("surface", ""),
                                    "translation": trace.get("translation", ""),
                                    "confidence": trace.get("confidence", "unknown"),
                                    "reason": trace.get("reason", ""),
                                },
                            )
            elif action in {"update_unified_entries", "generate_unified_prompts", "generate_unified_images", "generate_unified_missing_info", "generate_unified_translations"}:
                active_entries = list(picture_dictionary.entries.filter(is_active=True).order_by("id"))
                rows: list[dict[str, str]] = []
                prompts_by_entry_id: dict[int, str] = {}
                suggestions_by_entry_id: dict[int, str] = {}
                selected_entry_ids = {int(value) for value in request.POST.getlist("unified_selected_entry_id") if str(value).isdigit()}
                background_information = (request.POST.get("picture_dictionary_background_information") or "").strip()
                translation_language = (request.POST.get("picture_dictionary_translation_language") or picture_dictionary.project.target_language or "").strip()
                generation_prompt_language = (request.POST.get("picture_dictionary_generation_prompt_language") or _default_picture_dictionary_prompt_language(picture_dictionary)).strip()
                style_brief = (request.POST.get("picture_dictionary_style_brief") or "").strip()
                for entry in active_entries:
                    surface = (request.POST.get(f"unified_surface_{entry.id}") or entry.surface or "").strip()
                    lemma = (request.POST.get(f"unified_lemma_{entry.id}") or surface).strip()
                    pos = (request.POST.get(f"unified_pos_{entry.id}") or "").strip()
                    gloss = (request.POST.get(f"unified_gloss_{entry.id}") or "").strip()
                    prompt = (request.POST.get(f"unified_prompt_{entry.id}") or "").strip()
                    suggestion = (request.POST.get(f"unified_suggestion_{entry.id}") or "").strip()
                    if not surface:
                        messages.error(request, "Every active dictionary entry needs a surface word before saving the unified view.")
                        return redirect("community-organiser-home", community_id=community_id)
                    rows.append({"id": str(entry.id), "surface": surface, "lemma": lemma, "pos": pos, "gloss": gloss})
                    prompts_by_entry_id[entry.id] = prompt
                    suggestions_by_entry_id[entry.id] = suggestion
                _write_picture_dictionary_workspace_metadata(
                    picture_dictionary,
                    background_information=background_information,
                    translation_language=translation_language,
                    generation_prompt_language=generation_prompt_language,
                    entry_suggestions=suggestions_by_entry_id,
                )
                style, _created_style = ProjectImageStyle.objects.get_or_create(
                    project=picture_dictionary.project,
                    defaults={"ai_model": picture_dictionary.project.ai_model or DEFAULT_MODEL},
                )
                if translation_language and picture_dictionary.project.target_language != translation_language[:16]:
                    picture_dictionary.project.target_language = translation_language[:16]
                    picture_dictionary.project.save(update_fields=["target_language", "updated_at"])
                    subset_ids = picture_dictionary_subset_project_ids(picture_dictionary)
                    if subset_ids:
                        Project.objects.filter(id__in=subset_ids).update(target_language=translation_language[:16], updated_at=django_timezone.now())
                if style_brief and style.style_brief != style_brief:
                    style.style_brief = style_brief
                    style.save(update_fields=["style_brief", "updated_at"])
                result = picture_dictionary_update_entry_metadata(dictionary=picture_dictionary, rows=rows)
                refreshed_entries = list(picture_dictionary.entries.filter(is_active=True).order_by("id"))
                refreshed_by_id = {entry.id: entry for entry in refreshed_entries}
                pages_by_number = {
                    page.page_number: page
                    for page in picture_dictionary.project.image_pages.order_by("page_number", "id")
                }
                prompt_updates = 0
                for entry in refreshed_entries:
                    prompt = prompts_by_entry_id.get(entry.id, "").strip()
                    if not prompt:
                        continue
                    page = pages_by_number.get(entry.current_page_number or 0)
                    if page and page.generation_prompt != prompt:
                        page.generation_prompt = prompt
                        page.save(update_fields=["generation_prompt", "updated_at"])
                        prompt_updates += 1
                messages.success(
                    request,
                    "Saved unified dictionary view: %(submitted)s entr%(entry_suffix)s synchronized to dictionary stages; %(prompt_updates)s image prompt%(prompt_suffix)s updated."
                    % {
                        "submitted": result["submitted"],
                        "entry_suffix": "y" if result["submitted"] == 1 else "ies",
                        "prompt_updates": prompt_updates,
                        "prompt_suffix": "" if prompt_updates == 1 else "s",
                    },
                )
                if action in {"generate_unified_prompts", "generate_unified_images", "generate_unified_missing_info", "generate_unified_translations"} and not selected_entry_ids:
                    messages.error(request, "Select at least one dictionary row before creating prompts, images, translations, or missing information.")
                if action == "generate_unified_missing_info" and selected_entry_ids:
                    rows_by_id = {int(row["id"]): row for row in rows if str(row.get("id") or "").isdigit()}
                    missing_info_jobs = [
                        (entry_id, rows_by_id[entry_id])
                        for entry_id in selected_entry_ids
                        if entry_id in rows_by_id and not (rows_by_id[entry_id].get("lemma") and rows_by_id[entry_id].get("pos") and rows_by_id[entry_id].get("gloss"))
                    ]

                    def _missing_info_worker(job):
                        entry_id, row = job
                        generated_info = _generate_missing_picture_dictionary_info(
                            dictionary=picture_dictionary,
                            surface=row.get("surface", ""),
                            lemma=row.get("lemma", ""),
                            pos=row.get("pos", ""),
                            gloss=row.get("gloss", ""),
                            background_information=background_information,
                            user=request.user,
                        )
                        return entry_id, generated_info

                    filled_count = 0
                    try:
                        missing_info_results = _run_picture_dictionary_fanout(missing_info_jobs, _missing_info_worker)
                    except Exception as exc:
                        logger.exception("Unified picture-dictionary missing-info fan-out failed")
                        messages.error(request, f"Could not create missing lexical information for selected rows: {exc}")
                        missing_info_results = []
                    for entry_id, generated_info in missing_info_results:
                        row = rows_by_id.get(entry_id)
                        if not row:
                            continue
                        row["lemma"] = row.get("lemma") or generated_info["lemma"]
                        row["pos"] = row.get("pos") or generated_info["pos"]
                        row["gloss"] = row.get("gloss") or generated_info["gloss"]
                        filled_count += 1
                    if filled_count:
                        picture_dictionary_update_entry_metadata(dictionary=picture_dictionary, rows=rows)
                        messages.success(request, f"Created missing lemma/POS/translation information for {filled_count} selected dictionary row(s).")
                    else:
                        messages.info(request, "No selected rows needed missing lemma/POS/translation information.")

                    refreshed_entries = list(picture_dictionary.entries.filter(is_active=True).order_by("id"))
                    refreshed_by_id = {entry.id: entry for entry in refreshed_entries}
                    pages_by_number = {
                        page.page_number: page
                        for page in picture_dictionary.project.image_pages.order_by("page_number", "id")
                    }
                    rows_by_entry_id = {
                        entry.id: row
                        for entry, row in zip(
                            refreshed_entries,
                            _manual_rows_from_entries(picture_dictionary, refreshed_entries),
                            strict=False,
                        )
                    }
                    missing_prompt_jobs = []
                    for entry_id in selected_entry_ids:
                        entry = refreshed_by_id.get(entry_id)
                        if not entry:
                            continue
                        page = pages_by_number.get(entry.current_page_number or 0)
                        if not page:
                            continue
                        current_prompt = (page.generation_prompt or "").strip()
                        has_existing_image = bool((entry.image_path or page.image_path or "").strip())
                        surface_only_prompt = current_prompt.casefold() == (entry.surface or "").strip().casefold()
                        if current_prompt and (has_existing_image or not surface_only_prompt):
                            continue
                        missing_prompt_jobs.append((entry, page, rows_by_entry_id.get(entry.id, {})))

                    def _prompt_worker(job):
                        entry, page, row = job
                        generated_prompt = _build_unified_picture_dictionary_prompt(
                            dictionary=picture_dictionary,
                            entry=entry,
                            gloss=str(row.get("gloss") or row.get("translation") or "").strip(),
                            suggestion=suggestions_by_entry_id.get(entry.id, ""),
                            background_information=background_information,
                            style_brief=style_brief or style.style_brief,
                            prompt_language=generation_prompt_language,
                            user=request.user,
                        )
                        return entry.id, page.id, generated_prompt

                    missing_prompt_count = 0
                    try:
                        missing_prompt_results = _run_picture_dictionary_fanout(missing_prompt_jobs, _prompt_worker)
                    except Exception as exc:
                        logger.exception("Unified picture-dictionary missing prompt fan-out failed")
                        messages.error(request, f"Could not create missing image prompts for selected rows: {exc}")
                        missing_prompt_results = []
                    for entry_id, page_id, generated_prompt in missing_prompt_results:
                        page = ProjectImagePage.objects.get(id=page_id)
                        page.generation_prompt = generated_prompt
                        page.save(update_fields=["generation_prompt", "updated_at"])
                        prompts_by_entry_id[entry_id] = generated_prompt
                        missing_prompt_count += 1
                    if missing_prompt_count:
                        messages.success(request, f"Created missing image-generation prompts for {missing_prompt_count} selected dictionary row(s).")

                    pages_by_number = {
                        page.page_number: page
                        for page in picture_dictionary.project.image_pages.order_by("page_number", "id")
                    }
                    missing_image_requests: list[tuple[ProjectImagePage, int, str]] = []
                    for entry_id in selected_entry_ids:
                        entry = refreshed_by_id.get(entry_id)
                        if not entry:
                            continue
                        page = pages_by_number.get(entry.current_page_number or 0)
                        if not page or (entry.image_path or page.image_path or "").strip():
                            continue
                        missing_image_requests.append((page, 1, page.generation_prompt or prompts_by_entry_id.get(entry.id, "")))
                    if missing_image_requests:
                        try:
                            generated = _generate_requested_page_variants(
                                project=picture_dictionary.project,
                                image_model=style.sample_image_model or "gpt-image-1",
                                requests=missing_image_requests,
                            )
                        except Exception as exc:
                            logger.exception("Unified picture-dictionary missing image generation failed for dictionary %s", picture_dictionary.pk)
                            messages.error(request, f"Could not create missing selected dictionary images: {exc}")
                        else:
                            selected_pages = [page for page, _count, _prompt in missing_image_requests]
                            preferred_updates = _select_latest_generated_variants_for_pages(selected_pages)
                            synced_entries = _sync_entry_image_paths_from_pages(picture_dictionary, refreshed_entries)
                            messages.success(
                                request,
                                "Created %(generated)s missing image variant%(image_suffix)s; selected %(preferred)s latest image%(preferred_suffix)s and synchronized %(synced)s entr%(entry_suffix)s with image paths."
                                % {
                                    "generated": generated,
                                    "image_suffix": "" if generated == 1 else "s",
                                    "preferred": preferred_updates,
                                    "preferred_suffix": "" if preferred_updates == 1 else "s",
                                    "synced": synced_entries,
                                    "entry_suffix": "y" if synced_entries == 1 else "ies",
                                },
                            )
                    else:
                        messages.info(request, "No selected rows needed missing images.")
                if action == "generate_unified_prompts" and selected_entry_ids:
                    rows_by_entry_id = {
                        entry.id: row
                        for entry, row in zip(
                            refreshed_entries,
                            _manual_rows_from_entries(picture_dictionary, refreshed_entries),
                            strict=False,
                        )
                    }
                    prompt_jobs = []
                    for entry_id in selected_entry_ids:
                        entry = refreshed_by_id.get(entry_id)
                        if not entry:
                            continue
                        page = pages_by_number.get(entry.current_page_number or 0)
                        if not page:
                            continue
                        prompt_jobs.append((entry, page, rows_by_entry_id.get(entry.id, {})))

                    def _selected_prompt_worker(job):
                        entry, page, row = job
                        generated_prompt = _build_unified_picture_dictionary_prompt(
                            dictionary=picture_dictionary,
                            entry=entry,
                            gloss=str(row.get("gloss") or row.get("translation") or "").strip(),
                            suggestion=suggestions_by_entry_id.get(entry.id, ""),
                            background_information=background_information,
                            style_brief=style_brief or style.style_brief,
                            prompt_language=generation_prompt_language,
                            user=request.user,
                        )
                        return entry.id, page.id, generated_prompt

                    prompt_count = 0
                    try:
                        prompt_results = _run_picture_dictionary_fanout(prompt_jobs, _selected_prompt_worker)
                    except Exception as exc:
                        logger.exception("Unified picture-dictionary prompt fan-out failed")
                        messages.error(request, f"Could not create AI image prompts for selected rows: {exc}")
                        prompt_results = []
                    for entry_id, page_id, generated_prompt in prompt_results:
                        page = ProjectImagePage.objects.get(id=page_id)
                        if page.generation_prompt != generated_prompt:
                            page.generation_prompt = generated_prompt
                            page.save(update_fields=["generation_prompt", "updated_at"])
                        prompts_by_entry_id[entry_id] = generated_prompt
                        prompt_count += 1
                    if prompt_count:
                        messages.success(request, f"Created AI image-generation prompts for {prompt_count} selected dictionary row(s).")
                if action == "generate_unified_translations" and selected_entry_ids:
                    rows_by_id = {int(row["id"]): row for row in rows if str(row.get("id") or "").isdigit()}
                    translation_jobs = [
                        (entry_id, rows_by_id[entry_id])
                        for entry_id in selected_entry_ids
                        if entry_id in rows_by_id
                    ]

                    def _translation_worker(job):
                        entry_id, row = job
                        translation = _generate_picture_dictionary_translation(
                            dictionary=picture_dictionary,
                            surface=row.get("surface", ""),
                            lemma=row.get("lemma", ""),
                            pos=row.get("pos", ""),
                            background_information=background_information,
                            user=request.user,
                        )
                        return entry_id, translation

                    translation_count = 0
                    try:
                        translation_results = _run_picture_dictionary_fanout(translation_jobs, _translation_worker)
                    except Exception as exc:
                        logger.exception("Unified picture-dictionary translation fan-out failed")
                        messages.error(request, f"Could not create translations for selected rows: {exc}")
                        translation_results = []
                    for entry_id, translation in translation_results:
                        row = rows_by_id.get(entry_id)
                        if not row:
                            continue
                        row["gloss"] = translation
                        translation_count += 1
                    if translation_count:
                        picture_dictionary_update_entry_metadata(dictionary=picture_dictionary, rows=rows)
                        refreshed_entries = list(picture_dictionary.entries.filter(is_active=True).order_by("id"))
                        refreshed_by_id = {entry.id: entry for entry in refreshed_entries}
                        pages_by_number = {
                            page.page_number: page
                            for page in picture_dictionary.project.image_pages.order_by("page_number", "id")
                        }
                        messages.success(request, f"Created translations for {translation_count} selected dictionary row(s).")
                    else:
                        messages.info(request, "No translations were created for the selected rows.")
                if action == "generate_unified_images" and selected_entry_ids:
                    pages_by_number = {
                        page.page_number: page
                        for page in picture_dictionary.project.image_pages.order_by("page_number", "id")
                    }
                    requests_for_generation: list[tuple[ProjectImagePage, int, str]] = []
                    for entry_id in selected_entry_ids:
                        entry = refreshed_by_id.get(entry_id)
                        if not entry:
                            continue
                        page = pages_by_number.get(entry.current_page_number or 0)
                        if page:
                            requests_for_generation.append((page, 1, page.generation_prompt or prompts_by_entry_id.get(entry.id, "")))
                    if not requests_for_generation:
                        messages.error(request, "No selected dictionary rows have project pages available for image generation.")
                    else:
                        try:
                            generated = _generate_requested_page_variants(
                                project=picture_dictionary.project,
                                image_model=style.sample_image_model or "gpt-image-1",
                                requests=requests_for_generation,
                            )
                        except Exception as exc:
                            logger.exception("Unified picture-dictionary image generation failed for dictionary %s", picture_dictionary.pk)
                            messages.error(request, f"Could not create selected dictionary images: {exc}")
                        else:
                            selected_pages = [page for page, _count, _prompt in requests_for_generation]
                            preferred_updates = _select_latest_generated_variants_for_pages(selected_pages)
                            synced_entries = _sync_entry_image_paths_from_pages(picture_dictionary, refreshed_entries)
                            messages.success(
                                request,
                                "Created %(generated)s image variant%(image_suffix)s for selected dictionary row(s); selected %(preferred)s latest image%(preferred_suffix)s and synchronized %(synced)s entr%(entry_suffix)s with image paths."
                                % {
                                    "generated": generated,
                                    "image_suffix": "" if generated == 1 else "s",
                                    "preferred": preferred_updates,
                                    "preferred_suffix": "" if preferred_updates == 1 else "s",
                                    "synced": synced_entries,
                                    "entry_suffix": "y" if synced_entries == 1 else "ies",
                                },
                            )
            elif action == "save_subset":
                selected_entry_ids = [int(value) for value in request.POST.getlist("subset_entry_id") if str(value).isdigit()]
                subset_id = (request.POST.get("editing_subset_id") or request.POST.get("subset_id") or "").strip()
                subset_title = (request.POST.get("subset_title") or "").strip()
                subset_description = (request.POST.get("subset_description") or "").strip()
                subset_note = (request.POST.get("subset_selection_note") or "").strip()
                try:
                    summary = create_or_update_picture_dictionary_subset(
                        dictionary=picture_dictionary,
                        organiser=request.user,
                        title=subset_title,
                        entry_ids=selected_entry_ids,
                        subset_id=subset_id,
                        description=subset_description,
                        selection_note=subset_note,
                    )
                except ValueError as exc:
                    messages.error(request, str(exc))
                except PermissionDenied:
                    raise Http404()
                else:
                    request.session[subset_edit_session_key] = summary["subset_id"]
                    request.session.pop(subset_draft_session_key, None)
                    request.session.modified = True
                    project = summary["project"]
                    messages.success(
                        request,
                        "%s subset project “%s” with %s entr%s. It inherits images from the main picture dictionary; review/regenerate images there."
                        % (
                            "Created" if summary["created"] else "Updated",
                            project.title,
                            summary["entry_count"],
                            "y" if summary["entry_count"] == 1 else "ies",
                        ),
                    )
            elif action == "compile":
                compile_updates: list[str] = []

                def _record_compile_update(message: str) -> None:
                    compile_updates.append(message)

                low_resource_mode = bool(request.POST.get("picture_dictionary_low_resource_mode"))
                if low_resource_mode and (low_resource_missing_rows > 0 or not dictionary_entries):
                    review_url = reverse("manual-page-annotation", args=[picture_dictionary.project.id])
                    messages.error(
                        request,
                        "Compile temporarily blocked: low-resource compile mode is enabled, but some dictionary rows are missing gloss and/or translation. "
                        f"Please use “Review dictionary content (page-oriented editor)” first ({review_url}).",
                    )
                    for detail in low_resource_missing_row_details[:12]:
                        messages.info(request, f"Low-resource compile check detail: {detail}")
                    return redirect("community-organiser-home", community_id=community_id)

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
                if picture_dictionary.project.page_image_text_source != Project.PAGE_IMAGE_TEXT_SOURCE_TRANSLATION:
                    picture_dictionary.project.page_image_text_source = Project.PAGE_IMAGE_TEXT_SOURCE_TRANSLATION
                    picture_dictionary.project.save(update_fields=["page_image_text_source", "updated_at"])
                async_task(
                    _run_picture_dictionary_compile_task,
                    picture_dictionary.id,
                    request.user.id,
                    report_id,
                    low_resource_mode,
                    q_options={"sync": False},
                )
                messages.info(request, "Picture dictionary compilation started. Opening live status monitor.")
                monitor_url = reverse("project-compile-monitor", args=[picture_dictionary.project.id, report_id])
                return_to = reverse("community-organiser-home", args=[community_id])
                return redirect(f"{monitor_url}?next={quote(return_to, safe='/')}")
            elif action == "add_low_resource_rows":
                surfaces = request.POST.getlist("low_resource_surface")
                lemmas = request.POST.getlist("low_resource_lemma")
                poses = request.POST.getlist("low_resource_pos")
                glosses = request.POST.getlist("low_resource_gloss")
                max_rows = max(
                    len(surfaces),
                    len(lemmas),
                    len(poses),
                    len(glosses),
                )
                manual_rows = []
                for idx in range(max_rows):
                    row = {
                        "surface": surfaces[idx] if idx < len(surfaces) else "",
                        "lemma": lemmas[idx] if idx < len(lemmas) else "",
                        "pos": poses[idx] if idx < len(poses) else "",
                        "gloss": glosses[idx] if idx < len(glosses) else "",
                    }
                    if any(str(value or "").strip() for value in row.values()):
                        manual_rows.append(row)
                if not manual_rows:
                    request.session.pop(low_resource_pending_session_key, None)
                    messages.error(request, "Enter at least one low-resource dictionary row before adding new words.")
                else:
                    confirm_mixup = (request.POST.get("confirm_low_resource_mixup") or "").strip() == "1"
                    mixup_warnings, mixup_traces = _picture_dictionary_surface_translation_mixup_diagnostics(
                        dictionary=picture_dictionary,
                        rows=manual_rows,
                        user=request.user,
                    )
                    if mixup_warnings and not confirm_mixup:
                        request.session[low_resource_pending_session_key] = manual_rows
                        request.session.modified = True
                        messages.error(
                            request,
                            "Possible surface/translation mix-up: one or more dictionary words may have been entered in the wrong language. "
                            "Please check the language-ID trace and the highlighted row(s). If the rows are correct, tick the confirmation box and submit again.",
                        )
                        for trace in mixup_traces[:12]:
                            messages.info(
                                request,
                                "Dictionary language trace row %(row)s: word=%(text_id)s (%(text_conf)s), gloss=%(gloss_id)s (%(gloss_conf)s)."
                                % {
                                    "row": trace["row_number"],
                                    "text_id": trace["text_language_id"],
                                    "text_conf": trace["text_language_confidence"],
                                    "gloss_id": trace["gloss_language_id"],
                                    "gloss_conf": trace["gloss_language_confidence"],
                                },
                            )
                        for warning in mixup_warnings[:8]:
                            messages.info(
                                request,
                                "Possible dictionary mix-up row %(row)s: word ‘%(surface)s’ with gloss ‘%(translation)s’. %(reason)s"
                                % {
                                    "row": warning["row_number"],
                                    "surface": warning["surface"],
                                    "translation": warning["translation"],
                                    "reason": warning["reason"],
                                },
                            )
                        return redirect("community-organiser-home", community_id=community_id)
                    request.session.pop(low_resource_pending_session_key, None)
                    if mixup_warnings and confirm_mixup:
                        messages.warning(
                            request,
                            "Added rows after organiser confirmation despite language-ID warning(s).",
                        )
                    result = picture_dictionary_add_manual_rows(dictionary=picture_dictionary, rows=manual_rows)
                    messages.success(
                        request,
                        "Added %(added)s and updated %(updated)s low-resource dictionary row(s). "
                        "Annotation stages were updated so images can be created without using the page-oriented editor."
                        % {"added": result["added"], "updated": result["updated"]},
                    )
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
            elif action == "remove_all":
                removed = picture_dictionary_clear_entries(dictionary=picture_dictionary)
                messages.success(request, f"Removed {removed} dictionary entr{'y' if removed == 1 else 'ies'}.")
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
        if project.id in picture_dictionary_subset_project_id_set:
            continue
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
            "community_memberships": community_memberships,
            "community_membership_form": community_membership_form,
            "picture_dictionary": picture_dictionary,
            "dictionary_entries": dictionary_entries,
            "picture_dictionary_compile_info": picture_dictionary_compile_info,
            "picture_dictionary_entry_count": picture_dictionary_entry_count,
            "picture_dictionary_exercise_sets": picture_dictionary_exercise_sets,
            "community_back_url": reverse("community-organiser-home", args=[community_id]),
            "picture_dictionary_style_brief": picture_dictionary_style_brief,
            "picture_dictionary_background_information": picture_dictionary_background_information,
            "picture_dictionary_translation_language": picture_dictionary_translation_language,
            "picture_dictionary_generation_prompt_language": picture_dictionary_generation_prompt_language,
            "language_choices": ProjectForm.LANGUAGE_CHOICES,
            "community_projects": [project for project in projects if project.id not in picture_dictionary_subset_project_id_set],
            "picture_dictionary_subsets": picture_dictionary_subsets,
            "picture_dictionary_has_exercise_sets": picture_dictionary_has_exercise_sets,
            "picture_dictionary_subset_edit": picture_dictionary_subset_edit,
            "picture_dictionary_subset_selected_entry_ids": picture_dictionary_subset_selected_entry_ids,
            "picture_dictionary_subset_form": picture_dictionary_subset_form,
            "low_resource_mode_recommended": low_resource_mode_recommended,
            "low_resource_missing_rows": low_resource_missing_rows,
            "low_resource_missing_row_details": low_resource_missing_row_details[:12],
            "picture_dictionary_pending_image_count": picture_dictionary_pending_image_count,
            "low_resource_entry_rows": low_resource_entry_rows,
            "low_resource_word_column_label": f"{low_resource_source_label} word",
            "low_resource_gloss_column_label": (
                f"{low_resource_gloss_label} gloss (= translation)" if low_resource_gloss_label else "Gloss (= translation)"
            ),
            "low_resource_mixup_confirmation_required": low_resource_mixup_confirmation_required,
        },
    )


@login_required
def community_organiser_review_project(request: HttpRequest, community_id: int, project_id: int) -> HttpResponse:
    membership = _require_community_member(community_id, request.user)
    if membership.role != CommunityMembership.ROLE_ORGANISER:
        raise Http404()
    project = get_object_or_404(Project, pk=project_id, community_id=community_id)
    active_dictionary = (
        PictureDictionary.objects.select_related("project")
        .filter(community_id=community_id, is_active=True)
        .first()
    )
    if active_dictionary and project.id in picture_dictionary_subset_project_ids(active_dictionary):
        messages.info(
            request,
            "Subset dictionary projects inherit images from the main picture dictionary. Please review or regenerate images on the main dictionary project instead.",
        )
        return redirect("community-organiser-home", community_id=community_id)
    pages = list(ProjectImagePage.objects.filter(project=project).order_by("page_number").prefetch_related("variants"))

    if request.method == "POST":
        action = (request.POST.get("action") or request.POST.get("action_intent") or "").strip()
        if action == "mark_reviewed":
            note = (request.POST.get("review_note") or "").strip()
            preferred_updates = _apply_community_vote_preferred_variants(project=project, community_id=community_id)
            if preferred_updates:
                _persist_image_pages_artifacts(project)
            CommunityOrganiserReview.objects.update_or_create(
                community_id=community_id,
                project=project,
                organiser=request.user,
                defaults={"note": note},
            )
            if preferred_updates:
                messages.success(
                    request,
                    f"Marked review as up to date. Updated preferred image for {preferred_updates} page(s).",
                )
            else:
                messages.success(request, "Marked review as up to date.")
            return redirect("community-organiser-review-project", community_id=community_id, project_id=project.id)
        if action in {"generate_requested_preview", "generate_requested"}:
            requested: list[tuple[ProjectImagePage, int, str]] = []
            request_summaries: list[str] = []
            image_model = (request.POST.get("image_model") or "gpt-image-1").strip()
            if image_model not in IMAGE_MODEL_CHOICES:
                image_model = "gpt-image-1"
            filter_mode = (request.POST.get("generation_filter") or "all_unacceptable").strip()
            selected_page_ids = {int(v) for v in request.POST.getlist("selected_page_id") if str(v).isdigit()}
            candidate_pages: list[ProjectImagePage] = []
            if filter_mode == "selected_pages" and not selected_page_ids:
                messages.info(
                    request,
                    "No generation requests were specified. Select at least one page checkbox, or choose a different page filter.",
                )
                return redirect("community-organiser-review-project", community_id=community_id, project_id=project.id)
            if filter_mode == "missing_images":
                candidate_pages = [page for page in pages if not page.variants.exists() and not (page.image_path or "").strip()]
            elif filter_mode == "no_preferred":
                candidate_pages = [page for page in pages if not page.preferred_variant_id]
            elif filter_mode == "all_unacceptable":
                candidate_pages = []
                for page in pages:
                    variants = list(page.variants.all())
                    if not variants:
                        continue
                    has_acceptable = False
                    for variant in variants:
                        votes = CommunityImageVote.objects.filter(
                            community_id=community_id, project=project, page=page, variant=variant
                        )
                        up = votes.filter(value=CommunityImageVote.VALUE_UP).count()
                        down = votes.filter(value=CommunityImageVote.VALUE_DOWN).count()
                        if up > down:
                            has_acceptable = True
                            break
                    if not has_acceptable:
                        candidate_pages.append(page)
            elif filter_mode == "all_pages":
                candidate_pages = list(pages)
            else:
                candidate_pages = [page for page in pages if page.id in selected_page_ids]

            default_count_raw = (request.POST.get("request_count_all") or "").strip()
            try:
                default_count = int(default_count_raw or "0")
            except ValueError:
                default_count = 0
            default_count = max(0, min(8, default_count))
            default_prompt_update = (request.POST.get("request_prompt_all") or "").strip()

            for page in candidate_pages:
                count_raw = (request.POST.get(f"request_count_{page.id}") or "").strip()
                prompt_update = (request.POST.get(f"request_prompt_{page.id}") or "").strip()
                try:
                    count = int(count_raw or str(default_count))
                except ValueError:
                    count = 0
                count = max(0, min(8, count))
                if count <= 0:
                    continue
                if not prompt_update:
                    prompt_update = default_prompt_update
                base_prompt = page.generation_prompt or page.page_text
                final_prompt = f"{base_prompt}\n\nCommunity organiser request: {prompt_update}" if prompt_update else base_prompt
                requested.append((page, count, prompt_update))
                request_summaries.append(f"Page {page.page_number}: {count} variant(s)")
            if action == "generate_requested_preview" and not requested:
                messages.info(request, "No generation requests were specified.")
                return redirect("community-organiser-review-project", community_id=community_id, project_id=project.id)
            if action == "generate_requested_preview":
                request.session["community_generation_plan"] = {
                    "community_id": community_id,
                    "project_id": project.id,
                    "image_model": image_model,
                    "requests": [(page.id, count, prompt_update) for page, count, prompt_update in requested],
                }
                messages.info(
                    request,
                    "Proposed generation plan: " + "; ".join(request_summaries) + ". Submit again to confirm and start generation.",
                )
                return redirect("community-organiser-review-project", community_id=community_id, project_id=project.id)

            plan = request.session.get("community_generation_plan") or {}
            planned_items = plan.get("requests") or []
            if not planned_items or plan.get("project_id") != project.id or plan.get("community_id") != community_id:
                messages.warning(request, "Please preview the generation plan first, then confirm.")
                return redirect("community-organiser-review-project", community_id=community_id, project_id=project.id)

            planned_page_ids = [int(page_id) for page_id, _count, _prompt_update in planned_items]
            pages_by_id = {
                page.id: page
                for page in ProjectImagePage.objects.filter(project=project, id__in=planned_page_ids)
            }
            confirmed_requests: list[tuple[ProjectImagePage, int, str]] = []
            for page_id, count, prompt_update in planned_items:
                page = pages_by_id.get(int(page_id))
                if page is None:
                    continue
                confirmed_requests.append((page, max(0, min(8, int(count))), str(prompt_update)))
            confirmed_requests = [item for item in confirmed_requests if item[1] > 0]
            if not confirmed_requests:
                messages.warning(request, "The confirmed generation plan is no longer valid. Please preview again.")
                return redirect("community-organiser-review-project", community_id=community_id, project_id=project.id)

            image_model = str(plan.get("image_model") or image_model).strip()
            if image_model not in IMAGE_MODEL_CHOICES:
                image_model = "gpt-image-1"

            requested_count = sum(count for _page, count, _prompt in confirmed_requests)
            progress_marks: list[str] = []
            def _progress_callback(done: int, total: int) -> None:
                progress_marks.append(f"{done}/{total}")
            messages.info(request, f"Generating {requested_count} requested variant(s).")
            generated = _generate_requested_page_variants(
                project=project,
                image_model=image_model,
                requests=confirmed_requests,
                progress_callback=_progress_callback,
            )
            request.session.pop("community_generation_plan", None)
            _persist_image_pages_artifacts(project)
            if progress_marks:
                messages.info(request, f"Generation progress updates: {' -> '.join(progress_marks)}")
            messages.success(request, f"Generated {generated} new variant(s) from organiser requests.")
            return redirect("community-organiser-review-project", community_id=community_id, project_id=project.id)

    page_context = _page_review_context_rows(project, pages)
    page_rows = [
        {
            "page": page,
            "source_text": page_context.get(page.id, {}).get("source_text", ""),
            "translation_text": page_context.get(page.id, {}).get("translation_text", ""),
        }
        for page in pages
    ]
    vote_rows: list[dict[str, Any]] = []
    current_generation_filter = (request.GET.get("generation_filter") or "all_unacceptable").strip()
    if current_generation_filter not in {"selected_pages", "missing_images", "no_preferred", "all_unacceptable", "all_pages"}:
        current_generation_filter = "all_unacceptable"
    page_ids_for_project = {page.id for page in pages}
    selected_page_ids_for_filter = {
        int(v)
        for v in request.GET.getlist("selected_page_id")
        if str(v).isdigit() and int(v) in page_ids_for_project
    }
    visible_page_ids: set[int] = set()
    if current_generation_filter == "missing_images":
        visible_page_ids = {page.id for page in pages if not page.variants.exists() and not (page.image_path or "").strip()}
    elif current_generation_filter == "no_preferred":
        visible_page_ids = {page.id for page in pages if not page.preferred_variant_id}
    elif current_generation_filter == "all_unacceptable":
        for page in pages:
            variants = list(page.variants.all())
            if not variants:
                continue
            has_acceptable = False
            for variant in variants:
                votes_qs = CommunityImageVote.objects.filter(
                    community_id=community_id, project=project, page=page, variant=variant
                )
                up_count = votes_qs.filter(value=CommunityImageVote.VALUE_UP).count()
                down_count = votes_qs.filter(value=CommunityImageVote.VALUE_DOWN).count()
                if up_count > down_count:
                    has_acceptable = True
                    break
            if not has_acceptable:
                visible_page_ids.add(page.id)
    elif current_generation_filter == "all_pages":
        visible_page_ids = {page.id for page in pages}
    else:
        visible_page_ids = selected_page_ids_for_filter or {page.id for page in pages}
    preview_page_ids: set[int] = set()
    plan = request.session.get("community_generation_plan") or {}
    if plan.get("project_id") == project.id and plan.get("community_id") == community_id:
        for page_id, _count, _prompt_update in (plan.get("requests") or []):
            try:
                preview_page_ids.add(int(page_id))
            except (TypeError, ValueError):
                continue
    filter_counts = {
        "selected_pages": len(pages),
        "missing_images": 0,
        "no_preferred": 0,
        "all_unacceptable": 0,
    }
    for page in pages:
        context = page_context.get(page.id, {})
        page_no_preferred = not page.preferred_variant_id
        page_missing_images = not page.variants.exists() and not (page.image_path or "").strip()
        if page_no_preferred:
            filter_counts["no_preferred"] += 1
        if page_missing_images:
            filter_counts["missing_images"] += 1
        page_all_unacceptable = False
        variants_for_page = list(page.variants.order_by("variant_index"))
        if variants_for_page:
            has_acceptable = False
            for variant in variants_for_page:
                votes_qs = CommunityImageVote.objects.filter(
                    community_id=community_id, project=project, page=page, variant=variant
                )
                up_count = votes_qs.filter(value=CommunityImageVote.VALUE_UP).count()
                down_count = votes_qs.filter(value=CommunityImageVote.VALUE_DOWN).count()
                if up_count > down_count:
                    has_acceptable = True
                    break
            page_all_unacceptable = not has_acceptable
            if page_all_unacceptable:
                filter_counts["all_unacceptable"] += 1
        for variant in variants_for_page:
            votes = list(
                CommunityImageVote.objects.filter(community_id=community_id, project=project, variant=variant)
                .select_related("user")
                .order_by("-updated_at")
            )
            up = sum(1 for vote in votes if vote.value == CommunityImageVote.VALUE_UP)
            down = sum(1 for vote in votes if vote.value == CommunityImageVote.VALUE_DOWN)
            in_preview_plan = page.id in preview_page_ids
            visible_by_filter = page.id in visible_page_ids
            vote_rows.append({
                "page": page,
                "source_text": context.get("source_text", ""),
                "translation_text": context.get("translation_text", ""),
                "variant": variant,
                "votes": votes,
                "up": up,
                "down": down,
                "matches_filters": {
                    "all_pages": True,
                    "missing_images": page_missing_images,
                    "no_preferred": page_no_preferred,
                    "all_unacceptable": page_all_unacceptable,
                },
                "in_preview_plan": in_preview_plan,
                "selected_for_regeneration": page.id in selected_page_ids_for_filter or in_preview_plan,
                "visible_by_filter": visible_by_filter,
                "initially_visible": visible_by_filter and (not preview_page_ids or in_preview_plan),
            })
    review = CommunityOrganiserReview.objects.filter(
        community_id=community_id, project=project, organiser=request.user
    ).first()
    project_picture_dictionary = getattr(project, "picture_dictionary", None)
    picture_dictionary_mixup_warnings, picture_dictionary_mixup_traces = _picture_dictionary_existing_mixup_diagnostics(
        dictionary=project_picture_dictionary,
        user=request.user,
    )
    return render(
        request,
        "projects/community_organiser_review_project.html",
        {
            "community": membership.community,
            "membership": membership,
            "project": project,
            "pages": page_rows,
            "vote_rows": vote_rows,
            "review": review,
            "image_models": IMAGE_MODEL_CHOICES,
            "picture_dictionary_mixup_warnings": picture_dictionary_mixup_warnings,
            "picture_dictionary_mixup_traces": picture_dictionary_mixup_traces,
            "review_summary": {
                "reviewed": bool(review),
                "review_note": (review.note or "") if review else "",
                "total_pages": len(pages),
                "total_variants": len(vote_rows),
                "filter_counts": filter_counts,
                "selected_page_count": len(selected_page_ids_for_filter),
                "preview_plan_count": len(preview_page_ids),
            },
            "has_preview_plan": bool(preview_page_ids),
            "current_generation_filter": current_generation_filter,
            "generation_filter_options": [
                ("selected_pages", "Selected pages"),
                ("all_pages", "All pages"),
                ("missing_images", "Missing images only"),
                ("no_preferred", "No preferred image"),
                ("all_unacceptable", "All variants unacceptable"),
            ],
        },
    )

@login_required
def set_processing_options(request: HttpRequest, pk: int) -> HttpResponse:
    project = _get_project_for_user(pk=pk, user=request.user, min_role=ProjectCollaborator.ROLE_OWNER)
    return_to = (request.POST.get("return_to") or "").strip()
    if not return_to.startswith("/"):
        return_to = reverse("project-detail", args=[project.pk])
    segmentation_method = _normalize_processing_method_choice(
        request.POST.get("segmentation_method") or project.segmentation_method, SEGMENTATION_METHOD_CHOICES
    )
    romanization_method = _normalize_processing_method_choice(
        request.POST.get("romanization_method") or project.romanization_method, ROMANIZATION_METHOD_CHOICES
    )
    audio_mode = (request.POST.get("audio_mode") or project.audio_mode or Project.AUDIO_MODE_TTS).strip().lower()
    if segmentation_method not in SEGMENTATION_METHOD_CHOICES:
        messages.error(request, "Unknown segmentation method option.")
        return redirect(return_to)
    if romanization_method not in ROMANIZATION_METHOD_CHOICES:
        messages.error(request, "Unknown romanization method option.")
        return redirect(return_to)
    if audio_mode not in {Project.AUDIO_MODE_TTS, Project.AUDIO_MODE_NONE}:
        messages.error(request, "Unknown audio mode option.")
        return redirect(return_to)
    update_fields: list[str] = []
    if segmentation_method != project.segmentation_method:
        project.segmentation_method = segmentation_method
        update_fields.append("segmentation_method")
    if romanization_method != project.romanization_method:
        project.romanization_method = romanization_method
        update_fields.append("romanization_method")
    if audio_mode != project.audio_mode:
        project.audio_mode = audio_mode
        update_fields.append("audio_mode")
    if update_fields:
        project.save(update_fields=update_fields + ["updated_at"])
    messages.success(request, "Saved language-processing options.")
    return redirect(return_to)


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
    manual_level = _normalize_cefr_level_expression(request.GET.get("level") or "", max_levels=3)

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
        level = _normalize_cefr_level_expression(str(nl_plan.get("level") or "").strip(), max_levels=3)
    else:
        title = manual_title
        text_language = manual_text_language
        annotation_language = manual_annotation_language
        date_posted = manual_date_posted
        level = manual_level

    qs = _published_projects_visible_to_user(request.user)
    title_hard_filter = title
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
        requested_level = level
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
            "nl_filters": {
                "nl_query": nl_query,
                "dialogue_language": dialogue_language,
                "level": level,
            },
            "simple_filters": {
                "title": manual_title,
                "text_language": manual_text_language,
                "annotation_language": manual_annotation_language,
                "date_posted": manual_date_posted,
                "level": manual_level,
            },
            "simple_filters": {
                "title": manual_title,
                "text_language": manual_text_language,
                "annotation_language": manual_annotation_language,
                "date_posted": manual_date_posted,
                "level": manual_level,
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
            "level_options": [
                ("", "Any level"),
                ("A1/A2", "A1/A2"),
                ("B1/B2", "B1/B2"),
                ("C1/C2", "C1/C2"),
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
def set_project_target_language(request: HttpRequest, pk: int) -> HttpResponse:
    project = _get_project_for_user(pk=pk, user=request.user, min_role=ProjectCollaborator.ROLE_OWNER)
    if request.method != "POST":
        return redirect("project-detail", pk=project.pk)
    new_target_language = (request.POST.get("target_language") or "").strip().lower()
    allowed_target_languages = {code for code, _label in ProjectForm.LANGUAGE_CHOICES}
    if new_target_language not in allowed_target_languages:
        messages.error(request, "Unknown glossing language.")
        return redirect("project-detail", pk=project.pk)
    if new_target_language == (project.target_language or "").strip().lower():
        messages.info(request, "Glossing language unchanged.")
        return redirect("project-detail", pk=project.pk)

    removed_files = 0
    for run_dir in _iter_runs(project):
        for stage_name in ("translation", "gloss"):
            stage_path = stage_artifact_path(run_dir, stage_name)
            if stage_path.exists():
                stage_path.unlink()
                removed_files += 1

    project.target_language = new_target_language
    project.save(update_fields=["target_language", "updated_at"])
    messages.success(
        request,
        f"Glossing language changed to {new_target_language}. Removed {removed_files} translation/gloss stage file(s).",
    )
    return redirect("project-detail", pk=project.pk)


@xframe_options_sameorigin
def serve_compiled(request: HttpRequest, pk: int, path: str) -> HttpResponse:
    """Serve compiled artifacts from a project's run directory.

    Mirrors the C-LARA behaviour so concordance iframes and relative links work
    without refusing the connection.
    """

    project = get_object_or_404(Project, pk=pk)
    user = request.user
    is_authenticated = bool(getattr(user, "is_authenticated", False))
    is_owner = bool(is_authenticated and project.owner_id == getattr(user, "id", None))
    is_collaborator = bool(is_authenticated and project.collaborators.filter(user=user).exists())
    is_project_community_member = bool(
        is_authenticated
        and project.community_id
        and CommunityMembership.objects.filter(
            community_id=project.community_id,
            user=user,
            community__is_active=True,
        ).exists()
    )
    can_access_unpublished = is_owner or is_collaborator or is_project_community_member
    if not can_access_unpublished and not project.is_published:
        raise Http404()
    if not can_access_unpublished and project.access_scope != Project.ACCESS_PUBLIC:
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
    if (content_type or "").startswith("text/html"):
        try:
            html_text = data.decode("utf-8")
            entry_context = (request.GET.get("ctx") or "project").strip().lower()
            if entry_context == "content":
                back_href = reverse("content-detail", args=[project.pk])
                back_label = "Back to content"
            else:
                back_href = reverse("project-detail", args=[project.pk])
                back_label = "Back to project"
            back_block = (
                f'<div style="padding:0.5rem 1rem;background:#f6f6f6;border-bottom:1px solid #ddd;">'
                f'<a href="{back_href}">&#x2190; {back_label}</a></div>'
            )
            html_text = html_text.replace("<body>", f"<body>\n{back_block}", 1)
            data = html_text.encode("utf-8")
        except Exception:
            pass
    return HttpResponse(data, content_type=content_type or "application/octet-stream")


EXERCISE_SOURCE_STAGE_NAMES = ["gloss", "lemma", "mwe", "translation", "segmentation_phase_2"]
EXERCISE_CLOZE_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "but",
    "by",
    "for",
    "from",
    "had",
    "has",
    "he",
    "her",
    "him",
    "his",
    "in",
    "is",
    "it",
    "its",
    "of",
    "on",
    "one",
    "or",
    "she",
    "that",
    "the",
    "their",
    "them",
    "they",
    "to",
    "too",
    "was",
    "were",
    "with",
}



def _resolve_project_compiled_run_dir(project: Project) -> Path | None:
    if not project.compiled_path:
        return None
    base = project.artifact_dir().resolve()
    rel = Path(project.compiled_path)
    if len(rel.parts) < 2 or rel.parts[0] != "runs":
        return None
    candidate = (base / rel.parts[0] / rel.parts[1]).resolve()
    return candidate if candidate.exists() else None

def _exercise_run_candidates(run_dir: Path) -> list[Path]:
    """Return run directories to try when extracting exercise source material.

    Imported legacy projects are often recompiled from existing artifacts.  That
    can leave the newest run containing only compile output while the usable
    token/gloss stages remain in an older import run.  Exercise generation should
    therefore fall back through sibling runs instead of treating the newest
    compile-only run as authoritative.
    """

    primary = Path(run_dir)
    runs_root = primary.parent
    candidates: list[Path] = []
    if primary.exists():
        candidates.append(primary)
    if runs_root.exists():
        siblings = [path for path in runs_root.iterdir() if path.is_dir() and path != primary]
        siblings.sort(key=lambda path: path.stat().st_mtime, reverse=True)
        candidates.extend(siblings)
    return candidates


def _exercise_stage_payloads(run_dir: Path, stage_names: list[str]) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for candidate_run in _exercise_run_candidates(run_dir):
        for stage in stage_names:
            path = stage_artifact_path(candidate_run, stage)
            if not path.exists():
                continue
            try:
                payload = read_stage_artifact(candidate_run, stage)
            except Exception:
                continue
            if isinstance(payload, dict):
                payloads.append(payload)
                break
    return payloads


EXERCISE_FUNCTION_POS = {
    "ADP",
    "AUX",
    "CCONJ",
    "DET",
    "INTJ",
    "PART",
    "PRON",
    "PUNCT",
    "SCONJ",
    "SYM",
}
EXERCISE_CONTENT_POS = {"ADJ", "ADV", "NOUN", "PROPN", "VERB"}
EXERCISE_POS_ALIASES = {
    "NN": "NOUN",
    "NNS": "NOUN",
    "NNP": "PROPN",
    "NNPS": "PROPN",
    "N": "NOUN",
    "V": "VERB",
    "VB": "VERB",
    "VBD": "VERB",
    "VBG": "VERB",
    "VBN": "VERB",
    "VBP": "VERB",
    "VBZ": "VERB",
    "A": "ADJ",
    "JJ": "ADJ",
    "JJR": "ADJ",
    "JJS": "ADJ",
    "RB": "ADV",
    "RBR": "ADV",
    "RBS": "ADV",
}
EXERCISE_LEXICAL_CATEGORIES = {
    "NOUN": "noun/proper noun",
    "PROPN": "noun/proper noun",
    "VERB": "verb",
    "ADJ": "adjective",
    "ADV": "adverb",
    "NUM": "number",
}


def _exercise_token_pos(annotations: dict[str, Any]) -> str:
    raw_pos = str(annotations.get("pos") or annotations.get("POS") or "").strip().upper()
    if not raw_pos:
        return ""
    return EXERCISE_POS_ALIASES.get(raw_pos, raw_pos)


def _exercise_lexical_category(pos: str) -> str:
    normalized = EXERCISE_POS_ALIASES.get(str(pos or "").upper(), str(pos or "").upper())
    return "NOUN" if normalized == "PROPN" else normalized


def _exercise_is_same_lexical_category(left_pos: str, right_pos: str) -> bool:
    if not left_pos or not right_pos:
        return True
    return _exercise_lexical_category(left_pos) == _exercise_lexical_category(right_pos)


def _exercise_script_key(value: str) -> str:
    scripts: set[str] = set()
    for ch in value:
        if not ch.isalpha():
            continue
        name = unicodedata.name(ch, "")
        scripts.add(name.split()[0] if name else "OTHER")
    return "+".join(sorted(scripts))


def _exercise_base_form(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(ch for ch in decomposed if ch.isalnum())


def _exercise_edit_distance_at_most_one(left: str, right: str) -> bool:
    if abs(len(left) - len(right)) > 1:
        return False
    if left == right:
        return True
    if len(left) == len(right):
        return sum(1 for a, b in zip(left, right) if a != b) <= 1
    shorter, longer = (left, right) if len(left) < len(right) else (right, left)
    for idx in range(len(longer)):
        if longer[:idx] + longer[idx + 1 :] == shorter:
            return True
    return False


def _exercise_near_duplicate(left: str, right: str) -> bool:
    left_base = _exercise_base_form(left)
    right_base = _exercise_base_form(right)
    if not left_base or not right_base:
        return False
    if left_base == right_base:
        return True
    shorter, longer = (left_base, right_base) if len(left_base) < len(right_base) else (right_base, left_base)
    if len(shorter) >= 4 and longer.startswith(shorter):
        return True
    return _exercise_edit_distance_at_most_one(left_base, right_base)


def _exercise_length_delta(left: str, right: str) -> int:
    return abs(len(left.strip()) - len(right.strip()))


def _exercise_token_metadata(surface: str, annotations: dict[str, Any]) -> dict[str, Any]:
    pos = _exercise_token_pos(annotations)
    return {
        "surface": surface.strip(),
        "lemma": str(annotations.get("lemma") or "").strip(),
        "pos": pos,
        "lexical_category": _exercise_lexical_category(pos),
        "script": _exercise_script_key(surface),
        "length": len(surface.strip()),
    }


def _is_cloze_word_candidate(surface: str, annotations: dict[str, Any] | None = None) -> bool:
    normalized = surface.strip()
    if not any(ch.isalpha() for ch in normalized):
        return False
    if normalized.casefold() in EXERCISE_CLOZE_STOPWORDS:
        return False
    pos = _exercise_token_pos(annotations or {})
    if pos in EXERCISE_FUNCTION_POS:
        return False
    if pos and pos not in EXERCISE_CONTENT_POS:
        return False
    return True


def _exercise_filter_distractors(
    distractors: list[str],
    *,
    answer: str,
    answer_pos: str = "",
    answer_script: str = "",
    known_metadata: dict[str, dict[str, Any]] | None = None,
    forbidden_values: set[str] | None = None,
    limit: int = 3,
) -> list[str]:
    """Validate generated distractors against category/script/duplicate constraints."""

    metadata_by_value = known_metadata or {}
    forbidden = {value.casefold() for value in (forbidden_values or set()) if value}
    forbidden.add(answer.casefold())
    seen: set[str] = set()
    filtered: list[str] = []
    for raw in distractors:
        candidate = str(raw or "").strip()
        key = candidate.casefold()
        if not candidate or key in seen or key in forbidden:
            continue
        if _exercise_near_duplicate(candidate, answer):
            continue
        script = _exercise_script_key(candidate)
        if answer_script and script and script != answer_script:
            continue
        meta = metadata_by_value.get(key)
        if meta and not _exercise_is_same_lexical_category(answer_pos, str(meta.get("pos") or "")):
            continue
        seen.add(key)
        filtered.append(candidate)
        if len(filtered) >= limit:
            break
    return filtered


def _exercise_ranked_fallback_values(
    fallback_values: list[Any],
    *,
    answer: str,
    answer_pos: str = "",
    answer_script: str = "",
) -> list[str]:
    ranked: list[tuple[int, int, str]] = []
    seen: set[str] = set()
    for index, raw in enumerate(fallback_values):
        if isinstance(raw, dict):
            candidate = str(raw.get("surface") or raw.get("value") or "").strip()
            pos = str(raw.get("pos") or "")
            script = str(raw.get("script") or "") or _exercise_script_key(candidate)
        else:
            candidate = str(raw or "").strip()
            pos = ""
            script = _exercise_script_key(candidate)
        key = candidate.casefold()
        if not candidate or key in seen or key == answer.casefold():
            continue
        if _exercise_near_duplicate(candidate, answer):
            continue
        same_category = _exercise_is_same_lexical_category(answer_pos, pos)
        same_script = not answer_script or not script or script == answer_script
        if not same_category or not same_script:
            continue
        length_penalty = _exercise_length_delta(candidate, answer)
        ranked.append((length_penalty, index, candidate))
        seen.add(key)
    ranked.sort(key=lambda item: (item[0], item[1]))
    return [candidate for _length, _index, candidate in ranked]


def _extract_segment_candidates_from_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for page in payload.get("pages", []):
        page_number = page.get("page_number", 1)
        for idx, seg in enumerate(page.get("segments", [])):
            tokens = seg.get("tokens", [])
            words: list[dict[str, Any]] = []
            token_metadata: list[dict[str, Any]] = []
            for t in tokens:
                surface = (t.get("surface") or "").strip()
                ann = t.get("annotations", {}) or {}
                if not surface:
                    continue
                metadata = _exercise_token_metadata(surface, ann)
                token_metadata.append(metadata)
                if ann.get("mwe_id"):
                    continue
                if _is_cloze_word_candidate(surface, ann):
                    words.append(metadata)
            if words:
                seg_text = "".join(t.get("surface", "") for t in tokens).strip() or seg.get("surface", "")
                candidates.append(
                    {
                        "page_number": page_number,
                        "segment_index": idx,
                        "segment_text": seg_text,
                        "words": words,
                        "token_metadata": token_metadata,
                    }
                )
    return candidates


def _extract_segment_candidates_for_cloze(run_dir: Path) -> list[dict[str, Any]]:
    for payload in _exercise_stage_payloads(run_dir, EXERCISE_SOURCE_STAGE_NAMES):
        candidates = _extract_segment_candidates_from_payload(payload)
        if candidates:
            return candidates
    return []


def _extract_token_candidates_from_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for page in payload.get("pages", []):
        page_number = page.get("page_number", 1)
        for seg_idx, seg in enumerate(page.get("segments", [])):
            tokens = seg.get("tokens", [])
            segment_token_metadata = [
                _exercise_token_metadata((t.get("surface") or "").strip(), t.get("annotations", {}) or {})
                for t in tokens
                if (t.get("surface") or "").strip()
            ]
            for tok_idx, token in enumerate(tokens):
                surface = (token.get("surface") or "").strip()
                if not surface or not any(ch.isalpha() for ch in surface):
                    continue
                ann = token.get("annotations", {}) or {}
                if ann.get("mwe_id"):
                    continue
                if not _is_cloze_word_candidate(surface, ann):
                    continue
                gloss = str(ann.get("gloss") or "").strip()
                if not gloss:
                    continue
                pair = (surface.lower(), gloss.lower())
                if pair in seen:
                    continue
                seen.add(pair)
                metadata = _exercise_token_metadata(surface, ann)
                candidates.append(
                    {
                        "page_number": page_number,
                        "segment_index": seg_idx,
                        "token_index": tok_idx,
                        "source_word": surface,
                        "target_gloss": gloss,
                        "pos": metadata["pos"],
                        "lexical_category": metadata["lexical_category"],
                        "script": metadata["script"],
                        "source_length": metadata["length"],
                        "token_metadata": segment_token_metadata,
                        "segment_text": "".join(t.get("surface", "") for t in tokens).strip() or seg.get("surface", ""),
                    }
                )
    return candidates


def _extract_token_candidates_for_flashcards(run_dir: Path) -> list[dict[str, Any]]:
    for payload in _exercise_stage_payloads(run_dir, EXERCISE_SOURCE_STAGE_NAMES):
        candidates = _extract_token_candidates_from_payload(payload)
        if candidates:
            return candidates
    return []


def _nonempty_exercise_translation(annotations: dict[str, Any]) -> str:
    for key in ("gloss", "translation"):
        value = str(annotations.get(key) or "").strip()
        if value and value.casefold() not in {"none", "null", "-"}:
            return value
    return ""


def _find_project_picture_dictionary(project: Project) -> PictureDictionary | None:
    query = PictureDictionary.objects.select_related("project").filter(is_active=True)
    if project.community_id:
        dictionary = query.filter(community_id=project.community_id).first()
        if dictionary:
            return dictionary
    language = (project.language or "").strip()
    if language:
        return query.filter(language__iexact=language).first()
    return None


def _picture_dictionary_image_exists(dictionary: PictureDictionary, image_path: str) -> bool:
    if not image_path:
        return False
    try:
        image_file = (dictionary.project.artifact_dir() / image_path).resolve()
        image_file.relative_to(dictionary.project.artifact_dir().resolve())
    except ValueError:
        return False
    return image_file.exists()


def _picture_dictionary_entry_index(dictionary: PictureDictionary) -> dict[str, PictureDictionaryEntry]:
    indexed: dict[str, PictureDictionaryEntry] = {}
    entries = dictionary.entries.filter(is_active=True).exclude(image_path="").order_by("id")
    for entry in entries:
        if not _picture_dictionary_image_exists(dictionary, entry.image_path):
            continue
        for value in (entry.surface, entry.lemma):
            key = str(value or "").strip().casefold()
            if key and key not in indexed:
                indexed[key] = entry
    return indexed


def _extract_image_flashcard_candidates_from_payload(
    payload: dict[str, Any],
    *,
    dictionary: PictureDictionary,
) -> list[dict[str, Any]]:
    entry_index = _picture_dictionary_entry_index(dictionary)
    if not entry_index:
        return []
    candidates: list[dict[str, Any]] = []
    seen_entries: set[int] = set()
    for page in payload.get("pages", []):
        page_number = page.get("page_number", 1)
        for seg_idx, seg in enumerate(page.get("segments", [])):
            tokens = seg.get("tokens", [])
            segment_text = "".join(t.get("surface", "") for t in tokens).strip() or seg.get("surface", "")
            segment_token_metadata = [
                _exercise_token_metadata((t.get("surface") or "").strip(), t.get("annotations", {}) or {})
                for t in tokens
                if (t.get("surface") or "").strip()
            ]
            for tok_idx, token in enumerate(tokens):
                surface = (token.get("surface") or "").strip()
                if not surface or not any(ch.isalpha() for ch in surface):
                    continue
                ann = token.get("annotations", {}) or {}
                if ann.get("mwe_id") or not _is_cloze_word_candidate(surface, ann):
                    continue
                translation = _nonempty_exercise_translation(ann)
                if not translation:
                    continue
                lemma = str(ann.get("lemma") or "").strip()
                entry = entry_index.get(surface.casefold()) or entry_index.get(lemma.casefold())
                if not entry or entry.id in seen_entries:
                    continue
                seen_entries.add(entry.id)
                metadata = _exercise_token_metadata(surface, ann)
                prompt_word = str(entry.surface or surface or "").strip()
                if not prompt_word:
                    continue
                candidates.append(
                    {
                        "page_number": page_number,
                        "segment_index": seg_idx,
                        "token_index": tok_idx,
                        "source_word": prompt_word,
                        "source_word_seen_in_text": surface,
                        "target_gloss": translation,
                        "pos": metadata["pos"] or entry.pos,
                        "lexical_category": metadata["lexical_category"],
                        "script": metadata["script"],
                        "source_length": metadata["length"],
                        "segment_text": segment_text,
                        "token_metadata": segment_token_metadata,
                        "dictionary_entry_id": entry.id,
                        "dictionary_project_id": dictionary.project_id,
                        "image_path": entry.image_path,
                        "dictionary_surface": entry.surface,
                        "dictionary_lemma": entry.lemma,
                    }
                )
    return candidates


def _extract_image_flashcard_candidates(run_dir: Path, *, dictionary: PictureDictionary) -> list[dict[str, Any]]:
    for payload in _exercise_stage_payloads(run_dir, EXERCISE_SOURCE_STAGE_NAMES):
        candidates = _extract_image_flashcard_candidates_from_payload(payload, dictionary=dictionary)
        if candidates:
            return candidates
    return []


WORD_SCRAMBLE_DIRECTIONS: tuple[tuple[int, int], ...] = (
    (0, 1),
    (1, 0),
    (1, 1),
    (-1, 1),
)
WORD_SCRAMBLE_DISTRACTOR_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _word_scramble_normalize_answer(value: str) -> str:
    return "".join(ch.upper() for ch in unicodedata.normalize("NFC", value or "") if ch.isalpha())


def _word_scramble_random_letters(candidates: list[dict[str, Any]]) -> list[str]:
    letters: list[str] = []
    for candidate in candidates:
        letters.extend(_word_scramble_normalize_answer(str(candidate.get("source_word") or "")))
    return letters or list(WORD_SCRAMBLE_DISTRACTOR_LETTERS)


def _word_scramble_can_place(
    grid: list[list[str | None]],
    word: str,
    row: int,
    col: int,
    dr: int,
    dc: int,
) -> bool:
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    end_row = row + dr * (len(word) - 1)
    end_col = col + dc * (len(word) - 1)
    if end_row < 0 or end_row >= rows or end_col < 0 or end_col >= cols:
        return False
    for idx, letter in enumerate(word):
        cell = grid[row + dr * idx][col + dc * idx]
        if cell is not None and cell != letter:
            return False
    return True


def _word_scramble_place_word(
    grid: list[list[str | None]],
    word: str,
    rng: random.Random,
) -> list[dict[str, int]] | None:
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    placements: list[tuple[int, int, int, int]] = []
    for row in range(rows):
        for col in range(cols):
            for dr, dc in WORD_SCRAMBLE_DIRECTIONS:
                if _word_scramble_can_place(grid, word, row, col, dr, dc):
                    placements.append((row, col, dr, dc))
    if not placements:
        return None
    row, col, dr, dc = rng.choice(placements)
    path: list[dict[str, int]] = []
    for idx, letter in enumerate(word):
        cell_row = row + dr * idx
        cell_col = col + dc * idx
        grid[cell_row][cell_col] = letter
        path.append({"row": cell_row, "col": cell_col})
    return path


def _generate_word_scramble_items(
    candidates: list[dict[str, Any]],
    *,
    item_count: int,
    rows: int,
    cols: int,
    seed: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Create a single word-search-style grid and one picture-clue item per word."""

    rng = random.Random(seed)
    normalized_candidates: list[dict[str, Any]] = []
    seen_answers: set[str] = set()
    for candidate in candidates:
        answer = _word_scramble_normalize_answer(str(candidate.get("source_word") or ""))
        if len(answer) < 2 or len(answer) > max(rows, cols):
            continue
        if answer in seen_answers:
            continue
        seen_answers.add(answer)
        normalized_candidates.append({**candidate, "scramble_answer": answer})

    normalized_candidates.sort(
        key=lambda cand: (
            -len(str(cand.get("scramble_answer") or "")),
            str(cand.get("source_word") or "").casefold(),
        )
    )
    grid: list[list[str | None]] = [[None for _ in range(cols)] for _ in range(rows)]
    placed: list[tuple[dict[str, Any], list[dict[str, int]]]] = []
    for candidate in normalized_candidates:
        if len(placed) >= item_count:
            break
        answer = str(candidate["scramble_answer"])
        path = _word_scramble_place_word(grid, answer, rng)
        if path is None:
            continue
        placed.append((candidate, path))

    distractor_letters = _word_scramble_random_letters(normalized_candidates)
    for row in range(rows):
        for col in range(cols):
            if grid[row][col] is None:
                grid[row][col] = rng.choice(distractor_letters)
    grid_rows = ["".join(str(cell) for cell in row) for row in grid]
    grid_payload = {
        "rows": rows,
        "cols": cols,
        "grid": grid_rows,
    }
    items: list[dict[str, Any]] = []
    for order_index, (candidate, path) in enumerate(placed):
        answer = str(candidate["scramble_answer"])
        items.append(
            {
                "order_index": order_index,
                "page_number": candidate["page_number"],
                "segment_index": candidate["segment_index"],
                "segment_text": candidate["segment_text"],
                "prompt": "Select the letters in the grid that match the picture clue.",
                "answer": answer,
                "options": [],
                "rationale": {
                    "exercise_kind": "word_scramble",
                    **grid_payload,
                    "path": path,
                    "display_answer": candidate.get("source_word") or answer,
                    "translation": candidate.get("target_gloss") or "",
                    "image_project_id": candidate.get("dictionary_project_id"),
                    "image_path": candidate.get("image_path"),
                    "dictionary_entry_id": candidate.get("dictionary_entry_id"),
                    "dictionary_surface": candidate.get("dictionary_surface") or "",
                    "dictionary_lemma": candidate.get("dictionary_lemma") or "",
                },
            }
        )
    return items, grid_payload


CROSSWORD_DIRECTIONS = {
    "across": (0, 1),
    "down": (1, 0),
}


def _crossword_can_place(
    grid: dict[tuple[int, int], str],
    word: str,
    row: int,
    col: int,
    direction: str,
    *,
    require_intersection: bool,
    max_grid_size: int,
) -> tuple[bool, int]:
    dr, dc = CROSSWORD_DIRECTIONS[direction]
    intersections = 0
    end_row = row + dr * (len(word) - 1)
    end_col = col + dc * (len(word) - 1)
    if min(row, col, end_row, end_col) < 0 or max(row, col, end_row, end_col) >= max_grid_size:
        return False, 0
    before = (row - dr, col - dc)
    after = (end_row + dr, end_col + dc)
    if before in grid or after in grid:
        return False, 0
    for idx, letter in enumerate(word):
        pos = (row + dr * idx, col + dc * idx)
        existing = grid.get(pos)
        if existing is not None:
            if existing != letter:
                return False, 0
            intersections += 1
            continue
        if direction == "across":
            if (pos[0] - 1, pos[1]) in grid or (pos[0] + 1, pos[1]) in grid:
                return False, 0
        else:
            if (pos[0], pos[1] - 1) in grid or (pos[0], pos[1] + 1) in grid:
                return False, 0
    if require_intersection and intersections == 0:
        return False, 0
    return True, intersections


def _crossword_path(word: str, row: int, col: int, direction: str) -> list[dict[str, int]]:
    dr, dc = CROSSWORD_DIRECTIONS[direction]
    return [{"row": row + dr * idx, "col": col + dc * idx} for idx, _letter in enumerate(word)]


def _crossword_place_word(
    grid: dict[tuple[int, int], str],
    word: str,
    row: int,
    col: int,
    direction: str,
) -> list[dict[str, int]]:
    path = _crossword_path(word, row, col, direction)
    for idx, pos in enumerate(path):
        grid[(pos["row"], pos["col"])] = word[idx]
    return path


def _crossword_find_intersection_placement(
    grid: dict[tuple[int, int], str],
    placed_words: list[dict[str, Any]],
    word: str,
    *,
    max_grid_size: int,
) -> tuple[int, int, str, int] | None:
    options: list[tuple[int, int, str, int]] = []
    for placed in placed_words:
        next_direction = "down" if placed["direction"] == "across" else "across"
        for placed_idx, placed_cell in enumerate(placed["path"]):
            placed_letter = placed["answer"][placed_idx]
            for word_idx, letter in enumerate(word):
                if letter != placed_letter:
                    continue
                dr, dc = CROSSWORD_DIRECTIONS[next_direction]
                row = placed_cell["row"] - dr * word_idx
                col = placed_cell["col"] - dc * word_idx
                can_place, intersections = _crossword_can_place(
                    grid,
                    word,
                    row,
                    col,
                    next_direction,
                    require_intersection=True,
                    max_grid_size=max_grid_size,
                )
                if can_place:
                    options.append((row, col, next_direction, intersections))
    if not options:
        return None
    options.sort(key=lambda item: (-item[3], item[0], item[1], item[2]))
    return options[0]


def _crossword_find_disconnected_placement(
    grid: dict[tuple[int, int], str],
    word: str,
    *,
    max_grid_size: int,
) -> tuple[int, int, str] | None:
    for row in range(max_grid_size):
        for col in range(max_grid_size):
            for direction in ("across", "down"):
                can_place, _intersections = _crossword_can_place(
                    grid,
                    word,
                    row,
                    col,
                    direction,
                    require_intersection=False,
                    max_grid_size=max_grid_size,
                )
                if can_place:
                    return row, col, direction
    return None


def _build_crossword_item(
    candidates: list[dict[str, Any]],
    *,
    item_count: int,
    max_grid_size: int,
) -> dict[str, Any] | None:
    normalized_candidates: list[dict[str, Any]] = []
    seen_answers: set[str] = set()
    for candidate in candidates:
        answer = _word_scramble_normalize_answer(str(candidate.get("source_word") or ""))
        if len(answer) < 2 or len(answer) > max_grid_size:
            continue
        if answer in seen_answers:
            continue
        seen_answers.add(answer)
        normalized_candidates.append({**candidate, "crossword_answer": answer})
    normalized_candidates.sort(
        key=lambda cand: (
            -len(str(cand.get("crossword_answer") or "")),
            str(cand.get("source_word") or "").casefold(),
        )
    )
    selected = normalized_candidates[:item_count]
    if not selected:
        return None

    grid: dict[tuple[int, int], str] = {}
    placed_words: list[dict[str, Any]] = []
    unplaced_words: list[str] = []
    first = selected[0]
    first_answer = str(first["crossword_answer"])
    first_row = max_grid_size // 2
    first_col = max(0, (max_grid_size - len(first_answer)) // 2)
    first_path = _crossword_place_word(grid, first_answer, first_row, first_col, "across")
    placed_words.append({**first, "answer": first_answer, "direction": "across", "path": first_path})

    disconnected_used = False
    for candidate in selected[1:]:
        answer = str(candidate["crossword_answer"])
        placement = _crossword_find_intersection_placement(
            grid,
            placed_words,
            answer,
            max_grid_size=max_grid_size,
        )
        if placement is not None:
            row, col, direction, _intersections = placement
            path = _crossword_place_word(grid, answer, row, col, direction)
            placed_words.append({**candidate, "answer": answer, "direction": direction, "path": path})
            continue
        if not disconnected_used:
            fallback = _crossword_find_disconnected_placement(grid, answer, max_grid_size=max_grid_size)
            if fallback is not None:
                row, col, direction = fallback
                path = _crossword_place_word(grid, answer, row, col, direction)
                placed_words.append({**candidate, "answer": answer, "direction": direction, "path": path, "disconnected": True})
                disconnected_used = True
                continue
        unplaced_words.append(str(candidate.get("source_word") or answer))

    if not placed_words:
        return None
    min_row = min(row for row, _col in grid)
    max_row = max(row for row, _col in grid)
    min_col = min(col for _row, col in grid)
    max_col = max(col for _row, col in grid)
    for placed in placed_words:
        for cell in placed["path"]:
            cell["row"] -= min_row
            cell["col"] -= min_col
    shifted_grid = {(row - min_row, col - min_col): letter for (row, col), letter in grid.items()}
    rows = max_row - min_row + 1
    cols = max_col - min_col + 1

    starts: dict[tuple[int, int], int] = {}
    next_number = 1
    for placed in sorted(placed_words, key=lambda item: (item["path"][0]["row"], item["path"][0]["col"], item["direction"])):
        start = (placed["path"][0]["row"], placed["path"][0]["col"])
        if start not in starts:
            starts[start] = next_number
            next_number += 1
        placed["number"] = starts[start]
        placed["clue_id"] = f"{placed['direction']}-{placed['number']}-{placed['answer'].lower()}"

    grid_rows: list[list[dict[str, Any]]] = []
    for row in range(rows):
        rendered_row: list[dict[str, Any]] = []
        for col in range(cols):
            letter = shifted_grid.get((row, col))
            rendered_row.append(
                {
                    "row": row,
                    "col": col,
                    "letter": letter or "",
                    "is_black": letter is None,
                    "number": starts.get((row, col)),
                }
            )
        grid_rows.append(rendered_row)

    clues_by_direction = {"across": [], "down": []}
    option_images: dict[str, dict[str, Any]] = {}
    for placed in placed_words:
        clue = {
            "clue_id": placed["clue_id"],
            "number": placed["number"],
            "direction": placed["direction"],
            "answer": placed["answer"],
            "display_answer": placed.get("source_word") or placed["answer"],
            "translation": placed.get("target_gloss") or "",
            "path": placed["path"],
            "dictionary_entry_id": placed.get("dictionary_entry_id"),
            "image_project_id": placed.get("dictionary_project_id"),
            "image_path": placed.get("image_path"),
            "page_number": placed.get("page_number"),
            "segment_index": placed.get("segment_index"),
            "disconnected": bool(placed.get("disconnected")),
        }
        clues_by_direction[placed["direction"]].append(clue)
        option_images[placed["clue_id"]] = {
            "source_word": clue["display_answer"],
            "image_project_id": clue["image_project_id"],
            "image_path": clue["image_path"],
        }
    for clues in clues_by_direction.values():
        clues.sort(key=lambda clue: (clue["number"], clue["display_answer"]))

    path_counts: dict[tuple[int, int], int] = {}
    for placed in placed_words:
        for cell in placed["path"]:
            pos = (cell["row"], cell["col"])
            path_counts[pos] = path_counts.get(pos, 0) + 1
    intersections = sum(1 for count in path_counts.values() if count > 1)
    summary = {
        "selected_count": len(selected),
        "placed_count": len(placed_words),
        "unplaced_words": unplaced_words,
        "intersection_count": intersections,
        "has_disconnected_fallback": any(bool(placed.get("disconnected")) for placed in placed_words),
    }
    first_candidate = placed_words[0]
    return {
        "order_index": 0,
        "page_number": first_candidate.get("page_number") or 1,
        "segment_index": first_candidate.get("segment_index") or 0,
        "segment_text": "Picture-clue crossword",
        "prompt": "Review this picture-clue crossword layout.",
        "answer": "",
        "options": [],
        "rationale": {
            "exercise_kind": "crossword",
            "rows": rows,
            "cols": cols,
            "grid": grid_rows,
            "clues": clues_by_direction,
            "option_images": option_images,
            "summary": summary,
        },
    }


def _image_flashcard_option_metadata(candidates: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(cand.get("source_word") or "").casefold(): {
            "surface": cand.get("source_word") or "",
            "pos": cand.get("pos") or "",
            "script": cand.get("script") or "",
            "translation": cand.get("target_gloss") or "",
        }
        for cand in candidates
        if cand.get("source_word")
    }


def _append_fallback_distractors(
    distractors: list[str],
    fallback_values: list[Any],
    *,
    forbidden_values: set[str],
    answer: str | None = None,
    answer_pos: str = "",
    answer_script: str = "",
    known_metadata: dict[str, dict[str, Any]] | None = None,
    limit: int = 3,
) -> list[str]:
    """Top up distractors from known project values before using placeholders."""

    answer_value = answer or next(iter(forbidden_values), "")
    topped_up = _exercise_filter_distractors(
        distractors,
        answer=answer_value,
        answer_pos=answer_pos,
        answer_script=answer_script,
        known_metadata=known_metadata,
        forbidden_values=forbidden_values,
        limit=limit,
    )
    seen = {value.casefold() for value in topped_up}
    forbidden = {value.casefold() for value in forbidden_values if value}
    for candidate in _exercise_ranked_fallback_values(
        fallback_values,
        answer=answer_value,
        answer_pos=answer_pos,
        answer_script=answer_script,
    ):
        key = candidate.casefold()
        if key in seen or key in forbidden:
            continue
        topped_up.append(candidate)
        seen.add(key)
        if len(topped_up) >= limit:
            break
    return topped_up[:limit]


async def _generate_cloze_item(
    client: OpenAIClient,
    model: str,
    theme: str,
    candidate: dict[str, Any],
    order_index: int,
    fallback_words: list[Any],
) -> dict[str, Any]:
    target_meta = candidate["words"][order_index % len(candidate["words"])]
    target_word = str(target_meta.get("surface") or "").strip()
    target_pos = str(target_meta.get("pos") or "")
    target_script = str(target_meta.get("script") or "")
    target_category = EXERCISE_LEXICAL_CATEGORIES.get(
        _exercise_lexical_category(target_pos),
        target_pos or "the same broad lexical category",
    )
    segment_text = candidate["segment_text"]
    cloze_text = segment_text.replace(target_word, "____", 1)
    prompt = f"""
Create exactly 3 plausible distractors for a cloze exercise.
Theme: {theme}
Segment: {segment_text}
Correct answer: {target_word}
Correct answer POS/category: {target_pos or "unknown"} ({target_category})
Hard constraints:
- Use the same broad lexical category as the correct answer when possible.
- Use the same language and script as the correct answer.
- Use similar length/form to reduce trivial elimination.
- Avoid duplicates, spelling variants, and near-identical inflections of the correct answer.
- Each distractor must make the sentence clearly incorrect in context.
- Do not produce near-synonyms that could still fit.

Return JSON with:
- distractors: array of 3 strings
- rationale: object mapping each distractor string to one short rationale
"""
    try:
        data = await client.chat_json(prompt, model=model)
    except Exception:
        data = {}
    distractors = [str(x).strip() for x in (data.get("distractors") or []) if str(x).strip()]
    known_metadata = {
        str(meta.get("surface") or "").casefold(): meta
        for meta in [*candidate.get("token_metadata", []), *fallback_words]
        if isinstance(meta, dict) and meta.get("surface")
    }
    distractors = _append_fallback_distractors(
        distractors,
        fallback_words,
        forbidden_values={target_word},
        answer=target_word,
        answer_pos=target_pos,
        answer_script=target_script,
        known_metadata=known_metadata,
    )
    while len(distractors) < 3:
        distractors.append(f"option {len(distractors)+1}")
    options = [target_word] + distractors
    random.Random(f"{target_word}|{segment_text}|{order_index}|cloze").shuffle(options)
    if options and options[0] == target_word and len(options) > 1:
        options[0], options[1] = options[1], options[0]
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
    fallback_values: list[Any],
) -> dict[str, Any]:
    source_word = candidate["source_word"]
    correct_gloss = candidate["target_gloss"]
    source_pos = str(candidate.get("pos") or "")
    source_script = str(candidate.get("script") or "")
    source_category = EXERCISE_LEXICAL_CATEGORIES.get(
        _exercise_lexical_category(source_pos),
        source_pos or "the same broad lexical category",
    )
    segment_text = candidate["segment_text"]
    if flashcard_mode == "meaning_to_form":
        prompt = f"""
Create exactly 3 WRONG distractor source-language words for a flashcard multiple-choice item.
Theme: {theme}
Gloss-language prompt: {correct_gloss}
Correct source-language answer: {source_word}
Correct answer POS/category: {source_pos or "unknown"} ({source_category})
Segment context: {segment_text}
Hard constraints:
- Every distractor must be incorrect for this prompt.
- Use the same broad lexical category/POS as the correct answer when possible.
- Use the same language and script as the correct answer.
- Use similar length/form to reduce trivial elimination.
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
Source word POS/category: {source_pos or "unknown"} ({source_category})
Correct gloss: {correct_gloss}
Segment context: {segment_text}
Hard constraints:
- Every distractor must be incorrect for this source word in this context.
- Prefer meanings for source-language words with the same broad lexical category/POS.
- Use similar length/form to reduce trivial elimination.
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
    answer = source_word if flashcard_mode == "meaning_to_form" else correct_gloss
    known_metadata = {
        str(meta.get("surface") or meta.get("value") or "").casefold(): meta
        for meta in [*candidate.get("token_metadata", []), *fallback_values]
        if isinstance(meta, dict) and (meta.get("surface") or meta.get("value"))
    }
    distractors = _append_fallback_distractors(
        distractors,
        fallback_values,
        forbidden_values={source_word, correct_gloss, answer},
        answer=answer,
        answer_pos=source_pos,
        answer_script=source_script if flashcard_mode == "meaning_to_form" else "",
        known_metadata=known_metadata if flashcard_mode == "meaning_to_form" else None,
    )
    while len(distractors) < 3:
        distractors.append(f"option {len(distractors)+1}")

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


async def _generate_image_flashcard_item(
    client: OpenAIClient,
    model: str,
    theme: str,
    candidate: dict[str, Any],
    order_index: int,
    fallback_values: list[dict[str, Any]],
) -> dict[str, Any]:
    source_word = candidate["source_word"]
    correct_gloss = candidate["target_gloss"]
    source_pos = str(candidate.get("pos") or "")
    source_script = str(candidate.get("script") or "")
    source_category = EXERCISE_LEXICAL_CATEGORIES.get(
        _exercise_lexical_category(source_pos),
        source_pos or "the same broad lexical category",
    )
    pool_lines = []
    for cand in fallback_values[:40]:
        word = str(cand.get("surface") or cand.get("value") or "").strip()
        translation = str(cand.get("translation") or "").strip()
        pos = str(cand.get("pos") or "").strip()
        if word and word.casefold() != source_word.casefold():
            pool_lines.append(f"- {word} | translation: {translation or '[unknown]'} | POS: {pos or '[unknown]'}")
    pool_text = "\n".join(pool_lines)
    prompt = f"""
Choose exactly 3 WRONG source-language word distractors for an image-to-word flashcard.
Theme: {theme}
The image represents this correct source-language word: {source_word}
Translation/gloss of the correct word: {correct_gloss}
Correct answer POS/category: {source_pos or "unknown"} ({source_category})
Candidate distractor pool (source word | translation | POS):
{pool_text}
Hard constraints:
- Choose distractors only from the candidate pool.
- Every distractor must be incorrect for the image.
- Use the translations/glosses to avoid near-synonyms or words that could plausibly describe the same image.
- Prefer the same broad lexical category/POS as the correct answer when possible.
- Use the same language and script as the correct answer.
- Use similar length/form to reduce trivial elimination.
- Do NOT return the correct answer or close variants/spellings/morphological forms of it.

Return JSON with:
- distractors: array of 3 source-language words from the pool
- rationale: object mapping each distractor to a short reason it is clearly wrong
"""
    try:
        data = await client.chat_json(prompt, model=model)
    except Exception:
        data = {}
    known_metadata = _image_flashcard_option_metadata(fallback_values)
    distractors = [
        str(x).strip()
        for x in (data.get("distractors") or [])
        if str(x).strip() and str(x).strip().casefold() in known_metadata
    ]
    distractors = _append_fallback_distractors(
        distractors,
        fallback_values,
        forbidden_values={source_word},
        answer=source_word,
        answer_pos=source_pos,
        answer_script=source_script,
        known_metadata=known_metadata,
    )
    while len(distractors) < 3:
        distractors.append(f"option {len(distractors)+1}")

    answer = source_word
    options = [answer] + distractors
    random.Random(f"{source_word}|{correct_gloss}|{candidate.get('image_path')}|{order_index}|image_to_form").shuffle(options)
    if options and options[0] == answer and len(options) > 1:
        options[0], options[1] = options[1], options[0]
    option_translations = {
        opt: str(known_metadata.get(opt.casefold(), {}).get("translation") or "")
        for opt in options
    }
    rationale = data.get("rationale") if isinstance(data.get("rationale"), dict) else {}
    rationale = {
        **rationale,
        "exercise_kind": "image_to_form",
        "image_project_id": candidate.get("dictionary_project_id"),
        "image_path": candidate.get("image_path"),
        "dictionary_entry_id": candidate.get("dictionary_entry_id"),
        "answer_translation": correct_gloss,
        "option_translations": option_translations,
    }
    return {
        "order_index": order_index,
        "page_number": candidate["page_number"],
        "segment_index": candidate["segment_index"],
        "segment_text": candidate["segment_text"],
        "prompt": "Choose the word that matches the image.",
        "answer": answer,
        "options": options,
        "rationale": rationale,
    }


async def _generate_form_to_image_flashcard_item(
    client: OpenAIClient,
    model: str,
    theme: str,
    candidate: dict[str, Any],
    order_index: int,
    fallback_values: list[dict[str, Any]],
) -> dict[str, Any]:
    source_word = candidate["source_word"]
    correct_gloss = candidate["target_gloss"]
    source_pos = str(candidate.get("pos") or "")
    source_script = str(candidate.get("script") or "")
    known_metadata = {
        str(cand.get("source_word") or "").casefold(): cand
        for cand in fallback_values
        if cand.get("source_word")
    }
    pool_lines = []
    for cand in fallback_values[:40]:
        word = str(cand.get("source_word") or "").strip()
        translation = str(cand.get("target_gloss") or "").strip()
        pos = str(cand.get("pos") or "").strip()
        if word and word.casefold() != source_word.casefold():
            pool_lines.append(f"- {word} | translation: {translation or '[unknown]'} | POS: {pos or '[unknown]'}")
    prompt = f"""
Choose exactly 3 WRONG source-language word distractors for a word-to-image flashcard.
Theme: {theme}
Correct source-language word: {source_word}
Correct translation/gloss: {correct_gloss}
Candidate distractor pool:
{chr(10).join(pool_lines)}
Hard constraints:
- Choose distractors only from the candidate pool.
- Every distractor must be incorrect for the prompt word.
- Prefer same broad lexical category/POS and script where possible.
- Do not return the correct word or close variants.
Return JSON with:
- distractors: array of 3 source-language words from the pool
"""
    try:
        data = await client.chat_json(prompt, model=model)
    except Exception:
        data = {}
    distractors = [
        str(x).strip()
        for x in (data.get("distractors") or [])
        if str(x).strip() and str(x).strip().casefold() in known_metadata
    ]
    distractors = _append_fallback_distractors(
        distractors,
        [{"surface": c.get("source_word", ""), "pos": c.get("pos", ""), "script": c.get("script", "")} for c in fallback_values],
        forbidden_values={source_word},
        answer=source_word,
        answer_pos=source_pos,
        answer_script=source_script,
        known_metadata=_image_flashcard_option_metadata(fallback_values),
    )
    # Keep only distractors with usable image metadata; this mode requires image-backed options.
    distractors = [
        d
        for d in distractors
        if d.casefold() in known_metadata
        and str(known_metadata[d.casefold()].get("image_path") or "").strip()
    ]
    options_words = [source_word] + distractors[:3]
    while len(options_words) < 4:
        for cand in fallback_values:
            word = str(cand.get("source_word") or "").strip()
            if not word or word.casefold() == source_word.casefold():
                continue
            if word in options_words:
                continue
            if not str(cand.get("image_path") or "").strip():
                continue
            options_words.append(word)
            if len(options_words) >= 4:
                break
        if len(options_words) >= 4:
            break
        # deterministic hard fallback: reuse known valid dictionary words from pool
        break
    options_words = options_words[:4]
    labels = ["A", "B", "C", "D"]
    random.Random(f"{source_word}|{candidate.get('image_path')}|{order_index}|form_to_image").shuffle(options_words)
    label_to_word = {label: word for label, word in zip(labels, options_words)}
    correct_label = next((k for k, v in label_to_word.items() if v == source_word), labels[0])
    option_images = {
        label: {
            "source_word": word,
            "image_project_id": known_metadata.get(word.casefold(), {}).get("dictionary_project_id"),
            "image_path": known_metadata.get(word.casefold(), {}).get("image_path"),
        }
        for label, word in label_to_word.items()
    }
    trace = {
        "mode": "form_to_image",
        "candidate_source_word_seen_in_text": candidate.get("source_word_seen_in_text"),
        "dictionary_surface": candidate.get("dictionary_surface"),
        "pool_size": len(fallback_values),
        "selected_option_words": options_words,
        "missing_option_images": [w for w in options_words if not option_images.get(next((k for k,v in label_to_word.items() if v==w), ""), {}).get("image_path")],
    }
    return {
        "order_index": order_index,
        "page_number": candidate["page_number"],
        "segment_index": candidate["segment_index"],
        "segment_text": candidate["segment_text"],
        "prompt": f"Choose the image that matches: {source_word}",
        "answer": correct_label,
        "options": labels,
        "rationale": {
            "exercise_kind": "form_to_image",
            "correct_source_word": source_word,
            "correct_translation": correct_gloss,
            "option_images": option_images,
            "trace": trace,
        },
    }


@login_required
def generate_cloze_exercises(request: HttpRequest, pk: int) -> HttpResponse:
    project = _get_project_for_user(pk=pk, user=request.user, min_role=ProjectCollaborator.ROLE_ANNOTATOR)
    run_dir = _resolve_project_compiled_run_dir(project) or _resolve_run_dir(project)
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
            fallback_words = []
            for cand in candidates:
                fallback_words.extend(cand.get("words") or [])
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
                    _generate_cloze_item(client, model, theme, cand, idx, fallback_words)
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
    run_dir = _resolve_project_compiled_run_dir(project) or _resolve_run_dir(project)
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

            if flashcard_mode in {ExerciseSet.FLASHCARD_MODE_IMAGE_TO_FORM, ExerciseSet.FLASHCARD_MODE_FORM_TO_IMAGE}:
                dictionary = _find_project_picture_dictionary(project)
                if not dictionary:
                    messages.error(
                        request,
                        "Image flashcards require an active picture dictionary for this project's community/language.",
                    )
                    return redirect("project-detail", pk=project.pk)
                candidates = _extract_image_flashcard_candidates(run_dir, dictionary=dictionary)
                if len(candidates) < 4:
                    messages.error(
                        request,
                        "Image flashcards require at least four current-project words that also have images and translations in the picture dictionary.",
                    )
                    return redirect("project-detail", pk=project.pk)
                selected = candidates[:item_count]
                fallback_values = [
                    {
                        "surface": cand["source_word"],
                        "value": cand["source_word"],
                        "pos": cand.get("pos") or "",
                        "script": cand.get("script") or "",
                        "translation": cand.get("target_gloss") or "",
                    }
                    for cand in candidates
                ]
            else:
                candidates = _extract_token_candidates_for_flashcards(run_dir)
                if not candidates:
                    messages.error(
                        request,
                        "Could not find suitable glossed tokens for flashcard generation. Run glossing first.",
                    )
                    return redirect("project-detail", pk=project.pk)

                selected = candidates[:item_count]
                fallback_values = [
                    {
                        "surface": cand["source_word"] if flashcard_mode == "meaning_to_form" else cand["target_gloss"],
                        "value": cand["source_word"] if flashcard_mode == "meaning_to_form" else cand["target_gloss"],
                        "pos": cand.get("pos") or "",
                        "script": (cand.get("script") or "") if flashcard_mode == "meaning_to_form" else "",
                    }
                    for cand in candidates
                ]
            ex_set = ExerciseSet.objects.create(
                project=project,
                exercise_type=ExerciseSet.TYPE_FLASHCARD,
                flashcard_mode=flashcard_mode,
                theme=theme,
                title=f"{project.title} — Flashcards ({flashcard_mode}, {theme})",
                status=ExerciseSet.STATUS_DRAFT,
                created_by=request.user,
            )

            client = _build_billed_project_ai_client(
                project,
                model_name=model,
                request_type="exercise_flashcard_generation",
            )

            async def _run() -> list[dict[str, Any]]:
                if flashcard_mode == ExerciseSet.FLASHCARD_MODE_IMAGE_TO_FORM:
                    tasks = [
                        _generate_image_flashcard_item(client, model, theme, cand, idx, fallback_values)
                        for idx, cand in enumerate(selected)
                    ]
                elif flashcard_mode == ExerciseSet.FLASHCARD_MODE_FORM_TO_IMAGE:
                    tasks = [
                        _generate_form_to_image_flashcard_item(client, model, theme, cand, idx, candidates)
                        for idx, cand in enumerate(selected)
                    ]
                else:
                    tasks = [
                        _generate_flashcard_item(client, model, theme, cand, idx, flashcard_mode, fallback_values)
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
def generate_word_scramble_exercises(request: HttpRequest, pk: int) -> HttpResponse:
    project = _get_project_for_user(pk=pk, user=request.user, min_role=ProjectCollaborator.ROLE_ANNOTATOR)
    run_dir = _resolve_project_compiled_run_dir(project) or _resolve_run_dir(project)
    if run_dir is None or not run_dir.exists():
        messages.error(request, "Please run the pipeline first to generate stage artifacts.")
        return redirect("project-detail", pk=project.pk)

    if request.method == "POST":
        form = WordScrambleExerciseSetForm(request.POST)
        if form.is_valid():
            theme = form.cleaned_data["theme"]
            item_count = form.cleaned_data["item_count"]
            grid_rows = form.cleaned_data["grid_rows"]
            grid_cols = form.cleaned_data["grid_cols"]
            dictionary = _find_project_picture_dictionary(project)
            if not dictionary:
                messages.error(
                    request,
                    "Word scrambles require an active picture dictionary for this project's community/language.",
                )
                return redirect("project-detail", pk=project.pk)
            candidates = _extract_image_flashcard_candidates(run_dir, dictionary=dictionary)
            if not candidates:
                messages.error(
                    request,
                    "Could not find current-project words that have translations and picture-dictionary images.",
                )
                return redirect("project-detail", pk=project.pk)
            seed = f"{project.pk}|{django_timezone.now().isoformat()}|word_scramble"
            items, grid_payload = _generate_word_scramble_items(
                candidates,
                item_count=item_count,
                rows=grid_rows,
                cols=grid_cols,
                seed=seed,
            )
            if not items:
                messages.error(
                    request,
                    "Could not place any picture-dictionary words in the requested grid. Try a larger grid or fewer/shorter words.",
                )
                return redirect("project-generate-word-scramble", pk=project.pk)

            ex_set = ExerciseSet.objects.create(
                project=project,
                exercise_type=ExerciseSet.TYPE_WORD_SCRAMBLE,
                theme=theme,
                title=f"{project.title} — Picture word scramble ({len(items)} words)",
                instructions=(
                    "Look at each picture clue, then select the matching letters in the grid. "
                    "The written answer is hidden until you check your selection."
                ),
                status=ExerciseSet.STATUS_DRAFT,
                created_by=request.user,
            )
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
            messages.success(
                request,
                f"Generated a {grid_payload['rows']}×{grid_payload['cols']} word scramble with {len(items)} picture clues.",
            )
            return redirect("exercise-set-detail", set_id=ex_set.id)
    else:
        form = WordScrambleExerciseSetForm()

    return render(
        request,
        "projects/exercise_generate_word_scramble.html",
        {"project": project, "form": form},
    )


@login_required
def generate_crossword_exercises(request: HttpRequest, pk: int) -> HttpResponse:
    project = _get_project_for_user(pk=pk, user=request.user, min_role=ProjectCollaborator.ROLE_ANNOTATOR)
    run_dir = _resolve_project_compiled_run_dir(project) or _resolve_run_dir(project)
    if run_dir is None or not run_dir.exists():
        messages.error(request, "Please run the pipeline first to generate stage artifacts.")
        return redirect("project-detail", pk=project.pk)

    if request.method == "POST":
        form = CrosswordExerciseSetForm(request.POST)
        if form.is_valid():
            theme = form.cleaned_data["theme"]
            item_count = form.cleaned_data["item_count"]
            max_grid_size = form.cleaned_data["max_grid_size"]
            dictionary = _find_project_picture_dictionary(project)
            if not dictionary:
                messages.error(
                    request,
                    "Crosswords require an active picture dictionary for this project's community/language.",
                )
                return redirect("project-detail", pk=project.pk)
            candidates = _extract_image_flashcard_candidates(run_dir, dictionary=dictionary)
            if len(candidates) < 2:
                messages.error(
                    request,
                    "Crosswords require at least two current-project words that have translations and picture-dictionary images.",
                )
                return redirect("project-detail", pk=project.pk)
            item = _build_crossword_item(candidates, item_count=item_count, max_grid_size=max_grid_size)
            if item is None:
                messages.error(
                    request,
                    "Could not build a crossword from the available picture-dictionary words. Try more/shorter words or use a word scramble.",
                )
                return redirect("project-generate-crossword", pk=project.pk)

            summary = item["rationale"].get("summary", {}) if isinstance(item.get("rationale"), dict) else {}
            ex_set = ExerciseSet.objects.create(
                project=project,
                exercise_type=ExerciseSet.TYPE_CROSSWORD,
                theme=theme,
                title=f"{project.title} — Picture crossword ({summary.get('placed_count', 0)} words)",
                instructions=(
                    "Review the generated picture-clue crossword layout. "
                    "This first version renders the static grid and across/down picture clues."
                ),
                status=ExerciseSet.STATUS_DRAFT,
                created_by=request.user,
            )
            ExerciseItem.objects.create(
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
            ex_set.status = ExerciseSet.STATUS_READY
            ex_set.save(update_fields=["status", "updated_at"])
            unplaced = summary.get("unplaced_words") or []
            if unplaced:
                messages.warning(request, f"Generated crossword; {len(unplaced)} word(s) could not be placed.")
            messages.success(request, f"Generated a picture crossword with {summary.get('placed_count', 0)} placed words.")
            return redirect("exercise-set-detail", set_id=ex_set.id)
    else:
        form = CrosswordExerciseSetForm()

    return render(
        request,
        "projects/exercise_generate_crossword.html",
        {"project": project, "form": form},
    )


@login_required
def exercise_item_image(request: HttpRequest, item_id: int) -> HttpResponse:
    item = get_object_or_404(
        ExerciseItem.objects.select_related("exercise_set", "exercise_set__project"),
        pk=item_id,
    )
    ex_set = item.exercise_set
    project = ex_set.project
    if project.owner != request.user and not ex_set.is_published:
        raise Http404()
    rationale = item.rationale if isinstance(item.rationale, dict) else {}
    image_project_id = rationale.get("image_project_id")
    image_path = str(rationale.get("image_path") or "").strip()
    if not image_project_id or not image_path:
        raise Http404()
    image_project = get_object_or_404(Project, pk=image_project_id)
    base = image_project.artifact_dir().resolve()
    file_path = (base / image_path).resolve()
    try:
        file_path.relative_to(base)
    except ValueError:
        raise Http404()
    if not file_path.exists() or not file_path.is_file():
        raise Http404()
    content_type, _ = mimetypes.guess_type(str(file_path))
    return FileResponse(open(file_path, "rb"), content_type=content_type or "application/octet-stream")


@login_required
def exercise_item_option_image(request: HttpRequest, item_id: int, option_key: str) -> HttpResponse:
    item = get_object_or_404(
        ExerciseItem.objects.select_related("exercise_set", "exercise_set__project"),
        pk=item_id,
    )
    ex_set = item.exercise_set
    project = ex_set.project
    if project.owner != request.user and not ex_set.is_published:
        raise Http404()
    rationale = item.rationale if isinstance(item.rationale, dict) else {}
    option_images = rationale.get("option_images")
    if not isinstance(option_images, dict):
        raise Http404()
    payload = option_images.get(option_key)
    if not isinstance(payload, dict):
        raise Http404()
    image_project_id = payload.get("image_project_id")
    image_path = str(payload.get("image_path") or "").strip()
    if not image_project_id or not image_path:
        raise Http404()
    image_project = get_object_or_404(Project, pk=image_project_id)
    base = image_project.artifact_dir().resolve()
    file_path = (base / image_path).resolve()
    try:
        file_path.relative_to(base)
    except ValueError:
        raise Http404()
    if not file_path.exists() or not file_path.is_file():
        raise Http404()
    content_type, _ = mimetypes.guess_type(str(file_path))
    return FileResponse(open(file_path, "rb"), content_type=content_type or "application/octet-stream")


@login_required
def exercise_set_detail(request: HttpRequest, set_id: int) -> HttpResponse:
    ex_set = get_object_or_404(ExerciseSet.objects.select_related("project"), pk=set_id)
    project = ex_set.project
    if project.owner != request.user and not ex_set.is_published:
        raise Http404()
    back_url = _safe_exercise_back_url(request)
    return render(
        request,
        "projects/exercise_set_detail.html",
        {"exercise_set": ex_set, "items": ex_set.items.all(), "project": project, "back_url": back_url},
    )


@login_required
def exercise_set_play(request: HttpRequest, set_id: int) -> HttpResponse:
    ex_set = get_object_or_404(ExerciseSet.objects.select_related("project"), pk=set_id)
    project = ex_set.project
    if project.owner != request.user and not ex_set.is_published:
        raise Http404()
    items = list(ex_set.items.all())
    back_url = _safe_exercise_back_url(request)
    if not items:
        return render(request, "projects/exercise_set_play.html", {"exercise_set": ex_set, "project": project, "done": True, "back_url": back_url})

    idx = int(request.GET.get("i", "0") or "0")
    idx = max(0, min(idx, len(items) - 1))
    current = items[idx]
    feedback = None
    selected = None
    if request.method == "POST":
        selected = (request.POST.get("choice") or "").strip()
        correct = current.answer
        rationale = current.rationale if isinstance(current.rationale, dict) else {}
        if rationale.get("exercise_kind") == "word_scramble":
            selected = _word_scramble_normalize_answer(selected)
            submitted_path_raw = request.POST.get("path") or "[]"
            try:
                submitted_path = json.loads(submitted_path_raw)
            except json.JSONDecodeError:
                submitted_path = []
            expected_path = rationale.get("path") if isinstance(rationale.get("path"), list) else []
            is_path_match = submitted_path == expected_path or submitted_path == list(reversed(expected_path))
            is_correct = (selected == correct or selected == correct[::-1]) and is_path_match
        else:
            is_correct = selected == correct
        feedback = {
            "selected": selected,
            "correct": correct,
            "is_correct": is_correct,
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
            "back_url": back_url,
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

    missing_stages = _missing_source_bundle_stages(stages_dir)
    if missing_stages:
        refreshed_run_dir, refresh_error = _refresh_source_bundle_stages_for_export(
            project=project,
            user=request.user,
            current_run_dir=run_dir,
            missing_stages=missing_stages,
        )
        if refresh_error or refreshed_run_dir is None:
            messages.error(request, refresh_error or "Could not refresh source bundle stage artifacts.")
            return redirect("project-detail", pk=project.pk)
        run_dir = refreshed_run_dir
        stages_dir = run_dir / "stages"
        messages.info(
            request,
            "Missing source bundle stage artifacts were regenerated automatically by rerunning "
            "the pipeline from audio through compile_html before export.",
        )

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
            "discourage_text_in_images": style.discourage_text_in_images,
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
            "audio_mode": project.audio_mode,
        }
        zf.writestr((bundle_root / "project" / "metadata.json").as_posix(), json.dumps(metadata, ensure_ascii=False, indent=2))

        pipeline_config = {
            "ai_model": project.ai_model,
            "segmentation_method": project.segmentation_method,
            "romanization_method": project.romanization_method,
            "page_image_placement": project.page_image_placement,
            "image_generation_pivot_language": project.image_generation_pivot_language,
            "page_image_text_source": project.page_image_text_source,
            "audio_mode": project.audio_mode,
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


def _legacy_bundle_library_root() -> Path | None:
    configured = (getattr(settings, "LEGACY_CLARA_BUNDLE_LIBRARY_ROOT", "") or "").strip()
    if not configured:
        return None
    return Path(configured).expanduser().resolve()


def _legacy_bundle_library_metadata_path() -> Path | None:
    root = _legacy_bundle_library_root()
    if root is None:
        return None
    configured = (getattr(settings, "LEGACY_CLARA_BUNDLE_LIBRARY_METADATA", "legacy_bundle_metadata.json") or "legacy_bundle_metadata.json").strip()
    path = Path(configured).expanduser()
    if not path.is_absolute():
        path = root / path
    return path.resolve()


def _legacy_bundle_library_diagnostics() -> dict[str, Any]:
    root_setting = getattr(settings, "LEGACY_CLARA_BUNDLE_LIBRARY_ROOT", "") or ""
    metadata_setting = getattr(settings, "LEGACY_CLARA_BUNDLE_LIBRARY_METADATA", "legacy_bundle_metadata.json") or "legacy_bundle_metadata.json"
    root = _legacy_bundle_library_root()
    metadata_path = _legacy_bundle_library_metadata_path()
    return {
        "root_setting": root_setting,
        "metadata_setting": metadata_setting,
        "root_path": str(root) if root is not None else "",
        "root_exists": bool(root and root.exists()),
        "root_is_dir": bool(root and root.is_dir()),
        "metadata_path": str(metadata_path) if metadata_path is not None else "",
        "metadata_exists": bool(metadata_path and metadata_path.exists()),
        "env_root_present": "C_LARA_LEGACY_BUNDLE_LIBRARY_ROOT" in os.environ,
        "env_metadata_present": "C_LARA_LEGACY_BUNDLE_LIBRARY_METADATA" in os.environ,
        "process_pid": os.getpid(),
    }


def _load_legacy_bundle_library() -> tuple[list[dict[str, Any]], str | None]:
    root = _legacy_bundle_library_root()
    metadata_path = _legacy_bundle_library_metadata_path()
    if root is None or metadata_path is None:
        return [], "Legacy bundle library root is not configured."
    if not root.exists() or not root.is_dir():
        return [], f"Legacy bundle library root does not exist: {root}"
    try:
        metadata_path.relative_to(root)
    except ValueError:
        return [], "Legacy bundle metadata file must be inside the configured library root."
    if not metadata_path.exists():
        return [], f"Legacy bundle metadata file does not exist: {metadata_path}"
    try:
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return [], f"Could not read legacy bundle metadata: {exc}"
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict) and isinstance(payload.get("bundles"), list):
        rows = payload["bundles"]
    else:
        return [], "Legacy bundle metadata must be a list or an object with a bundles list."
    bundles = [row for row in rows if isinstance(row, dict)]
    return bundles, None


def _filter_legacy_bundle_rows(rows: list[dict[str, Any]], query: dict[str, str]) -> list[dict[str, Any]]:
    def contains(value: Any, needle: str) -> bool:
        return not needle or needle.casefold() in str(value or "").casefold()

    title = (query.get("title") or "").strip()
    owner = (query.get("owner") or "").strip()
    l2 = (query.get("l2") or "").strip()
    l1 = (query.get("l1") or "").strip()
    filtered = []
    for row in rows:
        if not contains(row.get("title"), title):
            continue
        if not contains(row.get("owner_username") or row.get("userid") or row.get("user_id"), owner):
            continue
        if not contains(row.get("l2") or row.get("source_language") or row.get("language"), l2):
            continue
        if not contains(row.get("l1") or row.get("target_language"), l1):
            continue
        filtered.append(row)
    return filtered


def _legacy_bundle_row_key(row: dict[str, Any]) -> str:
    for key in ("id", "directory_name", "relative_path", "import_relative_path", "zip_relative_path"):
        value = row.get(key)
        if value not in (None, ""):
            return str(value)
    return ""


def _find_legacy_bundle_row(rows: list[dict[str, Any]], selection: str) -> dict[str, Any] | None:
    selection = (selection or "").strip()
    if not selection:
        return None
    for row in rows:
        if _legacy_bundle_row_key(row) == selection:
            return row
    return None


def _safe_legacy_import_path(root: Path, row: dict[str, Any]) -> Path | None:
    raw = (
        row.get("import_relative_path")
        or row.get("zip_relative_path")
        or row.get("relative_path")
        or row.get("directory_name")
        or ""
    )
    if not raw:
        return None
    candidate = Path(str(raw))
    if candidate.is_absolute():
        return None
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        return None
    return resolved


def _zip_directory_to_spooled_file(directory: Path):
    spool = tempfile.SpooledTemporaryFile(max_size=20 * 1024 * 1024)
    with zipfile.ZipFile(spool, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(directory.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(directory).as_posix())
    spool.seek(0)
    return spool


def _metadata_arcnames_for_legacy_source_zip(names: list[str]) -> list[str]:
    """Return sidecar metadata locations for a legacy source.zip, if needed."""

    if any(PurePosixPath(name).name == "metadata.json" for name in names):
        return []

    arcnames: list[str] = []
    for name in names:
        path = PurePosixPath(name)
        if path.name != "annotated_text.json":
            continue
        parent = path.parent.as_posix()
        arcnames.append("metadata.json" if parent == "." else f"{parent}/metadata.json")
    return list(dict.fromkeys(arcnames))


def _legacy_zip_trace(names: list[str], *, limit: int = 20) -> dict[str, Any]:
    annotated = [name for name in names if PurePosixPath(name).name == "annotated_text.json"]
    metadata = [name for name in names if PurePosixPath(name).name == "metadata.json"]
    return {
        "entry_count": len(names),
        "first_entries": names[:limit],
        "annotated_text_entries": annotated[:limit],
        "metadata_entries": metadata[:limit],
        "legacy_root_detected": find_legacy_clara_bundle_root(names),
    }


def _format_legacy_import_trace(trace: dict[str, Any] | None) -> str:
    if not trace:
        return ""

    parts = []
    for key in (
        "selected_import_path",
        "selected_import_path_type",
        "source_zip_path",
        "sidecar_metadata_path",
        "sidecar_metadata_exists",
        "injected_metadata_entries",
        "entry_count",
        "annotated_text_entries",
        "metadata_entries",
        "legacy_root_detected",
        "first_entries",
    ):
        if key in trace:
            parts.append(f"{key}={trace[key]}")
    return " Import trace: " + "; ".join(parts) if parts else ""


def _zip_with_sidecar_legacy_metadata(zip_path: Path, metadata_path: Path):
    """Copy a legacy source.zip to a spool, adding sibling metadata.json if needed."""

    spool = tempfile.SpooledTemporaryFile(max_size=20 * 1024 * 1024)
    with zipfile.ZipFile(zip_path) as source_zf:
        names = source_zf.namelist()
        metadata_arcnames = _metadata_arcnames_for_legacy_source_zip(names)
        trace = {
            **_legacy_zip_trace(names),
            "source_zip_path": str(zip_path),
            "sidecar_metadata_path": str(metadata_path),
            "sidecar_metadata_exists": metadata_path.exists(),
            "injected_metadata_entries": metadata_arcnames if metadata_path.exists() else [],
        }
        if not metadata_arcnames or not metadata_path.exists():
            spool.write(zip_path.read_bytes())
        else:
            metadata_text = metadata_path.read_text(encoding="utf-8")
            with zipfile.ZipFile(spool, "w", zipfile.ZIP_DEFLATED) as target_zf:
                for info in source_zf.infolist():
                    target_zf.writestr(info, source_zf.read(info.filename))
                for metadata_arcname in metadata_arcnames:
                    target_zf.writestr(metadata_arcname, metadata_text)
            trace.update(_legacy_zip_trace(names + metadata_arcnames))
    spool.seek(0)
    return spool, trace


def _open_server_bundle_for_import(import_path: Path):
    """Return a spooled ZIP and trace data for a configured server-side bundle path."""

    base_trace = {
        "selected_import_path": str(import_path),
        "selected_import_path_type": "directory" if import_path.is_dir() else "file",
    }

    if import_path.is_dir():
        zip_candidates = sorted(import_path.glob("*.zip"), key=lambda p: (p.name != "source.zip", p.name))
        metadata_path = import_path / "metadata.json"
        if zip_candidates and metadata_path.exists():
            spool, trace = _zip_with_sidecar_legacy_metadata(zip_candidates[0], metadata_path)
            trace.update(base_trace)
            return spool, trace
        spool = _zip_directory_to_spooled_file(import_path)
        with zipfile.ZipFile(spool) as zf:
            trace = {**base_trace, **_legacy_zip_trace(zf.namelist())}
        spool.seek(0)
        return spool, trace

    metadata_path = import_path.with_name("metadata.json")
    if import_path.suffix.lower() == ".zip" and metadata_path.exists():
        spool, trace = _zip_with_sidecar_legacy_metadata(import_path, metadata_path)
        trace.update(base_trace)
        return spool, trace

    spool = tempfile.SpooledTemporaryFile(max_size=20 * 1024 * 1024)
    spool.write(import_path.read_bytes())
    spool.seek(0)
    with zipfile.ZipFile(spool) as zf:
        trace = {**base_trace, **_legacy_zip_trace(zf.namelist())}
    spool.seek(0)
    return spool, trace


def _import_open_project_source_zip(
    request: HttpRequest,
    zf: zipfile.ZipFile,
    *,
    error_redirect: str = "project-list",
    import_trace: dict[str, Any] | None = None,
) -> HttpResponse:
    """Import an already opened source/legacy ZIP and redirect to the created project."""

    names = zf.namelist()
    if not names:
        messages.error(request, "ZIP file is empty.")
        return redirect(error_redirect)

    root = Path(names[0]).parts[0]
    legacy_root = find_legacy_clara_bundle_root(names)
    if legacy_root is not None:
        try:
            base_title = legacy_clara_bundle_title(zf, legacy_root)
            result = import_legacy_clara_bundle(
                zf=zf,
                names=names,
                root=legacy_root,
                user=request.user,
                unique_title=_build_unique_import_title(request.user, base_title),
            )
        except LegacyClaraImportError as exc:
            messages.error(request, str(exc))
            return redirect(error_redirect)
        _persist_project_source(result.project)
        detail = ""
        if result.diagnostics:
            detail = f" Import diagnostics: {'; '.join(result.diagnostics[:3])}"
        messages.success(request, f"Imported legacy C-LARA bundle as new project '{result.project.title}'.{detail}")
        return redirect("project-detail", pk=result.project.pk)

    if is_legacy_clara_project_dir_bundle(names):
        try:
            base_title = legacy_clara_project_dir_bundle_title(zf)
            result = import_legacy_clara_project_dir_bundle(
                zf=zf,
                names=names,
                user=request.user,
                unique_title=_build_unique_import_title(request.user, base_title),
            )
        except LegacyClaraImportError as exc:
            messages.error(request, f"{exc}{_format_legacy_import_trace(import_trace or _legacy_zip_trace(names))}")
            return redirect(error_redirect)
        _persist_project_source(result.project)
        detail = ""
        if result.diagnostics:
            detail = f" Import diagnostics: {'; '.join(result.diagnostics[:3])}"
        messages.success(request, f"Imported legacy C-LARA project_dir bundle as new project '{result.project.title}'.{detail}")
        return redirect("project-detail", pk=result.project.pk)

    metadata = _safe_zip_read_json(zf, f"{root}/project/metadata.json")
    if not metadata:
        legacy_hint = ""
        if any(PurePosixPath(name).name == "annotated_text.json" for name in names):
            legacy_hint = " The ZIP looks like a legacy C-LARA export because it contains annotated_text.json, but metadata.json was not found beside it."
        messages.error(request, f"Bundle is missing project metadata.{legacy_hint}{_format_legacy_import_trace(import_trace or _legacy_zip_trace(names))}")
        return redirect(error_redirect)

    stage_prefix = f"{root}/stages/"
    missing_stages = _missing_source_bundle_zip_stages(names, stage_prefix)
    if missing_stages:
        messages.error(
            request,
            "Source bundle is missing required stage artifacts: "
            f"{', '.join(missing_stages)}. Re-export the project after regenerating source bundle stages.",
        )
        return redirect(error_redirect)

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
            (metadata.get("image_generation_pivot_language") or "none")
            if (metadata.get("image_generation_pivot_language") or "none") in valid_pivot_languages
            else "none"
        ),
        page_image_text_source=(
            metadata.get("page_image_text_source")
            if metadata.get("page_image_text_source") in {value for value, _label in Project.PAGE_IMAGE_TEXT_SOURCE_CHOICES}
            else Project.PAGE_IMAGE_TEXT_SOURCE_SEGMENTATION
        ),
        access_scope=(
            metadata.get("access_scope")
            if metadata.get("access_scope") in {value for value, _label in Project.ACCESS_CHOICES}
            else Project.ACCESS_PRIVATE
        ),
        segmentation_method=_normalize_processing_method_choice(
            metadata.get("segmentation_method"), SEGMENTATION_METHOD_CHOICES
        ) or "auto",
        romanization_method=_normalize_processing_method_choice(
            metadata.get("romanization_method"), ROMANIZATION_METHOD_CHOICES
        ) or "auto",
        audio_mode=(
            metadata.get("audio_mode")
            if metadata.get("audio_mode") in {Project.AUDIO_MODE_TTS, Project.AUDIO_MODE_NONE}
            else Project.AUDIO_MODE_TTS
        ),
    )
    artifact_root = project.artifact_dir()
    artifact_root.mkdir(parents=True, exist_ok=True)
    run_dir = artifact_root / "runs" / "run_imported_source_bundle"
    stages_dir = run_dir / "stages"
    stages_dir.mkdir(parents=True, exist_ok=True)

    def _safe_write(member_name: str, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        with zf.open(member_name) as src, target.open("wb") as dst:
            shutil.copyfileobj(src, dst)

    for stage in PIPELINE_ORDER:
        member = f"{root}/stages/{stage}.json"
        if member in names:
            _safe_write(member, stages_dir / f"{stage}.json")

    logs_prefix = f"{root}/logs/"
    for member_name in names:
        if not member_name.startswith(logs_prefix):
            continue
        rel = Path(member_name).relative_to(logs_prefix)
        target = (run_dir / "logs" / rel).resolve()
        try:
            target.relative_to(run_dir / "logs")
        except ValueError:
            continue
        _safe_write(member_name, target)

    style_payload = _safe_zip_read_json(zf, f"{root}/images/style.json")
    if isinstance(style_payload, dict):
        ProjectImageStyle.objects.update_or_create(
            project=project,
            defaults={
                "style_brief": style_payload.get("style_brief") or "",
                "expanded_style_description": (
                    style_payload.get("expanded_style_description")
                    or style_payload.get("style_text")
                    or ""
                ),
                "representative_excerpt": style_payload.get("representative_excerpt") or "",
                "sample_image_prompt": style_payload.get("sample_image_prompt") or "",
                "sample_image_path": (style_payload.get("sample_image_path") or "")[:512],
                "sample_image_revised_prompt": style_payload.get("sample_image_revised_prompt") or "",
                "sample_image_model": (
                    style_payload.get("sample_image_model")
                    or style_payload.get("image_model")
                    or "gpt-image-1"
                )[:64],
                "discourage_text_in_images": bool(style_payload.get("discourage_text_in_images")),
                "ai_model": (style_payload.get("ai_model") or DEFAULT_MODEL)[:64],
                "status": (style_payload.get("status") or ProjectImageStyle.STATUS_APPROVED)[:32],
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
def import_project_source_bundle(request: HttpRequest) -> HttpResponse:
    """Compatibility endpoint for the original source-bundle upload form."""

    if request.method != "POST":
        return redirect("project-import-zip")

    upload = request.FILES.get("source_bundle")
    if upload is None:
        messages.error(request, "Please select a ZIP file to import.")
        return redirect("project-import-zip")

    try:
        zf = zipfile.ZipFile(upload)
    except zipfile.BadZipFile:
        messages.error(request, "Could not read ZIP file.")
        return redirect("project-import-zip")
    try:
        with zf:
            return _import_open_project_source_zip(request, zf, error_redirect="project-import-zip")
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to import uploaded source bundle")
        messages.error(request, f"Could not import ZIP file: {exc}")
        return redirect("project-import-zip")


@login_required
def import_project_zip(request: HttpRequest) -> HttpResponse:
    """Import a project ZIP from upload or an admin-configured legacy corpus."""

    legacy_rows: list[dict[str, Any]] = []
    legacy_error: str | None = None
    legacy_query = {
        "title": (request.GET.get("title") or "").strip(),
        "owner": (request.GET.get("owner") or "").strip(),
        "l2": (request.GET.get("l2") or "").strip(),
        "l1": (request.GET.get("l1") or "").strip(),
    }
    if request.user.is_staff:
        all_rows, legacy_error = _load_legacy_bundle_library()
        legacy_rows = _filter_legacy_bundle_rows(all_rows, legacy_query)[:200]

    if request.method == "POST":
        mode = (request.POST.get("import_mode") or "upload").strip()
        if mode == "server_bundle":
            if not request.user.is_staff:
                raise PermissionDenied
            root = _legacy_bundle_library_root()
            rows, legacy_error = _load_legacy_bundle_library()
            if root is None or legacy_error:
                messages.error(request, legacy_error or "Legacy bundle library is not configured.")
                return redirect("project-import-zip")
            row = _find_legacy_bundle_row(rows, request.POST.get("bundle_key") or "")
            if row is None:
                messages.error(request, "Please choose a legacy bundle to import.")
                return redirect("project-import-zip")
            import_path = _safe_legacy_import_path(root, row)
            if import_path is None or not import_path.exists():
                messages.error(request, "Selected legacy bundle path is missing or unsafe.")
                return redirect("project-import-zip")
            try:
                spool, import_trace = _open_server_bundle_for_import(import_path)
                with spool:
                    with zipfile.ZipFile(spool) as zf:
                        return _import_open_project_source_zip(request, zf, error_redirect="project-import-zip", import_trace=import_trace)
            except Exception as exc:  # noqa: BLE001
                messages.error(request, f"Could not import selected legacy bundle: {exc}")
                return redirect("project-import-zip")

        upload = request.FILES.get("source_bundle")
        if upload is None:
            messages.error(request, "Please select a ZIP file to import.")
            return redirect("project-import-zip")
        try:
            with zipfile.ZipFile(upload) as zf:
                return _import_open_project_source_zip(request, zf, error_redirect="project-import-zip")
        except zipfile.BadZipFile:
            messages.error(request, "Could not read ZIP file.")
            return redirect("project-import-zip")
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to import uploaded project ZIP")
            messages.error(request, f"Could not import ZIP file: {exc}")
            return redirect("project-import-zip")

    return render(
        request,
        "projects/import_zip.html",
        {
            "legacy_rows": legacy_rows,
            "legacy_error": legacy_error,
            "legacy_query": legacy_query,
            "legacy_library_configured": _legacy_bundle_library_root() is not None,
            "legacy_library_diagnostics": _legacy_bundle_library_diagnostics() if request.user.is_staff else None,
        },
    )


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
                "discourage_text_in_images": source_style.discourage_text_in_images,
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
        audio_mode=source_project.audio_mode,
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
