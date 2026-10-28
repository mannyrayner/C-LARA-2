from django.apps import AppConfig


class CommunityDictionaryConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "community_dictionary"
    verbose_name = "Community dictionaries"

    def ready(self):
        from . import checks  # noqa: F401
        from .deployment_health import capture_release
        capture_release()
