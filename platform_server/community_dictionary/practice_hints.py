"""Read-only hints from current accepted dictionary material. No AI calls."""
import json
from .capture import sentence_links
from .lexicon import linked_words, vocabulary, word_row

KINDS = ('words_text', 'words_audio', 'sentence_text', 'sentence_audio')


def parse_usage(value):
    # Empty means unknown (older clients / JavaScript disabled), not unaided.
    if not value:
        return None
    data = json.loads(value)
    if not isinstance(data, list) or len(data) > len(KINDS) or any(
            not isinstance(kind, str) or kind not in KINDS for kind in data):
        raise ValueError('hint_usage')
    return list(dict.fromkeys(data))


def material(image, dictionary):
    result = {'sentence': None, 'words': [], 'word_audio_count': 0}
    if not image:
        return result
    entry = image.entry
    ids = set(linked_words(image, dictionary).values_list('pk', flat=True))
    if entry.entry_type == 'sentence' and entry.word and entry.current_text and entry.current_text.status == 'accepted':
        result['sentence'] = word_row(entry, dictionary)
        ids.update(sentence_links(dictionary).filter(sentence_text=entry.current_text).values_list('word_entry_id', flat=True))
    elif entry.entry_type == 'word':
        ids.add(entry.pk)
    words = vocabulary(dictionary).filter(pk__in=ids, current_text__status='accepted').select_related(
        'current_meaning').order_by('word', 'pk')
    for word in words:
        row = word_row(word, dictionary)
        row['meaning'] = word.meaning if word.current_meaning and word.current_meaning.status == 'accepted' else ''
        result['words'].append(row)
        result['word_audio_count'] += int(bool(row['audio']))
    return result
