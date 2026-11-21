"""Durable personal workflows and bounded sentence-level generation guidance."""
from django.utils import timezone
from django.db import transaction
from django.utils.translation import gettext_lazy as _
from .models import ContributionPreference, DictionaryLearningSettings

LEVELS = [('beginner', _('Beginner')), ('low_intermediate', _('Low intermediate')),
          ('high_intermediate', _('Higher intermediate')), ('advanced', _('Advanced'))]
GUIDANCE = {
    'beginner': 'Approximate A1: one short clause, common surrounding words and simple grammar.',
    'low_intermediate': 'Approximate A2: short everyday sentences and simple connections between ideas.',
    'high_intermediate': 'Approximate B1-B2: varied natural grammar and more precise descriptions when useful.',
    'advanced': 'Unrestricted natural language when useful. Do not manufacture complexity or unnecessary detail.',
}


def level(dictionary):
    try:
        value = dictionary.learning_settings.level
    except DictionaryLearningSettings.DoesNotExist:
        value = 'beginner'
    return value if value in GUIDANCE else 'beginner'


def instructions(value):
    return ('\nLanguage level guidance (not a certified CEFR assessment): ' + GUIDANCE.get(value, GUIDANCE['beginner']) +
        '\nKeep the intended subject, action and relationships. Never simplify away core content: '
        'a puffin stays a puffin, not merely a bird. Necessary concrete vocabulary is welcome. '
        'Use a precise name only when supported by the image or contributor; ask if materially uncertain. '
        'Simplify surrounding grammar, not meaning. Keep explanations clear at every level.')


def preference(request, dictionary):
    if not dictionary or not request.user.is_authenticated:
        return {'mode': 'manual', 'consent': {}}
    key = dictionary.pk
    cache = getattr(request, '_contribution_preferences', {})
    if key not in cache:
        row = ContributionPreference.objects.filter(user=request.user, dictionary=dictionary).first()
        old = getattr(request, 'session', {}).get(f'writing-{key}', {})
        consent = dict(row.consent) if row else {}
        choices = consent.pop('_guided_choices', {})
        consent.pop('_picture_practice', None)  # UI preferences are never paid workflow consent.
        consent.pop('_picture_history', None)
        cache[key] = {'mode': row.mode if row else 'writing' if old.get('enabled') else
                      'guided' if available(dictionary) else 'manual',
                      'consent': consent, 'choices': choices}
        request._contribution_preferences = cache
    return cache[key]


def available(dictionary):
    from .tts import language_code
    return bool(dictionary and dictionary.sentence_capture_enabled and dictionary.tts_enabled and
        language_code(dictionary.language) and language_code(dictionary.explanation_language or 'English'))


def mode(request, dictionary):
    return preference(request, dictionary)['mode'] if available(dictionary) else 'manual'


@transaction.atomic
def save_preference(request, dictionary, mode, consent=None):
    choices = preference(request, dictionary).get('choices', {})
    consent = dict(consent or {})
    row, _ = ContributionPreference.objects.select_for_update().get_or_create(
        user=request.user, dictionary=dictionary, defaults={'mode':mode})
    for key in ('_picture_practice', '_picture_history'):
        if key in row.consent:
            consent[key] = row.consent[key]
    if choices:
        consent['_guided_choices'] = choices
    ContributionPreference.objects.update_or_create(user=request.user, dictionary=dictionary,
        defaults={'mode': mode, 'consent': consent, 'updated_at': timezone.now()})
    request.session.pop(f'writing-{dictionary.pk}', None)
    request._contribution_preferences = {}


@transaction.atomic
def save_guided_choices(request, dictionary, choices):
    """UI metadata is separate from paid consent, using the existing JSON store."""
    row, _created = ContributionPreference.objects.select_for_update().get_or_create(user=request.user, dictionary=dictionary,
        defaults={'mode': mode(request, dictionary)})
    consent = dict(row.consent)
    consent['_guided_choices'] = choices
    row.consent, row.updated_at = consent, timezone.now()
    row.save(update_fields=['consent', 'updated_at'])
    request._contribution_preferences = {}


def copy_level(source, target):
    DictionaryLearningSettings.objects.update_or_create(dictionary=target, defaults={'level': level(source)})
