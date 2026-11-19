import json
import os
from pathlib import Path
import shutil
import subprocess
from types import SimpleNamespace
import uuid
from unittest.mock import patch
from django.core import signing
from django.test import TestCase, Client, override_settings
from django.utils import timezone
from datetime import timedelta
from community_dictionary import picture_practice as practice, capture, capture_limits, writing_ai
from community_dictionary.picture_practice_views import SALT
from community_dictionary.models import PictureCapture, Contribution, Entry, CaptureSpeech, Participation, ContributionPreference
from community_dictionary.services import Conflict
from . import test_picture_capture as fixtures
from .test_workflow import recording as audio

ORIGINAL = 'Il gatto sono felice.'
CORRECTED = 'Il gatto è felice.'
FEEDBACK = {'outcome': 'ready', 'text': CORRECTED, 'question': '',
    'understood': 'You are saying the cat is happy.',
    'corrections': [{'before': 'sono', 'after': 'è', 'reason': 'Use the singular verb with il gatto.'}],
    'suggestions': []}


@override_settings(OPENAI_API_KEY='test-only', CREDITS_ENABLED=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class PicturePracticeTests(TestCase):
    url = fixtures.PictureCaptureTests.url
    word = fixtures.PictureCaptureTests.word
    image = fixtures.PictureCaptureTests.image

    def setUp(self):
        fixtures.PictureCaptureTests.setUp(self)
        self.d.language = 'Italian'
        self.d.save()
        self.photo = self.image()
        self.review = patch('community_dictionary.writing_ai.review', return_value=fixtures.response(FEEDBACK)).start()
        self.asr = patch('community_dictionary.capture_ai.transcribe', return_value=SimpleNamespace(
            text=ORIGINAL, usage=SimpleNamespace(type='tokens', input_tokens=80, output_tokens=15))).start()
        self.enqueue = patch('community_dictionary.picture_practice.queue').start()
        self.before = (Entry.objects.count(), Contribution.objects.count())

    def start(self, mode='text', **extra):
        data = {'submission_id': str(uuid.uuid4()), 'image': self.photo.pk, 'mode': mode,
            'feedback_language': 'English', 'voice': 'marin', 'permission': 'on',
            'quote': signing.dumps(practice.quote(self.user, self.d), salt=SALT)}
        data.update({'audio': audio()} if mode == 'voice' else {'description': ORIGINAL})
        data.update(extra)
        return self.client.post(self.url('picture-practice'), data)

    def attempt(self, mode='text', **extra):
        result = self.start(mode, **extra)
        self.assertEqual(result.status_code, 302, result.content[:1000])
        return PictureCapture.objects.latest('created_at')

    def act(self, study, action, **extra):
        return self.client.post(self.url('picture-practice-action', study.pk),
            {'action': action, 'submission_id': str(uuid.uuid4()), **extra})

    def feedback(self):
        study = self.attempt()
        practice.run(study.pk)
        study.refresh_from_db()
        self.assertEqual(study.status, 'feedback')
        return study

    def test_entry_point_pins_picture_without_rows_or_calls_and_hides_example(self):
        page = self.client.get(self.url('practice'))
        self.assertContains(page, 'Describe a picture')
        page = self.client.get(self.url('picture-practice'), follow=True)
        self.assertContains(page, 'Show an example')
        self.assertContains(page, 'data-practice-type disabled hidden')
        self.assertEqual(PictureCapture.objects.count(), 0)
        self.review.assert_not_called()
        self.asr.assert_not_called()
        self.assertIn('image=', page.request['QUERY_STRING'])
        self.assertIn('no-store', page['Cache-Control'])

    def test_feedback_uses_image_and_intention_without_enrichment_or_automatic_audio(self):
        study = self.feedback()
        self.assertEqual((Entry.objects.count(), Contribution.objects.count()), self.before)
        self.ai.assert_not_called()
        self.tts.assert_not_called()
        self.asr.assert_not_called()
        self.assertEqual(CaptureSpeech.objects.count(), 0)
        self.assertEqual(capture_limits.usage(self.d)['used'], 1)
        self.assertEqual(self.review.call_args.kwargs['text'], ORIGINAL)
        self.assertEqual(self.review.call_args.kwargs['schema'], practice.SCHEMA)
        self.assertIn('imagining', self.review.call_args.kwargs['instructions'])
        page = self.client.get(self.url('picture-practice-detail', study.pk))
        self.assertContains(page, FEEDBACK['understood'])
        self.assertContains(page, 'Try again')
        self.assertContains(page, 'Listen to this version')
        self.assertContains(page, 'not pronunciation')
        for _ in range(2): practice.run(study.pk)
        self.assertEqual(self.review.call_count, 1)

    def test_speech_pauses_at_confirmable_transcript_and_allows_editing(self):
        study = self.attempt('voice')
        practice.run(study.pk); practice.run(study.pk)
        study.refresh_from_db()
        self.assertEqual(study.status, 'transcript')
        self.review.assert_not_called()
        self.assertEqual(self.asr.call_count, 1)
        page = self.client.get(self.url('picture-practice-detail', study.pk))
        self.assertContains(page, 'Is this what you said?')
        self.assertEqual(self.client.get(self.url('capture-media', study.pk, 'recording')).status_code, 200)
        data = dict(mode='text', description='Il gatto è felice.', feedback_language='Italian', voice='marin',
            permission='on', quote=signing.dumps(practice.quote(self.user, self.d), salt=SALT), submission_id=str(uuid.uuid4()))
        for _ in range(2): self.assertEqual(self.act(study, 'check', **data).status_code, 302)
        self.review.return_value = fixtures.response({**FEEDBACK, 'text': data['description'], 'corrections': []})
        practice.run(study.pk)
        study.refresh_from_db()
        self.assertEqual(study.status, 'feedback')
        self.assertEqual(study.result['practice']['transcript'], ORIGINAL)
        self.assertEqual(self.review.call_args.kwargs['text'], data['description'])
        self.assertEqual(self.review.call_args.kwargs['feedback_language'], 'Italian')
        self.assertEqual(capture_limits.usage(self.d)['used'], 1)

    def test_replayed_upload_jobs_and_listen_cannot_repeat_paid_requests(self):
        token = str(uuid.uuid4())
        first = self.start(submission_id=token)
        second = self.start(submission_id=token)
        self.assertEqual(first.url, second.url)
        self.assertEqual(PictureCapture.objects.count(), 1)
        study = PictureCapture.objects.get()
        practice.run(study.pk)
        self.assertEqual(self.act(study, 'listen').status_code, 409)
        for _ in range(2): self.assertEqual(self.act(study, 'listen', permission='yes').status_code, 302)
        self.assertEqual(CaptureSpeech.objects.count(), 1)
        for _ in range(2): practice.run(study.pk)
        self.assertEqual(self.tts.call_count, 1)
        self.assertEqual(self.review.call_count, 1)
        self.assertEqual(CaptureSpeech.objects.get().status, 'ready')
        self.assertEqual((Entry.objects.count(), Contribution.objects.count()), self.before)
        self.assertEqual(self.client.get(self.url('capture-media', study.pk, 'feedback')).status_code, 200)
        study.refresh_from_db()
        self.assertIn('practice_feedback', study.usage)

    def test_draft_recovery_excludes_inactive_input_and_remembers_mode_without_changing_contribution_mode(self):
        ContributionPreference.objects.create(user=self.user, dictionary=self.d, mode='guided', consent={'test': 'kept'})
        study = self.attempt(description=ORIGINAL, audio=audio())
        self.assertEqual(study.recording_path, '')
        row = ContributionPreference.objects.get(user=self.user, dictionary=self.d)
        self.assertEqual(row.mode, 'guided')
        self.assertEqual(row.consent['test'], 'kept')
        self.assertEqual(row.consent['_picture_practice']['mode'], 'text')
        from community_dictionary.learning import preference, save_preference
        from django.test import RequestFactory
        request = RequestFactory().get('/'); request.user = self.user; request.session = {}
        self.assertNotIn('_picture_practice', preference(request, self.d)['consent'])
        save_preference(request, self.d, 'manual')
        self.assertEqual(practice.choices(self.user, self.d)['mode'], 'text')
        page = self.client.get(self.url('picture-practice')+f'?image={self.photo.pk}')
        self.assertEqual(page.context['form'].initial['mode'], 'text')
        self.assertEqual(self.start(description='a'*256).status_code, 200)

    def test_credit_quota_consent_and_expired_quote_precede_work(self):
        self.assertEqual(self.start(permission='').status_code, 200)
        self.assertEqual(self.start(quote='bad').status_code, 200)
        with override_settings(COMMUNITY_DICTIONARY_CAPTURE_DAILY_LIMIT=0):
            self.assertEqual(self.start().status_code, 200)
        with patch('community_dictionary.picture_practice.has_minimum_balance_for_compile', return_value=False):
            self.assertEqual(self.start().status_code, 200)
        self.assertEqual(PictureCapture.objects.count(), 0)
        self.review.assert_not_called()
        self.asr.assert_not_called()

    def test_other_accounts_and_legacy_publication_cannot_access_or_publish_attempt(self):
        study = self.feedback()
        self.assertEqual(self.client.post(self.url('capture-action', study.pk), {'action': 'confirm', 'permission': 'yes'}).status_code, 409)
        self.assertRedirects(self.client.get(self.url('capture-detail', study.pk)), self.url('picture-practice-detail', study.pk))
        with self.assertRaises(Conflict): capture.publish(study.pk, self.user)
        capture.prepare(study.pk)
        self.ai.assert_not_called()
        for user in [self.owner, self.outsider]:
            self.client.force_login(user)
            self.assertEqual(self.client.get(self.url('picture-practice-detail', study.pk)).status_code, 404)
            self.assertEqual(self.client.get(self.url('capture-media', study.pk, 'picture')).status_code, 404)
        self.assertEqual(Client().get(self.url('picture-practice-detail', study.pk)).status_code, 302)
        self.client.force_login(self.user)
        secure = Client(enforce_csrf_checks=True); secure.force_login(self.user)
        self.assertEqual(secure.post(self.url('picture-practice-action', study.pk), {'action': 'listen'}).status_code, 403)
        self.assertEqual(self.client.get(self.url('picture-practice-action', study.pk)).status_code, 405)

    def test_withdrawn_image_participation_and_expiry_block_private_media(self):
        study = self.feedback()
        self.photo.status = 'withdrawn'; self.photo.save()
        self.assertEqual(self.client.get(self.url('capture-media', study.pk, 'picture')).status_code, 404)
        self.assertEqual(self.act(study, 'listen', permission='yes').status_code, 409)
        self.photo.status = 'accepted'; self.photo.save()
        Participation.objects.create(dictionary=self.d, user=self.user, withdrawn=True)
        self.assertEqual(self.client.get(self.url('picture-practice-detail', study.pk)).status_code, 404)

    def test_source_withdrawal_during_provider_call_discards_result_but_records_usage(self):
        study = self.attempt()
        def withdraw(*args, **kwargs):
            self.photo.status = 'withdrawn'; self.photo.save()
            return fixtures.response(FEEDBACK)
        self.review.side_effect = withdraw
        practice.run(study.pk)
        study.refresh_from_db()
        self.assertEqual(study.status, 'failed')
        self.assertNotIn('feedback', study.result['practice'])
        self.assertIn('practice_feedback', study.usage)
        self.assertEqual((Entry.objects.count(), Contribution.objects.count()), self.before)

    def test_failures_not_retried_and_cleared_attempt_stays_in_allowance(self):
        study = self.attempt('voice')
        self.asr.side_effect = TimeoutError()
        practice.run(study.pk); practice.run(study.pk)
        study.refresh_from_db(); self.assertEqual(study.status, 'failed')
        self.assertEqual(self.asr.call_count, 1)
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.act(study, 'discard').status_code, 302)
        study.refresh_from_db()
        self.assertEqual(study.result, {})
        self.assertEqual(study.recording_path, '')
        self.assertEqual(capture_limits.usage(self.d)['used'], 1)

    def test_text_feedback_does_not_require_audio_configuration(self):
        self.d.tts_enabled = False; self.d.save()
        study = self.feedback()
        self.assertNotContains(self.client.get(self.url('picture-practice-detail', study.pk)), 'Listen to this version')
        self.assertEqual(self.act(study, 'listen', permission='yes').status_code, 409)

    def test_picture_selection_excludes_pending_style_archived_and_uses_category(self):
        pending = self.image(); pending.status='pending'; pending.save()
        style = self.image(); self.d.image_style=style; self.d.save()
        archived = self.image(); archived.entry.archived=True; archived.entry.save()
        self.assertEqual(list(practice.images(self.d).values_list('pk', flat=True)), [self.photo.pk])
        self.assertEqual(self.client.get(self.url('picture-practice')+'?category=missing').status_code, 200)
        self.assertEqual(self.client.post(self.url('picture-practice'), {'image': pending.pk}).status_code, 404)

    def test_browser_actual_submit_and_recovery(self):
        node = shutil.which('node')
        if not node or subprocess.run([node, '-e', "require('jsdom')"], capture_output=True).returncode:
            self.skipTest('Optional jsdom is unavailable')
        page = self.client.get(self.url('picture-practice')+f'?image={self.photo.pk}')
        root = Path(__file__).resolve().parent.parent
        payload = {'html': page.content.decode(), 'app': (root/'static/community_dictionary/app.js').read_text(),
            'controller': (root/'static/community_dictionary/picture_practice.js').read_text()}
        result = subprocess.run([node, str(Path(__file__).with_name('picture_practice_browser.cjs'))],
            input=json.dumps(payload), text=True, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)


class PracticeFeedbackValidationTests(TestCase):
    def test_schema_requires_understanding_and_explained_changes(self):
        self.assertEqual(practice.parse(fixtures.response(FEEDBACK), ORIGINAL), FEEDBACK)
        for bad in [{**FEEDBACK, 'understood': ''}, {**FEEDBACK, 'corrections': []},
                    {**FEEDBACK, 'extra': 'x'}, {**FEEDBACK, 'text': 'a'*256}]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                practice.parse(fixtures.response(bad), ORIGINAL)
