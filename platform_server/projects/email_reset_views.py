"""A shared recovery workflow, with a Community Dictionaries presentation."""
import logging

from django.conf import settings
from django.contrib.auth import views as auth_views
from django.core.exceptions import ImproperlyConfigured
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods
from django.views.generic import TemplateView

from .email_reset import RecoveryEmailForm, admit_request, configuration, enqueue_recovery
from .password_forms import AdminSetPasswordForm

logger = logging.getLogger(__name__)


def presentation(community):
    prefix = 'community_dictionary:' if community else ''
    return {
        'recovery_base': 'community_dictionary/base.html' if community else 'projects/password_form_base.html',
        'recovery_login': prefix + 'login',
        'recovery_start': prefix + 'password-reset',
    }


@sensitive_post_parameters()
@never_cache
@csrf_protect
@require_http_methods(['GET', 'POST'])
def start(request, community=False):
    context = presentation(community)
    try:
        configuration()
    except ImproperlyConfigured:
        context['unavailable'] = True
        return render(request, 'projects/recovery_start.html', context, status=503)
    form = RecoveryEmailForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        try:
            allowed = admit_request(form.cleaned_data['email'])
        except Exception as exc:
            # Fail closed if the throttle database is unavailable.
            logger.error('Password-reset request failed (%s).', type(exc).__name__)
            allowed = False
        if allowed:
            enqueue_recovery(form.cleaned_data['email'], community)
        return redirect(('community_dictionary:' if community else '') + 'password-reset-done')
    context['form'] = form
    return render(request, 'projects/recovery_start.html', context)


@method_decorator(never_cache, name='dispatch')
class RecoveryPage(TemplateView):
    community = False

    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), **presentation(self.community)}


@method_decorator(never_cache, name='dispatch')
class RecoveryConfirm(auth_views.PasswordResetConfirmView):
    community = False
    form_class = AdminSetPasswordForm  # Same password policy as our existing reset/change forms.
    template_name = 'projects/recovery_confirm.html'
    post_reset_login = False

    def dispatch(self, request, *args, **kwargs):
        if not settings.PASSWORD_RESET_EMAIL_ENABLED:
            return render(request, 'projects/recovery_start.html', {**presentation(self.community), 'unavailable': True}, status=503)
        response = super().dispatch(request, *args, **kwargs)
        response['Referrer-Policy'] = 'same-origin'
        return response

    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), **presentation(self.community)}

    def get_user(self, uidb64):
        user = super().get_user(uidb64)
        return user if user and user.is_active and user.has_usable_password() else None

    def get_success_url(self):
        return reverse(('community_dictionary:' if self.community else '') + 'password-reset-complete')


def patterns(community=False):
    return [
        path('', start, {'community': community}, name='password-reset'),
        path('sent/', RecoveryPage.as_view(community=community, template_name='projects/recovery_done.html'), name='password-reset-done'),
        path('complete/', RecoveryPage.as_view(community=community, template_name='projects/recovery_complete.html'), name='password-reset-complete'),
        path('<uidb64>/<token>/', RecoveryConfirm.as_view(community=community), name='password-reset-confirm'),
    ]
