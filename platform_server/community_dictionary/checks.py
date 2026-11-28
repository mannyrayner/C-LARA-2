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


@register()
def picture_concurrency(app_configs, **kwargs):
    from .image_capacity import limit
    from .services import Conflict
    try:
        limit()
    except Conflict as exc:
        return [Error(str(exc), id='community_dictionary.E002')]
    return []
