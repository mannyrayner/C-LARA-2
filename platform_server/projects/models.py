from __future__ import annotations

from pathlib import Path
from decimal import Decimal
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
import uuid


class Project(models.Model):
    ACCESS_PUBLIC = "public"
    ACCESS_PRIVATE = "private"
    ACCESS_COMMUNITY = "community"
    ACCESS_CHOICES = [
        (ACCESS_PUBLIC, "Public"),
        (ACCESS_PRIVATE, "Private (owner/collaborators)"),
        (ACCESS_COMMUNITY, "Community members only"),
    ]

    INPUT_DESCRIPTION = "description"
    INPUT_SOURCE = "source_text"
    INPUT_CHOICES = [
        (INPUT_DESCRIPTION, "Description (AI-generate text)"),
        (INPUT_SOURCE, "Source text"),
    ]
    PAGE_IMAGE_TEXT_SOURCE_SEGMENTATION = "segmentation"
    PAGE_IMAGE_TEXT_SOURCE_TRANSLATION = "translation"
    PAGE_IMAGE_TEXT_SOURCE_CHOICES = [
        (PAGE_IMAGE_TEXT_SOURCE_SEGMENTATION, "Segmented source text"),
        (PAGE_IMAGE_TEXT_SOURCE_TRANSLATION, "Concatenated page translations"),
    ]
    AUDIO_MODE_TTS = "tts"
    AUDIO_MODE_NONE = "none"
    AUDIO_MODE_CHOICES = [
        (AUDIO_MODE_TTS, "Use TTS audio"),
        (AUDIO_MODE_NONE, "No audio / skip TTS"),
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
    image_generation_pivot_language = models.CharField(max_length=16, blank=True, default="")
    page_image_text_source = models.CharField(
        max_length=32,
        choices=PAGE_IMAGE_TEXT_SOURCE_CHOICES,
        default=PAGE_IMAGE_TEXT_SOURCE_SEGMENTATION,
    )
    segmentation_method = models.CharField(max_length=32, default="auto")
    romanization_method = models.CharField(max_length=32, default="auto")
    audio_mode = models.CharField(max_length=16, choices=AUDIO_MODE_CHOICES, default=AUDIO_MODE_TTS)
    compiled_path = models.CharField(max_length=512, blank=True)
    artifact_root = models.CharField(max_length=512, blank=True)
    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    discovery_summary = models.TextField(blank=True, default="")
    discovery_keywords = models.JSONField(default=list, blank=True)
    discovery_keywords_en = models.JSONField(default=list, blank=True)
    discovery_level = models.CharField(max_length=16, blank=True, default="")
    discovery_word_count = models.PositiveIntegerField(default=0)
    discovery_metadata_updated_at = models.DateTimeField(null=True, blank=True)
    access_count = models.PositiveIntegerField(default=0)
    access_scope = models.CharField(max_length=16, choices=ACCESS_CHOICES, default=ACCESS_PUBLIC)
    community = models.ForeignKey(
        "Community",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="projects",
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    total_cost_usd = models.DecimalField(max_digits=12, decimal_places=4, default=Decimal("0.0000"))

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
    dialogue_language = models.CharField(max_length=16, default="en")
    dialogue_memory_enabled = models.BooleanField(default=True)
    dialogue_memory = models.JSONField(default=dict, blank=True)
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


class CreditAccount(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="credit_account"
    )
    balance_usd = models.DecimalField(max_digits=12, decimal_places=4, default=Decimal("0.0000"))
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:  # pragma: no cover - display helper
        return f"Credit account for {self.user.username}: ${self.balance_usd}"


class CreditLedgerEntry(models.Model):
    ENTRY_USAGE = "usage"
    ENTRY_ADMIN_ADJUST = "admin_adjust"
    ENTRY_TRANSFER_OUT = "transfer_out"
    ENTRY_TRANSFER_IN = "transfer_in"
    ENTRY_CHOICES = [
        (ENTRY_USAGE, "Usage charge"),
        (ENTRY_ADMIN_ADJUST, "Admin adjustment"),
        (ENTRY_TRANSFER_OUT, "Transfer sent"),
        (ENTRY_TRANSFER_IN, "Transfer received"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="credit_ledger_entries"
    )
    entry_type = models.CharField(max_length=32, choices=ENTRY_CHOICES)
    amount_usd = models.DecimalField(max_digits=12, decimal_places=4)
    balance_after_usd = models.DecimalField(max_digits=12, decimal_places=4)
    description = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]


class AIUsageCharge(models.Model):
    PROVIDER_OPENAI = "openai"
    STATUS_CHARGED = "charged"
    STATUS_SKIPPED = "skipped"
    STATUS_CHOICES = [
        (STATUS_CHARGED, "Charged"),
        (STATUS_SKIPPED, "Skipped"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ai_usage_charges"
    )
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="ai_usage_charges", null=True, blank=True
    )
    provider = models.CharField(max_length=32, default=PROVIDER_OPENAI)
    model = models.CharField(max_length=64, blank=True)
    operation = models.CharField(max_length=64, blank=True)
    request_type = models.CharField(max_length=64, blank=True, default="")
    prompt_tokens = models.PositiveIntegerField(default=0)
    completion_tokens = models.PositiveIntegerField(default=0)
    total_tokens = models.PositiveIntegerField(default=0)
    cost_usd = models.DecimalField(max_digits=12, decimal_places=6, default=Decimal("0"))
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_CHARGED)
    notes = models.CharField(max_length=255, blank=True)
    ledger_entry = models.ForeignKey(
        CreditLedgerEntry, on_delete=models.SET_NULL, null=True, blank=True, related_name="usage_rows"
    )
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]


