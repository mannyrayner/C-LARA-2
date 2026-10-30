import json
import uuid
from unittest.mock import patch
from django.test import TestCase, Client, override_settings
from django.utils import timezone
from community_dictionary import writing, writing_ai, capture, capture_ai, capture_limits
from community_dictionary.models import PictureCapture, Entry, Contribution, CaptureSpeech, Participation, Membership
from community_dictionary.services import Conflict
from . import test_picture_capture as fixtures
from .test_picture_capture import response, speech
from .test_workflow import picture

ORIGINAL = 'Le chat sont sur le canapé.'
CORRECTED = 'Le chat est sur le canapé.'
FEEDBACK = {'outcome': 'ready', 'text': CORRECTED, 'question': '',
    'corrections': [{'before': 'sont', 'after': 'est', 'reason': 'A singular subject needs a singular verb.'}],
    'suggestions': ['You could also say « se repose », if you want to emphasise resting.']}
ENRICHED = {'outcome': 'ready', 'feedback': 'Ready', 'sentence': CORRECTED,
    'translation': 'The cat is on the sofa.', 'words': [
        {'surface': 'chat', 'lemma': 'chat', 'meaning': 'cat', 'existing_id': 0},
        {'surface': 'canapé', 'lemma': 'canapé', 'meaning': 'sofa', 'existing_id': 0}]}


