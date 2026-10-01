from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from . import collections, membership
from .contribution_display import entry_cards
from .models import Contribution, Dictionary, Entry, Membership, MembershipDecision
from .permissions import dictionaries_for, get_dictionary
from .services import Conflict, entry_url, submit_once
from .views import context, fail, private_media_response


def owned(user):
    return Contribution.objects.filter(Q(controlled_by=user) | Q(controlled_by__isnull=True, author=user)).exclude(status='removed')


@login_required
def mine(request):
    parts = owned(request.user)
    mode = 'private' if request.GET.get('view') == 'private' else 'shared'
    parts = parts.filter(entry__dictionary__personal=(mode == 'private'))
    if mode == 'private':
        parts = parts.filter(entry__dictionary__owner=request.user)
    source = request.GET.get('dictionary', '')
    if source.isdigit():
        parts = parts.filter(entry__dictionary_id=source)
    kind = request.GET.get('kind', '')
    if kind in {'image', 'audio', 'text', 'note'}:
        parts = parts.filter(kind=kind)
    else:
        kind = ''
    from django.core.paginator import Paginator
    entries = Entry.objects.filter(pk__in=parts.values('entry_id')).select_related('dictionary')
    page = Paginator(entries.order_by('-created_at', '-pk'), 12).get_page(request.GET.get('page'))
    dictionaries = Dictionary.objects.filter(pk__in=owned(request.user).values('entry__dictionary_id')).order_by('name')
    return render(request, 'community_dictionary/my_contributions.html', context(request,
        page=page, cards=entry_cards(page.object_list, request.user, kind), mode=mode,
        selected_dictionary=source, selected_kind=kind, collection_dictionaries=dictionaries,
        inactive_memberships=Membership.objects.filter(user=request.user, status='inactive').select_related('dictionary')))


def selected(request):
    raw = request.POST.getlist('contributions')
    if not raw or any(not v.isdigit() for v in raw) or len(raw) > 500:
        raise Conflict('Select one or more contributions (up to 500 at a time).')
    ids = set(map(int, raw))
    items = list(owned(request.user).filter(pk__in=ids).select_related('entry__dictionary'))
    if len(items) != len(ids):
        raise Http404
    return items


@login_required
@require_POST
def withdraw(request):
    try:
        if request.POST.get('scope') == 'all':
            source = request.POST.get('dictionary', '')
            if not source.isdigit():
                raise Conflict('Choose a dictionary before withdrawing all or a category of material.')
            query = owned(request.user).filter(entry__dictionary_id=source, entry__dictionary__personal=False)
            kind = request.POST.get('kind', '')
            if kind and kind not in {'image', 'audio', 'text', 'note'}:
                raise Conflict('Choose a valid material category.')
            if kind:
                query = query.filter(kind=kind)
            ids = list(query.values_list('pk', flat=True))
        else:
            ids = [c.pk for c in selected(request)]
        count = collections.withdraw(request.user, ids) if ids else 0
    except Conflict as exc:
        return fail(request, exc, 409)
    messages.success(request, f'{count} contributions retained privately for their contributors. Choose material below to share it again.')
    return redirect(reverse('community_dictionary:mine') + '?view=private')


@login_required
@require_POST
def share(request):
    try:
        items = selected(request)
        if any(not c.entry.dictionary.personal or c.entry.dictionary.owner_id != request.user.pk for c in items):
            raise Conflict('Choose material from your private collection.')
        dictionaries = dictionaries_for(request.user).filter(personal=False, language=items[0].entry.dictionary.language)
        target_id = request.POST.get('target_dictionary', '')
        destination = get_object_or_404(dictionaries, pk=target_id) if target_id.isdigit() else None
        entries = destination.entries.filter(archived=False).order_by('word', 'pk') if destination else Entry.objects.none()
        if request.POST.get('confirm') == 'yes':
            if not destination or not request.POST.get('consent'):
                raise Conflict('Choose a dictionary and confirm permission to share the selected material.')
            target_id = request.POST.get('target_entry', '')
            target = get_object_or_404(entries, pk=target_id) if target_id.isdigit() else None
            def create(paths):
                entry = collections.share(request.user, [c.pk for c in items], destination, target)
                return entry_url(entry)
            url = submit_once(request, destination, 'share-personal', create)
            messages.success(request, 'Shared for review. The original attribution has been kept.')
            return redirect(url)
        return render(request, 'community_dictionary/share.html', context(request,
            items=items, destinations=dictionaries, destination=destination, entries=entries))
    except Conflict as exc:
        return fail(request, exc, 409)


@login_required
def own_media(request, contribution_id):
    item = get_object_or_404(owned(request.user), pk=contribution_id)
    if not item.file_path:
        raise Http404
    if item.entry.dictionary.personal and item.entry.dictionary.owner_id != request.user.pk:
        raise Http404
    return private_media_response(request, item.file_path, item.mime_type, f'my-contribution-{item.pk}')


@login_required
@require_POST
def membership_action(request, pk):
    dictionary = get_dictionary(request.user, pk)
    try:
        action = request.POST.get('action')
        if action == 'leave':
            membership.leave(request.user, dictionary)
            return redirect('community_dictionary:mine')
        if action in {'approve', 'cancel'}:
            decision_id = request.POST.get('decision_id', '')
            decision = get_object_or_404(MembershipDecision, pk=decision_id if decision_id.isdigit() else 0, dictionary=dictionary)
            membership.decide(request.user, dictionary, decision.pk, cancel=action == 'cancel')
        else:
            member_id = request.POST.get('member_id', '')
            member = get_object_or_404(Membership, pk=member_id if member_id.isdigit() else 0, dictionary=dictionary) if action != 'policy' else None
            decision = membership.propose(request.user, dictionary, action, member, request.POST.get('value', ''))
            if decision.status == 'pending':
                messages.success(request, 'Proposed. A different coordinator must approve this change.')
        return redirect('community_dictionary:people', pk=pk)
    except Conflict as exc:
        return fail(request, exc, 409)
