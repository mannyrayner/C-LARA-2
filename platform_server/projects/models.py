from __future__ import annotations

from pathlib import Path
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
import uuid


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


class Profile(models.Model):
    user = models.OneToOneField(
        get_user_model(), on_delete=models.CASCADE, related_name="profile"
    )
    timezone = models.CharField(max_length=64, default="UTC")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:  # pragma: no cover - display helper
        return f"Profile for {self.user.username}"


class TaskUpdate(models.Model):
    """Lightweight progress updates emitted by background tasks.

    ``report_id`` groups updates for a single task invocation. ``user`` scopes
    updates to the requesting user. ``status`` can be ``"running"``,
    ``"finished"``, or ``"error"`` to help the polling endpoint know whether to
    redirect once the task completes.
    """

    report_id = models.UUIDField(default=uuid.uuid4, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE
    )
    task_type = models.CharField(max_length=255, null=True, blank=True)
    message = models.CharField(max_length=1024)
    status = models.CharField(max_length=32, null=True, blank=True)
    read = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["report_id", "timestamp"])]
        ordering = ["timestamp"]

    def __str__(self) -> str:  # pragma: no cover - display helper
        return f"Update {self.report_id}: {self.message}"
