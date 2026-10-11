"""Community account presentation and separately consented public profiles."""
from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods

from projects.forms import TIMEZONE_CHOICES
from projects.models import Profile
from . import discovery
from .models import CommunityProfile, Dictionary, MembershipRequest
from .public_views import visitor_page
from .views import fail


class ContributorForm(forms.ModelForm):
    revision = forms.IntegerField(min_value=0, widget=forms.HiddenInput)

    class Meta:
        model = CommunityProfile
        fields = ['public_name', 'introduction', 'list_as_contributor']
        labels = {'public_name': 'Public name (a pseudonym is fine)',
                  'introduction': 'Short introduction (optional)',
                  'list_as_contributor': 'List me as a contributor'}
        widgets = {'introduction': forms.Textarea(attrs={'rows': 3})}

    def clean(self):
        data = super().clean()
        if data.get('list_as_contributor') and not data.get('public_name'):
            self.add_error('public_name', 'Choose the name you want people to see.')
        return data


class PreferencesForm(forms.ModelForm):
    timezone = forms.ChoiceField(choices=TIMEZONE_CHOICES)
    openai_api_key = forms.CharField(required=False, label='New OpenAI API key',
        widget=forms.PasswordInput(render_value=False, attrs={'autocomplete': 'new-password'}),
        help_text='Leave blank to keep your saved key. It is never shown on public pages.')
    clear_key = forms.BooleanField(required=False, label='Remove my saved API key')

    class Meta:
        model = Profile
        fields = ['timezone', 'use_personal_openai_key', 'openai_api_key']
        labels = {'use_personal_openai_key': 'Use my own OpenAI API key instead of platform credits'}

    def clean(self):
        data = super().clean()
        key = '' if data.get('clear_key') else data.get('openai_api_key') or self.instance.openai_api_key
        if data.get('clear_key') and data.get('openai_api_key'):
            self.add_error('openai_api_key', 'Choose either a new key or removal of the saved key.')
        if data.get('use_personal_openai_key') and not key:
            self.add_error('use_personal_openai_key', 'Supply a key, or turn off this option to use platform credits.')
        data['openai_api_key'] = key
        return data


@sensitive_post_parameters('openai_api_key')
@never_cache
@login_required(login_url='community_dictionary:login')
@require_http_methods(['GET', 'POST'])
@transaction.atomic
def profile(request):
    # These settings share the C-LARA account; contributor publication is separate.
    common, _ = Profile.objects.get_or_create(user=request.user)
    common = Profile.objects.select_for_update().get(pk=common.pk)
    local, _ = CommunityProfile.objects.get_or_create(user=request.user)
    local = CommunityProfile.objects.select_for_update().get(pk=local.pk)
    contributor = ContributorForm(instance=local, initial={'revision': local.revision})
    preferences = PreferencesForm(instance=common)
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'contributor':
            contributor = ContributorForm(request.POST, instance=local)
            if contributor.is_valid():
                if contributor.cleaned_data['revision'] != local.revision:
                    return fail(request, 'Your public profile changed. Reload Profile before saving.', 409)
                local = contributor.save(commit=False)
                local.revision += 1
                local.save(update_fields=['public_name', 'introduction', 'list_as_contributor', 'revision'])
                messages.success(request, 'Contributor listing saved.')
                return redirect('community_dictionary:profile')
        elif action == 'preferences':
            preferences = PreferencesForm(request.POST, instance=common)
            if preferences.is_valid():
                updated = preferences.save(commit=False)
                # Honour explicit removal even when an API client omitted the
                # password field (ModelForm otherwise keeps its model default).
                updated.openai_api_key = preferences.cleaned_data['openai_api_key']
                updated.save(update_fields=['timezone', 'use_personal_openai_key', 'openai_api_key', 'updated_at'])
                messages.success(request, 'Account preferences saved.')
                return redirect('community_dictionary:profile')
        else:
            return fail(request, 'Choose which profile settings to save.')
    requests_page = Paginator(MembershipRequest.objects.filter(user=request.user).select_related('dictionary'), 20).get_page(request.GET.get('page'))
    rows = []
    for item in requests_page:
        listed = discovery.dictionaries().filter(pk=item.dictionary_id).exists()
        rows.append({'item': item, 'listed': listed, 'name': item.dictionary.name if listed else 'Dictionary no longer listed'})
    return render(request, 'community_dictionary/profile.html', {
        'contributor_form': contributor, 'preferences_form': preferences,
        'is_listed': local.list_as_contributor and bool(local.public_name),
        'has_personal_key': bool(common.openai_api_key),
        'owned': Dictionary.objects.filter(owner=request.user, personal=False, archived=False),
        'request_rows': rows, 'page': requests_page,
        'pending_count': discovery.pending_for(request.user).count()})


@visitor_page
def contributor(request, user_id):
    profile = get_object_or_404(discovery.contributors(), user_id=user_id)
    page = Paginator(discovery.dictionaries().filter(owner_id=user_id), 24).get_page(request.GET.get('page'))
    return render(request, 'community_dictionary/contributor.html', {
        'public_browsing': True, 'public_name': profile.public_name,
        'introduction': profile.introduction,
        'discovery_rows': [discovery.row(d, request.user) for d in page], 'page': page})


@visitor_page
def about(request):
    page = Paginator(discovery.contributors().values('user_id', 'public_name', 'introduction'), 24).get_page(request.GET.get('page'))
    return render(request, 'community_dictionary/about.html', {
        'public_browsing': True, 'contributors': page, 'page': page,
        'contact_email': getattr(settings, 'COMMUNITY_DICTIONARY_CONTACT_EMAIL', 'mannyrayner@c-lara.org')})
