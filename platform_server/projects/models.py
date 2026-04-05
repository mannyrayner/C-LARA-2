from __future__ import annotations

from pathlib import Path
from django.conf import settings
from django.db import models
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone as django_timezone


class Project(models.Model):
    INPUT_DESCRIPTION = "description"
    INPUT_SOURCE = "source_text"
    INPUT_CHOICES = [
        (INPUT_DESCRIPTION, "Description (AI-generate text)"),
        (INPUT_SOURCE, "Source text"),
    ]

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="projects")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    source_text = models.TextField(blank=True)
    input_mode = models.CharField(max_length=20, choices=INPUT_CHOICES, default=INPUT_SOURCE)
    language = models.CharField(max_length=16, default="en")
    target_language = models.CharField(max_length=16, default="fr")
    ai_model = models.CharField(max_length=64, default="gpt-4o")
    page_image_placement = models.CharField(max_length=16, default="none")
    segmentation_method = models.CharField(max_length=32, default="auto")
    romanization_method = models.CharField(max_length=32, default="auto")
    compiled_path = models.CharField(max_length=512, blank=True)
    artifact_root = models.CharField(max_length=512, blank=True)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=django_timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        unique_together = ("owner", "title")

    def __str__(self) -> str:  # pragma: no cover - display helper
        return f"{self.title} ({self.owner})"

    def artifact_dir(self) -> Path:
        """Return the base artifact directory for this project.

        Layout mirrors the documented structure under ``media/users/<user_id>/projects``
        so each project keeps its runs grouped beneath a user-specific folder.
        """

        base = getattr(settings, "PIPELINE_OUTPUT_ROOT", Path(settings.MEDIA_ROOT) / "users")
        return Path(base) / str(self.owner.id) / "projects" / f"project_{self.id}"

    def compiled_index(self) -> Path | None:
        if self.compiled_path:
            return Path(self.compiled_path)
        return None


class ManualStageState(models.Model):
    STATUS_NOT_STARTED = "not_started"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_READY_FOR_REVIEW = "ready_for_review"
    STATUS_APPROVED = "approved"
    STATUS_CHOICES = [
        (STATUS_NOT_STARTED, "Not started"),
        (STATUS_IN_PROGRESS, "In progress"),
        (STATUS_READY_FOR_REVIEW, "Ready for review"),
        (STATUS_APPROVED, "Approved"),
    ]

    STAGE_SEGMENTATION = "segmentation"
    STAGE_TRANSLATION = "translation"
    STAGE_MWE = "mwe"
    STAGE_LEMMA = "lemma"
    STAGE_GLOSS = "gloss"
    STAGE_AUDIO = "audio"
    STAGE_ROMANIZATION = "romanization"
    STAGE_CHOICES = [
        (STAGE_SEGMENTATION, "Segmentation"),
        (STAGE_TRANSLATION, "Translation"),
        (STAGE_MWE, "MWE"),
        (STAGE_LEMMA, "Lemma"),
        (STAGE_GLOSS, "Gloss"),
        (STAGE_AUDIO, "Audio"),
        (STAGE_ROMANIZATION, "Pinyin/Romanization"),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="manual_stage_states")
    stage = models.CharField(max_length=32, choices=STAGE_CHOICES)
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default=STATUS_NOT_STARTED)
    approved_version = models.PositiveIntegerField(default=0)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("project", "stage")
        ordering = ["project_id", "stage"]

    def __str__(self) -> str:  # pragma: no cover - display helper
        return f"{self.project_id}:{self.stage}:{self.status}"


class SegmentationManualVersion(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="segmentation_versions")
    version = models.PositiveIntegerField()
    source_text_snapshot = models.TextField(default="", blank=True)
    page_breaks = models.JSONField(default=list, blank=True)
    segment_breaks = models.JSONField(default=list, blank=True)
    token_breaks = models.JSONField(default=list, blank=True)
    note = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    created_at = models.DateTimeField(default=django_timezone.now)

    class Meta:
        unique_together = ("project", "version")
        ordering = ["project_id", "-version"]

    def __str__(self) -> str:  # pragma: no cover - display helper
        return f"{self.project_id}:segmentation:v{self.version}"


