"""Optional, same-dictionary return context for visits from a practice game."""
import re
from urllib.parse import urlencode

from django.urls import reverse


def context(request, dictionary, *, public=False):
    token = request.GET.get('return_game', '')
    if not dictionary or not re.fullmatch(r'[0-9a-f]{32}', token):
        return {}
    category = request.GET.get('game_category', '')[:80]
    prefix = 'public-' if public else ''
    url = reverse('community_dictionary:' + prefix + 'practice', args=[dictionary.pk])
    return {'game_return': {
        'token': token, 'category': category,
        'url': url + '?' + urlencode({'resume': token, 'category': category}),
        'word_prefix': reverse('community_dictionary:' + prefix + 'word', args=[dictionary.pk, 0])[:-2],
        'entry_prefix': reverse('community_dictionary:' + prefix + 'entry', args=[dictionary.pk, 0])[:-2],
    }}
