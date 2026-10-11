"""Owner-controlled discovery and account-based, private membership requests."""
from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST, require_http_methods

from . import discovery
from .models import Dictionary, Membership, MembershipRequest
from .permissions import require_owner
from .public_views import visitor_page
from .services import event
from .views import fail

login = login_required(login_url='community_dictionary:login')


class DiscoveryForm(forms.Form):
    revision = forms.IntegerField(min_value=0, widget=forms.HiddenInput)


class JoinForm(forms.Form):
    message = forms.CharField(required=False, max_length=1000, label='Message to the owner (optional)',
        widget=forms.Textarea(attrs={'rows': 3}), help_text='Your username and this message are shown only to the owner.')


@visitor_page
def detail(request, pk):
    dictionary = get_object_or_404(discovery.dictionaries(), pk=pk)
    return render(request, 'community_dictionary/discovery_detail.html', {
        'public_browsing': True, 'row': discovery.row(dictionary, request.user), 'form': JoinForm()})


@never_cache
@login
@require_POST
@transaction.atomic
def change(request, pk):
    dictionary = get_object_or_404(Dictionary.objects.select_for_update(), pk=pk)
    require_owner(request.user, dictionary)
    form = DiscoveryForm(request.POST)
    action = request.POST.get('action')
    if not form.is_valid() or action not in {'enable', 'disable'}:
        return fail(request, 'Reload Settings and choose a discovery setting.')
    enabled = action == 'enable'
    revision = form.cleaned_data['revision']
    if enabled and dictionary.hidden:
        return fail(request, 'Make the dictionary visible before listing it.', 409)
    if dictionary.discoverable == enabled and revision == dictionary.discovery_revision - 1:
        return redirect('community_dictionary:settings', pk=pk)
    if revision != dictionary.discovery_revision:
        return fail(request, 'The discovery setting changed. Reload Settings.', 409)
    if dictionary.discoverable != enabled:
        dictionary.discoverable = enabled
        dictionary.discovery_revision += 1
        dictionary.save(update_fields=['discoverable', 'discovery_revision'])
        event(dictionary, request.user, 'dictionary_discovery', detail='Enabled' if enabled else 'Disabled')
    messages.success(request, 'Dictionary is discoverable.' if enabled else 'Dictionary is no longer listed.')
    return redirect('community_dictionary:settings', pk=pk)


@never_cache
@login
@require_POST
@transaction.atomic
def ask(request, pk):
    # User lock serialises this account's pending-request limit across dictionaries.
    # NO KEY UPDATE leaves foreign-key checks free to run in owner decisions.
    get_user_model().objects.select_for_update(no_key=True).get(pk=request.user.pk)
    dictionary = get_object_or_404(discovery.dictionaries().select_for_update(), pk=pk)
    state = discovery.state(request.user, dictionary)
    if state == 'pending':
        return redirect('community_dictionary:discover-dictionary', pk=pk)
    if state != 'available':
        return fail(request, 'Use your existing invitation or membership controls. A new request cannot change an existing membership or restore withdrawn content.', 409)
    form = JoinForm(request.POST)
    if not form.is_valid():
        return render(request, 'community_dictionary/discovery_detail.html', {
            'public_browsing': True, 'row': discovery.row(dictionary, request.user), 'form': form}, status=400)
    if MembershipRequest.objects.filter(user=request.user, status='pending').count() >= 20:
        return fail(request, 'You already have 20 pending requests. Cancel an unwanted request in Profile first.', 429)
    item, _ = MembershipRequest.objects.get_or_create(dictionary=dictionary, user=request.user)
    item.message = form.cleaned_data['message']
    item.status = 'pending'
    item.revision += 1
    item.updated_at = timezone.now()
    item.save(update_fields=['message', 'status', 'revision', 'updated_at'])
    event(dictionary, request.user, 'membership_requested', detail=f'Request {item.pk}')
    messages.success(request, 'Request saved for the owner. You can see its status in Profile. No email was sent.')
    return redirect('community_dictionary:discover-dictionary', pk=pk)


@never_cache
@login
@require_http_methods(['GET'])
def pending(request):
    page = Paginator(discovery.pending_for(request.user).select_related('dictionary', 'user'), 20).get_page(request.GET.get('page'))
    return render(request, 'community_dictionary/membership_requests.html', {'page': page})


@never_cache
@login
@require_POST
@transaction.atomic
def decide(request, pk, request_id):
    dictionary = get_object_or_404(Dictionary.objects.select_for_update(), pk=pk)
    require_owner(request.user, dictionary)
    item = get_object_or_404(MembershipRequest.objects.select_for_update(of=('self',)).select_related('user'), pk=request_id, dictionary=dictionary)
    action = request.POST.get('action')
    if action not in {'approve', 'decline'}:
        return fail(request, 'Choose Approve or Decline.')
    desired = 'approved' if action == 'approve' else 'declined'
    if item.status == desired:  # Harmless retry after a completed decision.
        return redirect('community_dictionary:membership-requests')
    if item.status != 'pending' or str(item.revision) != request.POST.get('revision'):
        return fail(request, 'This request changed. Reload the pending requests list.', 409)
    if action == 'approve':
        if not item.user.is_active or discovery.state(item.user, dictionary) in {'withdrawn', 'inactive'}:
            return fail(request, 'This account is inactive or its content is withdrawn. Use the existing membership and contribution controls; approving a request cannot bypass them.', 409)
        member = Membership.objects.filter(dictionary=dictionary, user=item.user).first()
        if not member and dictionary.owner_id != item.user_id:
            Membership.objects.create(dictionary=dictionary, user=item.user, role='member', accepted=True, status='active')
            dictionary.membership_revision += 1
            dictionary.save(update_fields=['membership_revision'])
        # A separately issued invitation retains its role and acceptance step.
        # Never reactivate, promote, downgrade or restore an existing member.
    item.status = desired
    item.revision += 1
    item.updated_at = timezone.now()
    item.save(update_fields=['status', 'revision', 'updated_at'])
    event(dictionary, request.user, 'membership_request_' + desired, detail=f'Request {item.pk}')
    messages.success(request, 'Membership request ' + desired + '.')
    return redirect('community_dictionary:membership-requests')


@never_cache
@login
@require_POST
@transaction.atomic
def cancel(request, request_id):
    # Match the dictionary -> request lock order used by owner decisions.
    item = get_object_or_404(MembershipRequest, pk=request_id, user=request.user)
    Dictionary.objects.select_for_update().get(pk=item.dictionary_id)
    item = MembershipRequest.objects.select_for_update().get(pk=item.pk)
    if item.status == 'cancelled':
        return redirect('community_dictionary:profile')
    if item.status != 'pending' or str(item.revision) != request.POST.get('revision'):
        return fail(request, 'This request changed. Reload Profile.', 409)
    item.status, item.updated_at = 'cancelled', timezone.now()
    item.revision += 1
    item.save(update_fields=['status', 'revision', 'updated_at'])
    event(item.dictionary, request.user, 'membership_request_cancelled', detail=f'Request {item.pk}')
    return redirect('community_dictionary:profile')
