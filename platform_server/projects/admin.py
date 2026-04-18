from django.contrib import admin
from .models import (
    Profile,
    Project,
    Community,
    CommunityMembership,
    ProjectImageElement,
    ProjectImagePage,
    ProjectImagePageVariant,
    ProjectImageStyle,
    TaskUpdate,
    ExerciseSet,
    ExerciseItem,
    CreditAccount,
    CreditLedgerEntry,
    AIUsageCharge,
    OpenAIModelPricing,
)

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "is_published", "access_scope", "community", "updated_at")
    search_fields = ("title", "owner__username")
    list_filter = ("is_published", "access_scope", "community")


@admin.register(Community)
class CommunityAdmin(admin.ModelAdmin):
    list_display = ("name", "language", "is_active", "updated_at")
    search_fields = ("name", "language", "description")
    list_filter = ("is_active", "language")


@admin.register(CommunityMembership)
class CommunityMembershipAdmin(admin.ModelAdmin):
    list_display = ("community", "user", "role", "updated_at")
    search_fields = ("community__name", "user__username", "user__email")
    list_filter = ("role", "community")


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "timezone", "updated_at")
    search_fields = ("user__username", "timezone")


@admin.register(TaskUpdate)
class TaskUpdateAdmin(admin.ModelAdmin):
    list_display = ("report_id", "user", "task_type", "status", "timestamp", "read")
    search_fields = ("report_id", "user__username", "task_type", "message")
    list_filter = ("status", "read")


@admin.register(ProjectImageStyle)
class ProjectImageStyleAdmin(admin.ModelAdmin):
    list_display = ("project", "ai_model", "status", "updated_at")
    search_fields = ("project__title", "project__owner__username", "style_brief")
    list_filter = ("status", "ai_model")


@admin.register(ProjectImageElement)
class ProjectImageElementAdmin(admin.ModelAdmin):
    list_display = ("project", "name", "element_type", "status", "image_model", "is_confirmed", "updated_at")
    search_fields = ("project__title", "name", "why_consistency_matters")
    list_filter = ("status", "is_confirmed", "element_type")


@admin.register(ProjectImagePage)
class ProjectImagePageAdmin(admin.ModelAdmin):
    list_display = ("project", "page_number", "status", "image_model", "updated_at")
    search_fields = ("project__title", "page_number", "page_text")
    list_filter = ("status", "image_model")


@admin.register(ProjectImagePageVariant)
class ProjectImagePageVariantAdmin(admin.ModelAdmin):
    list_display = ("page", "variant_index", "status", "image_model", "updated_at")
    search_fields = ("page__project__title", "page__page_number", "image_path")
    list_filter = ("status", "image_model")


@admin.register(ExerciseSet)
class ExerciseSetAdmin(admin.ModelAdmin):
    list_display = ("project", "exercise_type", "theme", "status", "is_published", "updated_at")
    search_fields = ("project__title", "title")
    list_filter = ("exercise_type", "theme", "status", "is_published")


@admin.register(ExerciseItem)
class ExerciseItemAdmin(admin.ModelAdmin):
    list_display = ("exercise_set", "order_index", "page_number", "segment_index", "answer")
    search_fields = ("exercise_set__project__title", "prompt", "answer")


@admin.register(CreditAccount)
class CreditAccountAdmin(admin.ModelAdmin):
    list_display = ("user", "balance_usd", "updated_at")
    search_fields = ("user__username", "user__email")


@admin.register(CreditLedgerEntry)
class CreditLedgerEntryAdmin(admin.ModelAdmin):
    list_display = ("user", "entry_type", "amount_usd", "balance_after_usd", "created_at")
    search_fields = ("user__username", "description")
    list_filter = ("entry_type",)


@admin.register(AIUsageCharge)
class AIUsageChargeAdmin(admin.ModelAdmin):
    list_display = ("user", "project", "provider", "model", "operation", "request_type", "cost_usd", "status", "created_at")
    search_fields = ("user__username", "project__title", "model", "operation", "request_type")
    list_filter = ("provider", "status")


@admin.register(OpenAIModelPricing)
class OpenAIModelPricingAdmin(admin.ModelAdmin):
    list_display = ("model_name", "input_usd_per_1m", "output_usd_per_1m", "status", "last_synced_at")
    search_fields = ("model_name", "source_url", "notes")
    list_filter = ("status",)