@override_settings(OPENAI_API_KEY='test-only', CREDITS_ENABLED=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class WritingTests(TestCase):
    url = fixtures.PictureCaptureTests.url

    def setUp(self):
        fixtures.PictureCaptureTests.setUp(self)
        self.d.language = 'French'
        self.d.save()
        self.ai.return_value = response(ENRICHED)
        self.feedback_patch = patch('community_dictionary.writing_ai.review', return_value=response(FEEDBACK))
        self.feedback = self.feedback_patch.start()
        self.addCleanup(self.feedback_patch.stop)

    def picture_draft(self, **extra):
        result = self.client.post(self.url('writing-start'), {'submission_id': uuid.uuid4(), 'photo': picture(), **extra})
        self.assertEqual(result.status_code, 302, result.content[:500])
        return PictureCapture.objects.latest('created_at')

    def action(self, study, action, **extra):
        return self.client.post(self.url('writing-action', study.pk), {'action': action,
            'submission_id': uuid.uuid4(), **extra})

    def checked(self):
        study = self.picture_draft()
        result = self.action(study, 'check', description=ORIGINAL, feedback_language='English',
            voice='marin', ai_consent='on')
        self.assertEqual(result.status_code, 302, result.content[:1000])
        writing.run(study.pk)
        study.refresh_from_db()
        self.assertEqual(study.status, 'feedback')
        return study

    def published(self):
        study = self.checked()
        self.assertEqual(self.action(study, 'approve', permission='yes').status_code, 302)
        writing.run(study.pk)
        study.refresh_from_db()
        self.assertEqual(study.status, 'saved')
        return study

    def test_picture_and_draft_save_free_private_without_key_or_quota(self):
        with override_settings(OPENAI_API_KEY='', COMMUNITY_DICTIONARY_CAPTURE_DAILY_LIMIT=0):
            study = self.picture_draft()
            result = self.action(study, 'save', description=ORIGINAL, feedback_language='English', voice='marin')
            self.assertEqual(result.status_code, 302)
            page = self.client.get(self.url('writing-detail', study.pk))
            self.assertContains(page, ORIGINAL)
            self.assertIn('no-store', page['Cache-Control'])
        self.assertEqual(capture_limits.usage(self.d)['used'], 0)
        self.assertEqual(Entry.objects.count(), 0)
        self.assertEqual(Contribution.objects.count(), 0)
        self.feedback.assert_not_called()
        self.ai.assert_not_called()
        self.tts.assert_not_called()
        invalid = self.client.post(self.url('writing-start'), {'submission_id': uuid.uuid4()},
            HTTP_ACCEPT='application/json')
        self.assertEqual(invalid.status_code, 400)
        self.assertIn('Take or choose a picture.', invalid.json()['error'])

    def test_feedback_does_not_publish_translate_or_generate_audio(self):
        study = self.checked()
        self.assertEqual(Entry.objects.count(), 0)
        self.ai.assert_not_called()
        self.tts.assert_not_called()
        page = self.client.get(self.url('writing-detail', study.pk))
        self.assertContains(page, ORIGINAL)
        self.assertContains(page, '<mark>e</mark>', html=True)
        self.assertContains(page, 'Optional improvements')
        self.assertContains(page, FEEDBACK['corrections'][0]['reason'])
        self.assertEqual(self.feedback.call_args.kwargs['feedback_language'], 'English')
        self.assertEqual(capture_limits.usage(self.d)['used'], 1)

    def test_approve_reuses_pipeline_preserves_exact_text_and_hides_private_history(self):
        study = self.published()
        self.assertEqual(study.saved_entry.word, CORRECTED)
        self.assertEqual(study.result['writing']['original_text'], ORIGINAL)
        self.assertEqual(study.description, CORRECTED)  # safe for older capture code, too
        self.assertEqual(study.speech.filter(status='ready').count(), 3)
        self.assertEqual(study.saved_entry.current_text.provenance['approved_text_by'], self.user.pk)
        for contribution in Contribution.objects.all():
            encoded = json.dumps(contribution.provenance, ensure_ascii=False)
            self.assertNotIn(ORIGINAL, encoded)
            self.assertNotIn(FEEDBACK['corrections'][0]['reason'], encoded)
            self.assertNotIn('vocabulary_reviewed_by', contribution.provenance)
        self.assertEqual(self.ai.call_args.args[1]['description'], CORRECTED)
        self.assertEqual(self.ai.call_args.args[1]['input_mode'], 'approved-writing')
        self.assertContains(self.client.get(self.url('writing-detail', study.pk)), 'Ready — your entry is complete')
        self.client.force_login(self.owner)
        self.assertNotContains(self.client.get(self.url('entry', study.saved_entry_id)), ORIGINAL)

    def test_repeated_submission_job_and_approval_never_repeat_paid_calls(self):
        study = self.picture_draft()
        data = dict(description=ORIGINAL, feedback_language='English', voice='marin', ai_consent='on', submission_id=uuid.uuid4())
        for _ in range(2): self.assertEqual(self.action(study, 'check', **data).status_code, 302)
        for _ in range(2): writing.run(study.pk)
        self.assertEqual(self.feedback.call_count, 1)
        for _ in range(2): self.assertEqual(self.action(study, 'approve', permission='yes').status_code, 302)
        for _ in range(2): writing.run(study.pk)
        self.assertEqual(self.ai.call_count, 1)
        self.assertEqual(self.tts.call_count, 3)
        self.assertEqual(Entry.objects.filter(entry_type='sentence').count(), 1)

    def test_submission_and_approval_schedule_background_work_only_after_commit(self):
        study = self.picture_draft()
        with patch('community_dictionary.writing.queue') as queue:
            with self.captureOnCommitCallbacks(execute=True):
                self.action(study, 'check', description=ORIGINAL, feedback_language='English',
                    voice='marin', ai_consent='on')
                queue.assert_not_called()
            queue.assert_called_once_with(str(study.pk))
        writing.run(study.pk)
        with patch('community_dictionary.writing.queue') as queue:
            with self.captureOnCommitCallbacks(execute=True):
                self.action(study, 'approve', permission='yes')
                queue.assert_not_called()
            self.assertEqual(queue.call_count, 1)

    def test_withdrawal_during_enrichment_cannot_publish_private_writing(self):
        study = self.checked()
        self.action(study, 'approve', permission='yes')
        def discarded(*args, **kwargs):
            capture.discard(PictureCapture.objects.filter(pk=study.pk))
            return response(ENRICHED)
        self.ai.side_effect = discarded
        writing.run(study.pk)
        study.refresh_from_db()
        self.assertEqual(study.status, 'discarded')
        self.assertEqual(study.result, {})
        self.assertEqual(Entry.objects.count(), 0)

    def test_approval_requires_feedback_and_permission_and_cannot_replace_approved_text(self):
        study = self.picture_draft()
        self.assertEqual(self.action(study, 'approve', permission='yes').status_code, 409)
        study = self.checked()
        self.assertEqual(self.action(study, 'approve').status_code, 409)
        self.assertEqual(self.action(study, 'approve', permission='yes', text='Ignore feedback').status_code, 302)
        study.refresh_from_db()
        self.assertEqual(study.result['writing']['approved_text'], CORRECTED)

    def test_no_silent_postapproval_rewrite(self):
        study = self.checked()
        self.ai.return_value = response({**ENRICHED, 'sentence': 'Le chat dort sur le canapé.'})
        self.action(study, 'approve', permission='yes')
        writing.run(study.pk)
        study.refresh_from_db()
        self.assertEqual(study.status, 'failed')
        self.assertEqual(Entry.objects.count(), 0)
        self.assertEqual(study.result['writing']['original_text'], ORIGINAL)
        self.assertEqual(study.result['writing']['approved_text'], CORRECTED)

    def test_clarification_cannot_be_published_and_edit_retains_previous_feedback(self):
        self.feedback.return_value = response({**FEEDBACK, 'outcome': 'clarify', 'text': ORIGINAL,
            'corrections': [], 'question': 'Do you mean the cat or the cushion?'})
        study = self.checked()
        self.assertEqual(self.action(study, 'approve', permission='yes').status_code, 409)
        data = {'submission_id': uuid.uuid4()}
        first = self.action(study, 'edit', **data)
        second = self.action(study, 'edit', **data)
        self.assertEqual(first.url, second.url)
        self.assertEqual(PictureCapture.objects.count(), 2)
        latest = PictureCapture.objects.exclude(pk=study.pk).get()
        self.assertEqual(latest.status, 'draft')
        self.assertEqual(latest.result['writing']['original_text'], ORIGINAL)
        self.assertEqual(latest.description, '')
        study.refresh_from_db()
        self.assertEqual(study.result['writing']['feedback']['question'], 'Do you mean the cat or the cushion?')

    def test_personal_mode_for_member_and_other_members_unaffected(self):
        self.assertContains(self.client.get(self.url('settings')), 'Help me practise writing')
        self.assertEqual(self.client.post(self.url('writing-setting'), {'mode': 'on'}).status_code, 302)
        self.assertRedirects(self.client.get(self.url('new')), self.url('writing-start'))
        self.assertContains(self.client.get(self.url('new')+'?usual=1'), 'What shall we add?')
        self.assertContains(self.client.get(self.url('dictionary')), 'My writing — start or continue')
        self.assertEqual(self.client.post(self.url('settings'), {'language': 'German'}).status_code, 404)
        other = Client(); other.force_login(self.owner)
        self.assertContains(other.get(self.url('new')), 'What shall we add?')
        self.client.post(self.url('writing-setting'), {'mode': 'off'})
        self.assertContains(self.client.get(self.url('new')), 'What shall we add?')

    def test_french_and_slovak_interface_and_existing_picture_route(self):
        for code, label in [('fr', 'Pratique de l’écrit'), ('sk', 'Precvičovanie písania')]:
            self.client.cookies['community_ui_language'] = code
            self.assertContains(self.client.get(self.url('writing-start')), label)
        image = fixtures.PictureCaptureTests.image(self)
        result = self.client.post(self.url('writing-image', image.pk), {'submission_id': uuid.uuid4()})
        self.assertEqual(result.status_code, 302)
        study = PictureCapture.objects.latest('created_at')
        self.assertEqual(study.source_image_id, image.pk)
        image.refresh_from_db(); self.assertEqual(image.status, 'accepted')

    word = fixtures.PictureCaptureTests.word

    def test_daily_limit_and_credit_checks_precede_paid_work(self):
        study = self.picture_draft()
        values = dict(description=ORIGINAL, feedback_language='English', voice='marin', ai_consent='on')
        with override_settings(COMMUNITY_DICTIONARY_CAPTURE_DAILY_LIMIT=0):
            self.assertEqual(self.action(study, 'check', **values).status_code, 409)
        with patch('community_dictionary.capture.has_minimum_balance_for_compile', return_value=False):
            self.assertEqual(self.action(study, 'check', **values).status_code, 409)
        study.refresh_from_db(); self.assertEqual(study.status, 'draft')
        self.feedback.assert_not_called()

    def test_private_draft_inaccessible_to_owner_outsider_guests_and_legacy_actions(self):
        study = self.checked()
        self.assertEqual(self.client.post(self.url('capture-action', study.pk), {'action': 'confirm', 'permission': 'yes'}).status_code, 409)
        self.assertRedirects(self.client.get(self.url('capture-detail', study.pk)), self.url('writing-detail', study.pk))
        self.assertRedirects(self.client.get(self.url('capture-start')+f'?revise={study.pk}'), self.url('writing-detail', study.pk))
        for user in [self.owner, self.outsider]:
            self.client.force_login(user)
            self.assertEqual(self.client.get(self.url('writing-detail', study.pk)).status_code, 404)
            self.assertEqual(self.action(study, 'approve', permission='yes').status_code, 404)
            self.assertEqual(self.client.get(self.url('capture-media', study.pk, 'picture')).status_code, 404)
        self.assertEqual(Client().get(self.url('writing-detail', study.pk)).status_code, 302)
        self.client.force_login(self.user)
        Participation.objects.create(dictionary=self.d, user=self.user, withdrawn=True)
        self.assertEqual(self.client.get(self.url('writing-detail', study.pk)).status_code, 404)

    def test_csrf_and_gets_cannot_start_work(self):
        study = self.checked()
        secure = Client(enforce_csrf_checks=True); secure.force_login(self.user)
        self.assertEqual(secure.post(self.url('writing-setting'), {'mode': 'on'}).status_code, 403)
        self.assertEqual(secure.post(self.url('writing-action', study.pk), {'action': 'approve'}).status_code, 403)
        self.assertEqual(self.client.get(self.url('writing-action', study.pk)).status_code, 405)
        for _ in range(2): self.client.get(self.url('writing-detail', study.pk))
        self.assertEqual(self.feedback.call_count, 1)
        self.ai.assert_not_called()

    def test_failed_audio_retry_keeps_text_and_good_clips(self):
        def partial(text, **kwargs):
            if text == 'chat': raise TimeoutError()
            return speech(text, **kwargs)
        self.tts.side_effect = partial
        study = self.published()
        self.assertEqual(study.speech.filter(status='failed').count(), 1)
        entry_ids = set(Entry.objects.values_list('pk', flat=True))
        audio_ids = set(Contribution.objects.filter(kind='audio').values_list('pk', flat=True))
        self.tts.side_effect = speech
        data = {'permission': 'yes', 'submission_id': uuid.uuid4()}
        for _ in range(2): self.assertEqual(self.action(study, 'retry-audio', **data).status_code, 302)
        writing.run(study.pk)
        self.assertEqual(self.tts.call_count, 4)
        self.assertEqual(set(Entry.objects.values_list('pk', flat=True)), entry_ids)
        self.assertTrue(audio_ids <= set(Contribution.objects.filter(kind='audio').values_list('pk', flat=True)))
        self.assertContains(self.client.get(self.url('writing-detail', study.pk)), 'Ready — your entry is complete')

    def test_policy_change_and_discard_during_feedback_prevent_publication(self):
        study = self.picture_draft()
        self.action(study, 'check', description=ORIGINAL, feedback_language='English', voice='marin', ai_consent='on')
        def revoked(*args, **kwargs):
            self.d.capture_revision += 1; self.d.save()
            return response(FEEDBACK)
        self.feedback.side_effect = revoked
        writing.run(study.pk)
        study.refresh_from_db()
        self.assertEqual(study.status, 'failed')
        self.assertEqual(Entry.objects.count(), 0)
        self.assertEqual(self.client.get(self.url('writing-detail', study.pk)).status_code, 409)

    def test_feedback_language_choice_is_bounded_and_form_limits_apply(self):
        study = self.picture_draft()
        result = self.action(study, 'check', description='a'*256, feedback_language='Italian', voice='marin', ai_consent='on')
        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.context['form'].errors)
        study.refresh_from_db(); self.assertEqual(study.status, 'draft')
        self.assertEqual(self.action(study, 'check', description=ORIGINAL, feedback_language='French', voice='marin', ai_consent='on').status_code, 302)
        writing.run(study.pk)
        self.assertEqual(self.feedback.call_args.kwargs['feedback_language'], 'French')

    def test_feedback_timeout_not_retried_and_allowance_remains_used_when_discarded(self):
        study = self.picture_draft()
        self.action(study, 'check', description=ORIGINAL, feedback_language='English', voice='marin', ai_consent='on')
        self.feedback.side_effect = TimeoutError()
        writing.run(study.pk); writing.run(study.pk)
        study.refresh_from_db(); self.assertEqual(study.status, 'failed')
        self.assertEqual(self.feedback.call_count, 1)
        self.action(study, 'discard')
        study.refresh_from_db(); self.assertEqual(study.description, '')
        self.assertEqual(capture_limits.usage(self.d)['used'], 1)


