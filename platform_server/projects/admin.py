from django.contrib import admin
from . import models as project_models


Project = project_models.Project


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "is_published", "updated_at")
    search_fields = ("title", "owner__username")
    list_filter = ("is_published",)


# Defensive registration for optional models. This keeps admin import stable
# when branches differ in available project-related model classes.
OPTIONAL_MODEL_NAMES = (
    "Profile",
    "TaskUpdate",
    "ProjectImageStyle",
    "ProjectImageElement",
    "ProjectImagePage",
    "ProjectCollaborator",
    "ExerciseSet",
    "ExerciseItem",
)

for model_name in OPTIONAL_MODEL_NAMES:
    model_cls = getattr(project_models, model_name, None)
    if model_cls is not None:
        try:
            admin.site.register(model_cls)
        except admin.sites.AlreadyRegistered:
            pass
