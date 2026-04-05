from __future__ import annotations

from pathlib import Path
from django.conf import settings
from django.db import models
from django.utils import timezone


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
    compiled_path = models.CharField(max_length=512, blank=True)
    artifact_root = models.CharField(max_length=512, blank=True)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
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
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ("project", "version")
        ordering = ["project_id", "-version"]

    def __str__(self) -> str:  # pragma: no cover - display helper
        return f"{self.project_id}:segmentation:v{self.version}"