class OpenAIModelPricing(models.Model):
    STATUS_AI_PARSED = "ai_parsed"
    STATUS_HUMAN_REVISED = "human_revised"
    STATUS_CHOICES = [
        (STATUS_AI_PARSED, "AI parsed"),
        (STATUS_HUMAN_REVISED, "Human revised"),
    ]

    model_name = models.CharField(max_length=64, unique=True)
    input_usd_per_1m = models.DecimalField(max_digits=12, decimal_places=6)
    output_usd_per_1m = models.DecimalField(max_digits=12, decimal_places=6)
    source_url = models.URLField(blank=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_AI_PARSED)
    last_synced_at = models.DateTimeField(default=timezone.now)
    last_human_reviewed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["model_name"]


class IssueSuggestion(models.Model):
    STATUS_NEW = "new"
    STATUS_EXPORTED = "exported"
    STATUS_INCORPORATED = "incorporated"
    STATUS_CHOICES = [
        (STATUS_NEW, "New"),
        (STATUS_EXPORTED, "Exported"),
        (STATUS_INCORPORATED, "Incorporated"),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField()
    submitter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="issue_suggestions",
    )
    submitted_at = models.DateTimeField(default=timezone.now, db_index=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_NEW, db_index=True)

    class Meta:
        ordering = ["-submitted_at", "-id"]


class IssueUpdateSuggestion(models.Model):
    STATUS_NEW = "new"
    STATUS_EXPORTED = "exported"
    STATUS_INCORPORATED = "incorporated"
    STATUS_CHOICES = [
        (STATUS_NEW, "New"),
        (STATUS_EXPORTED, "Exported"),
        (STATUS_INCORPORATED, "Incorporated"),
    ]

    issue_id = models.CharField(max_length=32, db_index=True)
    issue_title = models.CharField(max_length=300, blank=True)
    update_description = models.TextField()
    submitter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="issue_update_suggestions",
    )
    submitted_at = models.DateTimeField(default=timezone.now, db_index=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_NEW, db_index=True)

    class Meta:
        ordering = ["-submitted_at", "-id"]


class ProjectImageStyle(models.Model):
    """Project-scoped artifacts for the initial image style substep."""

    STATUS_DRAFT = "draft"
    STATUS_GENERATED = "generated"
    STATUS_APPROVED = "approved"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_GENERATED, "Generated"),
        (STATUS_APPROVED, "Approved"),
    ]

    project = models.OneToOneField(
        Project, on_delete=models.CASCADE, related_name="image_style"
    )
    style_brief = models.TextField(blank=True)
    expanded_style_description = models.TextField(blank=True)
    representative_excerpt = models.TextField(blank=True)
    sample_image_prompt = models.TextField(blank=True)
    sample_image_path = models.CharField(max_length=512, blank=True)
    sample_image_revised_prompt = models.TextField(blank=True)
    sample_image_model = models.CharField(max_length=64, default="gpt-image-1")
    discourage_text_in_images = models.BooleanField(default=False)
    ai_model = models.CharField(max_length=64, default="gpt-4o")
    status = models.CharField(
        max_length=32, choices=STATUS_CHOICES, default=STATUS_DRAFT
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self) -> str:  # pragma: no cover - display helper
        return f"Image style for {self.project.title}"


