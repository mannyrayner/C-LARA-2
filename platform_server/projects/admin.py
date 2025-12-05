from django.contrib import admin
from .models import Profile, Project

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "is_published", "updated_at")
    search_fields = ("title", "owner__username")
    list_filter = ("is_published",)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "timezone", "updated_at")
    search_fields = ("user__username", "timezone")
