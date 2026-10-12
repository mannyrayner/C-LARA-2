"""Application estimates, not provider tariffs or hard provider spending caps."""
from decimal import Decimal
from . import tts, pronunciation

def text_cost(prices, inputs, outputs):
    return (Decimal(inputs)*Decimal(prices['input']) + Decimal(outputs)*Decimal(prices['output']))/1_000_000


def speech(text, language, prices, *, sentence=False, unknown=False):
    # Short lexical audio, or sentence duration inferred from its length.
    duration = max(2, min(25, len(text)/12)) if sentence else max(2, min(10, len(text)/12))
    cost = tts.estimate_cost(text + 'x'*800, duration)
    if not sentence:
        probability = Decimal('.20') if unknown else Decimal(bool(pronunciation.homographs(text, tts.language_code(language))))
        cost += probability * tts.guidance_estimate(prices)
    return cost


def allowance(estimate):
    from .porting import money
    return money(max(Decimal('.01'), estimate*Decimal('2.5')))


def analysis(entry, prices, extra=0):
    size = len((entry.word+entry.meaning+entry.category).encode('utf-8')) + extra
    return text_cost(prices, 1200+size//3, 350 if entry.entry_type=='sentence' else 200)


def language_check(prices, text):
    return text_cost(prices, 250+len(text.encode('utf-8')), 80)