class ProjectImageElement(models.Model):
    """Recurring visual element proposed/curated for a project."""

    STATUS_PROPOSED = "proposed"
    STATUS_EXPANDED = "expanded"
    STATUS_CONFIRMED = "confirmed"
    STATUS_CHOICES = [
        (STATUS_PROPOSED, "Proposed"),
        (STATUS_EXPANDED, "Expanded"),
        (STATUS_CONFIRMED, "Confirmed"),
    ]

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="image_elements"
    )
    name = models.CharField(max_length=255)
    element_type = models.CharField(max_length=64, blank=True, default="character")
    page_refs = models.CharField(max_length=255, blank=True)
    why_consistency_matters = models.TextField(blank=True)
    expanded_description = models.TextField(blank=True)
    expanded_prompt = models.TextField(blank=True)
    image_model = models.CharField(max_length=64, default="gpt-image-1")
    image_path = models.CharField(max_length=512, blank=True)
    image_revised_prompt = models.TextField(blank=True)
    is_confirmed = models.BooleanField(default=False)
    ai_model = models.CharField(max_length=64, default="gpt-4o")
    status = models.CharField(
        max_length=32, choices=STATUS_CHOICES, default=STATUS_PROPOSED
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "id"]
        unique_together = ("project", "name")

    def __str__(self) -> str:  # pragma: no cover - display helper
        return f"{self.project.title}: {self.name}"


class ProjectImagePage(models.Model):
    """Per-page image prompt/output generated from style, text, and elements."""

    STATUS_DRAFT = "draft"
    STATUS_GENERATED = "generated"
    STATUS_APPROVED = "approved"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_GENERATED, "Generated"),
        (STATUS_APPROVED, "Approved"),
    ]

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="image_pages"
    )
    page_number = models.PositiveIntegerField()
    page_text = models.TextField(blank=True)
    generation_prompt = models.TextField(blank=True)
    image_model = models.CharField(max_length=64, default="gpt-image-1")
    image_path = models.CharField(max_length=512, blank=True)
    preferred_variant = models.ForeignKey(
        "ProjectImagePageVariant",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    image_revised_prompt = models.TextField(blank=True)
    status = models.CharField(
        max_length=32, choices=STATUS_CHOICES, default=STATUS_DRAFT
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["page_number", "id"]
        unique_together = ("project", "page_number")

    def __str__(self) -> str:  # pragma: no cover - display helper
        return f"{self.project.title}: page {self.page_number}"


class ProjectImagePageVariant(models.Model):
    """Generated image variants for a page plus selection state in parent row."""

    STATUS_DRAFT = "draft"
    STATUS_GENERATED = "generated"
    STATUS_APPROVED = "approved"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_GENERATED, "Generated"),
        (STATUS_APPROVED, "Approved"),
    ]

    page = models.ForeignKey(ProjectImagePage, on_delete=models.CASCADE, related_name="variants")
    variant_index = models.PositiveIntegerField()
    image_model = models.CharField(max_length=64, default="gpt-image-1")
    image_path = models.CharField(max_length=512, blank=True)
    generation_prompt = models.TextField(blank=True)
    image_revised_prompt = models.TextField(blank=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["page_id", "variant_index", "id"]
        unique_together = ("page", "variant_index")

    def __str__(self) -> str:  # pragma: no cover - display helper
        return f"{self.page.project.title}: page {self.page.page_number} variant {self.variant_index}"


class ProjectCollaborator(models.Model):
    ROLE_OWNER = "owner"
    ROLE_ANNOTATOR = "annotator"
    ROLE_VIEWER = "viewer"
    ROLE_CHOICES = [
        (ROLE_OWNER, "OWNER"),
        (ROLE_ANNOTATOR, "ANNOTATOR"),
        (ROLE_VIEWER, "VIEWER"),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="collaborators")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="project_collaborations")
    role = models.CharField(max_length=16, choices=ROLE_CHOICES, default=ROLE_VIEWER)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("project", "user")
        ordering = ["project_id", "user_id"]


class Community(models.Model):
    name = models.CharField(max_length=200, unique=True)
    language = models.CharField(max_length=16, blank=True, default="")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "id"]

    def __str__(self) -> str:  # pragma: no cover - display helper
        if self.language:
            return f"{self.name} ({self.language})"
        return self.name


class CommunityMembership(models.Model):
    ROLE_ORGANISER = "organiser"
    ROLE_MEMBER = "member"
    ROLE_CHOICES = [
        (ROLE_ORGANISER, "Organiser"),
        (ROLE_MEMBER, "Member"),
    ]

    community = models.ForeignKey(Community, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="community_memberships")
    role = models.CharField(max_length=16, choices=ROLE_CHOICES, default=ROLE_MEMBER)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("community", "user")
        ordering = ["community_id", "user_id"]


