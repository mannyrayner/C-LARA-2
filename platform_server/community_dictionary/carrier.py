"""Opt-in Swedish/French MWE carrier pilot; no pronunciation-quality claim."""
from decimal import Decimal
from pathlib import Path
import tempfile
import unicodedata

from . import tts, carrier_audio

VERSION = 'carrier-mwe-v1'
MAX_ATTEMPTS = 5


def eligible(text, language):
    # A conservative UI heuristic for existing multi-word lexical entries. No
    # segmentation model is invoked; contractions alone are not multi-word.
    tokens = unicodedata.normalize('NFC', text).split()
    return (tts.language_code(language) in {'fr', 'sv'} and 1 < len(tokens) <= 12
            and len(text) <= 120 and all(any(c.isalpha() for c in t) for t in tokens)
            and not any(c in text for c in '.!?;\n\r'))


class ExtractionFailed(ValueError):
    pass


def request(text, language):
    pause = 600
    item = {"language": language}
    if item['language'] == 'fr':
        prefix, suffix = 'On commence.', 'C’est fini.'
        instructions = (
            'Lis à voix haute les trois parties du texte, dans l’ordre et une seule fois, '
            'en français de France naturel. Prononce aussi « On commence » et « C’est fini » : '
            'ces phrases font partie du texte à lire. '
            f'Laisse environ {pause} millisecondes de silence entre les trois parties, '
            'sans pause à l’intérieur de la première ni de la dernière. '
            'Prononce le mot ou l’expression du milieu naturellement, avec une voix neutre '
            'et sans séparer les mots de l’expression. Ne prononce pas la ponctuation.')
    else:
        prefix, suffix = 'Vi börjar.', 'Vi avslutar.'
        instructions = (
            'Läs upp textens alla tre delar i ordning, en enda gång, på naturlig standardsvenska. '
            'Säg också ”Vi börjar” och ”Vi avslutar”: dessa fraser ingår i texten som ska läsas upp. '
            f'Lämna ungefär {pause} millisekunders tystnad mellan de tre delarna, '
            'utan paus inuti den första eller den sista delen. '
            'Uttala ordet eller uttrycket i mitten naturligt med neutral röst, '
            'utan att dela upp uttrycket i separata ord. Läs inte upp skiljetecknen.')
    text = f'{prefix} {text}. {suffix}'
    return text, instructions


def estimate(text, language, *, allowance=False):
    spoken, instructions = request(text, tts.language_code(language))
    # 1.4 completed requests per word is a planning assumption from the pilot.
    # The allowance includes five 16-second requests; not a provider spending cap.
    duration = 16 if allowance else max(5, min(12, len(text)/10+3))
    return tts.estimate_cost(spoken+instructions, duration) * (5 if allowance else Decimal('1.4'))


def synthesize(text, *, language, model, voice, api_key, report, before_request=None):
    if not eligible(text, language) or model != tts.MODEL or voice not in tts.VOICE_NAMES:
        raise ValueError('unsupported_carrier_synthesis')
    from pipeline.audio import OpenAITTSEngine
    spoken, instructions = request(text, tts.language_code(language))
    report.update(instructions_version=VERSION, speech_kind='entry', strategy='mwe_carrier',
        stage='setup', english_homographs=[], attempts=[], guidance_cost_usd='0',
        speech_cost_usd='0', uncertain_cost=False, instructions=instructions,
        extraction_algorithm=carrier_audio.ALGORITHM, extraction_config=carrier_audio.DEFAULT.copy())
    with tts._openai_client(api_key=api_key, timeout=30.0, max_retries=0) as client:
        engine = OpenAITTSEngine(client=client, model=model, require_language_instructions=True)
        with tempfile.TemporaryDirectory(prefix='community-carrier-') as temporary:
            output = Path(temporary)/'full.wav'
            for attempt in range(MAX_ATTEMPTS):
                if before_request:
                    before_request()
                record = {'attempt': attempt+1, 'outcome': 'unknown'}
                report['attempts'].append(record)
                try:
                    report['stage'] = 'speech'
                    engine.synthesize_to_path(spoken, output, voice=voice, language=language, instructions=instructions)
                    report['stage'] = 'audio_check'
                    prepared, duration = tts.normalize_wav(output.read_bytes())
                except tts.SilentAudio as exc:
                    report['speech_cost_usd'] = str(Decimal(report['speech_cost_usd'])+tts.estimate_cost(spoken+instructions, exc.duration))
                    record.update(outcome='near_silent', duration_seconds=exc.duration)
                    continue
                except Exception:
                    report['uncertain_cost'] = True
                    raise  # Unknown-cost network/API/malformed output is never retried.
                report['speech_cost_usd'] = str(Decimal(report['speech_cost_usd'])+tts.estimate_cost(spoken+instructions, duration))
                sound = carrier_audio.load(prepared[0])
                measurement = carrier_audio.measure(sound, carrier_audio.DEFAULT)
                record.update(outcome=measurement['status'], duration_seconds=duration, extraction=measurement)
                if measurement['status'] == 'candidate':
                    data = carrier_audio.segment(sound, measurement['cut']['start'], measurement['cut']['end'],
                        carrier_audio.DEFAULT['playback_padding_ms'])
                    try:
                        extracted, cut_duration = tts.normalize_wav(data)
                    except tts.SilentAudio:
                        record['outcome'] = 'near_silent_extract'
                        continue
                    report['stage'] = 'complete'
                    return extracted, cut_duration
            report['failure_code'] = 'extraction'
            raise ExtractionFailed('No structurally usable extract after five completed attempts')
