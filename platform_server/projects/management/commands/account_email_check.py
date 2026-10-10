"""Validate recovery configuration; optionally send one harmless diagnostic email."""
from django.conf import settings
from django.core.exceptions import ValidationError, ImproperlyConfigured
from django.core.management.base import BaseCommand, CommandError
from django.core.mail import send_mail
from django.core.validators import validate_email
from projects.email_reset import configuration
from projects.models import PasswordResetLimit


class Command(BaseCommand):
    help = 'Check email recovery configuration; --send-to sends one diagnostic email (no reset token).'

    def add_arguments(self, parser):
        parser.add_argument('--send-to', help='Recipient of an explicitly requested test email.')

    def handle(self, *args, **options):
        try:
            origin = configuration()
            PasswordResetLimit.objects.exists()  # Verify migration, even on an empty table.
        except ImproperlyConfigured as exc:
            raise CommandError(str(exc)) from None
        except Exception as exc:
            raise CommandError(f'Cannot check recovery table ({type(exc).__name__}); check migrations/database.') from None
        self.stdout.write(f'Recovery enabled; link origin: {origin.scheme}://{origin.netloc}')
        self.stdout.write(f'Mail backend: {settings.EMAIL_BACKEND}; link lifetime: {settings.PASSWORD_RESET_TIMEOUT // 60} minutes')
        if not options['send_to']:
            self.stdout.write('Configuration and database checks passed. No email sent; SMTP not contacted.')
            return
        try:
            validate_email(options['send_to'])
        except ValidationError:
            raise CommandError('Enter a valid --send-to email address.') from None
        try:
            count = send_mail('C-LARA-2 email delivery test',
                              'This is the requested email-delivery test for C-LARA-2 and Community Dictionaries. '
                              'No password was changed and this message contains no reset link.',
                              settings.DEFAULT_FROM_EMAIL, [options['send_to']], fail_silently=False)
            if count != 1:
                raise RuntimeError('Backend did not accept message')
        except Exception as exc:
            raise CommandError(f'Email test failed ({type(exc).__name__}). Check mail settings; no credentials are shown.') from None
        self.stdout.write('Test message accepted by the mail backend. Check the recipient inbox and spam folder to confirm delivery.')
