"""Read-only hints from current accepted dictionary material. No AI calls."""
import json
from .capture import sentence_links
from .lexicon import linked_words, vocabulary, word_row
from . import sentence_forms

VERSION = 'sentence-hints-1'
KINDS = ('words_text', 'words_audio', 'sentence_text', 'sentence_audio', 'lemmas_text')


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
    result = {'sentence': None, 'words': [], 'word_audio_count': 0, 'has_dictionary_forms': False}
    if not image:
        return result
    entry = image.entry
    links = {}
    ids = set(linked_words(image, dictionary).values_list('pk', flat=True))
    if entry.entry_type == 'sentence' and entry.word and entry.current_text and entry.current_text.status == 'accepted':
        result['sentence'] = word_row(entry, dictionary)
        links = {link.word_entry_id: link for link in sentence_links(dictionary).filter(
            sentence_text=entry.current_text).select_related('word_text', 'sentence_text__entry__dictionary')}
        ids.update(links)
    elif entry.entry_type == 'word':
        ids.add(entry.pk)
    words = vocabulary(dictionary).filter(pk__in=ids, current_text__status='accepted').select_related(
        'current_meaning').order_by('word', 'pk')
    for word in words:
        row = word_row(word, dictionary)
        row['dictionary_meaning'] = word.meaning if word.current_meaning and word.current_meaning.status == 'accepted' else ''
        row['meaning'] = row['dictionary_meaning']
        link = links.get(word.pk)
        row['text'] = link.surface if link else word.word
        row['is_inflected'] = bool(link and sentence_forms.different(link.surface, word.word))
        if row['is_inflected']:
            form = sentence_forms.presentation(link)
            row['meaning'] = form.get('meaning', '')
            clip = form.get('audio')
            # A separated expression's presentation can offer the whole
            # sentence. That must stay behind the sentence-hint action.
            row['audio'] = clip if (clip and not form.get('in_sentence') and
                sentence_forms.audio_current(clip)) else None
            result['has_dictionary_forms'] = True
        result['words'].append(row)
        result['word_audio_count'] += int(bool(row['audio']))
    return result
