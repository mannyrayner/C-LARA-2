"""Interface preferences and language matching, independent of dictionary content.

Language names are free text in existing dictionaries. Normalize only for matching;
never rewrite those names, words, explanations, or audio in the database.
"""
import unicodedata

from django.http import HttpResponseBadRequest
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _, gettext_noop as N_
from django.views.decorators.http import require_POST


UI_COOKIE = 'community_ui_language'
# Add an interface here and supply its django/djangojs translation catalogs.
# Canonical language names also initialise dictionary explanation fields; labels
# stay in each language so the selector remains recognisable in every locale.
UI_LANGUAGE_CONFIG = {
    'en': {'label': 'English', 'language': N_('English'), 'learning_default': 'fr'},
    'fr': {'label': 'Français', 'language': N_('French'), 'learning_default': 'en'},
    'sk': {'label': 'Slovenčina', 'language': N_('Slovak'), 'learning_default': 'en'},
}
UI_LANGUAGES = tuple((code, config['label']) for code, config in UI_LANGUAGE_CONFIG.items())
PREFIX = '/community-dictionaries/'
LANGUAGE_NAMES = {
    **{code: config['language'] for code, config in UI_LANGUAGE_CONFIG.items()},
    'de': N_('German'), 'it': N_('Italian'),
    'es': N_('Spanish'), 'sv': N_('Swedish'), 'is': N_('Icelandic'), 'ja': N_('Japanese'),
    'zh': N_('Chinese'), 'pt': N_('Portuguese'), 'nl': N_('Dutch'), 'ar': N_('Arabic'),
    'hi': N_('Hindi'),
}
ALIASES = {
    'english': 'en', 'anglais': 'en', 'french': 'fr', 'français': 'fr',
    'francais': 'fr', 'german': 'de', 'allemand': 'de', 'deutsch': 'de',
    'italian': 'it', 'italien': 'it', 'italiano': 'it',
    'spanish': 'es', 'espagnol': 'es', 'español': 'es',
    'swedish': 'sv', 'suédois': 'sv', 'svenska': 'sv',
    'icelandic': 'is', 'islandais': 'is', 'íslenska': 'is',
    'japanese': 'ja', 'japonais': 'ja', '日本語': 'ja',
    'chinese': 'zh', 'chinois': 'zh', '中文': 'zh',
    'portuguese': 'pt', 'portugais': 'pt', 'português': 'pt',
    'dutch': 'nl', 'néerlandais': 'nl', 'nederlands': 'nl',
    'arabic': 'ar', 'arabe': 'ar', 'العربية': 'ar', 'hindi': 'hi', 'हिन्दी': 'hi',
    'slovak': 'sk', 'slovaque': 'sk', 'slovenčina': 'sk', 'slovencina': 'sk',
    'angličtina': 'en', 'anglictina': 'en', 'francúzština': 'fr', 'francuzstina': 'fr',
}


def language_key(value, *, explanation=False):
    key = ' '.join(unicodedata.normalize('NFKC', value or '').casefold().split())
    if not key and explanation:
        return 'en'  # Existing dictionary processing treats blank as English.
    code = key.replace('_', '-').split('-')[0]
    return ALIASES.get(key, code if code in LANGUAGE_NAMES else key)


def language_label(value):
    return _(LANGUAGE_NAMES.get(language_key(value), value))


def interface_language(request):
    value = request.COOKIES.get(UI_COOKIE, 'en')
    return value if value in dict(UI_LANGUAGES) else 'en'


def interface_explanation_language(request):
    """Canonical stored-language default, independent of translated UI labels."""
    return UI_LANGUAGE_CONFIG[interface_language(request)]['language']


def context(request):
    if not request.path.startswith(PREFIX):
        return {}
    return {'community_ui_language': interface_language(request),
            'community_ui_choices': UI_LANGUAGES}


@require_POST
def set_language(request):
    language = request.POST.get('language')
    if language not in dict(UI_LANGUAGES):
        return HttpResponseBadRequest(_('Choose an interface language.'))
    destination = request.POST.get('next', '')
    # Keep this preference confined to the dictionary app; reject external,
    # protocol-relative and malformed redirects, even on the current host.
    if (not destination.startswith(PREFIX) or '\\' in destination or
            not url_has_allowed_host_and_scheme(destination, {request.get_host()},
                                                require_https=request.is_secure())):
        destination = reverse('community_dictionary:home' if request.user.is_authenticated
                              else 'community_dictionary:public-home')
    response = redirect(destination)
    response.set_cookie(UI_COOKIE, language, max_age=365 * 24 * 60 * 60,
                        path=PREFIX, secure=request.is_secure(), httponly=True,
                        samesite='Lax')
    return response


def learning_options(request, *, member=False):
    """Recommend matching explanations without filtering the existing lists."""
    from . import discovery
    from .permissions import dictionaries_for

    available = {d.pk: d for d in discovery.dictionaries().order_by('name', 'pk')}
    member_ids = set()
    if member:
        own = list(dictionaries_for(request.user).filter(hidden=False).order_by('name', 'pk'))
        member_ids = {d.pk for d in own}
        available.update({d.pk: d for d in own})
    ui = interface_language(request)
    matching = [d for d in available.values()
                if language_key(d.explanation_language, explanation=True) == ui
                and language_key(d.language)]
    names = {language_key(d.language): language_label(d.language) for d in matching}
    choices = sorted(names.items(), key=lambda item: item[1].casefold())
    saved = request.session.get('community_learning_languages', {})
    if not isinstance(saved, dict):
        saved = {}
    requested = request.GET.get('learning', saved.get(ui, ''))
    default = UI_LANGUAGE_CONFIG[ui]['learning_default']
    if requested in names or requested == 'all':
        selected = requested
    elif default in names:
        selected = default
    else:
        selected = next((key for key, _ in choices if key != ui), choices[0][0] if choices else '')
    if 'learning' in request.GET and (requested in names or requested == 'all'):
        request.session['community_learning_languages'] = {**saved, ui: requested}
    recommendations = []
    for d in sorted(matching, key=lambda d: (d.pk not in member_ids, d.name.casefold(), d.pk)):
        if selected != 'all' and language_key(d.language) != selected:
            continue
        route = ('dictionary' if d.pk in member_ids else
                 'public-dictionary' if d.public_browsing_enabled else 'discover-dictionary')
        recommendations.append({'name': d.name, 'language': language_label(d.language),
                                'url': reverse('community_dictionary:' + route, args=[d.pk])})
    return {'learning_choices': choices, 'learning_language': selected,
            'learning_recommendations': recommendations,
            'learning_explanation_language': language_label(LANGUAGE_NAMES[ui])}
