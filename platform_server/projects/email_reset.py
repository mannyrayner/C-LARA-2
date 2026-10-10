"""Email recovery: fixed-origin links, shared throttling, and bounded task dispatch."""
import logging
import unicodedata
from datetime import timedelta
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.auth.forms import PasswordResetForm
from django.core.exceptions import ImproperlyConfigured
from django.core.mail import EmailMultiAlternatives
from django.core.validators import URLValidator, validate_email
from django.db import transaction
from django.db.models import F
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.crypto import salted_hmac
from django_q.tasks import async_task

from .models import PasswordResetLimit

logger = logging.getLogger(__name__)


def configuration():
    """Never derive a password-reset link from an untrusted HTTP Host header."""
    if not settings.PASSWORD_RESET_EMAIL_ENABLED:
        raise ImproperlyConfigured("Email password resets are not enabled.")
    origin = settings.PUBLIC_BASE_URL.rstrip('/')
    try:
        URLValidator(schemes=['https', 'http'])(origin)
        url = urlsplit(origin)
        validate_email(settings.DEFAULT_FROM_EMAIL)
    except Exception:
        raise ImproperlyConfigured("Set a valid CLARA_PUBLIC_BASE_URL and DEFAULT_FROM_EMAIL.") from None
    if url.username or url.password or url.path or url.query or url.fragment:
        raise ImproperlyConfigured("CLARA_PUBLIC_BASE_URL must contain only scheme, host and optional port.")
    local_console = (settings.EMAIL_BACKEND == 'django.core.mail.backends.console.EmailBackend'
                     and url.hostname in {'localhost', '127.0.0.1', '::1'})
    if settings.EMAIL_BACKEND == 'django.core.mail.backends.console.EmailBackend' and not local_console:
        raise ImproperlyConfigured('The console mail backend is only for a localhost test.')
    if url.scheme != 'https' and not local_console:
        raise ImproperlyConfigured("Password-reset links must use HTTPS (except a local console test).")
    if settings.EMAIL_BACKEND == 'django.core.mail.backends.smtp.EmailBackend':
        if not settings.EMAIL_HOST or not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD:
            raise ImproperlyConfigured("Configure EMAIL_HOST, EMAIL_HOST_USER and EMAIL_HOST_PASSWORD.")
        if not (settings.EMAIL_USE_TLS or settings.EMAIL_USE_SSL) or (settings.EMAIL_USE_TLS and settings.EMAIL_USE_SSL):
            raise ImproperlyConfigured("Select exactly one of EMAIL_USE_TLS or EMAIL_USE_SSL.")
        if settings.SECRET_KEY == 'dev-secret-key':
            raise ImproperlyConfigured("Set a private DJANGO_SECRET_KEY before enabling email recovery.")
    return url


def admit_request(email):
    """Fixed windows shared by all workers, independent of whether an account exists.

    The global row serializes reservations on PostgreSQL. An atomic conditional
    UPDATE also enforces each bound on SQLite. Denials roll back both counters.
    Email addresses are HMACed, never stored in these rate-limit rows.
    """
    now = timezone.now()
    normalized = unicodedata.normalize('NFKC', email).casefold()
    key = salted_hmac('clara.password-reset.email', normalized, algorithm='sha256').hexdigest()
    class Limited(Exception):
        pass
    try:
        with transaction.atomic():
            for bucket, seconds, limit in [('global', 3600, 30), (key, 900, 3)]:
                row, _ = PasswordResetLimit.objects.get_or_create(key=bucket, defaults={'window_start': now})
                row = PasswordResetLimit.objects.select_for_update().get(pk=row.pk)
                if row.window_start <= now - timedelta(seconds=seconds):
                    row.count = 0
                    row.window_start = now
                    row.save(update_fields=['count', 'window_start'])
                if not PasswordResetLimit.objects.filter(pk=row.pk, count__lt=limit).update(count=F('count') + 1):
                    raise Limited
            PasswordResetLimit.objects.exclude(key='global').filter(window_start__lt=now - timedelta(days=1)).delete()
    except Limited:
        return False
    return True


class RecoveryEmailForm(PasswordResetForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].widget.attrs.update({
            'autocomplete': 'email', 'autocapitalize': 'none',
            'autocorrect': 'off', 'spellcheck': 'false',
        })

    def send_mail(self, subject_template_name, email_template_name, context,
                  from_email, to_email, html_email_template_name=None):
        # Django's default failure logger includes the recipient and traceback.
        # Keep our log output free of addresses, credentials, and reset links.
        subject = ''.join(render_to_string(subject_template_name, context).splitlines())
        body = render_to_string(email_template_name, context)
        if EmailMultiAlternatives(subject, body, from_email, [to_email]).send(fail_silently=False) != 1:
            raise RuntimeError('Mail backend did not accept the message')


def send_recovery_email(email, community=False, requested_at=None):
    """Run for unknown addresses too, so account lookup isn't in the HTTP request."""
    try:
        # In-memory queues may wait behind AI jobs. Don't send a very old request
        # after a restart/replay or after the feature has been disabled.
        if requested_at is None or timezone.now().timestamp() - requested_at > 900:
            return False
        origin = configuration()
        form = RecoveryEmailForm({'email': email})
        if not form.is_valid():
            return False
        prefix = 'community_dictionary:' if community else ''
        form.save(
            domain_override=origin.netloc,
            use_https=origin.scheme == 'https',
            from_email=settings.DEFAULT_FROM_EMAIL,
            subject_template_name='projects/recovery_subject.txt',
            email_template_name='projects/recovery_email.txt',
            extra_email_context={
                'reset_confirm_name': prefix + 'password-reset-confirm',
                'service_name': 'Community Dictionaries' if community else 'C-LARA-2',
                'expiry_minutes': settings.PASSWORD_RESET_TIMEOUT // 60,
            },
        )
        return True
    except Exception as exc:
        logger.error('Password-reset email failed (%s). Run account_email_check.', type(exc).__name__)
        return False


def enqueue_recovery(email, community):
    # No tokens, request objects, passwords or SMTP credentials enter the queue.
    try:
        async_task('projects.email_reset.send_recovery_email', email, community,
                   timezone.now().timestamp())
    except Exception as exc:
        logger.error('Password-reset dispatch failed (%s).', type(exc).__name__)


def recovery_context(request):
    return {'password_reset_email_enabled': settings.PASSWORD_RESET_EMAIL_ENABLED}