class CommunityImageVote(models.Model):
    VALUE_UP = "up"
    VALUE_DOWN = "down"
    VALUE_CHOICES = [
        (VALUE_UP, "Thumbs up"),
        (VALUE_DOWN, "Thumbs down"),
    ]

    community = models.ForeignKey(Community, on_delete=models.CASCADE, related_name="image_votes")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="community_image_votes")
    page = models.ForeignKey(ProjectImagePage, on_delete=models.CASCADE, related_name="community_image_votes")
    variant = models.ForeignKey(ProjectImagePageVariant, on_delete=models.CASCADE, related_name="community_image_votes")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="community_image_votes")
    value = models.CharField(max_length=8, choices=VALUE_CHOICES)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "variant")
        ordering = ["-updated_at", "-id"]


class CommunityOrganiserReview(models.Model):
    community = models.ForeignKey(Community, on_delete=models.CASCADE, related_name="organiser_reviews")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="community_organiser_reviews")
    organiser = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="community_organiser_reviews",
    )
    note = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("community", "project", "organiser")
        ordering = ["-updated_at", "-id"]


class PictureDictionary(models.Model):
    community = models.OneToOneField(Community, on_delete=models.CASCADE, related_name="picture_dictionary")
    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name="picture_dictionary")
    organiser = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="managed_picture_dictionaries",
    )
    language = models.CharField(max_length=16, blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["community_id"]


class PictureDictionaryEntry(models.Model):
    dictionary = models.ForeignKey(PictureDictionary, on_delete=models.CASCADE, related_name="entries")
    surface = models.CharField(max_length=255)
    lemma = models.CharField(max_length=255, blank=True, default="")
    pos = models.CharField(max_length=64, blank=True, default="")
    image_path = models.CharField(max_length=512, blank=True, default="")
    current_page_number = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]
        indexes = [
            models.Index(
                fields=["dictionary", "is_active"],
                name="picdictentry_dict_active_idx",
            )
        ]

class ContentComment(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="content_comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="content_comments")
    body = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    is_hidden = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]


class ContentRating(models.Model):
    VALUE_UP = "up"
    VALUE_DOWN = "down"
    VALUE_CHOICES = [
        (VALUE_UP, "Thumbs up"),
        (VALUE_DOWN, "Thumbs down"),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="content_ratings")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="content_ratings")
    value = models.CharField(max_length=8, choices=VALUE_CHOICES)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("project", "author")
        ordering = ["-updated_at"]


class ExerciseSet(models.Model):
    TYPE_CLOZE = "cloze"
    TYPE_FLASHCARD = "flashcard"
    TYPE_CHOICES = [
        (TYPE_CLOZE, "Cloze"),
        (TYPE_FLASHCARD, "Flashcard"),
    ]
    FLASHCARD_MODE_FORM_TO_MEANING = "form_to_meaning"
    FLASHCARD_MODE_MEANING_TO_FORM = "meaning_to_form"
    FLASHCARD_MODE_IMAGE_TO_FORM = "image_to_form"
    FLASHCARD_MODE_CHOICES = [
        (FLASHCARD_MODE_FORM_TO_MEANING, "Form → meaning"),
        (FLASHCARD_MODE_MEANING_TO_FORM, "Meaning → form"),
        (FLASHCARD_MODE_IMAGE_TO_FORM, "Image → form"),
    ]

    THEME_VOCAB = "vocabulary"
    THEME_GRAMMAR = "grammar"
    THEME_MORPH = "morphology"
    THEME_GRAMMAR_MORPH = "grammar_morphology"
    THEME_CHOICES = [
        (THEME_VOCAB, "Vocabulary"),
        (THEME_GRAMMAR, "Grammar"),
        (THEME_MORPH, "Morphology"),
        (THEME_GRAMMAR_MORPH, "Grammar/Morphology"),
    ]

    STATUS_DRAFT = "draft"
    STATUS_READY = "ready"
    STATUS_PUBLISHED = "published"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_READY, "Ready"),
        (STATUS_PUBLISHED, "Published"),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="exercise_sets")
    exercise_type = models.CharField(max_length=32, choices=TYPE_CHOICES, default=TYPE_CLOZE)
    flashcard_mode = models.CharField(max_length=32, choices=FLASHCARD_MODE_CHOICES, blank=True, default="")
    theme = models.CharField(max_length=32, choices=THEME_CHOICES, default=THEME_VOCAB)
    title = models.CharField(max_length=255, blank=True)
    instructions = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    is_published = models.BooleanField(default=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="created_exercise_sets")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]


class ExerciseItem(models.Model):
    exercise_set = models.ForeignKey(ExerciseSet, on_delete=models.CASCADE, related_name="items")
    order_index = models.PositiveIntegerField(default=0)
    page_number = models.PositiveIntegerField(default=1)
    segment_index = models.PositiveIntegerField(default=0)
    segment_text = models.TextField(blank=True)
    prompt = models.TextField(blank=True)
    answer = models.CharField(max_length=255, blank=True)
    options = models.JSONField(default=list, blank=True)
    rationale = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["order_index", "id"]
