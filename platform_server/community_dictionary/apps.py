from django.apps import AppConfig


class CommunityDictionaryConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "community_dictionary"
    verbose_name = "Community dictionaries"

    def ready(self):
        from . import checks  # noqa: F401
