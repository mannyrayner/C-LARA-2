"""Shared, dictionary-scoped presentation queries for pictures and vocabulary."""
from django.db.models import Prefetch, Q

from .models import Contribution, Entry, ImageWordLink


def outdated_tts(contribution, entry, dictionary):
    """Only synthetic recordings have a known spoken text to compare."""
    source = contribution.provenance
    return (contribution.kind == 'audio' and source.get('origin') == 'synthetic'
            and (source.get('source_text') != entry.word
                 or source.get('language') != dictionary.language))


def vocabulary(dictionary):
    return Entry.objects.filter(dictionary=dictionary, archived=False).exclude(word='').prefetch_related(
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
    return ImageWordLink.objects.filter(
        image__entry__dictionary=dictionary, word_entry__dictionary=dictionary,
        image__kind='image', image__status='accepted',
    ).exclude(image__file_path='').exclude(word_entry__word='')


def linked_words(image, dictionary):
    ids = valid_links(dictionary).filter(image=image).values('word_entry_id')
    return vocabulary(dictionary).filter(pk__in=ids).exclude(pk=image.entry_id).order_by('word', 'pk')


def pictures_for_word(entry, dictionary):
    linked = valid_links(dictionary).filter(word_entry=entry).values('image_id')
    return Contribution.objects.filter(
        entry__dictionary=dictionary, kind='image', status='accepted',
    ).exclude(file_path='').filter(Q(entry=entry) | Q(pk__in=linked)).select_related('entry').distinct()
