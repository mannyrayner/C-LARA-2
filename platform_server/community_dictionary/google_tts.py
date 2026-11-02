"""Google lexical audio; explicit user ADC or AWS federation, no legacy keys.

Local Windows installations use the gcloud user ADC file; other hosts opt in. Google calls
are billed to the configured Google project, independently of personal OpenAI
keys. Never log credential contents or provider error messages.
"""
import json
import os
import re
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
    'en': {'google_wavenet': 'en-GB-Wavenet-F'},
    'de': {'google_wavenet': 'de-DE-Wavenet-G', 'google_neural2': 'de-DE-Neural2-G'},
    'it': {'google_wavenet': 'it-IT-Wavenet-E', 'google_neural2': 'it-IT-Neural2-E'},
    'is': {'google_standard': 'is-IS-Standard-B'},
    'ja': {'google_wavenet': 'ja-JP-Wavenet-B', 'google_neural2': 'ja-JP-Neural2-B'},
    'sk': {'google_wavenet': 'sk-SK-Wavenet-B'},
    'es': {'google_wavenet': 'es-ES-Wavenet-F'},
    'zh': {'google_wavenet': 'cmn-CN-Wavenet-A'},
}
RATES = {'google_wavenet': Decimal('4'), 'google_neural2': Decimal('16'), 'google_standard': Decimal('4'), 'google_chirp3': Decimal('30')}


def project():
    return settings.COMMUNITY_DICTIONARY_GOOGLE_TTS_PROJECT


def prices():
    return {'google_recipe': VERSION, 'google_project': project(),
            'google_rates': {k: str(v) for k, v in RATES.items()}, 'google_voices': VOICES}


def require_access(user):
    if not user.is_active or not (user.is_staff or user.is_superuser):
        raise Conflict('A site administrator who owns this dictionary must authorise Google project charges.')
    if not settings.COMMUNITY_DICTIONARY_GOOGLE_TTS_ENABLED:
        raise Conflict('Google word audio is not configured on this host.')


def voice(language, method):
    try:
        return VOICES[tts.language_code(language)][method]
    except KeyError:
        raise Conflict('No Google voice is configured for this language. Load the available voices in Word audio settings.') from None


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
    if not isinstance(info, dict):
        raise Conflict('Invalid Google credential configuration.')
    try:
        if info.get('type') == 'authorized_user' and info.get('quota_project_id') == project():
            from google.oauth2.credentials import Credentials
            return Credentials.from_authorized_user_info(info).with_quota_project(project())
        if explicit and info.get('type') == 'external_account':
            source = info.get('credential_source', {})
            if (info.get('subject_token_type') != 'urn:ietf:params:aws:token-type:aws4_request' or
                    source.get('environment_id') != 'aws1' or
                    source.get('url') != 'http://169.254.169.254/latest/meta-data/iam/security-credentials' or
                    source.get('region_url') != 'http://169.254.169.254/latest/meta-data/placement/availability-zone' or
                    source.get('imdsv2_session_token_url') != 'http://169.254.169.254/latest/api/token' or
                    source.get('regional_cred_verification_url') != 'https://sts.{region}.amazonaws.com?Action=GetCallerIdentity&Version=2011-06-15' or
                    info.get('token_url') != 'https://sts.googleapis.com/v1/token' or
                    not re.fullmatch(r'//iam.googleapis.com/projects/[0-9]+/locations/global/workloadIdentityPools/[a-z0-9-]+/providers/[a-z0-9-]+', info.get('audience','')) or
                    not re.fullmatch(r'https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/[a-z0-9-]+@'+re.escape(project())+r'\.iam\.gserviceaccount\.com:generateAccessToken', info.get('service_account_impersonation_url',''))):
                raise Conflict('Use the reviewed AWS workload-identity configuration for this Google project.')
            from google.auth import aws
            return aws.Credentials.from_info(info, scopes=['https://www.googleapis.com/auth/cloud-platform']).with_quota_project(project())
    except (ImportError, TypeError, ValueError):
        raise Conflict('Google credentials or the Google authentication dependency are unavailable.') from None
    raise Conflict('Use user ADC for the configured quota project, or an explicit AWS workload-identity configuration. Service-account keys and legacy environment credentials are not used.')


def client():
    try:
        from google.cloud import texttospeech
    except ImportError:
        raise Conflict('Install the existing google-cloud-texttospeech project dependency before using this pilot.') from None
    return texttospeech.TextToSpeechClient(credentials=credentials())


def check_access(user, language, *, selected_voice=None):
    require_access(user)
    code = tts.language_code(language)
    expected = {'selected':selected_voice} if selected_voice else VOICES.get(code)
    if not expected:
        raise Conflict('No Google voice is configured for this language. Load the available voices in Word audio settings.')
    connection = client()
    try:
        locale = voice_locale(next(iter(expected.values())))
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


def synthesize(text, *, language, method, report, before_request, selected_voice=None):
    name = selected_voice or voice(language, method)
    if voice_method(name) != method or not matches_language(name, language):
        raise Conflict('The Google voice does not match the requested language or method.')
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
        report.update(stage='speech', uncertain_cost=True, speech_cost_usd=str(estimate(text, method)))
        attempt = {'attempt': 1, 'outcome': 'unknown'}
        report['attempts'].append(attempt)
        response = connection.synthesize_speech(request={
            'input': {'text': text},
            'voice': {'name': name, 'language_code': voice_locale(name)},
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


def voice_locale(name):
    return '-'.join(name.split('-')[:2])


def voice_method(name):
    for marker, method in [('-Wavenet-', 'google_wavenet'), ('-Neural2-', 'google_neural2'),
                           ('-Standard-', 'google_standard'), ('-Chirp3-HD-', 'google_chirp3')]:
        if marker in name and re.fullmatch(r'[A-Za-z0-9-]{4,100}', name):
            return method
    raise Conflict('Choose a supported Google WaveNet, Neural2, Standard or Chirp 3 voice.')


def matches_language(name, language):
    code = tts.language_code(language)
    aliases = {'zh': {'cmn','yue'}, 'no': {'nb','no'}, 'tl': {'fil','tl'}, 'he': {'he','iw'}}
    return name.split('-')[0] in aliases.get(code, {code})


def voices_for(dictionary):
    """Static trial voices plus the owner's explicitly verified selection."""
    from .models import DictionaryWordAudioSettings
    result = dict(VOICES.get(tts.language_code(dictionary.language), {}))
    selected = DictionaryWordAudioSettings.objects.filter(dictionary=dictionary,
        language=dictionary.language, authorised_by_id=dictionary.owner_id).values_list('voice', flat=True).first()
    if selected:
        result[voice_method(selected)] = selected
    return result


def comparison_prices(dictionary):
    values = prices()
    values['google_voices'] = {**VOICES, tts.language_code(dictionary.language): voices_for(dictionary)}
    return values


def discover(user, language):
    """Explicit setup action only: never called by dictionary browsing."""
    require_access(user)
    connection = client()
    try:
        response = connection.list_voices(request={}, retry=None, timeout=30)
        names = []
        for value in response.voices:
            if not matches_language(value.name, language):
                continue
            try: voice_method(value.name)
            except Conflict: continue
            names.append(value.name)
        order = {'google_wavenet':0, 'google_neural2':1, 'google_standard':2, 'google_chirp3':3}
        return sorted(set(names), key=lambda n:(order[voice_method(n)], n))
    except Exception as exc:
        raise Conflict('Google voice discovery failed ('+type(exc).__name__+'). No audio was generated.') from None
    finally:
        connection.transport.close()
