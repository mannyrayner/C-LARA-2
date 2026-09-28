"""Saved speech using C-LARA's real TTS engine, without its test-tone fallback."""
from decimal import Decimal
import io
from pathlib import Path
import tempfile
import wave

from projects.billing import apply_credit_delta, credits_enabled
from projects.models import AIUsageCharge, CreditLedgerEntry
from .photo_ai import _openai_client, api_credentials
from .services import Conflict
from .voices import DEFAULT_VOICE, VOICE_NAMES

MODEL = 'gpt-4o-mini-tts'
VOICE = DEFAULT_VOICE
# Application-level duration estimate, NOT a provider tariff or measured usage.
# The provider bills output audio tokens ($12/M at the 28 September check).
USD_PER_MINUTE = Decimal('0.015')
TEXT_USD_PER_MILLION = Decimal('0.60')
LANGUAGES = dict(pair.split(':') for pair in (
    'afrikaans:af arabic:ar armenian:hy azerbaijani:az belarusian:be bosnian:bs '
    'bulgarian:bg catalan:ca chinese:zh croatian:hr czech:cs danish:da dutch:nl '
    'english:en estonian:et finnish:fi french:fr galician:gl german:de greek:el '
    'hebrew:he hindi:hi hungarian:hu icelandic:is indonesian:id italian:it japanese:ja '
    'kannada:kn kazakh:kk korean:ko latvian:lv lithuanian:lt macedonian:mk malay:ms '
    'marathi:mr maori:mi nepali:ne norwegian:no persian:fa polish:pl portuguese:pt '
    'romanian:ro russian:ru serbian:sr slovak:sk slovenian:sl spanish:es swahili:sw '
    'swedish:sv tagalog:tl tamil:ta thai:th turkish:tr ukrainian:uk urdu:ur '
    'vietnamese:vi welsh:cy'
).split())


def language_code(language):
    name = language.strip().lower()
    return LANGUAGES.get(name) or (name if name in LANGUAGES.values() else None)


def configuration(user, dictionary):
    code = language_code(dictionary.language)
    if not code:
        raise Conflict('Saved TTS is not configured for this language. Please use a human recording.')
    key, personal = api_credentials(user)
    return key, personal, code


def estimate_cost(text, duration):
    # UTF-8 byte count is a conservative proxy for input tokens. Audio duration
    # uses our approximate rate. Record the basis, not fake token counts.
    return (Decimal(str(duration)) * USD_PER_MINUTE / 60 +
            len(text.encode('utf-8')) * TEXT_USD_PER_MILLION / 1_000_000).quantize(Decimal('.000001'))


def normalize_wav(data):
    if not data or len(data) > 15 * 1024 * 1024:
        raise ValueError('audio_size')
    with wave.open(io.BytesIO(data), 'rb') as source:
        channels, width, rate = source.getnchannels(), source.getsampwidth(), source.getframerate()
        if channels not in (1, 2) or width != 2 or not 8000 <= rate <= 48000 or source.getcomptype() != 'NONE':
            raise ValueError('audio_format')
        # Streaming WAV can have placeholder frame counts. Count actual PCM,
        # then write a normal finite WAV header for reliable browser playback.
        pcm = source.readframes(rate * 61)
    frames = len(pcm) // (channels * width)
    if len(pcm) % (channels * width) or not 0 < frames <= rate * 60 or not any(pcm):
        raise ValueError('audio_duration_or_silence')
    output = io.BytesIO()
    with wave.open(output, 'wb') as target:
        target.setnchannels(channels); target.setsampwidth(width); target.setframerate(rate)
        target.writeframes(pcm)
    return (output.getvalue(), 'audio/wav', '.wav'), frames / rate


def synthesize(text, *, language, model, voice, api_key):
    if model != MODEL or voice not in VOICE_NAMES or language not in LANGUAGES.values() or not 0 < len(text) <= 255:
        raise ValueError('unsupported_synthesis')
    # Import lazily: URL loading must not initialize optional SDK dependencies.
    from pipeline.audio import OpenAITTSEngine
    with _openai_client(api_key=api_key, timeout=30.0, max_retries=0) as client:
        engine = OpenAITTSEngine(client=client, model=model, require_language_instructions=True)
        with tempfile.TemporaryDirectory(prefix='community-tts-') as temporary:
            output = Path(temporary) / 'preview.wav'
            engine.synthesize_to_path(text, output, voice=voice, language=language)
            return normalize_wav(output.read_bytes())


def record_charge(study):
    """Called once under the attempt's row lock, after a usable response."""
    if study.personal_key:
        return
    metadata = {'provider': 'openai', 'model': study.model, 'operation': 'community_tts',
                'request_type': f'tts:{study.pk}', 'cost_usd': str(study.cost_usd),
                'cost_basis': 'duration_and_input_bytes_estimate',
                'duration_seconds': study.duration_seconds, 'input_bytes': len(study.source_text.encode('utf-8'))}
    ledger = None
    if credits_enabled():
        ledger = apply_credit_delta(user=study.user, amount_usd=-study.cost_usd,
            entry_type=CreditLedgerEntry.ENTRY_USAGE, description='Community dictionary synthetic audio (estimated)',
            metadata=metadata)
    AIUsageCharge.objects.create(user=study.user, provider=AIUsageCharge.PROVIDER_OPENAI,
        model=study.model, operation='community_tts', request_type=f'tts:{study.pk}',
        cost_usd=study.cost_usd, status=AIUsageCharge.STATUS_CHARGED if ledger else AIUsageCharge.STATUS_SKIPPED,
        notes='Estimated from audio duration and input byte count; provider invoice is authoritative.', ledger_entry=ledger)
