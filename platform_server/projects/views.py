from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import FileResponse, Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.generic import DetailView, ListView, CreateView

from core.config import OpenAIConfig
from core.ai_api import OpenAIClient
from pipeline.full_pipeline import FullPipelineSpec, run_full_pipeline

from .forms import ProjectForm, RegistrationForm
from .models import Project


def register(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Account created. Please log in.")
            return redirect("login")
    else:
        form = RegistrationForm()
    return render(request, "projects/register.html", {"form": form})


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
        stage_files: list[str] = []
        progress: list[dict[str, Any]] = []
        if project.artifact_root:
            stage_dir = Path(project.artifact_root) / "stages"
            if stage_dir.exists():
                stage_files = [
                    str(path.relative_to(project.artifact_root))
                    for path in sorted(stage_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)
                ]
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
        return context


class ProjectCreateView(LoginRequiredMixin, CreateView):
    model = Project
    form_class = ProjectForm
    template_name = "projects/project_form.html"

    def form_valid(self, form):  # type: ignore[override]
        form.instance.owner = self.request.user
        messages.info(self.request, "Project created. Compile when ready.")
        return super().form_valid(form)

    def get_success_url(self):  # type: ignore[override]
        return reverse("project-detail", args=[self.object.pk])


def _build_ai_client() -> OpenAIClient:
    config = OpenAIConfig()
    return OpenAIClient(config=config)


def _prepare_output_dir(project: Project) -> Path:
    base = project.artifact_dir()
    timestamp = datetime.utcnow().strftime("run_%Y%m%d_%H%M%S")
    output_dir = base / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


@login_required
def compile_project(request: HttpRequest, pk: int) -> HttpResponse:
    project = get_object_or_404(Project, pk=pk, owner=request.user)
    output_dir = _prepare_output_dir(project)
    stage_dir = output_dir / "stages"
    stage_dir.mkdir(parents=True, exist_ok=True)
    progress_log = stage_dir / "progress.jsonl"

    def progress_cb(stage: str, status: str, timestamp: str) -> None:
        entry = {"stage": stage, "status": status, "timestamp": timestamp}
        try:
            with progress_log.open("a", encoding="utf-8") as fp:
                fp.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass

    spec = FullPipelineSpec(
        text=project.source_text,
        language=project.language,
        target_language=project.target_language,
        output_dir=output_dir,
        audio_cache_dir=output_dir / "audio",
        require_real_tts=True,
        persist_intermediates=True,
        progress_callback=progress_cb,
    )

    client = _build_ai_client()
    messages.info(request, "Compiling project; this may take a moment...")
    try:
        result = asyncio.run(run_full_pipeline(spec, client=client))
    except Exception as exc:  # pragma: no cover - surface to UI
        messages.error(request, f"Compile failed: {exc}")
        return redirect("project-detail", pk=project.pk)

    html_info: dict[str, Any] | None = result.get("html") if isinstance(result, dict) else None
    index_path = None
    if html_info:
        index_path = html_info.get("index_path") or html_info.get("html_path")
    project.compiled_path = str(index_path) if index_path else ""
    project.artifact_root = str(output_dir)
    project.save(update_fields=["compiled_path", "artifact_root", "updated_at"])
    if index_path:
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
def serve_compiled(request: HttpRequest, pk: int, path: str) -> HttpResponse:
    project = get_object_or_404(Project, pk=pk)
    if project.owner != request.user and not project.is_published:
        raise Http404()
    base = Path(project.artifact_root)
    file_path = (base / path).resolve()
    try:
        file_path.relative_to(base.resolve())
    except ValueError:
        raise Http404()
    if not file_path.exists():
        raise Http404()
    return FileResponse(open(file_path, "rb"))
