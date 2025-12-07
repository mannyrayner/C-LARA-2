from django.contrib import admin
from .models import Profile, Project, TaskUpdate

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
