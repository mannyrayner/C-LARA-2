"""Recover from a real allowance block without authorising spend or mail spam."""
from datetime import timedelta
import json
from pathlib import Path
import shutil
import subprocess
from unittest.mock import patch

from django.core import mail
from django.core import signing
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from community_dictionary import capture_allowance_mail as notices
from community_dictionary import picture_practice as practice
from community_dictionary.picture_practice_views import SALT
from community_dictionary.models import Dictionary, Event, Membership, PictureCapture
from . import test_capture_limits as limits


@override_settings(OPENAI_API_KEY='test-only', CREDITS_ENABLED=False,
    PUBLIC_BASE_URL='https://clara.example.org', DEFAULT_FROM_EMAIL='clara@example.org',
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class AllowanceRecoveryTests(TestCase):
    setUp = limits.CaptureLimitTests.setUp
    url = limits.CaptureLimitTests.url
    word = limits.CaptureLimitTests.word
    attempt = limits.CaptureLimitTests.attempt
    submit = limits.CaptureLimitTests.submit
    confirm = limits.CaptureLimitTests.confirm

    def exhaust(self):
        for _ in range(10):
            self.attempt()
        self.owner.email = 'dictionary-owner@example.org'
        self.owner.save(update_fields=['email'])

    def test_new_dictionary_has_fifty_and_settings_preserve_existing_limit(self):
        self.client.force_login(self.owner)
        data = {'name':'Practice dictionary', 'language':'Swedish', 'explanation_language':'English',
            'tts_enabled':'on', 'sentence_capture_enabled':'on'}
        created = self.client.post(reverse('community_dictionary:home'), data)
        self.assertEqual(created.status_code, 302)
        self.assertEqual(Dictionary.objects.get(name='Practice dictionary').capture_daily_limit, 50)
        self.client.post(self.url('settings'), {**data, 'capture_daily_limit':500})
        self.d.refresh_from_db()
        self.assertEqual(self.d.capture_daily_limit, 10)

    def test_owner_offer_opens_signed_preview_and_needs_confirmation(self):
        self.exhaust(); self.client.force_login(self.owner)
        blocked = self.submit()
        self.assertContains(blocked, 'Daily allowance used up')
        self.assertContains(blocked, 'Add 40 more')
        values = blocked.wsgi_request.capture_allowance_offer
        preview = self.client.post(values['url'], {'action':'preview', 'daily_limit':values['proposed']})
        self.assertContains(preview, 'Review the daily cost')
        self.d.refresh_from_db(); self.assertEqual(self.d.capture_daily_limit, 10)
        self.assertEqual(self.confirm(preview.context['estimate'], approve='').status_code, 400)
        self.assertEqual(self.confirm(preview.context['estimate']).status_code, 302)
        self.d.refresh_from_db(); self.assertEqual(self.d.capture_daily_limit, 50)
        self.assertEqual(PictureCapture.objects.count(), 10)
        self.assertFalse(Event.objects.filter(action=notices.ACTION).exists())
        self.ai.assert_not_called(); self.tts.assert_not_called()

    def test_member_block_queues_once_and_duplicate_delivery_sends_once(self):
        self.exhaust()
        self.assertContains(self.client.get(self.url('capture-start')), 'Ask a dictionary owner')
        self.assertFalse(Event.objects.filter(action=notices.ACTION).exists())
        with patch.object(notices, 'enqueue') as enqueue, self.captureOnCommitCallbacks(execute=True):
            for _ in range(3):
                page = self.submit()
                self.assertContains(page, 'Ask a dictionary owner')
                self.assertNotContains(page, 'value="preview"')
        enqueue.assert_called_once()
        notice = Event.objects.get(action=notices.ACTION)
        self.assertTrue(notices.deliver(notice.pk))
        self.assertFalse(notices.deliver(notice.pk))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.owner.email])
        self.assertIn('https://clara.example.org'+self.url('capture-limit'), mail.outbox[0].body)
        self.assertNotIn(self.user.username, mail.outbox[0].body)
        self.assertNotIn('A cat.', mail.outbox[0].body)
        self.assertEqual(PictureCapture.objects.count(), 10)
        self.ai.assert_not_called(); self.tts.assert_not_called()

    def test_cooldown_expires_but_raise_before_delivery_cancels_stale_email(self):
        self.exhaust()
        with patch.object(notices, 'enqueue') as enqueue, self.captureOnCommitCallbacks(execute=True):
            self.submit()
            Event.objects.filter(action=notices.ACTION).update(created_at=timezone.now()-timedelta(hours=25))
            self.submit()
        self.assertEqual(enqueue.call_count, 2)
        self.d.capture_daily_limit = 50; self.d.save(update_fields=['capture_daily_limit'])
        for notice in Event.objects.filter(action=notices.ACTION):
            self.assertFalse(notices.deliver(notice.pk))
        self.assertEqual(len(mail.outbox), 0)

    def test_co_owner_can_increase_without_notifying_primary_owner(self):
        self.exhaust()
        Membership.objects.filter(dictionary=self.d, user=self.user).update(role='co_owner')
        with patch.object(notices, 'enqueue') as enqueue, self.captureOnCommitCallbacks(execute=True):
            page = self.submit()
        self.assertContains(page, 'Add 40 more')
        enqueue.assert_not_called()
        self.assertFalse(Event.objects.filter(action=notices.ACTION).exists())

    @override_settings(COMMUNITY_DICTIONARY_CAPTURE_DAILY_LIMIT=3)
    def test_account_ceiling_is_not_offered_a_dictionary_increase_or_email(self):
        other = Dictionary.objects.create(owner=self.user, name='Other', language='Swedish')
        for _ in range(3): self.attempt(dictionary=other)
        page = self.submit()
        self.assertContains(page, 'The server limit has been reached')
        self.assertNotContains(page, 'value="preview"')
        self.assertFalse(Event.objects.filter(action=notices.ACTION).exists())

    def test_json_block_includes_recovery_without_allocating(self):
        self.exhaust(); self.client.force_login(self.owner)
        # Same real capture route, requesting its JSON representation.
        from .test_picture_capture import picture
        import uuid
        page = self.client.post(self.url('capture-start'), {'submission_id':uuid.uuid4(),
            'photo':picture(), 'description':'A cat.', 'input_language':'English',
            'input_mode':'text', 'voice':'marin', 'ai_consent':'on'}, HTTP_ACCEPT='application/json')
        self.assertEqual(page.status_code, 409)
        self.assertEqual(page.json()['code'], 'allowance_exhausted')
        self.assertEqual(page.json()['allowance']['proposed'], 50)
        self.d.refresh_from_db(); self.assertEqual(self.d.capture_daily_limit, 10)

    def test_picture_practice_block_offers_recovery_and_notifies_without_processing(self):
        self.exhaust()
        photo = limits.CaptureLimitTests.image(self)
        import uuid
        data = {'submission_id':uuid.uuid4(), 'image':photo.pk, 'mode':'text',
            'description':'A cat.', 'feedback_language':'English', 'voice':'marin',
            'permission':'on', 'quote':signing.dumps(practice.quote(self.user, self.d), salt=SALT)}
        with patch.object(notices, 'enqueue') as enqueue, patch.object(practice, 'queue') as queue, \
                self.captureOnCommitCallbacks(execute=True):
            page = self.client.post(self.url('picture-practice'), data, HTTP_ACCEPT='application/json')
        self.assertEqual(page.status_code, 409)
        self.assertEqual(page.json()['code'], 'allowance_exhausted')
        self.assertEqual(page.json()['allowance']['proposed'], None)
        enqueue.assert_called_once(); queue.assert_not_called()
        self.assertEqual(PictureCapture.objects.count(), 10)

    def test_mail_failure_is_bounded_and_is_not_retried(self):
        self.exhaust()
        with patch.object(notices, 'enqueue'), self.captureOnCommitCallbacks(execute=True):
            self.submit()
        notice = Event.objects.get(action=notices.ACTION)
        with patch.object(notices, 'send_mail', side_effect=RuntimeError('private-credential')), \
                self.assertLogs(notices.log, level='WARNING') as logged:
            self.assertFalse(notices.deliver(notice.pk))
        self.assertNotIn('private-credential', str(logged.output))
        with patch.object(notices, 'send_mail') as send:
            self.assertFalse(notices.deliver(notice.pk))
        send.assert_not_called()

    def test_browser_allowance_offer_preserves_spoken_attempt(self):
        node = shutil.which('node')
        if not node or subprocess.run([node, '-e', "require('jsdom')"], capture_output=True).returncode:
            self.skipTest('Optional jsdom is unavailable')
        photo = limits.CaptureLimitTests.image(self)
        page = self.client.get(self.url('picture-practice')+f'?image={photo.pk}')
        root = Path(__file__).resolve().parent.parent
        payload = {'html':page.content.decode(),
            **{key:(root/'static/community_dictionary'/name).read_text() for key,name in
                [('app','app.js'),('recorder','recorder.js'),('controller','picture_practice.js'),('css','app.css')]}}
        result = subprocess.run([node, str(Path(__file__).with_name('allowance_recovery_browser.cjs'))],
            input=json.dumps(payload), text=True, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
