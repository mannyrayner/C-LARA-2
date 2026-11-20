"""Bounded, explicit hypotheses about ASR text, never acoustic diagnoses."""
import unicodedata

KINDS = {'word': 'help_word', 'phrase': 'help_phrase'}
FIELDS = {'before': 100, 'word': 100, 'meaning': 255, 'phrase': 160}


def prepare(candidates, original):
    if not isinstance(candidates, list) or len(candidates) > 3:
        raise ValueError('recognition_candidates')
    targets, spans, rejected = [], [], []
    for candidate in candidates:
        if not isinstance(candidate, dict) or set(candidate) != set(FIELDS) or any(
                not isinstance(candidate[k], str) or len(candidate[k]) > n for k, n in FIELDS.items()):
            raise ValueError('recognition_candidate_fields')
        item = {k: v.strip() for k, v in candidate.items()}
        before, word, phrase = item['before'], item['word'], item['phrase']
        # Optional help must not break an otherwise useful recognition question.
        # Ambiguous or overlapping edits stay in the raw review log, not the UI.
        if not before or not word or not phrase or original.count(before) != 1 or before == word:
            rejected.append('unaligned_or_empty'); continue
        start = original.index(before); end = start + len(before)
        if any(start < b and end > a for a, b in spans):
            rejected.append('overlapping'); continue
        nfc = lambda s: unicodedata.normalize('NFC', s).casefold()
        if nfc(word) not in nfc(phrase):
            rejected.append('phrase_missing_word'); continue
        spans.append((start, end))
        targets.append({**item, 'id': len(targets) + 1})
    proposed = original
    for (start, end), item in sorted(zip(spans, targets), reverse=True):
        proposed = proposed[:start] + item['word'] + proposed[end:]
    if len(proposed) > 255:
        return {'targets': [], 'proposed_text': '', 'rejected': [*rejected, 'too_long']}
    return {'targets': targets, 'proposed_text': proposed if targets else '', 'rejected': rejected}


def clip_spec(info, kind, target):
    if kind not in KINDS.values():
        return None
    for item in info.get('recognition_help', {}).get('targets', []):
        if item['id'] == target:
            part = 'word' if kind == KINDS['word'] else 'phrase'
            return {'text': item[part], 'meaning': item['meaning'] if part == 'word' else ''}
    return None
