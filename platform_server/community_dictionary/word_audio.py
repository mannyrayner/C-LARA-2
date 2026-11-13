"""Explicit lexical voice choice and automatic language-capability fallback.

Quotes and captures freeze this policy. Changing it invalidates unpaid work.
Google project charges are authorised by a site-administrator dictionary owner.
"""
from decimal import Decimal
from . import google_tts, tts
from .models import Dictionary, DictionaryWordAudioSettings
from .permissions import is_owner
from .services import Conflict

VERSION = 'dictionary-word-audio-1'


def authorised_settings(dictionary, row=None):
    row = row or DictionaryWordAudioSettings.objects.filter(dictionary=dictionary).select_related('authorised_by').first()
    return row if row and row.language == dictionary.language and is_owner(row.authorised_by, dictionary) else None


def policy(dictionary):
    if not dictionary or not dictionary.pk:
        return {}
    if tts.language_code(dictionary.language) not in tts.LANGUAGES.values():
        from . import google_fallback
        return google_fallback.policy(dictionary)
    row = DictionaryWordAudioSettings.objects.filter(dictionary_id=dictionary.pk).select_related('authorised_by').first()
    if not row or not row.voice:
        return {}
    if not authorised_settings(dictionary, row):
        raise Conflict('The owner or language changed. Choose word audio settings again.')
    method = google_tts.voice_method(row.voice)
    return {'version':VERSION, 'voice':row.voice, 'method':method, 'language':row.language,
            'revision':row.revision, 'project':google_tts.project(),
            'rate':str(google_tts.RATES[method]), 'recipe':google_tts.VERSION}


def validate(dictionary, expected):
    current = Dictionary.objects.select_related('owner').get(pk=dictionary.pk)
    if policy(current) != (expected or {}):
        raise Conflict('Word audio settings changed. Prepare a fresh estimate or picture.')
    if expected:
        if expected.get('method') == 'google_gemini':
            google_tts.require_access(current.owner)
            if not current.tts_enabled or current.archived:
                raise Conflict('Dictionary audio is disabled.')
            return
        settings = authorised_settings(current)
        if not settings:
            raise Conflict('The owner or language changed. Choose word audio settings again.')
        google_tts.require_access(settings.authorised_by)
        if not current.tts_enabled or current.archived:
            raise Conflict('Dictionary audio is disabled.')
        if not google_tts.matches_language(expected['voice'], current.language):
            raise Conflict('The configured voice does not match the dictionary language.')


def run_policy(run):
    return run.options.get('word_audio_policy', {})


def check_run(run):
    if run.stage in {'legacy','sentences','vocabulary','forms','audio','descriptions'} and not run.port.is_audio_batch:
        validate(run.port.target, run_policy(run)) if run.port.target else None


def quote_run(run):
    if run.stage in {'legacy','sentences','vocabulary','forms','audio','descriptions'} and not run.port.is_audio_batch:
        value = policy(run.port.target)
        if not run.port.target:
            from types import SimpleNamespace
            from . import google_fallback
            value = google_fallback.policy(SimpleNamespace(language=run.port.language, owner=run.port.user))
        if value.get('method') == 'google_gemini' and run.payer == 'personal':
            raise Conflict('Google fallback audio uses the Google project. Use C-LARA credit payment for this batch instead of personal OpenAI payment.')
        if value:
            run.options = {**run.options, 'word_audio_policy':value}


def synthesize(text, *, dictionary, expected, **kwargs):
    expected = expected or {}
    if kwargs.get('speech_kind') == 'sentence' and expected.get('method') != 'google_gemini':
        return tts.synthesize(text, **kwargs)
    validate(dictionary, expected)
    if expected.get('method') == 'google_gemini' and kwargs.get('language') in tts.LANGUAGES.values():
        # Picture feedback may be in the explanation language. Its OpenAI
        # consent/key remains applicable; do not read it as the target language.
        return tts.synthesize(text, **kwargs)
    if not expected:
        return tts.synthesize(text, **kwargs)
    report = kwargs.get('report')
    report = report if report is not None else {}
    original = kwargs.get('before_request')
    def gate():
        validate(dictionary, expected)
        if original: original()
    if expected.get('method') == 'google_gemini':
        from . import google_fallback
        result = google_fallback.synthesize(text, language=kwargs.get('language', dictionary.language), expected=expected,
            report=report, before_request=gate)
        report['speech_kind'] = kwargs.get('speech_kind', 'entry')
        return result
    return google_tts.synthesize(text, language=dictionary.language, method=expected['method'],
        selected_voice=expected['voice'], report=report, before_request=gate)


def metadata(report, voice):
    return {'provider':report.get('provider', 'openai'), 'model':report.get('model', tts.MODEL),
            'voice':report.get('voice', voice),
            'instructions_version':report.get('instructions_version', tts.INSTRUCTIONS_VERSION)}


def estimate(text, expected):
    if expected.get('method') == 'google_gemini':
        from . import google_fallback
        return google_fallback.estimate(text)
    return Decimal(len(text)) * Decimal(expected['rate']) / Decimal(1_000_000)
