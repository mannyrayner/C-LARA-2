from __future__ import annotations

import json
import logging
import os
import random
import shutil
import uuid
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django import forms
from django.http import FileResponse, Http404, HttpRequest, HttpResponse
from django.views.decorators.clickjacking import xframe_options_sameorigin
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
from urllib.parse import quote

from core.config import DEFAULT_MODEL, OpenAIConfig
from core.ai_api import OpenAIClient
from pipeline.full_pipeline import FullPipelineSpec, PIPELINE_ORDER, run_full_pipeline

from .forms import ProjectForm, RegistrationForm
from .models import ManualStageState, Profile, Project, SegmentationManualVersion


# Compatibility filters used by older content-list views in mixed branches.
# Values are rolling-window day counts; ``None`` means no date filter.
CONTENT_DATE_FILTERS = {
    "all": None,
    "today": 1,
    "week": 7,
    "month": 31,
    "year": 366,
}

# Compatibility AI model options used by older project detail templates/views.
AI_MODEL_CHOICES = [
    ("", "Default"),
    ("gpt-4.1-mini", "gpt-4.1-mini"),
    ("gpt-4.1", "gpt-4.1"),
]


def _ensure_bootstrap_admin(user) -> None:  # type: ignore[no-untyped-def]
    """Compatibility shim for older views that call bootstrap-admin setup.

    Older branch variants call this helper from list views; keeping a safe
    no-op implementation avoids NameError while preserving current behaviour.
    """

    return None


def _projects_for_user(user):  # type: ignore[no-untyped-def]
    """Compatibility helper for older detail/list views."""
    _ensure_bootstrap_admin(user)
    return Project.objects.filter(owner=user)


def _require_admin(user) -> None:  # type: ignore[no-untyped-def]
    """Compatibility guard used by older admin-tools views."""
    if not getattr(user, "is_authenticated", False) or not getattr(user, "is_staff", False):
        raise PermissionDenied("Admin access required.")


def _profile_for_user(user) -> Profile:
    """Return an existing profile or create one for compatibility code paths."""
    profile, _ = Profile.objects.get_or_create(user=user)
    return profile


def _format_timestamp(value, *_args, **_kwargs):  # type: ignore[no-untyped-def]
    """Compatibility formatter for older project-detail templates/views."""
    # Older call-sites may pass extra positional args (e.g. timezone/user).
    # Keep the helper permissive to avoid TypeError in mixed branch states.
    if isinstance(value, tuple) and value:
        value = value[0]
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S"), value
    if isinstance(value, str):
        for parser in (datetime.fromisoformat,):
            try:
                parsed = parser(value.replace("Z", "+00:00"))
                return parsed.strftime("%Y-%m-%d %H:%M:%S"), parsed
            except Exception:
                continue
        return value, None
    return "", None


class ProfileForm(forms.ModelForm):
    """Compatibility form for older profile views."""

    class Meta:
        model = Profile
        fields = ["display_name", "timezone", "bio"]


class DeleteCachedWordAudioForm(forms.Form):
    """Compatibility form for older admin-tools view code paths."""

    # Field names mirror historical usage patterns; both are optional here to
    # keep GET rendering and no-op POST handling stable across branches.
    language = forms.CharField(required=False)
    voice = forms.CharField(required=False)

    def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        self.language_choices = kwargs.pop("language_choices", None)
        super().__init__(*args, **kwargs)
        if self.language_choices:
            self.fields["language"] = forms.ChoiceField(
                required=False,
                choices=[("", "All")] + list(self.language_choices),
            )

    def save(self):  # type: ignore[no-untyped-def]
        # Keep API compatibility without assuming optional audio cache models.
        return SimpleNamespace(deleted=0)


class GrantAdminPrivilegesForm(forms.Form):
    """Compatibility form used by older admin-tools views."""

    email = forms.EmailField(required=False)

    def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        self.queryset = kwargs.pop("queryset", None)
        super().__init__(*args, **kwargs)

    def save(self):  # type: ignore[no-untyped-def]
        return SimpleNamespace(updated=0)


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


