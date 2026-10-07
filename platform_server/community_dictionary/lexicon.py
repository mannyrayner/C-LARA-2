"""Shared, dictionary-scoped presentation queries for pictures and vocabulary."""
from django.db.models import Exists, F, OuterRef, Prefetch, Q

from .models import Contribution, Entry, ImageWordLink, SentenceWord


def outdated_tts(contribution, entry, dictionary):
    """Only synthetic recordings have a known spoken text to compare."""
    source = contribution.provenance
    return (contribution.kind == 'audio' and source.get('origin') == 'synthetic'
            and (source.get('source_text') != entry.word
                 or source.get('language') != dictionary.language
                 or (source.get('source_meaning_id') is not None and
                     source['source_meaning_id'] != entry.current_meaning_id)))


def vocabulary(dictionary):
    return Entry.objects.filter(dictionary=dictionary, archived=False, entry_type='word').exclude(word='').prefetch_related(
        Prefetch('contributions', queryset=Contribution.objects.filter(kind='audio', status='accepted').exclude(file_path=''), to_attr='lexicon_audio'))


def recordings(entry, dictionary):
    audio = getattr(entry, 'lexicon_audio', None)
    if audio is None:
        audio = entry.contributions.filter(kind='audio', status='accepted').exclude(file_path='')
    return [item for item in audio if not outdated_tts(item, entry, dictionary)]


def word_row(entry, dictionary):
    audio = recordings(entry, dictionary)
    return {'entry': entry, 'audio': audio[0] if audio else None}


def valid_links(dictionary):
    # Scope both ends defensively, including fixtures/imports. Removed or
    # unaccepted media and entries without accepted words never enter the lexicon.
    aligned = SentenceWord.objects.filter(sentence_text_id=OuterRef('sentence_text_id'),
        word_entry_id=OuterRef('word_entry_id'), word_text_id=F('word_entry__current_text_id'))
    return ImageWordLink.objects.annotate(aligned=Exists(aligned)).filter(
        image__entry__dictionary=dictionary, word_entry__dictionary=dictionary,
        image__kind='image', image__status='accepted',
    ).filter(Q(sentence_text__isnull=True) | Q(aligned=True, sentence_text__status='accepted',
        sentence_text_id=F('sentence_text__entry__current_text_id'), sentence_text__entry__dictionary=dictionary)
    ).exclude(image__file_path='').exclude(word_entry__word='')


def linked_words(image, dictionary):
    ids = valid_links(dictionary).filter(image=image).values('word_entry_id')
    return vocabulary(dictionary).filter(pk__in=ids).exclude(pk=image.entry_id).order_by('word', 'pk')


def pictures_for_word(entry, dictionary):
    linked = valid_links(dictionary).filter(word_entry=entry).values('image_id')
    return Contribution.objects.filter(
        entry__dictionary=dictionary, kind='image', status='accepted',
    ).exclude(file_path='').filter(Q(entry=entry) | Q(pk__in=linked)).select_related('entry').distinct()
