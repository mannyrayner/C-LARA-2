"""Entry context for personal contribution controls, without widening access."""
from collections import defaultdict

from django.db.models import Q
from django.urls import reverse

from .lexicon import linked_words, word_row
from .models import Contribution, Entry
from .permissions import dictionaries_for
from .text import FIELDS


def entry_cards(entries, user, kind=''):
    entries = list(entries)
    accessible = set(dictionaries_for(user).values_list('pk', flat=True))
    # A private collection can show the live source alongside retained material,
    # but only while the reader can still open that shared entry. Never snapshot
    # someone else's content into a personal collection.
    sources = {e.pk: e for e in Entry.objects.filter(
        pk__in=[e.collection_source_id for e in entries if e.dictionary.personal],
        dictionary_id__in=accessible, dictionary__personal=False, archived=False,
    ).select_related('dictionary')}
    full_context = {e.pk for e in entries if e.dictionary_id in accessible and not e.archived} | sources.keys()
    own = Q(controlled_by=user) | Q(controlled_by__isnull=True, author=user)
    visible = Contribution.objects.filter(
        entry_id__in={e.pk for e in entries} | sources.keys(),
    ).exclude(status='removed').filter(
        own | Q(entry_id__in=full_context, status__in=['accepted', 'pending'])
    ).select_related('author', 'controlled_by').order_by('-created_at', '-pk')
    grouped = defaultdict(list)
    for part in visible:
        grouped[part.entry_id].append(part)

    def presentation(entry, selectable_entry_id):
        parts = grouped[entry.pk]
        current = [p for p in parts if p.status in {'accepted', 'pending'}]
        by_id = {p.pk: p for p in current}
        fields = []
        for field, (pointer, _) in FIELDS.items():
            part = by_id.get(getattr(entry, pointer + '_id'))
            if part is None:
                part = next((p for p in current if p.text_field == field and p.status == 'pending'), None)
            if part:
                fields.append(part)
        images = [p for p in current if p.kind == 'image']
        images.sort(key=lambda p: p.pk != entry.selected_image_id)
        audio = []
        for part in current:
            if part.kind != 'audio':
                continue
            # Use only visible wording, never cached text belonging to someone
            # an inactive member may no longer read.
            word = next((p.word for p in fields if p.text_field == 'word'), '')
            source = part.provenance
            part.earlier_audio = source.get('origin') == 'synthetic' and (
                source.get('source_text') != word or source.get('language') != entry.dictionary.language)
            if not part.earlier_audio:
                audio.append(part)
        notes = [p for p in current if p.kind == 'note']
        shown = {p.pk for p in fields + images + audio + notes}
        # Every owned revision stays reachable, including rejected proposals and
        # recordings for earlier wording. Reference histories are not copied.
        history = [p for p in parts if p.pk not in shown and
                   (p.controlled_by_id or p.author_id) == user.pk and entry.pk == selectable_entry_id]

        def component(part):
            yours = (part.controlled_by_id or part.author_id) == user.pk
            in_collection = entry.pk == selectable_entry_id
            selectable = yours and in_collection and (not kind or part.kind == kind)
            media_url = ''
            if part.file_path:
                media_url = reverse('community_dictionary:own-media', args=[part.pk]) if yours else reverse(
                    'community_dictionary:media', args=[entry.dictionary_id, part.pk])
            return {'part': part, 'yours': yours, 'selectable': selectable,
                    'filtered': yours and in_collection and not selectable,
                    'reference': not yours or not in_collection, 'media_url': media_url}

        title_part = next((p for p in fields if p.text_field == 'word' and p.word), None)
        return {
            'entry': entry, 'title': title_part.word if title_part else f'Entry {entry.pk}',
            'title_reference': bool(title_part and ((title_part.controlled_by_id or title_part.author_id) != user.pk
                                                   or entry.pk != selectable_entry_id)),
            'fields': [component(p) for p in fields],
            'image': component(images[0]) if images else None,
            'other_images': [component(p) for p in images[1:]],
            'audio': [component(p) for p in audio], 'notes': [component(p) for p in notes],
            'history': [component(p) for p in history],
        }

    cards = []
    for entry in entries:
        card = presentation(entry, entry.pk)
        card['can_open'] = entry.pk in full_context
        card['restricted'] = entry.pk not in full_context
        source = sources.get(entry.collection_source_id)
        if source:
            reference = presentation(source, entry.pk)
            card['source_entry'] = source
            fields = {c['part'].text_field for c in card['fields']}
            private_word = next((c['part'].word for c in card['fields'] if c['part'].text_field == 'word'), None)
            shared_word = next((c['part'].word for c in reference['fields'] if c['part'].text_field == 'word'), '')
            card['source_fields'] = [c for c in reference['fields'] if c['part'].text_field in fields]
            card['fields'] += [c for c in reference['fields'] if c['part'].text_field not in fields]
            card['fields'].sort(key=lambda c: list(FIELDS).index(c['part'].text_field))
            if not any(c['part'].text_field == 'word' for c in card['fields'] if not c['reference']):
                card['title'], card['title_reference'] = reference['title'], True
            if reference['image']:
                if card['image']:
                    card['other_images'].append(reference['image'])
                else:
                    card['image'] = reference['image']
            card['other_images'] += reference['other_images']
            if private_word is not None and private_word != shared_word:
                card['source_audio'] = reference['audio']
            else:
                card['audio'] += reference['audio']
            card['notes'] += reference['notes']
        image = card['image']['part'] if card['image'] else None
        if image and image.entry_id in full_context and image.status == 'accepted':
            image_dictionary = source.dictionary if source and image.entry_id == source.pk else entry.dictionary
            card['linked_dictionary'] = image_dictionary
            card['linked_words'] = [word_row(e, image_dictionary) for e in linked_words(image, image_dictionary)]
        cards.append(card)
    return cards
