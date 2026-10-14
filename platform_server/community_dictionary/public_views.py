"""Read-only, no-login routes; member endpoints retain their existing checks."""
from functools import wraps

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST, require_safe

from . import public_browsing as public
from .models import Dictionary
from .permissions import dictionaries_for, get_dictionary, require_owner
from .services import event
from .views import fail, private_media_response


class AccessForm(forms.Form):
    revision = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    permission = forms.BooleanField(required=False,
        label='I have permission from the contributors to make the accepted content '
              'in this dictionary available to anyone, including future accepted content.')


def visitor_page(view):
    @never_cache
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        try:
            response = require_safe(view)(request, *args, **kwargs)
        except Http404:
            response = render(request, 'community_dictionary/public_unavailable.html',
                              {'public_browsing': True}, status=404)
        response['X-Robots-Tag'] = 'noindex, nofollow, noarchive'
        response['Referrer-Policy'] = 'same-origin'
        return response
    return wrapped


def context(request, dictionary=None, **extra):
    can_join_view = bool(dictionary and request.user.is_authenticated and
                        dictionaries_for(request.user).filter(pk=dictionary.pk).exists())
    return {'public_browsing': True, 'dictionary': dictionary,
            'member_view': can_join_view, 'evaluation_available': bool(dictionary and dictionary.evaluation_sets.filter(allow_visitors=True, closed_at__isnull=True).exists()), **extra}


@visitor_page
def home(request):
    from . import discovery
    query = request.GET.get('q', '').strip()[:200]
    dictionaries = discovery.dictionaries()
    if query:
        dictionaries = dictionaries.filter(Q(name__icontains=query) | Q(language__icontains=query))
    page = Paginator(dictionaries, 24).get_page(request.GET.get('page'))
    rows = [discovery.row(d, request.user) for d in page]
    return render(request, 'community_dictionary/public_home.html',
                  context(request, discovery_rows=rows, page=page, query=query))


@visitor_page
def dictionary(request, pk):
    item = get_object_or_404(public.dictionaries(), pk=pk)
    mode = request.GET.get('view') if request.GET.get('view') in {'words', 'sentences'} else 'pictures'
    query = request.GET.get('q', '').strip()[:200]
    category = request.GET.get('category', '')[:80]
    candidates = public.entries(item)
    if mode == 'words':
        candidates = public.words(item).order_by('public_word', 'pk')
    elif mode == 'sentences':
        candidates = public.sentences(item)
    else:
        from .lexicon import described_picture_sources
        candidates = candidates.filter(Q(public_image=True) | Q(public_audio=True, public_word=''))
        candidates = candidates.exclude(pk__in=described_picture_sources(item).values('pk'))
    categories = candidates.exclude(public_category='').order_by('public_category').values_list('public_category', flat=True).distinct()
    if query:
        linked_words = public.words(item).filter(Q(public_word__icontains=query) | Q(public_meaning__icontains=query))
        linked_pictures = public.image_links(item).filter(word_entry__in=linked_words).values('image__entry_id')
        candidates = candidates.filter(Q(public_word__icontains=query) | Q(public_meaning__icontains=query) | Q(pk__in=linked_pictures))
    if category:
        candidates = candidates.filter(public_category=category)
    page = Paginator(candidates, 24).get_page(request.GET.get('page'))
    rows = [public.row(entry, item) for entry in page]
    # Empty obsolete-audio-only cards have no public learning content.
    rows = [row for row in rows if row['word'] or row['image'] or row['audio']]
    return render(request, 'community_dictionary/public_dictionary.html', context(
        request, item, rows=rows, mode=mode, page=page, query=query, category=category, categories=categories))


@visitor_page
def entry(request, pk, entry_id, word_only=False):
    item = get_object_or_404(public.dictionaries(), pk=pk)
    record = get_object_or_404(public.words(item) if word_only else public.entries(item), pk=entry_id)
    row = public.row(record, item)
    if not row['word'] and not row['image'] and not row['audio']:
        raise Http404
    if 'picture' in request.GET:
        picture = next((p for p in row['images'] if str(p['id']) == request.GET['picture']), None)
        if picture is None:
            raise Http404
        row['image'] = picture
    words = public.words_for(record, row['image'], item)
    related = public.sentences(item).filter(pk__in=public.sentence_links(item).filter(
        word_entry=record).values('sentence_text__entry_id'))
    # Picture pages also lead to descriptions of that accepted picture.
    if row['image']:
        related = public.sentences(item).filter(Q(pk__in=related.values('pk')) |
            Q(selected_image__shared_from_id=row['image']['id'],
              selected_image__in=public.contributions(item).filter(kind='image'))).exclude(pk=record.pk)
    return render(request, 'community_dictionary/public_entry.html', context(request, item,
        row=row, word_page=word_only, words=words,
        related_sentences=[public.row(e, item) for e in related],
        pictures=public.pictures_for(record, item) if word_only else row['images']))


@visitor_page
def media(request, pk, contribution_id):
    item = get_object_or_404(public.dictionaries(), pk=pk)
    part = get_object_or_404(public.contributions(item).filter(kind__in=['image', 'audio']).exclude(file_path=''), pk=contribution_id)
    entry = get_object_or_404(public.entries(item), pk=part.entry_id)
    if part.kind == 'audio' and not public.audio_is_current(part, entry, item):
        raise Http404
    return private_media_response(request, part.file_path, part.mime_type, f'contribution-{part.pk}')


@login_required
@require_POST
@transaction.atomic
def change_access(request, pk):
    get_object_or_404(Dictionary.objects.select_for_update(), pk=pk)
    item = get_dictionary(request.user, pk)
    require_owner(request.user, item)
    form = AccessForm(request.POST)
    action = request.POST.get('action')
    if action not in {'enable', 'disable'} or not form.is_valid():
        return fail(request, 'Reload Settings and choose whether to allow public browsing.')
    enabled = action == 'enable'
    revision = form.cleaned_data['revision']
    if enabled and (not form.cleaned_data['permission'] or item.hidden):
        return fail(request, 'Make this dictionary visible and confirm permission from its contributors before enabling public browsing.')
    if item.public_browsing_enabled == enabled and revision == item.public_browsing_revision - 1:
        return redirect('community_dictionary:settings', pk=pk)
    if revision != item.public_browsing_revision:
        return fail(request, 'Public browsing changed. Reload Settings before trying again.', 409)
    if item.public_browsing_enabled != enabled:
        item.public_browsing_enabled = enabled
        item.public_browsing_revision += 1
        item.save(update_fields=['public_browsing_enabled', 'public_browsing_revision'])
        event(item, request.user, 'public_browsing', detail='Enabled; contributor permission confirmed' if enabled else 'Disabled')
    messages.success(request, 'Public browsing enabled.' if enabled else 'Public browsing disabled.')
    return redirect('community_dictionary:settings', pk=pk)
