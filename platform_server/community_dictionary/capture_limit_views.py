"""Owner changes require an explicit, signed cost preview and confirmation."""
from decimal import Decimal

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from projects.billing import credits_enabled
from projects.models import CreditAccount
from . import capture_limits
from .models import Dictionary
from .permissions import get_dictionary, require_owner
from .services import Conflict, event
from .views import context, fail


class AllowanceForm(forms.Form):
    daily_limit = forms.IntegerField(min_value=1, label='Picture descriptions per 24 hours')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        maximum = capture_limits.ceiling()
        self.fields['daily_limit'].max_value = maximum
        from django.core.validators import MaxValueValidator
        self.fields['daily_limit'].validators.append(MaxValueValidator(maximum))
        self.fields['daily_limit'].widget.attrs.update(max=maximum, inputmode='numeric')
        self.fields['daily_limit'].help_text = f'Shared by all members of this dictionary. Choose 1–{maximum}.'


class ConfirmForm(forms.Form):
    token = forms.CharField(max_length=6000, widget=forms.HiddenInput)
    approve = forms.BooleanField(label='I understand the estimated daily cost and confirm this allowance.')


@login_required
@require_http_methods(['GET', 'POST'])
@transaction.atomic
def change(request, pk):
    if request.method == 'POST':
        get_object_or_404(Dictionary.objects.select_for_update(), pk=pk)
    dictionary = get_dictionary(request.user, pk)
    require_owner(request.user, dictionary)
    initial = {'daily_limit': dictionary.capture_daily_limit}
    form = AllowanceForm(initial=initial)
    confirmation = None
    estimate = None
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'confirm':
            confirmation = ConfirmForm(request.POST)
            if not confirmation.is_valid():
                return fail(request, 'Confirm your approval using the cost preview. No allowance was changed.', 400)
            try:
                limit = capture_limits.approved_limit(confirmation.cleaned_data['token'], dictionary, request.user)
            except Conflict as exc:
                return fail(request, exc, 409)
            if limit != dictionary.capture_daily_limit:
                old = dictionary.capture_daily_limit
                dictionary.capture_daily_limit = limit
                dictionary.save(update_fields=['capture_daily_limit'])
                event(dictionary, request.user, 'capture_allowance_changed',
                      detail=f'Picture-description allowance {old} → {limit} per rolling 24h; estimate approved')
            messages.success(request, f'Picture-description allowance saved: {limit} per 24 hours.')
            return redirect('community_dictionary:settings', pk=pk)
        if action != 'preview':
            return fail(request, 'Choose Preview cost before confirming an allowance.', 400)
        form = AllowanceForm(request.POST)
        if form.is_valid():
            try:
                estimate = capture_limits.preview(dictionary, request.user, form.cleaned_data['daily_limit'])
            except Conflict as exc:
                form.add_error(None, str(exc))
            else:
                confirmation = ConfirmForm(initial={'token': estimate['token']})
    # This is the owner's balance only: members retain their own payment settings.
    profile = getattr(request.user, 'profile', None)
    personal = bool(profile and profile.use_personal_openai_key)
    balance = None
    if credits_enabled() and not personal:
        balance = CreditAccount.objects.filter(user=request.user).values_list('balance_usd', flat=True).first() or Decimal('0')
    return render(request, 'community_dictionary/capture_limit.html', context(request, dictionary,
        form=form, confirmation=confirmation, estimate=estimate,
        counts=capture_limits.usage(dictionary, request.user), balance=balance,
        insufficient=estimate is not None and balance is not None and balance < estimate['daily_estimate'],
        audio_allowance=capture_limits.AUDIO_ALLOWANCE_USD))
