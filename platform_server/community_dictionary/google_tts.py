"""Administrator-only Google comparison pilot; explicit user ADC, no legacy keys.

This adapter does not alter dictionary TTS routing. Local Windows installations
use the gcloud user ADC file; other hosts require explicit opt-in. Google calls
are billed to the configured Google project, independently of personal OpenAI
keys. Never log credential contents or provider error messages.
"""
import json
import os
from pathlib import Path
from decimal import Decimal

from django.conf import settings
from . import tts
from .services import Conflict

VERSION = 'google-lexical-adc-1'
PRICING_DATE = '2026-11-02'
VOICES = {
    'fr': {'google_wavenet': 'fr-FR-Wavenet-F', 'google_neural2': 'fr-FR-Neural2-F'},
    'sv': {'google_wavenet': 'sv-SE-Wavenet-F'},
}
RATES = {'google_wavenet': Decimal('4'), 'google_neural2': Decimal('16')}


def project():
    return settings.COMMUNITY_DICTIONARY_GOOGLE_TTS_PROJECT


def prices():
    return {'google_recipe': VERSION, 'google_project': project(),
            'google_rates': {k: str(v) for k, v in RATES.items()}, 'google_voices': VOICES}


def require_access(user):
    if not user.is_active or not (user.is_staff or user.is_superuser):
        raise Conflict('The Google comparison pilot is available to dictionary owners who are site administrators.')
    if not settings.COMMUNITY_DICTIONARY_GOOGLE_TTS_ENABLED:
        raise Conflict('Google comparison is not configured on this host. Use the configured laptop for this pilot.')


def voice(language, method):
    try:
        return VOICES[tts.language_code(language)][method]
    except KeyError:
        raise Conflict('This comparison currently supports French and Swedish.') from None


def credentials():
    explicit = settings.COMMUNITY_DICTIONARY_GOOGLE_TTS_ADC_FILE
    root = (Path(os.environ['CLOUDSDK_CONFIG']) if os.environ.get('CLOUDSDK_CONFIG') else
            Path(os.environ.get('APPDATA', str(Path.home() / 'AppData' / 'Roaming'))) / 'gcloud'
            if os.name == 'nt' else Path.home() / '.config' / 'gcloud')
    path = Path(explicit) if explicit else root / 'application_default_credentials.json'
    try:
        info = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        raise Conflict('Google user credentials were not found or could not be read by the server process. Run the standalone Google access check in the same Windows account.') from None
    if not isinstance(info, dict) or info.get('type') != 'authorized_user' or info.get('quota_project_id') != project():
        raise Conflict('Google comparison requires user ADC for the configured quota project. Legacy service-account keys are not used.')
    try:
        from google.oauth2.credentials import Credentials
        return Credentials.from_authorized_user_info(info).with_quota_project(project())
    except (ImportError, TypeError, ValueError):
        raise Conflict('Google user credentials or the Google client dependency are unavailable.') from None


def client():
    try:
        from google.cloud import texttospeech
    except ImportError:
        raise Conflict('Install the existing google-cloud-texttospeech project dependency before using this pilot.') from None
    return texttospeech.TextToSpeechClient(credentials=credentials())


def check_access(user, language):
    require_access(user)
    code = tts.language_code(language)
    expected = VOICES.get(code)
    if not expected:
        raise Conflict('This comparison currently supports French and Swedish.')
    connection = client()
    try:
        locale = next(iter(expected.values()))[:5]
        response = connection.list_voices(request={'language_code': locale}, retry=None, timeout=30)
        available = {v.name for v in response.voices if locale in v.language_codes}
        if not set(expected.values()) <= available:
            raise Conflict('A configured Google voice is unavailable. No audio was generated.')
    except Conflict:
        raise
    except Exception as exc:
        raise Conflict('Google access check failed (' + type(exc).__name__ + '). No audio was generated; credentials are not shown.') from None
    finally:
        connection.transport.close()


def estimate(text, method):
    return Decimal(len(text)) * RATES[method] / Decimal(1_000_000)


def synthesize(text, *, language, method, report, before_request):
    name = voice(language, method)
    if not 0 < len(text) <= 255:
        raise ValueError('unsupported_google_text')
    report.update(provider='google', model=name, voice=name, strategy='bare_text',
                  instructions_version=VERSION, quota_project=project(),
                  pricing_date=PRICING_DATE, input_characters=len(text),
                  speech_cost_usd='0', guidance_cost_usd='0', uncertain_cost=False,
                  attempts=[], stage='setup')
    connection = client()
    try:
        before_request()
        report.update(stage='speech', uncertain_cost=True)
        attempt = {'attempt': 1, 'outcome': 'unknown'}
        report['attempts'].append(attempt)
        response = connection.synthesize_speech(request={
            'input': {'text': text},
            'voice': {'name': name, 'language_code': name[:5]},
            'audio_config': {'audio_encoding': 'LINEAR16'},
        }, retry=None, timeout=60)
        report.update(speech_cost_usd=str(estimate(text, method)), uncertain_cost=False, stage='audio_check')
        attempt['outcome'] = 'invalid_audio'
        prepared, duration = tts.normalize_wav(bytes(response.audio_content))
        attempt.update(outcome='usable', duration_seconds=duration)
        report['stage'] = 'complete'
        return prepared, duration
    finally:
        connection.transport.close()
