from pathlib import Path

from django.conf import settings
from django.core.checks import Error, register


@register()
def private_media_location(app_configs, **kwargs):
    private = Path(settings.COMMUNITY_DICTIONARY_MEDIA_ROOT).resolve()
    for public in [settings.MEDIA_ROOT, settings.STATIC_ROOT]:
        if public and private.is_relative_to(Path(public).resolve()):
            return [Error('Community dictionary media must be outside public MEDIA_ROOT and STATIC_ROOT.', id='community_dictionary.E001')]
    return []
