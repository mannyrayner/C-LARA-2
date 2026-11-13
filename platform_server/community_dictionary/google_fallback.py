"""Language-based Gemini speech fallback, using the existing Google project ADC.

This is a capability choice before consent, never a retry after OpenAI fails.
Gemini 3.8 uses the Agent Platform endpoint, not Cloud TTS synthesizeSpeech.
"""
import base64
from decimal import Decimal
from functools import partial
import re

from . import google_tts, tts
from .services import Conflict

VERSION = 'google-gemini-language-fallback-1'
MODEL = 'gemini-3.8-flash-tts'
VOICE = 'Kore'
# Explicitly mapped names from Google's supported-language table, checked
# 2026-11-13. Do not infer support for every language from model multilinguality.
LANGUAGES = dict(pair.split(':') for pair in (
    'igbo:ig amharic:am assamese:as basque:eu bengali:bn bangla:bn burmese:my '
    'gujarati:gu hausa:ha khmer:km lao:lo malayalam:ml punjabi:pa '
    'sindhi:sd sinhala:si somali:so telugu:te'
).split())
# Standard rates, deliberately excluding temporary promotional credits.
INPUT_RATE = Decimal('1')
OUTPUT_RATE = Decimal('18')


def language_code(language):
    name = language.strip().casefold()
    return LANGUAGES.get(name) or (name if name in LANGUAGES.values() else None)


def policy(dictionary):
    code = language_code(dictionary.language)
    if not code:
        return {}
    owner = dictionary.owner
    # Preserve the existing requirement for administrator authorization of
    # this project's Google charges. Enabling saved audio authorizes the
    # language fallback; each paid request still discloses Google explicitly.
    google_tts.require_access(owner)
    return {'version': VERSION, 'method': 'google_gemini', 'model': MODEL,
            'voice': VOICE, 'language': dictionary.language, 'owner': owner.pk,
            'project': google_tts.project(), 'input_rate': str(INPUT_RATE),
            'output_rate': str(OUTPUT_RATE), 'recipe': VERSION}


def estimate(text, duration=None):
    duration = max(2, min(25, len(text) / 12)) if duration is None else duration
    # Application estimate, not measured provider token usage. Reserve extra
    # input bytes for language/style guidance and estimate 25 audio tokens/s.
    return ((Decimal(len(text.encode('utf-8')) + 300) * INPUT_RATE +
             Decimal(str(duration)) * 25 * OUTPUT_RATE) / 1_000_000).quantize(Decimal('.000001'))


def session():
    from google.auth.transport.requests import AuthorizedSession, Request
    from requests import Session
    try:
        auth = google_tts.credentials()
    except Conflict:
        raise google_tts.GoogleAccessError('credentials', 'Gemini credential file') from None
    try:
        with Session() as transport:
            auth.refresh(partial(Request(session=transport), timeout=30))
        return AuthorizedSession(auth, max_refresh_attempts=0)
    except Exception as exc:
        raise google_tts.access_error(exc, 'Gemini sign-in renewal') from None


def synthesize(text, *, language, expected, report, before_request):
    code = language_code(language)
    if not code or expected.get('method') != 'google_gemini' or expected.get('model') != MODEL:
        raise Conflict('The Google speech configuration changed. Prepare a fresh request.')
    if not 0 < len(text) <= 255:
        raise ValueError('unsupported_google_text')
    project = google_tts.project()
    if expected.get('project') != project or not re.fullmatch(r'[a-z][a-z0-9-]{4,61}[a-z0-9]', project):
        raise Conflict('The Google project changed. Prepare a fresh request.')
    name = next(name for name, value in LANGUAGES.items() if value == code)
    style = f'Read naturally in {name}, preserving its pronunciation and tones. Speak only the supplied text.'
    report.update(provider='google', model=MODEL, voice=VOICE, strategy='language_fallback',
        instructions_version=VERSION, quota_project=project, speech_kind='entry',
        cost_basis='google_gemini_tokens_or_duration_estimate', input_characters=len(text),
        input_rate=str(INPUT_RATE), output_rate=str(OUTPUT_RATE),
        speech_cost_usd='0', guidance_cost_usd='0', uncertain_cost=False,
        attempts=[], stage='setup')
    connection = session()
    try:
        before_request()
        report.update(stage='speech', uncertain_cost=True)
        attempt = {'attempt': 1, 'outcome': 'unknown'}
        report['attempts'].append(attempt)
        url = f'https://aiplatform.googleapis.com/v1/projects/{project}/locations/global/publishers/google/models/{MODEL}:generateContent'
        try:
            response = connection.post(url, json={
                'contents': [{'role': 'user', 'parts': [{'text': text, 'speechMetadata': {'style': style}}]}],
                'generationConfig': {'responseModalities': ['AUDIO'], 'speechConfig': {'voiceConfig': {'voice': VOICE}}},
            }, timeout=(15, 60), allow_redirects=False)
        except Exception as exc:
            from requests.exceptions import ConnectionError, Timeout
            if isinstance(exc, (ConnectionError, Timeout)):
                raise google_tts.GoogleAccessError('connection', 'Gemini speech request') from None
            raise google_tts.access_error(exc, 'Gemini speech request') from None
        if response.status_code != 200:
            # Google documents non-200 responses as uncharged; transport
            # failures remain uncertain and are never automatically retried.
            report['uncertain_cost'] = False
            attempt['outcome'] = 'rejected'
            if response.status_code in (401, 403):
                raise google_tts.GoogleAccessError('permission', 'Gemini speech request')
            raise Conflict('Google Gemini could not create this recording. No automatic retry was sent.')
        report['stage'] = 'audio_check'
        attempt['outcome'] = 'invalid_audio'
        payload = response.json()
        usage = payload.get('usageMetadata', {})
        counts = [usage.get('promptTokenCount'), usage.get('candidatesTokenCount')]
        if all(type(value) is int and 0 <= value <= 100_000 for value in counts):
            report['usage'] = {'input_tokens': counts[0], 'output_tokens': counts[1]}
            report['speech_cost_usd'] = str((
                (Decimal(counts[0]) * INPUT_RATE + Decimal(counts[1]) * OUTPUT_RATE) /
                1_000_000).quantize(Decimal('.000001')))
            report['cost_basis'] = 'google_gemini_returned_tokens'
            report['uncertain_cost'] = False
        candidates = payload.get('candidates', [])
        if len(candidates) != 1 or candidates[0].get('finishReason') not in (None, 'STOP'):
            raise ValueError('incomplete_google_audio')
        parts = candidates[0].get('content', {}).get('parts', [])
        clips = [part['inlineData'] for part in parts if 'inlineData' in part]
        if len(clips) != 1:
            raise ValueError('missing_google_audio')
        clip = clips[0]
        if clip.get('mimeType', '').split(';')[0].lower() not in {'audio/wav', 'audio/x-wav', 'audio/wave'}:
            raise ValueError('unsupported_google_audio')
        data = clip.get('data', '')
        if not isinstance(data, str) or len(data) > 21 * 1024 * 1024:
            raise ValueError('google_audio_size')
        prepared, duration = tts.normalize_wav(base64.b64decode(data, validate=True))
        if 'usage' not in report:
            report.update(speech_cost_usd=str(estimate(text, duration)), uncertain_cost=False)
        attempt.update(outcome='usable', duration_seconds=duration)
        report['stage'] = 'complete'
        return prepared, duration
    finally:
        connection.close()
