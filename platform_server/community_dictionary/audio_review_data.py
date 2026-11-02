"""Request-local material for lexical audio review; never cached across requests.

Use the same live visibility, sentence-link and form checks as individual media
requests. Loading one page does not load the rest of a batch's contributions.
"""
from collections import defaultdict

from django.db.models import Q

from .capture import sentence_links
from .models import Contribution
from .public_browsing import contributions


class ReviewData:
    def __init__(self, dictionary, part_ids=None):
        self.dictionary = dictionary
        selected = Contribution.objects.filter(entry__dictionary=dictionary,
            entry__archived=False, status='accepted', kind__in=['text', 'form'])
        if part_ids is not None:
            selected = selected.filter(pk__in=set(part_ids))
        selected = selected.select_related('entry__dictionary', 'entry__current_text', 'entry__current_meaning')
        self.selected = {p.pk:p for p in selected}
        self.entries = {p.entry_id:p.entry for p in self.selected.values()}
        entry_ids = {p.entry_id for p in self.selected.values()}
        links = sentence_links(dictionary).filter(
            Q(sentence_text__entry_id__in=entry_ids) | Q(word_entry_id__in=entry_ids)
        ).select_related('sentence_text__entry__dictionary', 'sentence_text__entry__current_meaning',
                         'word_entry__dictionary', 'word_entry__current_meaning', 'word_text')
        self.links = {(link.sentence_text_id, link.word_entry_id):link for link in links}
        ids = set(self.selected)
        ids.update(p.entry.current_meaning_id for p in self.selected.values())
        for link in self.links.values():
            ids.update([link.sentence_text_id, link.sentence_text.entry.current_meaning_id,
                        link.word_text_id, link.word_entry.current_meaning_id])
        self.parts = {p.pk:p for p in contributions(dictionary).filter(pk__in=ids - {None}).distinct()}
        self.audio = {p.pk:p for p in contributions(dictionary).filter(entry_id__in=entry_ids,
            kind='audio').exclude(file_path='').distinct().order_by('pk')}
        self.by_entry = defaultdict(list)
        for audio in self.audio.values():
            self.by_entry[audio.entry_id].append(audio)

    def contexts(self, row):
        """Current, visible sentence occurrences, for the review and export."""
        result = []
        for link in self.links.values():
            if ((row['kind'] == 'form' and link.sentence_text.entry_id != row['entry']) or
                    (row['kind'] == 'word' and link.word_text_id != row['id'])):
                continue
            if row['kind'] == 'form':
                basis = self.selected[row['id']].provenance.get('form_basis', {})
                if link.word_entry_id != basis.get('word_entry'):
                    continue
            sentence = self.parts.get(link.sentence_text_id)
            if not sentence or link.word_text_id not in self.parts:
                continue
            meaning = self.parts.get(link.sentence_text.entry.current_meaning_id)
            result.append({'sentence_entry_id':link.sentence_text.entry_id,
                'sentence_text_id':sentence.pk, 'sentence':sentence.word,
                'translation':meaning.meaning if meaning else '', 'surface':link.surface})
        return sorted(result, key=lambda r:(r['sentence_entry_id'], r['sentence_text_id']))
