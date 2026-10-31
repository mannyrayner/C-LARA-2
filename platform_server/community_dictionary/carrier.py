"""Opt-in lexical carrier pilot; Japanese selection is explicitly manual."""
from decimal import Decimal
from pathlib import Path
import tempfile
import unicodedata

from . import tts, carrier_audio

VERSION = 'carrier-mwe-v1'
MAX_ATTEMPTS = 5
AUTOMATIC_LANGUAGES = frozenset({'en', 'fr', 'sv', 'de', 'it', 'is'})
SUPPORTED_LANGUAGES = AUTOMATIC_LANGUAGES | {'ja'}
LANGUAGE_LABEL = 'English, French, Swedish, German, Italian, Icelandic or Japanese'


def eligible(text, language, *, explicit_selection=False):
    # A conservative UI heuristic for existing multi-word lexical entries. No
    # segmentation model is invoked; contractions alone are not multi-word.
    tokens = unicodedata.normalize('NFC', text).split()
    code = tts.language_code(language)
    # Neither kanji count nor spaces reliably identify Japanese MWEs. Only an
    # owner-selected lexical entry may use this experimental route in Japanese.
    selected_japanese = code == 'ja' and explicit_selection
    return ((code in AUTOMATIC_LANGUAGES or selected_japanese)
            and (1 if selected_japanese else 2) <= len(tokens) <= 12
            and len(text) <= 120 and all(any(c.isalpha() for c in t) for t in tokens)
            and not any(c in text for c in '.!?;\n\r。！？；'))


class ExtractionFailed(ValueError):
    pass


def request(text, language):
    pause = 600
    code = tts.language_code(language)
    if code not in SUPPORTED_LANGUAGES:
        raise ValueError('unsupported_carrier_language')
    item = {"language": code}
    if code == 'en':
        prefix, suffix = 'We begin.', 'We are finished.'
        instructions = (
            'Read all three parts of the text exactly once, in order, in natural native English. '
            'Also say "We begin" and "We are finished": these phrases are part of the text to read. '
            f'Leave about {pause} milliseconds of silence between the three parts, '
            'with no pause inside the first or last part. '
            'Pronounce the expression in the middle naturally as one coherent phrase, '
            'with neutral intonation, natural stress and linking. '
            'Do not separate its words with artificial pauses or give every word equal stress. '
            'Do not read punctuation aloud.')
    elif item['language'] == 'fr':
        prefix, suffix = 'On commence.', 'C’est fini.'
        instructions = (
            'Lis à voix haute les trois parties du texte, dans l’ordre et une seule fois, '
            'en français de France naturel. Prononce aussi « On commence » et « C’est fini » : '
            'ces phrases font partie du texte à lire. '
            f'Laisse environ {pause} millisecondes de silence entre les trois parties, '
            'sans pause à l’intérieur de la première ni de la dernière. '
            'Prononce le mot ou l’expression du milieu naturellement, avec une voix neutre '
            'et sans séparer les mots de l’expression. Ne prononce pas la ponctuation.')
    elif code == 'sv':
        prefix, suffix = 'Vi börjar.', 'Vi avslutar.'
        instructions = (
            'Läs upp textens alla tre delar i ordning, en enda gång, på naturlig standardsvenska. '
            'Säg också ”Vi börjar” och ”Vi avslutar”: dessa fraser ingår i texten som ska läsas upp. '
            f'Lämna ungefär {pause} millisekunders tystnad mellan de tre delarna, '
            'utan paus inuti den första eller den sista delen. '
            'Uttala ordet eller uttrycket i mitten naturligt med neutral röst, '
            'utan att dela upp uttrycket i separata ord. Läs inte upp skiljetecknen.')
    elif code == 'de':
        prefix, suffix = 'Wir beginnen.', 'Wir sind fertig.'
        instructions = (
            'Lies alle drei Teile des Textes der Reihe nach genau einmal auf natürlichem Standarddeutsch vor. '
            'Sprich auch „Wir beginnen“ und „Wir sind fertig“ aus: Diese Sätze gehören zum Text. '
            f'Lass zwischen den drei Teilen jeweils ungefähr {pause} Millisekunden Stille, '
            'ohne Pause innerhalb des ersten oder letzten Teils. '
            'Sprich das Wort oder den Ausdruck in der Mitte natürlich und mit neutraler Stimme aus. '
            'Trenne die Wörter des Ausdrucks nicht durch künstliche Pausen. Lies die Satzzeichen nicht vor.')
    elif code == 'it':
        prefix, suffix = 'Cominciamo.', 'Abbiamo finito.'
        instructions = (
            'Leggi ad alta voce tutte e tre le parti del testo, in ordine e una sola volta, in italiano standard naturale. '
            'Pronuncia anche «Cominciamo» e «Abbiamo finito»: queste frasi fanno parte del testo da leggere. '
            f'Lascia circa {pause} millisecondi di silenzio tra le tre parti, '
            'senza pause all’interno della prima o dell’ultima parte. '
            'Pronuncia la parola o l’espressione centrale in modo naturale, con voce neutra, '
            'senza separare artificialmente le parole dell’espressione. Non leggere la punteggiatura.')
    elif code == 'is':
        prefix, suffix = 'Við byrjum.', 'Við erum búin.'
        instructions = (
            'Lestu alla þrjá hluta textans upp í réttri röð, aðeins einu sinni, á eðlilegri íslensku. '
            'Segðu líka „Við byrjum“ og „Við erum búin“: þessar setningar eru hluti af textanum. '
            f'Hafðu um {pause} millisekúndna þögn á milli hlutanna þriggja, '
            'en ekkert hlé inni í fyrsta eða síðasta hlutanum. '
            'Berðu orðið eða orðasambandið í miðjunni fram á eðlilegan hátt með hlutlausum raddblæ. '
            'Ekki aðskilja orð orðasambandsins með óeðlilegum hléum. Ekki lesa greinarmerkin upp.')
    else:  # Japanese; eligibility is checked separately before synthesis.
        prefix, suffix = '始めます。', '終わりました。'
        instructions = (
            'テキストの三つの部分を、自然な標準日本語で、順番に一度ずつ読み上げてください。'
            '「始めます」と「終わりました」も必ず読んでください。これらも読むテキストの一部です。'
            f'三つの部分の間には、それぞれ約{pause}ミリ秒の無音を入れてください。'
            '最初と最後の部分の途中には間を入れないでください。'
            '中央の語句は、落ち着いた声で自然なアクセントとイントネーションで読んでください。'
            '語句の内部を不自然な間で区切らず、句読点の名前は読まないでください。')
    text = f'{prefix} {text}{"。" if code == "ja" else "."} {suffix}'
    return text, instructions


