"""Request-local bulk reads for workflow guidance, never a cross-request cache.

Approval, jobs and saves still use their normal fresh database checks. A read
scope exists only while building suggestions; it is discarded before a quote
can create or mutate anything.
"""
from collections import defaultdict
from contextlib import contextmanager
from contextvars import ContextVar

from .models import Contribution, Entry, VocabularyState

_scope = ContextVar('community_workflow_reads', default=None)


@contextmanager
def reading():
    if _scope.get() is not None:
        yield
        return
    token = _scope.set({'dictionaries': {}, 'memo': {}})
    try:
        yield
    finally:
        _scope.reset(token)


def memo(key, compute):
    scope = _scope.get()
    if scope is None:
        return compute()
    if key not in scope['memo']:
        scope['memo'][key] = compute()
    return scope['memo'][key]


def data(dictionary):
    scope = _scope.get()
    if scope is None:
        return None
    if dictionary.pk not in scope['dictionaries']:
        scope['dictionaries'][dictionary.pk] = DictionaryData(dictionary)
    return scope['dictionaries'][dictionary.pk]


class DictionaryData:
    def __init__(self, dictionary):
        from .capture import sentence_links
        from .lexicon import valid_links
        self.dictionary = dictionary
        self.entries = {e.pk: e for e in Entry.objects.filter(dictionary=dictionary).select_related(
            'current_text', 'current_meaning', 'current_category')}
        for entry in self.entries.values():
            entry.dictionary = dictionary
        self.parts = {}
        self.by_entry = defaultdict(list)
        for part in Contribution.objects.filter(entry__dictionary=dictionary).order_by('pk'):
            part.entry = self.entries[part.entry_id]
            self.parts[part.pk] = part
            self.by_entry[part.entry_id].append(part)
        self.pictures = defaultdict(dict)
        for part in self.parts.values():
            if part.kind == 'image' and part.status == 'accepted' and part.file_path and not part.entry.archived:
                self.pictures[part.entry_id][part.pk] = part
        for image_id, word_id in valid_links(dictionary).filter(image__entry__archived=False).values_list('image_id', 'word_entry_id'):
            self.pictures[word_id][image_id] = self.parts[image_id]
        self.references = defaultdict(list)
        self.word_pairs = defaultdict(set)
        self.word_link_entries = set()
        for link in sentence_links(dictionary).order_by('word_entry_id'):
            word = self.entries[link.word_entry_id]
            meaning = word.current_meaning
            self.references[self.parts[link.sentence_text_id].entry_id].append({
                'entry': word.pk, 'text': link.word_text_id,
                'meaning': meaning.pk if meaning and meaning.status == 'accepted' else None,
                'surface': link.surface})
            self.word_link_entries.add(word.pk)
        # Match current_state's historical semantics, independently of the
        # stricter capture link projection used by translation snapshots.
        from django.db.models import F
        from .models import SentenceWord
        for text_id, word_id, word_text in SentenceWord.objects.filter(
                sentence_text__entry__dictionary=dictionary, word_text__status='accepted',
                word_entry__archived=False, word_entry__current_text_id=F('word_text_id')
                ).values_list('sentence_text_id', 'word_entry_id', 'word_text_id'):
            self.word_pairs[text_id].add((word_id, word_text))
        self.states = {s.sentence_id: s for s in VocabularyState.objects.filter(sentence__dictionary=dictionary)}

    def entry(self, entry):
        return self.entries[entry.pk]

    def media(self, entry, kind):
        return [p for p in self.by_entry[entry.pk] if p.kind == kind and p.status == 'accepted' and p.file_path]
