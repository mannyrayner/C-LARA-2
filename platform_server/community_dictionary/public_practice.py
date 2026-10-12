"""Visitor games reuse the public projection, never member draft fallbacks."""
import hashlib
import json

from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from . import public_browsing as public, practice_views
from .public_views import visitor_page, context


def catalogue(dictionary, category=''):
    entries = list(public.entries(dictionary).order_by('pk'))
    media = {e.pk: public.media_for(e, dictionary) for e in entries}
    images = {e.pk: [p for p in media[e.pk] if p.kind == 'image'] for e in entries}
    by_image = {p.pk: p for parts in images.values() for p in parts}
    for image_id, word_id in public.image_links(dictionary).values_list('image_id', 'word_entry_id'):
        if image_id in by_image and word_id in images:
            images[word_id].append(by_image[image_id])
    rows, categories = [], set()
    for entry in entries:
        if entry.entry_type != 'word':
            continue
        if entry.public_category:
            categories.add(entry.public_category)
        if category and entry.public_category != category:
            continue
        pictures = sorted(images[entry.pk], key=lambda p: (p.pk != entry.selected_image_id, p.entry_id != entry.pk, -p.pk))
        picture = next(iter(pictures), None)
        audio = next((p for p in media[entry.pk] if p.kind == 'audio'), None)
        if not entry.public_word and not picture and not audio:
            continue
        def media_url(part):
            return reverse('community_dictionary:public-media', args=[dictionary.pk, part.pk]) if part else ''
        rows.append({'id': entry.pk, 'text': entry.public_word, 'meaning': entry.public_meaning,
            'category': entry.public_category, 'picture_ids': sorted({p.pk for p in pictures}),
            'image': media_url(picture), 'audio': media_url(audio),
            'image_generated': bool(picture and picture.provenance.get('origin') == 'generated'),
            'audio_synthetic': bool(audio and audio.provenance.get('origin') == 'synthetic'),
            'word_url': reverse('community_dictionary:public-word', args=[dictionary.pk, entry.pk]) if entry.public_word else '',
            'entry_url': reverse('community_dictionary:public-entry', args=[dictionary.pk, entry.pk])})
    digest = hashlib.sha256(json.dumps([dictionary.pk, dictionary.public_browsing_revision,
        dictionary.language, rows], ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    return rows, sorted(categories, key=str.casefold), digest


@visitor_page
def home(request, pk):
    dictionary = get_object_or_404(public.dictionaries(), pk=pk)
    rows, categories, _ = catalogue(dictionary, request.GET.get('category', ''))
    return render(request, 'community_dictionary/practice.html', context(request, dictionary,
        **practice_views.page_data(request, dictionary, rows, categories, public=True)))


@visitor_page
def data(request, pk):
    dictionary = get_object_or_404(public.dictionaries(), pk=pk)
    rows, _, revision = catalogue(dictionary, request.GET.get('category', ''))
    return practice_views.game_response(request, rows, revision)