def estimate(text, language, *, allowance=False):
    spoken, instructions = request(text, tts.language_code(language))
    # 1.4 completed requests per word is a planning assumption from the pilot.
    # The allowance includes five 16-second requests; not a provider spending cap.
    duration = 16 if allowance else max(5, min(12, len(text)/10+3))
    return tts.estimate_cost(spoken+instructions, duration) * (5 if allowance else Decimal('1.4'))


def homograph_eligible(text, language):
    """Explicit experiment only; never broadens the ordinary MWE selection."""
    from .pronunciation import homographs
    return (tts.language_code(language) in AUTOMATIC_LANGUAGES - {'en'}
            and 1 <= len(text.split()) <= 12 and len(text) <= 120
            and not any(c in text for c in '.!?;\n\r。！？；')
            and bool(homographs(text, tts.language_code(language))))


def synthesize(text, *, language, model, voice, api_key, report, before_request=None,
               explicit_selection=False, homograph_experiment=False, keep_full=None):
    allowed = (homograph_eligible(text, language) if homograph_experiment else
               eligible(text, language, explicit_selection=explicit_selection))
    if not allowed or model != tts.MODEL or voice not in tts.VOICE_NAMES:
        raise ValueError('unsupported_carrier_synthesis')
    from pipeline.audio import OpenAITTSEngine
    spoken, instructions = request(text, tts.language_code(language))
    report.update(instructions_version=VERSION, speech_kind='entry',
        strategy='lexical_carrier' if tts.language_code(language) == 'ja' else 'mwe_carrier',
        carrier_language=tts.language_code(language), explicit_selection=explicit_selection,
        stage='setup', english_homographs=[], attempts=[], guidance_cost_usd='0',
        speech_cost_usd='0', uncertain_cost=False, instructions=instructions,
        extraction_algorithm=carrier_audio.ALGORITHM, extraction_config=carrier_audio.DEFAULT.copy())
    if homograph_experiment:
        report['strategy'] = 'homograph_carrier_experiment'
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
                if keep_full:
                    keep_full(prepared)  # Caller may retain the last completed take privately.
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
