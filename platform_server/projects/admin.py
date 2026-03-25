from django.contrib import admin
from .models import Profile, Project, ProjectImageElement, ProjectImageStyle, TaskUpdate

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "is_published", "updated_at")
    search_fields = ("title", "owner__username")
    list_filter = ("is_published",)


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
