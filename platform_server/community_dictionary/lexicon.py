"""Shared, dictionary-scoped presentation queries for pictures and vocabulary."""
from django.db.models import Exists, F, OuterRef, Prefetch, Q

from .models import Contribution, Entry, ImageWordLink, SentenceWord, Request


def described_picture_sources(dictionary):
    """Unlabelled source cards already represented by a live sentence card.

    This is a presentation query, never an archive/delete operation. Preserve
    sources with independent text, discussion, recordings, pending work, manual
    tags or another undescribed image. Withdrawal of the description naturally
    makes the source visible again, including captures made before this fix.
    """
    # Copies made by image-only copying, description and language porting can
    # share an ancestor rather than a direct parent. Compare explicit provenance
    # families; never merge merely because filenames or pixels happen to match.
    image_rows = list(Contribution.objects.filter(entry__dictionary=dictionary,
        entry__archived=False, kind='image').values('pk','shared_from_id','entry_id',
        'status','file_path','kind','provenance__role','provenance__source_style_id',
        'entry__entry_type','entry__word','entry__current_text__status'))
    roots = image_family_roots(image_rows)
    described = {roots[row['pk']] for row in image_rows if roots[row['pk']] is not None and
        row['status'] == 'accepted' and row['file_path'] and row['entry__entry_type'] == 'sentence' and
        row['entry__word'] and row['entry__current_text__status'] == 'accepted'}
    covered = [row['pk'] for row in image_rows if roots[row['pk']] in described and row['file_path']]
    images = Contribution.objects.filter(entry_id=OuterRef('pk'), kind='image',
        status__in=['accepted', 'pending'])
    uncovered = images.filter(~Q(pk__in=covered) | Q(status='pending'))
    other = Contribution.objects.filter(entry_id=OuterRef('pk'),
        status__in=['accepted', 'pending']).exclude(kind='image')
    tags = ImageWordLink.objects.filter(image__entry_id=OuterRef('pk'), sentence_text__isnull=True)
    requests = Request.objects.filter(entry_id=OuterRef('pk'), withdrawn=False).exclude(completed_with__status='accepted')
    return Entry.objects.filter(dictionary=dictionary, archived=False, entry_type='word',
        word='', meaning='', category='').annotate(
        has_image=Exists(images), uncovered=Exists(uncovered), other=Exists(other),
        manual_tags=Exists(tags), open_requests=Exists(requests)).filter(
        has_image=True, uncovered=False, other=False, manual_tags=False, open_requests=False)


def image_family_roots(rows):
    """Follow copy provenance in batches; malformed/deep chains never hide cards."""
    parents = {row['pk']:row['shared_from_id'] for row in rows}
    records = {row['pk']:row for row in rows}
    for _ in range(32):
        missing = {pk for pk in parents.values() if pk and pk not in parents}
        if not missing:
            break
        ancestors = list(Contribution.objects.filter(pk__in=missing).values(
            'pk','shared_from_id','kind','provenance__role','provenance__source_style_id'))
        fetched = {row['pk']:row['shared_from_id'] for row in ancestors}
        records.update({row['pk']:row for row in ancestors})
        parents.update(fetched)
        # A missing record cannot be a trustworthy basis for grouping copies.
        for pk in missing-fetched.keys():
            parents[pk] = pk
    roots = {}
    for row in rows:
        pk, seen = row['pk'], set()
        while pk in parents and parents[pk] and pk not in seen:
            parent = parents[pk]
            if parent in records and (records[parent]['kind'] != 'image' or
                    records[parent].get('provenance__role') == 'dictionary_style' or
                    records[pk].get('provenance__source_style_id') == parent):
                # shared_from can mean "generated using this style", not a
                # copy. Capture copies can have new JPEG paths, so filenames
                # cannot determine identity in either direction.
                break
            seen.add(pk); pk = parent
        roots[row['pk']] = pk if pk in records and pk not in seen else None
    return roots


def outdated_tts(contribution, entry, dictionary):
    """Only synthetic recordings have a known spoken text to compare."""
    source = contribution.provenance
    return bool(source.get('sentence_form')) or (contribution.kind == 'audio' and source.get('origin') == 'synthetic'
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
