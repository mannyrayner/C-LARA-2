"""Accepted-only projections for visitors. Never use Entry.title's draft fallback.

The member views deliberately include proposals, discussions and provenance.
Keep their permission boundary intact; this module exposes a smaller projection
whose text, links and media all pass the same live contribution checks.
"""
from django.utils.translation import gettext
from django.db.models import CharField, Exists, F, OuterRef, Prefetch, Q, Subquery, TextField, Value
from django.db.models.functions import Coalesce

from .lexicon import valid_links
from .models import Contribution, Dictionary, Entry, Participation, SentenceWord, LanguageCheck


def dictionaries():
    return Dictionary.objects.filter(public_browsing_enabled=True, hidden=False,
                                     personal=False, archived=False)


def contributions(dictionary):
    departed = Participation.objects.filter(dictionary=dictionary, withdrawn=True,
        user_id=Coalesce(OuterRef('controlled_by_id'), OuterRef('author_id')))
    return Contribution.objects.filter(entry__dictionary=dictionary,
        entry__archived=False, status='accepted', withdrawal_holds__isnull=True
    ).annotate(public_departed=Exists(departed)).filter(public_departed=False)


def entries(dictionary):
    parts = contributions(dictionary)
    fields = {}
    for field, pointer in [('word', 'current_text_id'), ('meaning', 'current_meaning_id'),
                           ('category', 'current_category_id')]:
        current = parts.filter(pk=OuterRef(pointer), entry_id=OuterRef('pk'),
                               kind='text', text_field=field)
        output = TextField() if field == 'meaning' else CharField()
        fields['public_' + field] = Coalesce(Subquery(current.values(field)[:1]),
                                           Value(''), output_field=output)
    media = parts.filter(kind__in=['image', 'audio']).exclude(file_path='')
    # Synthetic clips need their exact accepted source wording. Do not publish
    # obsolete speech by guessing a direct media URL after an edit/withdrawal.
    audio = parts.filter(entry_id=OuterRef('pk'), kind='audio').exclude(file_path='')
    return Entry.objects.filter(dictionary=dictionary, archived=False).annotate(
        **fields,
        public_automatic=Exists(parts.filter(entry_id=OuterRef('pk'),kind='text',
            provenance__automatic_publication=True).filter(
                Q(pk=OuterRef('current_text_id'),text_field='word') |
                Q(pk=OuterRef('current_meaning_id'),text_field='meaning'))),
        public_checked=Exists(LanguageCheck.objects.filter(entry_id=OuterRef('pk'),
            text_id=OuterRef('current_text_id'),meaning_id=OuterRef('current_meaning_id'))),
        public_image=Exists(media.filter(entry_id=OuterRef('pk'), kind='image')),
        public_audio=Exists(audio),
    ).prefetch_related(Prefetch('contributions', queryset=media, to_attr='public_media'))


def words(dictionary):
    return entries(dictionary).filter(entry_type='word').exclude(public_word='')


def sentences(dictionary):
    return entries(dictionary).filter(entry_type='sentence').exclude(public_word='')


def audio_is_current(audio, entry, dictionary):
    source = audio.provenance
    if source.get('origin') != 'synthetic':
        return True
    if not entry.public_word or source.get('source_text') != entry.public_word:
        return False
    if source.get('language') != dictionary.language:
        return False
    meaning_id = source.get('source_meaning_id')
    if meaning_id is not None:
        return contributions(dictionary).filter(pk=meaning_id, entry=entry,
            kind='text', text_field='meaning', pk__in=[entry.current_meaning_id]).exists()
    return True


def media_for(entry, dictionary):
    return [c for c in entry.public_media if c.kind == 'image' or
            (c.kind == 'audio' and audio_is_current(c, entry, dictionary))]


def row(entry, dictionary):
    media = media_for(entry, dictionary)
    images = [c for c in media if c.kind == 'image']
    image = next((c for c in images if c.pk == entry.selected_image_id), images[0] if images else None)
    recordings = [c for c in media if c.kind == 'audio']
    # Only these explicit fields reach public templates. No author, prompt,
    # file path, private caption, pending text, historical version or note.
    return {'id': entry.pk, 'word': entry.public_word, 'meaning': entry.public_meaning,
            'automatic_unreviewed':entry.public_automatic and not entry.public_checked,
            'category': entry.public_category, 'kind': entry.entry_type,
            'title': entry.public_word or (gettext('Picture') if image else gettext('Recording')),
            'image': media_row(image) if image else None,
            'audio': media_row(recordings[0]) if recordings else None,
            'images': [media_row(c) for c in images],
            'recordings': [media_row(c) for c in recordings]}


def media_row(part):
    return {'id': part.pk, 'entry_id': part.entry_id,
            'generated': part.kind == 'image' and part.provenance.get('origin') == 'generated',
            'synthetic': part.kind == 'audio' and part.provenance.get('origin') == 'synthetic'}


def image_links(dictionary):
    parts = contributions(dictionary)
    return valid_links(dictionary).filter(image__in=parts.filter(kind='image'),
        word_entry__in=words(dictionary)).filter(
            Q(sentence_text__isnull=True) | Q(sentence_text__in=parts.filter(kind='text', text_field='word')))


def sentence_links(dictionary):
    parts = contributions(dictionary).filter(kind='text', text_field='word')
    return SentenceWord.objects.filter(sentence_text__in=parts, word_text__in=parts,
        sentence_text_id=F('sentence_text__entry__current_text_id'),
        word_text_id=F('word_entry__current_text_id'),
        word_text__entry_id=F('word_entry_id'),
        sentence_text__entry__entry_type='sentence',
        word_entry__in=words(dictionary))


def words_for(entry, image, dictionary):
    linked = sentence_links(dictionary).filter(sentence_text_id=entry.current_text_id)
    surfaces = dict(linked.values_list('word_entry_id', 'surface'))
    ids = set(surfaces)
    if image:
        ids.update(image_links(dictionary).filter(image_id=image['id']).values_list('word_entry_id', flat=True))
    result = []
    for word in words(dictionary).filter(pk__in=ids).exclude(pk=entry.pk).order_by('public_word', 'pk'):
        result.append({**row(word, dictionary), 'surface': surfaces.get(word.pk, '')})
    return result


def pictures_for(entry, dictionary):
    linked = image_links(dictionary).filter(word_entry=entry).values('image_id')
    pictures = contributions(dictionary).filter(kind='image').exclude(file_path='').filter(
        Q(entry=entry) | Q(pk__in=linked)).order_by('pk')
    return [media_row(part) for part in pictures]
