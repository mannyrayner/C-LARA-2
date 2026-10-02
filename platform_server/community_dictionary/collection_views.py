from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from . import membership
from .models import Contribution, Dictionary, Entry, Membership, MembershipDecision
from .permissions import dictionaries_for, get_dictionary
from .services import Conflict, entry_url, submit_once
from .views import context, fail, private_media_response


def owned(user):
    return Contribution.objects.filter(Q(controlled_by=user) | Q(controlled_by__isnull=True, author=user)).exclude(status='removed')


@login_required
def mine(request):
    # Old bookmarks lead to the project-level controls; there are no component
    # selection, personal editing or alternative-destination operations anymore.
    return redirect('community_dictionary:home')


@login_required
@require_POST
def obsolete_action(request, **kwargs):
    return fail(request, 'Individual sharing and withdrawal have been replaced by Withdraw my content and Restore my content on the dictionary page.', 409)


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
            return fail(request, 'Use Withdraw my content on the dictionary page to leave and save your material privately.', 409)
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
