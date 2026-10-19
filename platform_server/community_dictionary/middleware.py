from django.utils import translation
from django.utils.cache import patch_vary_headers

from .localisation import PREFIX, interface_language


class InterfaceLanguageMiddleware:
    """Use the dictionary UI preference without localising the rest of C-LARA."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path.startswith(PREFIX):
            return self.get_response(request)
        language = interface_language(request)
        request.LANGUAGE_CODE = language
        with translation.override(language):
            response = self.get_response(request)
        response['Content-Language'] = language
        patch_vary_headers(response, ('Cookie',))
        return response


class PrivatePagesMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith('/community-dictionaries/'):
            response['Cache-Control'] = 'private, no-store'
            response['X-Content-Type-Options'] = 'nosniff'
        return response
