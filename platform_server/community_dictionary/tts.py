"""Saved speech using C-LARA's real TTS engine, without its test-tone fallback."""
from decimal import Decimal
from array import array
import io
import math
from pathlib import Path
import sys
import tempfile
import wave

from projects.billing import apply_credit_delta, credits_enabled, openai_price_for_model
from projects.models import AIUsageCharge, CreditLedgerEntry
from .photo_ai import _openai_client, api_credentials
from .services import Conflict
from .voices import DEFAULT_VOICE, VOICE_NAMES
from . import pronunciation

MODEL = 'gpt-4o-mini-tts'
INSTRUCTIONS_VERSION = pronunciation.VERSION
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


class SilentAudio(ValueError):
    def __init__(self, duration, peak, rms):
        super().__init__('silent_or_near_silent_audio')
        self.duration, self.peak, self.rms = duration, peak, rms


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
    if len(pcm) % (channels * width) or not 0 < frames <= rate * 60:
        raise ValueError('audio_duration')
    samples = array('h', pcm)
    if sys.byteorder != 'little':
        samples.byteswap()
    peak = max(abs(x) for x in samples)
    rms = math.sqrt(sum(x*x for x in samples) / len(samples))
    # Same conservative audibility thresholds as the listening probe. This is
    # not a pronunciation check, and no waveform is amplified or cropped.
    if peak < 300 or rms < 100:
        raise SilentAudio(frames / rate, peak, rms)
    output = io.BytesIO()
    with wave.open(output, 'wb') as target:
        target.setnchannels(channels); target.setsampwidth(width); target.setframerate(rate)
        target.writeframes(pcm)
    return (output.getvalue(), 'audio/wav', '.wav'), frames / rate


def guidance_configuration():
    from django.conf import settings
    from projects.models import OpenAIModelPricing
    name = settings.COMMUNITY_DICTIONARY_PHOTO_MODEL
    if name not in settings.OPENAI_TOKEN_PRICING_USD_PER_1M and not OpenAIModelPricing.objects.filter(model_name=name).exists():
        raise Conflict('The administrator needs to configure pricing for pronunciation guidance.')
    return name, openai_price_for_model(name)


def guidance_estimate(prices, *, allowance=False):
    # Reserve for every translated entry: its spelling is unknown at quote time.
    return ((Decimal(5000 if allowance else 1000)*Decimal(prices['input']) +
             Decimal(pronunciation.MAX_OUTPUT_TOKENS if allowance else 500)*Decimal(prices['output'])) / 1_000_000)


def report_cost(report):
    return sum((Decimal(report.get(key, '0')) for key in ['guidance_cost_usd', 'speech_cost_usd']), Decimal('0'))


def synthesize(text, *, language, model, voice, api_key, meaning='', meaning_language='',
               report=None, guidance_model=None, guidance_prices=None, before_request=None):
    if model != MODEL or voice not in VOICE_NAMES or language not in LANGUAGES.values() or not 0 < len(text) <= 255:
        raise ValueError('unsupported_synthesis')
    # Import lazily: URL loading must not initialize optional SDK dependencies.
    from pipeline.audio import OpenAITTSEngine
    report = report if report is not None else {}
    report.update(instructions_version=INSTRUCTIONS_VERSION,
                  english_homographs=pronunciation.homographs(text, language), attempts=[],
                  guidance_cost_usd='0', speech_cost_usd='0', uncertain_cost=False)
    instructions = pronunciation.simple_instructions(language)
    with _openai_client(api_key=api_key, timeout=30.0, max_retries=0) as client:
        if report['english_homographs']:
            if guidance_model is None:
                guidance_model, guidance_prices = guidance_configuration()
            if not guidance_prices:
                raise ValueError('missing_guidance_prices')
            if before_request:
                before_request()
            report['guidance_model'] = guidance_model
            report['uncertain_cost'] = True
            response = pronunciation.request_guidance(client, text, language, meaning, meaning_language, model=guidance_model)
            usage = getattr(response, 'usage', None)
            if usage:
                used = {k: max(0, int(getattr(usage, k, 0) or 0)) for k in ['input_tokens', 'output_tokens']}
                report['guidance_usage'] = used
                report['guidance_cost_usd'] = str(((Decimal(used['input_tokens'])*Decimal(guidance_prices['input']) +
                    Decimal(used['output_tokens'])*Decimal(guidance_prices['output'])) / 1_000_000).quantize(Decimal('.000001')))
                report['uncertain_cost'] = False
            hints = pronunciation.parse_guidance(response)
            report['guidance'] = hints
            instructions = pronunciation.enriched_instructions(text, language, hints)
        report['instructions'] = instructions
        engine = OpenAITTSEngine(client=client, model=model, require_language_instructions=True)
        with tempfile.TemporaryDirectory(prefix='community-tts-') as temporary:
            output = Path(temporary) / 'preview.wav'
            for attempt in range(2):
                if before_request:
                    before_request()
                record = {'attempt': attempt + 1, 'outcome': 'unknown'}
                report['attempts'].append(record)
                try:
                    engine.synthesize_to_path(text, output, voice=voice, language=language, instructions=instructions)
                    prepared, duration = normalize_wav(output.read_bytes())
                except SilentAudio as exc:
                    duration = exc.duration
                    record.update(outcome='near_silent', duration_seconds=duration,
                                  peak=exc.peak, rms=round(exc.rms, 2))
                    report['speech_cost_usd'] = str(Decimal(report['speech_cost_usd']) + estimate_cost(text + instructions, duration))
                    if attempt == 1:
                        raise
                    continue  # Only a completed, demonstrably quiet response is retried.
                except Exception:
                    report['uncertain_cost'] = True
                    raise  # Never retry timeouts, malformed responses or SDK/API errors.
                record.update(outcome='usable', duration_seconds=duration)
                report['speech_cost_usd'] = str(Decimal(report['speech_cost_usd']) + estimate_cost(text + instructions, duration))
                return prepared, duration


def record_charge(study):
    """Called once under the attempt's row lock, including known failed-call costs."""
    if study.personal_key:
        return
    metadata = {'provider': 'openai', 'model': study.model, 'operation': 'community_tts',
                'request_type': f'tts:{study.pk}', 'cost_usd': str(study.cost_usd),
                'cost_basis': 'guidance_tokens_plus_speech_duration_and_input_bytes',
                'synthesis_attempts': len(study.synthesis.get('attempts', [])),
                'guidance_model': study.synthesis.get('guidance_model'),
                'duration_seconds': study.duration_seconds, 'input_bytes': len(study.source_text.encode('utf-8'))}
    ledger = None
    if credits_enabled():
        ledger = apply_credit_delta(user=study.user, amount_usd=-study.cost_usd,
            entry_type=CreditLedgerEntry.ENTRY_USAGE, description='Community dictionary synthetic audio (estimated)',
            metadata=metadata)
    AIUsageCharge.objects.create(user=study.user, provider=AIUsageCharge.PROVIDER_OPENAI,
        model=study.model, operation='community_tts', request_type=f'tts:{study.pk}',
        cost_usd=study.cost_usd, status=AIUsageCharge.STATUS_CHARGED if ledger else AIUsageCharge.STATUS_SKIPPED,
        notes='Includes returned pronunciation-guidance usage and estimated speech costs for all completed attempts; provider invoice is authoritative.', ledger_entry=ledger)