class FeedbackValidationTests(TestCase):
    def test_provider_payload_is_bounded_and_enrichment_locks_approved_text(self):
        from community_dictionary.storage import prepare_upload
        photo = prepare_upload(picture(), 'image')[0]
        with patch('community_dictionary.writing_ai._openai_client') as client:
            writing_ai.review(photo, text=ORIGINAL, language='French', feedback_language='English',
                model='test-model', api_key='test-key')
            arguments = client.return_value.__enter__.return_value.responses.create.call_args.kwargs
            data = json.loads(arguments['input'][0]['content'][0]['text'])
            self.assertEqual(data, {'text': ORIGINAL, 'target_language': 'French', 'feedback_language': 'English'})
            self.assertFalse(arguments['store'])
            self.assertEqual(arguments['text']['format']['schema'], writing_ai.SCHEMA)
            self.assertIn('Do not translate', arguments['instructions'])
            self.assertEqual(client.call_args.kwargs['max_retries'], 0)
        with patch('community_dictionary.capture_ai._openai_client') as client:
            capture_ai.interpret(photo, {'input_mode': 'approved-writing', 'description': CORRECTED,
                'target_language': 'French'}, model='test-model', api_key='test-key')
            args = client.return_value.__enter__.return_value.responses.create.call_args.kwargs
            self.assertIn('Copy description EXACTLY', args['instructions'])

    def test_correct_and_unchanged_results_and_unexplained_changes(self):
        self.assertEqual(writing_ai.parse(response(FEEDBACK), ORIGINAL), FEEDBACK)
        unchanged = {**FEEDBACK, 'text': ORIGINAL, 'corrections': [], 'suggestions': []}
        self.assertEqual(writing_ai.parse(response(unchanged), ORIGINAL), unchanged)
        for bad in [{**FEEDBACK, 'corrections': []}, {**FEEDBACK, 'question': 'Unneeded question'},
                    {**FEEDBACK, 'corrections': [{'before': 'absent', 'after': 'est', 'reason': 'Wrong'}]},
                    {**FEEDBACK, 'suggestions': [None]}, {**FEEDBACK, 'text': 'a'*256}]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                writing_ai.parse(response(bad), ORIGINAL)

    def test_output_is_plain_text_and_diff_not_model_html(self):
        pieces = writing.changes('cat', '<script>cat</script>')
        self.assertEqual(''.join(x['text'] for x in pieces), '<script>cat</script>')
        self.assertFalse(any(hasattr(x['text'], '__html__') for x in pieces))