class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    timezone = models.CharField(max_length=64, default="UTC")
    display_name = models.CharField(max_length=120, blank=True, default="")
    bio = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(default=django_timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user_id"]

    def __str__(self) -> str:  # pragma: no cover - display helper
        return f"Profile<{self.user_id}:{self.timezone}>"


class TaskUpdate(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="task_updates")
    message = models.TextField()
    level = models.CharField(max_length=20, default="info")
    created_at = models.DateTimeField(default=django_timezone.now)

    class Meta:
        ordering = ["project_id", "-created_at"]


class ProjectImageStyle(models.Model):
    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name="image_style")
    style_brief = models.TextField(blank=True, default="")
    expanded_style_description = models.TextField(blank=True, default="")
    ai_model = models.CharField(max_length=120, blank=True, default="")
    status = models.CharField(max_length=40, blank=True, default="")
    sample_image_prompt = models.TextField(blank=True, default="")
    sample_image_model = models.CharField(max_length=120, blank=True, default="")
    brief_description = models.TextField(blank=True, default="")
    expanded_prompt = models.TextField(blank=True, default="")
    sample_image_path = models.CharField(max_length=512, blank=True, default="")
    created_at = models.DateTimeField(default=django_timezone.now)
    updated_at = models.DateTimeField(auto_now=True)


class ProjectImageElement(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="image_elements")
    name = models.CharField(max_length=200, blank=True, default="")
    element_key = models.CharField(max_length=120)
    element_type = models.CharField(max_length=80, blank=True, default="")
    expanded_description = models.TextField(blank=True, default="")
    why_consistency_matters = models.TextField(blank=True, default="")
    page_refs = models.CharField(max_length=200, blank=True, default="")
    expanded_prompt = models.TextField(blank=True, default="")
    image_model = models.CharField(max_length=120, blank=True, default="")
    image_revised_prompt = models.TextField(blank=True, default="")
    is_confirmed = models.BooleanField(default=False)
    description = models.TextField(blank=True, default="")
    canonical_image_path = models.CharField(max_length=512, blank=True, default="")
    created_at = models.DateTimeField(default=django_timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("project", "element_key")
        ordering = ["project_id", "element_key"]


class ProjectImagePage(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="image_pages")
    page_number = models.PositiveIntegerField(default=1)
    page_index = models.PositiveIntegerField(default=1)
    page_text = models.TextField(blank=True, default="")
    generation_prompt = models.TextField(blank=True, default="")
    prompt = models.TextField(blank=True, default="")
    image_model = models.CharField(max_length=120, blank=True, default="")
    image_revised_prompt = models.TextField(blank=True, default="")
    status = models.CharField(max_length=40, blank=True, default="")
    image_path = models.CharField(max_length=512, blank=True, default="")
    created_at = models.DateTimeField(default=django_timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("project", "page_index")
        ordering = ["project_id", "page_index"]


class ProjectCollaborator(models.Model):
    ROLE_OWNER = "owner"
    ROLE_ANNOTATOR = "annotator"
    ROLE_VIEWER = "viewer"
    ROLE_CHOICES = [
        (ROLE_OWNER, "Owner"),
        (ROLE_ANNOTATOR, "Annotator"),
        (ROLE_VIEWER, "Viewer"),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="collaborators")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="project_collaborations")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_VIEWER)
    created_at = models.DateTimeField(default=django_timezone.now)

    class Meta:
        unique_together = ("project", "user")
        ordering = ["project_id", "user_id"]


class ExerciseSet(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="exercise_sets")
    title = models.CharField(max_length=200)
    exercise_type = models.CharField(max_length=30, default="cloze")
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=django_timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["project_id", "-created_at"]


class ExerciseItem(models.Model):
    exercise_set = models.ForeignKey(ExerciseSet, on_delete=models.CASCADE, related_name="items")
    prompt = models.TextField()
    answer = models.TextField(blank=True, default="")
    distractors = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(default=django_timezone.now)

    class Meta:
        ordering = ["exercise_set_id", "id"]


@receiver(post_save, sender=get_user_model())
def ensure_profile_for_user(sender, instance, created, **kwargs):  # type: ignore[no-untyped-def]
    if created:
        Profile.objects.get_or_create(user=instance)
