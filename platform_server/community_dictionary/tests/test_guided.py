import json
import uuid
from unittest.mock import patch
from django.core import signing
from django.test import TestCase, Client, override_settings
from community_dictionary import capture, capture_ai, capture_limits, guided, guided_ai, learning
from community_dictionary.forms import DictionaryForm
from community_dictionary.guided_views import SALT
from community_dictionary.models import (PictureCapture, Entry, Contribution, ContributionPreference,
    DictionaryLearningSettings, Dictionary, Participation)
from community_dictionary.storage import path_for, prepare_upload
from . import test_picture_capture as fixtures
from .test_picture_capture import response, speech, RESULT
from .test_workflow import picture

DESCRIPTION = RESULT['translation']
SUGGESTION = {'outcome': 'ready', 'description': DESCRIPTION, 'question': ''}


@override_settings(OPENAI_API_KEY='test-only', CREDITS_ENABLED=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class GuidedTests(TestCase):
    url = fixtures.PictureCaptureTests.url
    word = fixtures.PictureCaptureTests.word

    def setUp(self):
        fixtures.PictureCaptureTests.setUp(self)
        self.describer = patch('community_dictionary.guided_ai.describe', return_value=response(SUGGESTION)).start()
        self.assertEqual(self.choose().status_code, 302)

    def choose(self, **extra):
        values = guided.consent_values(self.user, self.d)
        return self.client.post(self.url('contribution-setting'), {'mode': 'guided', 'permission': 'on',
            'quote': signing.dumps(values, salt=SALT), **extra})

    def start(self, **extra):
        r = self.client.post(self.url('guided-start'), {'submission_id': uuid.uuid4(), 'photo': picture(), **extra})
        self.assertEqual(r.status_code, 302, r.content[:1000])
        return PictureCapture.objects.latest('created_at')

    def action(self, study, action, **extra):
        return self.client.post(self.url('guided-action', study.pk),
            {'action': action, 'submission_id': uuid.uuid4(), **extra})

    def described(self):
        study = self.start(); guided.run(study.pk); study.refresh_from_db()
        self.assertEqual(study.status, 'feedback')
        return study

    def published(self):
        study = self.described()
        self.assertEqual(self.action(study, 'approve', description=DESCRIPTION).status_code, 302)
        guided.run(study.pk); study.refresh_from_db()
        self.assertEqual(study.status, 'saved')
        return study

    def test_standing_consent_persists_across_logins_and_is_personal(self):
        self.assertEqual(self.choose(permission='').status_code, 409)
        self.assertEqual(self.choose(quote='tampered').status_code, 409)
        self.client.logout(); self.client.force_login(self.user)
        self.assertRedirects(self.client.get(self.url('new')), self.url('guided-start'))
        self.assertContains(self.client.get(self.url('settings')), 'My way of adding pictures')
        other = Client(); other.force_login(self.owner)
        self.assertContains(other.get(self.url('new')), 'What shall we add?')
        self.assertEqual(self.client.post(self.url('settings'), {'generation_level': 'advanced'}).status_code, 404)
        self.client.post(self.url('contribution-setting'), {'mode': 'manual'})
        self.client.logout(); self.client.force_login(self.user)
        self.assertContains(self.client.get(self.url('new')), 'What shall we add?')
        self.assertFalse(ContributionPreference.objects.get(user=self.user, dictionary=self.d).consent)
        self.client.post(self.url('writing-setting'), {'mode': 'on'})
        self.client.logout(); self.client.force_login(self.user)
        self.assertRedirects(self.client.get(self.url('new')), self.url('writing-start'))

    def test_upload_schedules_only_initial_description_after_commit_and_no_public_entry(self):
        with patch('community_dictionary.guided.queue') as queue:
            with self.captureOnCommitCallbacks(execute=True):
                study = self.start(); queue.assert_not_called()
            queue.assert_called_once_with(study.pk)
        self.assertTrue(path_for(study.file_path).is_file())
        self.assertContains(self.client.get(self.url('guided-start')), 'In progress')
        self.assertEqual(Entry.objects.count(), 0)
        guided.run(study.pk)
        self.ai.assert_not_called(); self.tts.assert_not_called()
        self.assertEqual(self.describer.call_args.args[1]['explanation_language'], 'English')
        self.assertNotIn('target_language', self.describer.call_args.args[1])
        page = self.client.get(self.url('guided-detail', study.pk))
        self.assertContains(page, DESCRIPTION)
        self.assertContains(page, 'Use this description and finish')
        self.assertIn('no-store', page['Cache-Control'])

    def test_approval_automatically_finishes_and_labels_provenance_truthfully(self):
        study = self.published()
        self.assertEqual(study.saved_entry.word, RESULT['sentence'])
        self.assertEqual(study.saved_entry.meaning, DESCRIPTION)
        self.assertEqual(Entry.objects.filter(entry_type='sentence').count(), 1)
        self.assertFalse(Entry.objects.filter(word='').exists())
        self.assertEqual(study.speech.filter(status='ready').count(), 5)
        provenance = study.saved_entry.current_text.provenance
        self.assertTrue(provenance['target_language_generated_automatically'])
        self.assertNotIn('vocabulary_reviewed_by', provenance)
        self.assertNotIn('consent', provenance)
        self.assertContains(self.client.get(self.url('guided-detail', study.pk)), 'Ready — your entry is complete')

    def test_repeated_posts_workers_and_approval_are_idempotent(self):
        token = uuid.uuid4()
        study = self.start(submission_id=token)
        other = self.start(submission_id=token)
        self.assertEqual(study.pk, other.pk)
        for _ in range(2): guided.run(study.pk)
        for _ in range(2): self.action(study, 'approve', description=DESCRIPTION)
        for _ in range(2): guided.run(study.pk)
        self.assertEqual(self.describer.call_count, 1)
        self.assertEqual(self.ai.call_count, 1)
        self.assertEqual(self.tts.call_count, 5)
        self.assertEqual(capture_limits.usage(self.d)['used'], 1)
        self.assertEqual(self.action(study, 'approve', description='Different text').status_code, 409)

    def test_clarification_and_changed_focus_are_in_explanation_language(self):
        self.describer.return_value = response({'outcome': 'clarify', 'description': '', 'question': 'The cat or the chair?'})
        study = self.described()
        self.assertContains(self.client.get(self.url('guided-detail', study.pk)), 'The cat or the chair?')
        self.assertEqual(self.action(study, 'approve', description='').status_code, 200)
        self.assertEqual(self.action(study, 'approve', description=DESCRIPTION).status_code, 302)
        guided.run(study.pk)
        data = self.ai.call_args.args[1]
        self.assertEqual(data['description'], DESCRIPTION)
        self.assertEqual(data['input_mode'], 'approved-picture')
        self.assertEqual(data['input_language'], 'English')

    def test_nonmatching_final_meaning_stops_without_publication(self):
        study = self.described()
        self.ai.return_value = response({**RESULT, 'translation': 'A bird is flying.'})
        self.action(study, 'approve', description=DESCRIPTION)
        guided.run(study.pk); study.refresh_from_db()
        self.assertEqual(study.status, 'failed')
        self.assertEqual(Entry.objects.count(), 0)
        self.assertEqual(study.result['guided']['approved_description'], DESCRIPTION)

    def test_quota_and_insufficient_credit_keep_saved_picture_without_api_request(self):
        for blocker in [override_settings(COMMUNITY_DICTIONARY_CAPTURE_DAILY_LIMIT=0),
                        patch('community_dictionary.capture.has_minimum_balance_for_compile', return_value=False)]:
            with blocker:
                study = self.start()
                self.assertEqual(study.status, 'draft')
                self.assertTrue(path_for(study.file_path).is_file())
                self.assertEqual(capture_limits.usage(self.d)['used'], 0)
                self.assertContains(self.client.get(self.url('guided-detail', study.pk)), 'AI processing has not started')
        self.describer.assert_not_called(); self.ai.assert_not_called()
        self.action(study, 'continue'); guided.run(study.pk)
        self.assertEqual(self.describer.call_count, 1)

    def test_changed_prices_require_new_standing_consent_before_spend(self):
        old = guided.consent_values(self.user, self.d)
        with patch('community_dictionary.guided.consent_values', return_value={**old, 'model': 'new-model'}):
            study = self.start()
        self.assertEqual(study.status, 'draft')
        self.describer.assert_not_called()

    def test_failed_description_retry_is_explicit_counted_and_idempotent(self):
        self.describer.side_effect = TimeoutError()
        study = self.start()
        guided.run(study.pk); guided.run(study.pk)
        study.refresh_from_db(); self.assertEqual(study.status, 'failed')
        self.assertEqual(self.describer.call_count, 1)
        self.describer.side_effect = None
        token = uuid.uuid4()
        a = self.action(study, 'retry', submission_id=token)
        b = self.action(study, 'retry', submission_id=token)
        self.assertEqual(a.url, b.url)
        latest = PictureCapture.objects.latest('created_at')
        guided.run(latest.pk)
        self.assertEqual(capture_limits.usage(self.d)['used'], 2)
        self.action(study, 'discard')
        self.assertEqual(capture_limits.usage(self.d)['used'], 2)

    def test_failed_enrichment_retry_keeps_meaning_without_second_description_call(self):
        study = self.described()
        self.ai.side_effect = TimeoutError()
        self.action(study, 'approve', description=DESCRIPTION); guided.run(study.pk)
        self.ai.side_effect = None
        self.action(study, 'retry')
        latest = PictureCapture.objects.exclude(pk=study.pk).get()
        self.assertEqual(latest.status, 'feedback')
        self.assertEqual(latest.result['guided']['suggestion']['description'], DESCRIPTION)
        self.assertEqual(self.describer.call_count, 1)
        with override_settings(COMMUNITY_DICTIONARY_CAPTURE_DAILY_LIMIT=1):
            self.assertEqual(self.action(latest, 'approve', description=DESCRIPTION).status_code, 409)
        self.action(latest, 'approve', description=DESCRIPTION); guided.run(latest.pk)
        self.assertEqual(capture_limits.usage(self.d)['used'], 2)
        self.assertEqual(Entry.objects.filter(entry_type='sentence').count(), 1)

    def test_failed_audio_retry_only_generates_missing_clip(self):
        def partial(text, **kwargs):
            if text == 'katt': raise TimeoutError()
            return speech(text, **kwargs)
        self.tts.side_effect = partial
        study = self.published()
        good = set(Contribution.objects.filter(kind='audio').values_list('pk', flat=True))
        self.tts.side_effect = speech
        token = uuid.uuid4()
        for _ in range(2): self.action(study, 'retry-audio', submission_id=token)
        guided.run(study.pk)
        self.assertEqual(self.tts.call_count, 6)
        self.assertTrue(good <= set(Contribution.objects.filter(kind='audio').values_list('pk', flat=True)))
        self.assertContains(self.client.get(self.url('guided-detail', study.pk)), 'Ready — your entry is complete')

    def test_privacy_csrf_legacy_routes_and_withdrawal(self):
        study = self.described()
        self.assertEqual(self.client.post(self.url('capture-action', study.pk), {'action': 'confirm', 'permission': 'yes'}).status_code, 409)
        self.assertRedirects(self.client.get(self.url('capture-detail', study.pk)), self.url('guided-detail', study.pk))
        self.assertRedirects(self.client.get(self.url('capture-start')+f'?revise={study.pk}'), self.url('guided-detail', study.pk))
        secure = Client(enforce_csrf_checks=True); secure.force_login(self.user)
        self.assertEqual(secure.post(self.url('guided-action', study.pk), {'action': 'approve', 'description': DESCRIPTION}).status_code, 403)
        self.assertEqual(self.client.get(self.url('guided-action', study.pk)).status_code, 405)
        for other in [self.owner, self.outsider]:
            self.client.force_login(other)
            self.assertEqual(self.client.get(self.url('guided-detail', study.pk)).status_code, 404)
            self.assertEqual(self.client.get(self.url('capture-media', study.pk, 'picture')).status_code, 404)
        self.client.force_login(self.user)
        Participation.objects.create(dictionary=self.d, user=self.user, withdrawn=True)
        self.assertEqual(self.action(study, 'approve', description=DESCRIPTION).status_code, 404)
        self.assertEqual(self.client.post(self.url('contribution-setting'), {'mode': 'manual'}).status_code, 404)

    def test_discard_during_provider_call_cannot_resurrect_preview_or_publish(self):
        study = self.start()
        def discard(*args, **kwargs):
            capture.discard(PictureCapture.objects.filter(pk=study.pk)); return response(SUGGESTION)
        self.describer.side_effect = discard
        guided.run(study.pk); study.refresh_from_db()
        self.assertEqual(study.status, 'discarded')
        self.assertEqual(study.result, {})
        self.assertEqual(Entry.objects.count(), 0)

    def test_existing_picture_attribution_and_no_cross_dictionary_access(self):
        image = fixtures.PictureCaptureTests.image(self)
        self.assertEqual(self.client.post(self.url('guided-image', image.pk), {'submission_id': uuid.uuid4()}).status_code, 302)
        study = PictureCapture.objects.latest('created_at')
        guided.run(study.pk); self.action(study, 'approve', description=DESCRIPTION); guided.run(study.pk)
        study.refresh_from_db()
        self.assertEqual(study.saved_entry.selected_image.author_id, self.owner.pk)
        self.assertEqual(study.saved_entry.selected_image.shared_from_id, image.pk)
        image.status = 'private'; image.save()
        self.assertEqual(self.client.get(self.url('guided-image', image.pk)).status_code, 404)

    def test_dictionary_level_affects_new_generations_only_and_owner_controls_it(self):
        DictionaryLearningSettings.objects.create(dictionary=self.d, level='low_intermediate')
        study = self.described()
        self.assertEqual(self.describer.call_args.args[1]['generation_level'], 'low_intermediate')
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(self.url('settings'), {'name': self.d.name, 'language': self.d.language,
            'explanation_language': 'English', 'text_direction': 'auto', 'tts_enabled': 'on',
            'sentence_capture_enabled': 'on', 'photo_ai_enabled': 'on', 'generation_level': 'advanced'}).status_code, 302)
        self.d.refresh_from_db()
        self.assertEqual(learning.level(self.d), 'advanced')
        self.assertEqual(self.d.capture_revision, 0)
        self.client.force_login(self.user)
        self.action(study, 'approve', description=DESCRIPTION); guided.run(study.pk)
        self.assertEqual(self.ai.call_args.args[1]['generation_level'], 'low_intermediate')
        self.assertEqual(study.result['guided']['level'], 'low_intermediate')

    def test_translated_interface_and_saved_previews_remain_available_after_switch(self):
        study = self.described()
        for code, label in [('fr', 'Image, confirmation et résultat'), ('sk', 'Obrázok, potvrdenie a dokončenie')]:
            self.client.cookies['community_ui_language'] = code
            self.assertContains(self.client.get(self.url('guided-detail', study.pk)), label)
        self.client.post(self.url('contribution-setting'), {'mode': 'manual'})
        self.assertContains(self.client.get(self.url('guided-start')), DESCRIPTION)
        self.assertEqual(self.client.post(self.url('guided-start'), {'submission_id': uuid.uuid4(), 'photo': picture()}).status_code, 409)
        self.assertEqual(self.client.get(self.url('guided-detail', study.pk)).status_code, 200)

    def test_creation_level_default_validation_and_persistence(self):
        from django.urls import reverse
        data = {'name': 'Test level', 'language': 'Swedish', 'generation_level': 'high_intermediate'}
        self.assertEqual(self.client.post(reverse('community_dictionary:home'), data).status_code, 302)
        dictionary = Dictionary.objects.get(name='Test level')
        self.assertEqual(learning.level(dictionary), 'high_intermediate')
        self.assertEqual(DictionaryForm().fields['generation_level'].initial, 'beginner')
        self.assertFalse(DictionaryForm({**data, 'generation_level': 'nonsense'}).is_valid())


