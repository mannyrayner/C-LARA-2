"""Explicit dictionary choice for future lexical audio; sentences keep OpenAI.

Quotes and captures freeze this policy. Changing it invalidates unpaid work.
Google project charges are authorised by a site-administrator dictionary owner.
"""
from decimal import Decimal
from . import google_tts, tts
from .models import Dictionary, DictionaryWordAudioSettings
from .services import Conflict

VERSION = 'dictionary-word-audio-1'


def policy(dictionary):
    if not dictionary or not dictionary.pk:
        return {}
    row = DictionaryWordAudioSettings.objects.filter(dictionary_id=dictionary.pk).first()
    if not row or not row.voice:
        return {}
    if row.language != dictionary.language or row.authorised_by_id != dictionary.owner_id:
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
        google_tts.require_access(current.owner)
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
        if value:
            run.options = {**run.options, 'word_audio_policy':value}


def synthesize(text, *, dictionary, expected, **kwargs):
    if kwargs.get('speech_kind') == 'sentence':
        return tts.synthesize(text, **kwargs)
    validate(dictionary, expected)
    if not expected:
        return tts.synthesize(text, **kwargs)
    report = kwargs.get('report')
    report = report if report is not None else {}
    original = kwargs.get('before_request')
    def gate():
        validate(dictionary, expected)
        if original: original()
    return google_tts.synthesize(text, language=dictionary.language, method=expected['method'],
        selected_voice=expected['voice'], report=report, before_request=gate)


def metadata(report, voice):
    return {'provider':report.get('provider', 'openai'), 'model':report.get('model', tts.MODEL),
            'voice':report.get('voice', voice),
            'instructions_version':report.get('instructions_version', tts.INSTRUCTIONS_VERSION)}


def estimate(text, expected):
    return Decimal(len(text)) * Decimal(expected['rate']) / Decimal(1_000_000)
