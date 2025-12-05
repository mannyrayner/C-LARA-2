from __future__ import annotations

import asyncio
import json
import logging
import shutil
import threading
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Any

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import FileResponse, Http404, HttpRequest, HttpResponse
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.generic import DetailView, ListView, CreateView
import mimetypes
from urllib.parse import unquote

from core.config import OpenAIConfig
from core.ai_api import OpenAIClient
from pipeline.full_pipeline import FullPipelineSpec, PIPELINE_ORDER, run_full_pipeline

from .forms import ProfileForm, ProjectForm, RegistrationForm
from .models import Profile, Project

logger = logging.getLogger(__name__)


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


class ProjectListView(LoginRequiredMixin, ListView):
    model = Project
    template_name = "projects/project_list.html"

    def get_queryset(self):  # type: ignore[override]
        return Project.objects.filter(owner=self.request.user)


class ProjectDetailView(LoginRequiredMixin, DetailView):
    model = Project
    template_name = "projects/project_detail.html"

    def get_queryset(self):  # type: ignore[override]
        return Project.objects.filter(owner=self.request.user)
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
                            progress.append(json.loads(line))
                        except Exception:
                            continue
                    progress.sort(key=lambda p: p.get("timestamp", ""))

        context["stage_files"] = stage_files
        context["progress"] = progress
        context["pipeline_stages"] = PIPELINE_ORDER
        context["default_start_stage"] = (
            "text_gen" if project.input_mode == Project.INPUT_DESCRIPTION else "segmentation_phase_1"
        )
        context["compiled_uri"] = compiled_uri
        context["compiled_media_url"] = compiled_media_url
        return context


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


def _build_ai_client() -> OpenAIClient:
    config = OpenAIConfig()
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


def _load_stage_payload(project: Project, stage: str) -> dict[str, Any] | None:
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


@login_required
def compile_project(request: HttpRequest, pk: int) -> HttpResponse:
    project = get_object_or_404(Project, pk=pk, owner=request.user)
    project_root = project.artifact_dir().resolve()
    _persist_project_source(project)
    output_dir = _prepare_output_dir(project).resolve()
    stage_dir = output_dir / "stages"
    stage_dir.mkdir(parents=True, exist_ok=True)
    progress_log = stage_dir / "progress.jsonl"

    try:
        profile = request.user.profile
        timezone_name = profile.timezone or "UTC"
    except Profile.DoesNotExist:
        timezone_name = "UTC"

    def _start_progress_watcher() -> tuple[threading.Event, threading.Thread]:
        stop_event = threading.Event()

        def _watch_progress_log() -> None:
            last_pos = 0
            while not stop_event.is_set():
                try:
                    if progress_log.exists():
                        with progress_log.open("r", encoding="utf-8") as fp:
                            fp.seek(last_pos)
                            while True:
                                line = fp.readline()
                                if not line:
                                    break

                                last_pos = fp.tell()
                                try:
                                    entry = json.loads(line)
                                except Exception:
                                    continue

                                stage = entry.get("stage") or "unknown"
                                status = entry.get("status") or ""
                                timestamp = entry.get("timestamp") or ""

                                try:
                                    dt = datetime.fromisoformat(timestamp)
                                    if dt.tzinfo is None:
                                        dt = dt.replace(tzinfo=timezone.utc)
                                    local_timestamp = dt.astimezone(ZoneInfo(timezone_name)).isoformat()
                                except Exception:
                                    local_timestamp = timestamp

                                try:
                                    messages.info(request, f"{stage}: {status} @ {local_timestamp}")
                                except Exception as exc:
                                    logger.exception(
                                        "Progress watcher failed to add message for %s (%s @ %s); user=%s (id=%s) tz=%s; progress_log=%s; request_path=%s; err=%s",
                                        stage,
                                        status,
                                        local_timestamp,
                                        getattr(request, "user", None),
                                        getattr(getattr(request, "user", None), "id", None),
                                        timezone_name,
                                        progress_log,
                                        getattr(request, "path", None),
                                        exc,
                                    )
                except Exception:
                    logger.exception("Progress watcher encountered an unexpected error; progress_log=%s", progress_log)

                stop_event.wait(1)

        thread = threading.Thread(target=_watch_progress_log, daemon=True)
        thread.start()
        return stop_event, thread

    def progress_cb(stage: str, status: str, timestamp: str) -> None:
        try:
            dt = datetime.fromisoformat(timestamp)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            local_timestamp = dt.astimezone(ZoneInfo(timezone_name)).isoformat()
        except Exception:
            local_timestamp = timestamp

        entry = {"stage": stage, "status": status, "timestamp": local_timestamp}
        try:
            with progress_log.open("a", encoding="utf-8") as fp:
                fp.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass

    start_stage = request.POST.get("start_stage") or (
        "text_gen" if project.input_mode == Project.INPUT_DESCRIPTION else "segmentation_phase_1"
    )
    if start_stage not in PIPELINE_ORDER:
        messages.error(request, "Unknown start stage.")
        return redirect("project-detail", pk=project.pk)

    text: str | None = None
    text_obj: dict[str, Any] | None = None
    description: str | None = None

    if start_stage == "text_gen":
        description = (project.description or "").strip()
        if not description:
            messages.error(request, "Please provide a description to generate text.")
            return redirect("project-detail", pk=project.pk)
    elif start_stage == "segmentation_phase_1":
        text = (project.source_text or "").strip()
        if not text:
            messages.error(request, "Please provide source text to segment.")
            return redirect("project-detail", pk=project.pk)
    else:
        # Start from a persisted intermediate produced by a previous run.
        upstream_index = PIPELINE_ORDER.index(start_stage) - 1
        upstream_stage = PIPELINE_ORDER[upstream_index]
        text_obj = _load_stage_payload(project, upstream_stage)
        if text_obj is None:
            messages.error(
                request,
                f"Cannot start at {start_stage}: missing upstream stage output ({upstream_stage}).",
            )
            return redirect("project-detail", pk=project.pk)

    spec = FullPipelineSpec(
        text=text,
        text_obj=text_obj,
        description=description,
        language=project.language,
        target_language=project.target_language,
        output_dir=output_dir,
        audio_cache_dir=output_dir / "audio",
        require_real_tts=True,
        persist_intermediates=True,
        progress_callback=progress_cb,
        start_stage=start_stage,
    )

    client = _build_ai_client()
    messages.info(request, f"Compiling project starting at {start_stage}; this may take a moment...")
    stop_event, watcher = _start_progress_watcher()
    try:
        result = asyncio.run(run_full_pipeline(spec, client=client))
    except Exception as exc:  # pragma: no cover - surface to UI
        messages.error(request, f"Compile failed: {exc}")
        return redirect("project-detail", pk=project.pk)
    finally:
        stop_event.set()
        watcher.join(timeout=2)

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
    project.compiled_path = compiled_rel.replace("\\", "/")
    project.artifact_root = str(project_root).replace("\\", "/")
    project.save(update_fields=["compiled_path", "artifact_root", "updated_at"])
    if compiled_rel:
        messages.success(request, "Project compiled to HTML.")
    else:
        messages.warning(request, "Compilation finished but no HTML was produced.")
    return redirect("project-detail", pk=project.pk)


@login_required
def toggle_publish(request: HttpRequest, pk: int) -> HttpResponse:
    project = get_object_or_404(Project, pk=pk, owner=request.user)
    project.is_published = not project.is_published
    project.save(update_fields=["is_published"])
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


@login_required
def delete_project(request: HttpRequest, pk: int) -> HttpResponse:
    project = get_object_or_404(Project, pk=pk, owner=request.user)
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