class GuidedPromptTests(TestCase):
    def test_description_parser_rejects_incomplete_oversized_and_ambiguous_answers(self):
        self.assertEqual(guided_ai.parse(response(SUGGESTION)), SUGGESTION)
        for bad in [{**SUGGESTION, 'description': ''}, {**SUGGESTION, 'description': 'x'*256},
                    {**SUGGESTION, 'question': 'Extra question'}, {**SUGGESTION, 'outcome': 'clarify'},
                    {**SUGGESTION, 'extra': True}]:
            with self.assertRaises(ValueError): guided_ai.parse(response(bad))

    def test_prompts_preserve_core_content_and_approved_writing_is_not_level_rewritten(self):
        photo = prepare_upload(picture(), 'image')[0]
        for level in learning.GUIDANCE:
            with patch('community_dictionary.photo_ai._openai_client') as client:
                guided_ai.describe(photo, {'explanation_language': 'English', 'generation_level': level}, model='test', api_key='test')
                kwargs = client.return_value.__enter__.return_value.responses.create.call_args.kwargs
                self.assertIn('a puffin stays a puffin', kwargs['instructions'])
                self.assertIn(learning.GUIDANCE[level], kwargs['instructions'])
                self.assertNotIn('target_language', kwargs['input'][0]['content'][0]['text'])
                self.assertFalse(kwargs['store'])
                self.assertEqual(client.call_args.kwargs['max_retries'], 0)
        with patch('community_dictionary.capture_ai._openai_client') as client:
            capture_ai.interpret(photo, {'input_mode': 'approved-picture', 'generation_level': 'beginner',
                'target_language': 'Swedish', 'description': DESCRIPTION}, model='test', api_key='test')
            text = client.return_value.__enter__.return_value.responses.create.call_args.kwargs['instructions']
            self.assertIn('Copy description EXACTLY into translation', text)
            capture_ai.interpret(photo, {'input_mode': 'approved-writing', 'generation_level': 'beginner',
                'target_language': 'Swedish', 'description': 'Test'}, model='test', api_key='test')
            text = client.return_value.__enter__.return_value.responses.create.call_args.kwargs['instructions']
            self.assertNotIn('Approximate A1', text)
            self.assertIn('Copy description EXACTLY into sentence', text)
