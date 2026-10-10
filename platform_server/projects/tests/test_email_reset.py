import io
import re
from datetime import timedelta
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command, CommandError
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from projects import email_reset
from projects.models import PasswordResetLimit


@override_settings(PASSWORD_RESET_EMAIL_ENABLED=True, PUBLIC_BASE_URL='https://clara.example',
                   DEFAULT_FROM_EMAIL='accounts@clara.example',
                   EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
                   PASSWORD_RESET_TIMEOUT=3600)
class EmailRecoveryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user('learner', 'learner@example.org', 'Original-safe-pass-712')

    def setUp(self):
        self.queue = patch('projects.email_reset.async_task').start()
        self.addCleanup(patch.stopall)
        mail.outbox = []

    def request_link(self, email=None, community=True):
        prefix = 'community_dictionary:' if community else ''
        return self.client.post(reverse(prefix + 'password-reset'), {'email': email or self.user.email})

    def deliver(self):
        args = self.queue.call_args.args
        self.assertEqual(args[0], 'projects.email_reset.send_recovery_email')
        email_reset.send_recovery_email(*args[1:])

    def link(self, community=True, user=None):
        user = user or self.user
        return reverse(('community_dictionary:' if community else '') + 'password-reset-confirm',
                       kwargs={'uidb64': urlsafe_base64_encode(force_bytes(user.pk)),
                               'token': default_token_generator.make_token(user)})

    def test_both_login_pages_link_to_matching_recovery(self):
        for prefix in ['', 'community_dictionary:']:
            response = self.client.get(reverse(prefix + 'login'))
            self.assertContains(response, reverse(prefix + 'password-reset'))
            self.assertContains(response, 'Forgotten password?')

    def test_both_flows_keep_brand_and_mobile_email_hints(self):
        for prefix, base in [('', 'projects/password_form_base.html'), ('community_dictionary:', 'community_dictionary/base.html')]:
            response = self.client.get(reverse(prefix + 'password-reset'))
            self.assertTemplateUsed(response, base)
            self.assertContains(response, 'autocomplete="email"')
            self.assertContains(response, 'autocapitalize="none"')
            self.assertIn('no-store', response['Cache-Control'])

    def test_real_reset_and_login_invalidates_other_sessions_and_old_tokens(self):
        other = Client()
        other.force_login(self.user)
        self.request_link()
        self.deliver()
        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        self.assertIn('Username: learner', body)
        self.assertIn('Community Dictionaries', mail.outbox[0].subject)
        self.assertNotIn('Original-safe-pass', body)
        link = re.search(r'https://clara.example(/\S+)', body).group(1)
        first = self.client.get(link)
        self.assertEqual(first.status_code, 302)
        self.assertIn('/set-password/', first.url)
        self.assertEqual(first['Referrer-Policy'], 'same-origin')
        page = self.client.get(first.url)
        self.assertTrue(page.context['validlink'])
        password = 'Replacement-unique-74913'
        done = self.client.post(first.url, {'new_password1': password, 'new_password2': password})
        self.assertRedirects(done, reverse('community_dictionary:password-reset-complete'))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(password))
        self.assertFalse(other.get(reverse('community_dictionary:home')).wsgi_request.user.is_authenticated)
        self.assertFalse(Client().get(link).context['validlink'])
        self.assertFalse(self.client.login(username='learner', password='Original-safe-pass-712'))
        self.assertTrue(self.client.login(username='learner', password=password))
        self.assertNotIn('_auth_user_id', Client().session)

    def test_plain_clara_flow_email_and_completion_link(self):
        self.request_link(community=False); self.deliver()
        self.assertIn('C-LARA-2', mail.outbox[0].subject)
        self.assertIn('https://clara.example/accounts/password/reset/', mail.outbox[0].body)
        response = self.client.get(reverse('password-reset-complete'))
        self.assertContains(response, reverse('login'))

    def test_unknown_inactive_unusable_return_same_page_without_email(self):
        User = get_user_model()
        User.objects.create_user('inactive', 'inactive@example.org', 'pw', is_active=False)
        User.objects.create_user('unusable', 'unusable@example.org', password=None)
        destinations = []
        for address in ['missing@example.org', 'inactive@example.org', 'unusable@example.org']:
            response = self.request_link(address); destinations.append(response.url); self.deliver()
        self.assertEqual(len(set(destinations)), 1)
        self.assertEqual(len(mail.outbox), 0)
        known = self.request_link()
        self.assertEqual(known.url, destinations[0])
        # The HTTP path queues all valid addresses, without querying for a user.
        self.assertEqual(self.queue.call_count, 4)

    def test_duplicate_email_accounts_get_independent_links(self):
        get_user_model().objects.create_user('second', self.user.email, 'Other-safe-password-421')
        self.request_link(); self.deliver()
        self.assertEqual(len(mail.outbox), 2)
        self.assertNotEqual(mail.outbox[0].body, mail.outbox[1].body)

    def test_case_insensitive_lookup_and_shared_throttle(self):
        self.request_link(self.user.email.upper()); self.deliver()
        self.assertEqual(len(mail.outbox), 1)
        self.request_link(community=False); self.request_link()
        fourth = self.request_link(self.user.email.upper())
        self.assertEqual(fourth.status_code, 302)
        self.assertEqual(self.queue.call_count, 3)
        self.assertEqual(PasswordResetLimit.objects.get(pk='global').count, 3)
        self.assertEqual(PasswordResetLimit.objects.count(), 2)
        self.assertNotIn('learner', str(list(PasswordResetLimit.objects.values())))

    def test_email_window_expires(self):
        for _ in range(3): self.request_link()
        PasswordResetLimit.objects.exclude(key='global').update(window_start=timezone.now() - timedelta(minutes=16))
        self.request_link()
        self.assertEqual(self.queue.call_count, 4)

    def test_global_limit_bounds_many_addresses_and_expires(self):
        for i in range(35): self.request_link(f'unknown-{i}@example.org')
        self.assertEqual(self.queue.call_count, 30)
        self.assertEqual(PasswordResetLimit.objects.count(), 31)
        PasswordResetLimit.objects.filter(key='global').update(window_start=timezone.now() - timedelta(hours=2))
        self.request_link('another@example.org')
        self.assertEqual(self.queue.call_count, 31)

    def test_stale_hashed_counters_are_pruned(self):
        PasswordResetLimit.objects.create(key='old', window_start=timezone.now() - timedelta(days=2))
        self.request_link()
        self.assertFalse(PasswordResetLimit.objects.filter(pk='old').exists())

    def test_invalid_email_and_csrf_do_not_enqueue(self):
        response = self.request_link('not-an-email')
        self.assertContains(response, 'Enter a valid email address')
        response = Client(enforce_csrf_checks=True).post(reverse('password-reset'), {'email': self.user.email})
        self.assertEqual(response.status_code, 403)
        self.queue.assert_not_called()

    def test_weak_and_mismatched_passwords_rejected(self):
        page = self.client.get(self.link())
        for a, b in [('12345678', '12345678'), ('A-safe-password-512', 'mismatch')]:
            response = self.client.post(page.url, {'new_password1': a, 'new_password2': b})
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context['form'].errors)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('Original-safe-pass-712'))

    def test_expired_or_malformed_link_fails(self):
        with patch('django.contrib.auth.tokens.PasswordResetTokenGenerator._now', return_value=timezone.now().replace(tzinfo=None) - timedelta(hours=2)):
            link = self.link()
        self.assertFalse(self.client.get(link).context['validlink'])
        response = self.client.get(reverse('password-reset-confirm', kwargs={'uidb64': 'bad', 'token': 'bad'}))
        self.assertFalse(response.context['validlink'])

    def test_email_change_invalidates_link(self):
        link = self.link()
        self.user.email = 'changed@example.org'; self.user.save(update_fields=['email'])
        self.assertFalse(self.client.get(link).context['validlink'])

    def test_confirm_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        page = client.get(self.link())
        response = client.post(page.url, {'new_password1': 'Safe-unique-812', 'new_password2': 'Safe-unique-812'})
        self.assertEqual(response.status_code, 403)

    def test_host_headers_cannot_poison_email_link(self):
        self.client.post(reverse('password-reset'), {'email': self.user.email}, HTTP_HOST='attacker.example', HTTP_X_FORWARDED_HOST='evil.example')
        self.deliver()
        self.assertIn('https://clara.example/', mail.outbox[0].body)
        self.assertNotIn('attacker', mail.outbox[0].body)
        self.assertNotIn('evil.example', mail.outbox[0].body)

    @override_settings(PASSWORD_RESET_EMAIL_ENABLED=False)
    def test_disabled_feature_is_hidden_and_does_not_send_or_redeem(self):
        self.assertNotContains(self.client.get(reverse('login')), 'Forgotten password?')
        self.assertEqual(self.request_link().status_code, 503)
        self.assertEqual(self.client.get(self.link()).status_code, 503)
        self.assertFalse(email_reset.send_recovery_email(self.user.email, True, timezone.now().timestamp()))
        self.queue.assert_not_called(); self.assertEqual(mail.outbox, [])

    def test_old_queued_request_is_not_sent(self):
        self.assertFalse(email_reset.send_recovery_email(self.user.email, True, (timezone.now() - timedelta(minutes=16)).timestamp()))
        self.assertEqual(mail.outbox, [])

    def test_mail_failure_is_sanitized_and_does_not_crash(self):
        with patch('projects.email_reset.EmailMultiAlternatives.send', side_effect=RuntimeError('SECRET token test@example.org')):
            with self.assertLogs('projects.email_reset', level='ERROR') as logs:
                result = email_reset.send_recovery_email(self.user.email, True, timezone.now().timestamp())
        self.assertFalse(result)
        self.assertNotIn('SECRET', ''.join(logs.output)); self.assertNotIn('test@example.org', ''.join(logs.output))

    def test_dispatch_and_database_failure_fail_closed(self):
        self.queue.side_effect = RuntimeError('SECRET')
        with self.assertLogs('projects.email_reset', level='ERROR') as logs:
            self.assertEqual(self.request_link().status_code, 302)
        self.assertNotIn('SECRET', ''.join(logs.output))
        self.queue.reset_mock()
        with patch('projects.email_reset_views.admit_request', side_effect=RuntimeError('SECRET')):
            with self.assertLogs('projects.email_reset_views', level='ERROR'):
                self.assertEqual(self.request_link().status_code, 302)
        self.queue.assert_not_called()

    def test_diagnostic_does_not_send_without_explicit_option(self):
        output = io.StringIO(); call_command('account_email_check', stdout=output)
        self.assertIn('No email sent', output.getvalue()); self.assertEqual(mail.outbox, [])
        call_command('account_email_check', send_to='tester@example.org', stdout=output)
        self.assertEqual(len(mail.outbox), 1)
        self.assertNotIn('/password/reset/', mail.outbox[0].body)
        self.assertTrue(self.user.check_password('Original-safe-pass-712'))

    def test_diagnostic_sanitizes_smtp_error(self):
        with patch('projects.management.commands.account_email_check.send_mail', side_effect=RuntimeError('SECRET')):
            with self.assertRaises(CommandError) as caught:
                call_command('account_email_check', send_to='tester@example.org', stdout=io.StringIO())
        self.assertNotIn('SECRET', str(caught.exception))

    def test_invalid_origins_fail_closed(self):
        for origin in ['', 'http://clara.example', 'https://clara.example/path', 'https://clara.example?x=1', 'https://user:pass@clara.example']:
            with self.subTest(origin=origin), override_settings(PUBLIC_BASE_URL=origin):
                self.assertEqual(self.request_link().status_code, 503)
        self.queue.assert_not_called()

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend', PUBLIC_BASE_URL='http://127.0.0.1:8000')
    def test_console_laptop_origin_allowed(self):
        self.assertEqual(email_reset.configuration().netloc, '127.0.0.1:8000')

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend', EMAIL_HOST='smtp.gmail.com',
                       EMAIL_HOST_USER='example@example.org', EMAIL_HOST_PASSWORD='PRIVATE',
                       EMAIL_USE_TLS=True, EMAIL_USE_SSL=False, SECRET_KEY='test-private-server-key')
    def test_smtp_configuration_requires_private_key_credentials_and_tls(self):
        self.assertEqual(email_reset.configuration().scheme, 'https')
        for values in [dict(SECRET_KEY='dev-secret-key'), dict(EMAIL_HOST_PASSWORD=''),
                       dict(EMAIL_USE_TLS=False), dict(EMAIL_USE_SSL=True)]:
            with self.subTest(values=values), override_settings(**values):
                with self.assertRaises(ImproperlyConfigured): email_reset.configuration()

    def test_profile_shows_recovery_address(self):
        self.client.force_login(self.user)
        self.assertContains(self.client.get(reverse('profile')), self.user.email)

    def test_deactivation_and_unusable_password_block_existing_links(self):
        link = self.link()
        self.user.is_active = False; self.user.save(update_fields=['is_active'])
        self.assertFalse(self.client.get(link).context['validlink'])
        self.user.is_active = True; self.user.set_unusable_password(); self.user.save()
        self.assertFalse(self.client.get(self.link()).context['validlink'])

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend')
    def test_console_backend_cannot_be_used_for_remote_site(self):
        with self.assertRaises(ImproperlyConfigured): email_reset.configuration()
