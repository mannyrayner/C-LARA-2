"""Sentence context and reviewed cross-links for language versions.

Only frozen, authorised source revisions enter a prompt. Destination links are
reconciled after either endpoint is saved, without an additional provider call.
Call reconciliation under the same dictionary locks as porting.save_item.
"""
from .models import Contribution, ImageWordLink, SentenceWord, VocabularyState
from .capture import sentence_links


def references(entry):
    if entry.entry_type != 'sentence':
        return []
    result = []
    for link in sentence_links(entry.dictionary).filter(sentence_text=entry.current_text).select_related(
            'word_entry__current_meaning').order_by('word_entry_id'):
        meaning = link.word_entry.current_meaning
        result.append({'entry': link.word_entry_id, 'text': link.word_text_id,
                       'meaning': meaning.pk if meaning and meaning.status == 'accepted' else None,
                       'surface': link.surface})
    return result


def reference_ids(refs):
    return sorted({pk for ref in refs for pk in [ref['text'], ref['meaning']] if pk})


def inputs(snapshot, parts):
    return [{'source_entry_id': ref['entry'], 'word': parts[ref['text']].word,
             'meaning': parts[ref['meaning']].meaning if ref['meaning'] else '',
             'surface': ref['surface']} for ref in snapshot.get('sentence_words', [])]


def vocabulary_only(entry):
    # A captured vocabulary entry borrows the sentence's picture. Copying that
    # picture onto every word would produce duplicate cards in Pictures view.
    return (entry.entry_type == 'word' and
            not entry.contributions.filter(kind='image', status='accepted').exists() and
            (entry.current_text and (entry.current_text.provenance.get('origin') == 'picture-description' or
             entry.current_text.provenance.get('sentence_vocabulary')) or
             sentence_links(entry.dictionary).filter(word_entry=entry).exists()))


def provenance(item, text):
    if item.snapshot.get('entry_type') != 'sentence' or item.snapshot.get('sentence_only'):
        return {}
    surfaces = {link['source_entry_id']: link['surface'] for link in item.result.get('word_links', [])}
    return {'port_sentence_links': [{**ref, 'surface': surfaces.get(ref['entry'], '')
                                    if text == item.result.get('word') else ''}
                                   for ref in item.snapshot.get('sentence_words', [])]}


def affected_links(port, source, snap):
    """Limit baseline checks to entries whose derived links can change."""
    source_ids = {source.pk} | {r['entry'] for r in snap.get('sentence_words', [])}
    source_ids.update(sentence_links(source.dictionary).filter(word_entry=source).values_list(
        'sentence_text__entry_id', flat=True))
    destination_ids = set(port.entry_links.filter(source_id__in=source_ids).values_list('destination_id', flat=True))
    destination_ids.update(SentenceWord.objects.filter(sentence_text__entry_id__in=destination_ids).values_list(
        'word_entry_id', flat=True))
    destination_ids.update(Contribution.objects.filter(entry__dictionary=port.destination,
        kind='image',status='accepted',shared_from_id__in=snap['images']).values_list('entry_id',flat=True))
    return port.entry_links.filter(destination_id__in=destination_ids).select_related('destination__dictionary')


def reconcile(port, user, eligible):
    sentences = list(port.entry_links.filter(destination_id__in=eligible, destination__entry_type='sentence').select_related(
        'source__current_text', 'destination__current_text'))
    word_ids = {ref['entry'] for link in sentences if link.destination.current_text
                for ref in link.destination.current_text.provenance.get('port_sentence_links', [])}
    links = {link.source_id: link for link in port.entry_links.filter(source_id__in=word_ids).select_related(
        'source__current_text', 'destination__current_text')}
    for link in sentences:
        sentence = link.destination
        text = sentence.current_text
        if VocabularyState.objects.filter(sentence=sentence).exists():
            continue  # Stage-two vocabulary is authoritative, including after a later edit.
        if (sentence.pk not in eligible or sentence.entry_type != 'sentence' or sentence.archived or
                not text or text.status != 'accepted' or
                text.shared_from_id != link.source.current_text_id):
            continue
        refs = text.provenance.get('port_sentence_links')
        if refs is None:
            continue
        # These rows are derived links. Historical text revisions remain intact.
        SentenceWord.objects.filter(sentence_text=text).delete()
        ImageWordLink.objects.filter(sentence_text=text).delete()
        images = sentence.contributions.filter(kind='image', status='accepted')
        for ref in refs:
            word_link = links.get(ref['entry'])
            if not word_link:
                continue  # Review may save the word after the sentence.
            source, word = word_link.source, word_link.destination
            word_text = word.current_text
            if (source.archived or source.current_text_id != ref['text'] or
                    word.archived or word.entry_type != 'word' or not word_text or
                    word_text.status != 'accepted' or word_text.shared_from_id != ref['text']):
                continue
            SentenceWord.objects.create(sentence_text=text, word_entry=word,
                                        word_text=word_text, surface=ref['surface'])
            for image in images:
                image_link, _ = ImageWordLink.objects.get_or_create(image=image, word_entry=word,
                    defaults={'created_by': user, 'sentence_text': text})
                if (image_link.sentence_text_id and image_link.sentence_text_id != text.pk and
                        image_link.sentence_text.entry_id == sentence.pk):
                    image_link.sentence_text = text
                    image_link.save(update_fields=['sentence_text'])