@login_required
def admin_tools(request: HttpRequest) -> HttpResponse:
    _require_admin(request.user)
    delete_form = DeleteCachedWordAudioForm(language_choices=_audio_cache_language_choices())
    grant_form = GrantAdminPrivilegesForm(
        queryset=get_user_model().objects.filter(is_staff=False).order_by("username")
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
        else:
            messages.error(request, "Unknown admin action.")

    return render(
        request,
        "projects/admin_tools.html",
        {
            "delete_audio_form": delete_form,
            "grant_admin_form": grant_form,
            "bootstrap_admin_usernames": sorted(_bootstrap_admin_usernames()),
            "current_admins": get_user_model().objects.filter(is_staff=True).order_by("username"),
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


MANUAL_STAGE_ORDER = [
    ManualStageState.STAGE_SEGMENTATION,
    ManualStageState.STAGE_TRANSLATION,
    ManualStageState.STAGE_MWE,
    ManualStageState.STAGE_LEMMA,
    ManualStageState.STAGE_GLOSS,
    ManualStageState.STAGE_AUDIO,
    ManualStageState.STAGE_ROMANIZATION,
]

MANUAL_STAGE_DEPENDENCIES: dict[str, list[str]] = {
    ManualStageState.STAGE_SEGMENTATION: [],
    ManualStageState.STAGE_TRANSLATION: [ManualStageState.STAGE_SEGMENTATION],
    ManualStageState.STAGE_MWE: [ManualStageState.STAGE_SEGMENTATION],
    ManualStageState.STAGE_LEMMA: [ManualStageState.STAGE_MWE],
    ManualStageState.STAGE_GLOSS: [ManualStageState.STAGE_MWE],
    ManualStageState.STAGE_AUDIO: [ManualStageState.STAGE_MWE, ManualStageState.STAGE_LEMMA],
    ManualStageState.STAGE_ROMANIZATION: [ManualStageState.STAGE_SEGMENTATION],
}


def _parse_breaks(raw: str, *, text_len: int, name: str) -> list[int]:
    if not raw.strip():
        return []
    parts = [p.strip() for p in raw.split(",")]
    out: list[int] = []
    for token in parts:
        if not token:
            continue
        try:
            value = int(token)
        except ValueError as exc:
            raise ValueError(f"{name} must contain integers separated by commas.") from exc
        if value <= 0 or value >= text_len:
            raise ValueError(f"{name} values must be between 1 and {text_len - 1}.")
        out.append(value)
    deduped = sorted(set(out))
    return deduped


def _validate_segmentation_breaks(
    text: str,
    *,
    page_breaks: list[int],
    segment_breaks: list[int],
    token_breaks: list[int],
) -> None:
    text_len = len(text)
    for label, breaks in (
        ("Page breaks", page_breaks),
        ("Segment breaks", segment_breaks),
        ("Token breaks", token_breaks),
    ):
        if breaks != sorted(breaks):
            raise ValueError(f"{label} must be sorted.")
        if len(set(breaks)) != len(breaks):
            raise ValueError(f"{label} must not contain duplicate values.")
        if any(v <= 0 or v >= text_len for v in breaks):
            raise ValueError(f"{label} must be between 1 and {text_len - 1}.")

    if not set(page_breaks).issubset(segment_breaks):
        raise ValueError("Each page break must also be a segment break.")
    if not set(segment_breaks).issubset(token_breaks):
        raise ValueError("Each segment break must also be a token break.")


def _render_marked_text(text: str, marks: dict[int, list[str]]) -> str:
    chunks: list[str] = []
    for idx, ch in enumerate(text):
        labels = marks.get(idx)
        if labels:
            chunks.append("⟦" + "|".join(labels) + "⟧")
        chunks.append(ch)
    end_labels = marks.get(len(text))
    if end_labels:
        chunks.append("⟦" + "|".join(end_labels) + "⟧")
    return "".join(chunks)


def _segmentation_preview(text: str, *, page_breaks: list[int], segment_breaks: list[int], token_breaks: list[int]) -> str:
    marks: dict[int, list[str]] = {}
    for pos in token_breaks:
        marks.setdefault(pos, []).append("T")
    for pos in segment_breaks:
        marks.setdefault(pos, []).append("S")
    for pos in page_breaks:
        marks.setdefault(pos, []).append("P")
    return _render_marked_text(text, marks)


def _ensure_manual_stage_states(project: Project) -> dict[str, ManualStageState]:
    existing = {row.stage: row for row in project.manual_stage_states.all()}
    for stage in MANUAL_STAGE_ORDER:
        if stage not in existing:
            existing[stage] = ManualStageState.objects.create(project=project, stage=stage)
    return existing


def _stage_unlocked(stage: str, states: dict[str, ManualStageState]) -> bool:
    deps = MANUAL_STAGE_DEPENDENCIES.get(stage, [])
    return all(states[d].status == ManualStageState.STATUS_APPROVED for d in deps)


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
    return_to = (request.POST.get("return_to") or "").strip()
    if not return_to.startswith("/"):
        return_to = reverse("project-detail", args=[project.pk])

    start_stage = request.POST.get("start_stage") or (
        "text_gen" if project.input_mode == Project.INPUT_DESCRIPTION else "segmentation_phase_1"
    )
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

    if start_stage == "text_gen":
        if not description:
            messages.error(request, "Please provide a description to generate text.")
            return redirect(return_to)
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
            return redirect(return_to)
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
            return redirect(return_to)

        text_obj = _load_stage_payload(project, upstream_stage, run_dir=source_run)
        if text_obj is None:
            messages.error(
                request,
                f"Cannot start at {start_stage}: missing upstream stage output ({upstream_stage}).",
            )
            return redirect(return_to)

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
            flashcard_mode = form.cleaned_data["flashcard_mode"]
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
                client = _build_ai_client(model)
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


@login_required
def project_manual_edit(request: HttpRequest, pk: int) -> HttpResponse:
    project = get_object_or_404(Project, pk=pk, owner=request.user)
    states = _ensure_manual_stage_states(project)
    stage_state = states[ManualStageState.STAGE_SEGMENTATION]
    latest = project.segmentation_versions.order_by("-version").first()

    text = project.source_text or ""
    if not text:
        messages.warning(
            request,
            "This project has empty source text. Add source text before using manual segmentation editing.",
        )

    default_token_breaks: list[int] = []
    if text:
        default_token_breaks = [i for i, ch in enumerate(text, start=1) if ch.isspace() and i < len(text)]

    if request.method == "POST":
        action = request.POST.get("action", "save")
        note = (request.POST.get("note") or "").strip()
        page_raw = request.POST.get("page_breaks", "")
        segment_raw = request.POST.get("segment_breaks", "")
        token_raw = request.POST.get("token_breaks", "")
        try:
            page_breaks = _parse_breaks(page_raw, text_len=len(text), name="Page breaks") if text else []
            segment_breaks = _parse_breaks(segment_raw, text_len=len(text), name="Segment breaks") if text else []
            token_breaks = _parse_breaks(token_raw, text_len=len(text), name="Token breaks") if text else []
            _validate_segmentation_breaks(
                text, page_breaks=page_breaks, segment_breaks=segment_breaks, token_breaks=token_breaks
            )
        except ValueError as exc:
            messages.error(request, str(exc))
        else:
            last_version = project.segmentation_versions.order_by("-version").first()
            next_version = 1 if not last_version else last_version.version + 1
            SegmentationManualVersion.objects.create(
                project=project,
                version=next_version,
                source_text_snapshot=text,
                page_breaks=page_breaks,
                segment_breaks=segment_breaks,
                token_breaks=token_breaks,
                note=note,
                created_by=request.user,
            )

            stage_state.status = (
                ManualStageState.STATUS_APPROVED if action == "approve" else ManualStageState.STATUS_IN_PROGRESS
            )
            if action == "approve":
                stage_state.approved_version = next_version
            stage_state.updated_by = request.user
            stage_state.save(update_fields=["status", "approved_version", "updated_by", "updated_at"])

            if action == "approve":
                messages.success(request, f"Segmentation version v{next_version} approved.")
            else:
                messages.success(request, f"Saved segmentation version v{next_version}.")
            return redirect("project-manual-edit", pk=project.pk)

    latest = project.segmentation_versions.order_by("-version").first()
    page_breaks = latest.page_breaks if latest else []
    segment_breaks = latest.segment_breaks if latest else []
    token_breaks = latest.token_breaks if latest else default_token_breaks
    preview = _segmentation_preview(
        text,
        page_breaks=list(page_breaks),
        segment_breaks=list(segment_breaks),
        token_breaks=list(token_breaks),
    ) if text else ""

    stage_rows: list[dict[str, Any]] = []
    for stage in MANUAL_STAGE_ORDER:
        state = states[stage]
        stage_rows.append(
            {
                "stage": stage,
                "label": state.get_stage_display(),
                "status": state.get_status_display(),
                "unlocked": _stage_unlocked(stage, states),
            }
        )

    return render(
        request,
        "projects/project_manual_edit.html",
        {
            "project": project,
            "stage_state": stage_state,
            "stage_rows": stage_rows,
            "latest_version": latest.version if latest else 0,
            "approved_version": stage_state.approved_version,
            "page_breaks": ",".join(str(x) for x in page_breaks),
            "segment_breaks": ",".join(str(x) for x in segment_breaks),
            "token_breaks": ",".join(str(x) for x in token_breaks),
            "preview": preview,
            "source_text": text,
            "latest_note": latest.note if latest else "",
        },
    )
