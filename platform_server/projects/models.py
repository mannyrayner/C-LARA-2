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
