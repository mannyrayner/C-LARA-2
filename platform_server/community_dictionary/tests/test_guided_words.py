"""Words stay authoritative through paid image generation and publication."""
import uuid
import time
import json
import shutil
import subprocess
from pathlib import Path
from html.parser import HTMLParser
from types import SimpleNamespace
from unittest.mock import patch
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from community_dictionary import capture, guided, learning, image_generation as images
from community_dictionary.models import ContributionPreference, Dictionary, Entry, ImageStudy, PictureCapture
from community_dictionary.services import Conflict
from community_dictionary.storage import path_for, prepare_upload
from . import test_picture_capture as fixtures
from .test_picture_capture import RESULT, response
from .test_workflow import picture


@override_settings(OPENAI_API_KEY='test-only', CREDITS_ENABLED=False,
    COMMUNITY_DICTIONARY_IMAGE_MODEL='gpt-image-2.5-sunburst',
    COMMUNITY_DICTIONARY_IMAGE_DAILY_LIMIT=20, COMMUNITY_DICTIONARY_IMAGE_ALLOWANCE_USD='0.50',
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class GuidedWordsTests(TestCase):
    url = fixtures.PictureCaptureTests.url

    def setUp(self):
        fixtures.PictureCaptureTests.setUp(self)
        self.d.image_generation_enabled = True
        self.d.save()
        self.images = patch('community_dictionary.image_generation.generate',
            return_value=(prepare_upload(picture(), 'image'), {'prompt_tokens': 100, 'completion_tokens': 10}, '')).start()
        self.describer = patch('community_dictionary.guided_ai.describe').start()
        self.asr = patch('community_dictionary.capture_ai.transcribe',
            return_value=SimpleNamespace(text=RESULT['sentence'], usage=None)).start()
        patch('community_dictionary.guided.queue').start()

    def post_words(self, **extra):
        page = self.client.get(self.url('guided-start'))
        return self.client.post(self.url('guided-start'), {'submission_id': uuid.uuid4(), 'start_with': 'words',
            'words_mode': 'text', 'words_language': 'Swedish', 'words': RESULT['sentence'],
            'picture_style': 'photo', 'words_permission': 'on',
            'words_quote': page.context['words_form']['words_quote'].value(), **extra})

    def start(self, **extra):
        r = self.post_words(**extra)
        self.assertEqual(r.status_code, 302, r.content[:1200])
        return PictureCapture.objects.latest('created_at')

    def action(self, study, action, **extra):
        return self.client.post(self.url('guided-action', study.pk),
            {'action': action, 'submission_id': uuid.uuid4(), **extra})

    def preview(self, **extra):
        study = self.start(**extra)
        guided.run(study.pk); study.refresh_from_db()
        self.assertEqual(study.status, 'feedback')
        return study

    def finish(self, study):
        self.assertEqual(self.action(study, 'approve', description=study.description).status_code, 302)
        guided.run(study.pk); study.refresh_from_db()
        return study

    def test_target_words_bypass_picture_description_and_remain_exact(self):
        study = self.preview()
        self.ai.assert_not_called(); self.describer.assert_not_called(); self.asr.assert_not_called()
        self.assertEqual(Entry.objects.count(), 0)
        self.assertTrue(path_for(study.file_path).is_file())
        self.assertEqual(self.images.call_args.args[0].subject, RESULT['sentence'])
        page = self.client.get(self.url('guided-detail', study.pk))
        self.assertContains(page, 'Use these words and finish')
        self.assertEqual(self.client.get(self.url('capture-media', study.pk, 'picture')).status_code, 200)
        self.finish(study)
        self.assertEqual(study.status, 'saved')
        self.assertEqual(study.saved_entry.word, RESULT['sentence'])
        self.assertEqual(self.ai.call_args.args[1]['input_mode'], 'approved-writing')
        self.assertEqual(self.ai.call_args.args[1]['description'], RESULT['sentence'])
        self.assertFalse(study.saved_entry.current_text.provenance['target_language_generated_automatically'])
        self.assertEqual(study.saved_entry.selected_image.provenance['origin'], 'generated')
        self.assertEqual(ImageStudy.objects.count(), 1)
        self.assertTrue(ImageStudy.objects.get().accounted)

    def test_commenting_language_words_are_preserved_in_translation(self):
        study = self.preview(words=RESULT['translation'], words_language='English')
        self.finish(study)
        self.assertEqual(study.status, 'saved')
        self.assertEqual(study.saved_entry.meaning, RESULT['translation'])
        self.assertEqual(self.ai.call_args.args[1]['input_mode'], 'approved-picture')

    def test_speech_requires_editable_transcript_confirmation_before_image_call(self):
        study = self.start(words_mode='voice', words='ignored typed draft', audio=picture_audio())
        guided.run(study.pk); study.refresh_from_db()
        self.assertEqual(study.status, 'feedback')
        self.images.assert_not_called()
        self.assertEqual(self.asr.call_args.args[1], 'sv')
        self.assertEqual(study.result['guided']['words']['stage'], 'confirm')
        self.assertContains(self.client.get(self.url('guided-detail', study.pk)), 'Correct the transcription')
        self.assertEqual(self.client.get(self.url('capture-media', study.pk, 'recording')).status_code, 200)
        corrected = 'En katt på en soffa.'
        for _ in range(2): self.assertEqual(self.action(study, 'generate', description=corrected).status_code, 302)
        for _ in range(2): guided.run(study.pk)
        study.refresh_from_db()
        self.assertEqual(study.description, corrected)
        self.assertEqual(self.images.call_count, 1)
        self.assertEqual(self.asr.call_count, 1)
        self.assertEqual(self.images.call_args.args[0].subject, corrected)

    def test_approval_cannot_change_the_words_used_for_the_picture(self):
        study = self.preview()
        self.assertEqual(self.action(study, 'approve', description='Something else').status_code, 409)
        self.assertEqual(Entry.objects.count(), 0)

    def test_rewrites_in_either_authoritative_language_fail_before_publication(self):
        for language, text, field in [('Swedish', RESULT['sentence'], 'sentence'),
                                      ('English', RESULT['translation'], 'translation')]:
            with self.subTest(language=language):
                study = self.preview(words=text, words_language=language)
                self.ai.return_value = response({**RESULT, field: 'Changed words.'})
                self.finish(study)
                self.assertEqual(study.status, 'failed')
                self.assertEqual(Entry.objects.count(), 0)
        self.assertEqual(self.images.call_count, 2)

    def test_publication_rechecks_authoritative_text(self):
        study = self.preview()
        guided.approve(study.pk, self.user, study.description)
        capture.prepare(study.pk)
        study.refresh_from_db()
        study.result['sentence'] = 'Changed after preparation.'
        study.save()
        with self.assertRaises(Conflict): capture.publish(study.pk, self.user)
        self.assertEqual(Entry.objects.count(), 0)

    def test_duplicate_submission_and_workers_buy_one_image(self):
        token = uuid.uuid4()
        quote = self.client.get(self.url('guided-start')).context['words_form']['words_quote'].value()
        study = self.start(submission_id=token, words_quote=quote)
        with patch('community_dictionary.guided_words.approved_quote', side_effect=Conflict('Expired quote')):
            self.assertEqual(self.start(submission_id=token, words_quote='refreshed quote').pk, study.pk)
        self.assertEqual(self.post_words(submission_id=token, words='A different picture.', words_quote=quote).status_code, 200)
        for _ in range(3): guided.run(study.pk)
        for _ in range(2): self.finish(study)
        self.assertEqual(self.images.call_count, 1)
        self.assertEqual(self.ai.call_count, 1)
        self.assertEqual(Entry.objects.filter(entry_type='sentence').count(), 1)

    def test_named_custom_styles_and_choices_are_personal_durable_and_not_consent(self):
        self.preview(picture_style='custom', style_name='Soft pencil', style_description='Soft coloured pencils.')
        self.client.logout(); self.client.force_login(self.user)
        page = self.client.get(self.url('guided-start'))
        form = page.context['words_form']
        self.assertEqual(form['start_with'].value(), 'words')
        self.assertTrue(page.context['needs_guided_consent'])
        self.assertFalse(form['words_permission'].value())
        key = form['picture_style'].value()
        self.assertTrue(key.startswith('saved-'))
        self.assertContains(page, 'Soft pencil')
        study = self.preview(picture_style=key)
        self.assertEqual(study.result['guided']['words']['style_description'], 'Soft coloured pencils.')
        self.d.refresh_from_db(); self.assertIsNone(self.d.image_style_id)
        owner = Client(); owner.force_login(self.owner)
        self.assertNotContains(owner.get(self.url('guided-start')), 'Soft pencil')
        other = Dictionary.objects.create(owner=self.user, name='Other', language='Swedish',
            sentence_capture_enabled=True, image_generation_enabled=True)
        self.assertNotContains(self.client.get(reverse('community_dictionary:guided-start', args=[other.pk])), 'Soft pencil')

    def test_switching_to_picture_validates_only_picture_fields_and_remembers_route(self):
        self.preview()
        page = self.client.get(self.url('guided-start'))
        r = self.client.post(self.url('guided-start'), {'submission_id': uuid.uuid4(), 'start_with': 'picture',
            'photo': picture(), 'permission': 'on', 'quote': page.context['form']['quote'].value(),
            'words': 'x' * 1000, 'words_language': 'invalid', 'audio': picture(), 'picture_style': 'invalid'})
        self.assertEqual(r.status_code, 302, r.content[:1000])
        study = PictureCapture.objects.latest('created_at')
        self.assertFalse(study.recording_path)
        self.assertNotIn('words', study.result['guided'])
        self.assertEqual(self.client.get(self.url('guided-start')).context['words_form']['start_with'].value(), 'picture')

    def test_missing_custom_fields_permission_and_stale_quote_create_no_attempt(self):
        for extra, error in [({'style_name': '', 'picture_style': 'custom'}, 'style_name'),
            ({'words_permission': ''}, 'words_permission'), ({'words': ''}, 'words'),
            ({'words_mode': 'voice'}, 'audio')]:
            r = self.post_words(**extra)
            self.assertEqual(r.status_code, 200)
            self.assertIn(error, r.context['words_form'].errors)
        page = self.client.get(self.url('guided-start'))
        quote = page.context['words_form']['words_quote'].value()
        self.assertEqual(self.post_words(words_quote='tampered').status_code, 200)
        self.d.image_generation_revision += 1; self.d.save()
        self.assertEqual(self.post_words(words_quote=quote).status_code, 200)
        self.assertEqual(PictureCapture.objects.count(), 0)
        self.images.assert_not_called(); self.asr.assert_not_called()

    def test_disabled_generation_and_daily_limit_prevent_provider_calls(self):
        self.d.image_generation_enabled = False; self.d.save()
        self.assertEqual(self.post_words().status_code, 200)
        self.assertEqual(PictureCapture.objects.count(), 0)
        self.d.image_generation_enabled = True; self.d.save()
        with override_settings(COMMUNITY_DICTIONARY_IMAGE_DAILY_LIMIT=0):
            self.assertContains(self.post_words(), 'paused AI picture generation')
            self.assertEqual(PictureCapture.objects.count(), 0)
        self.images.assert_not_called()

    def test_separate_limits_shown_and_normal_quota_failure_keeps_form_without_paid_draft(self):
        self.d.capture_daily_limit = 100; self.d.save()
        with override_settings(COMMUNITY_DICTIONARY_IMAGE_DAILY_LIMIT=1):
            self.preview()
            page = self.post_words()
            self.assertContains(page, 'normal AI image allowance is used up')
            self.assertEqual(PictureCapture.objects.count(), 1)
            self.assertEqual(self.images.call_count, 1)
        self.client.force_login(self.owner)
        page = self.client.get(self.url('settings'))
        self.assertContains(page, 'Daily AI allowances')
        self.assertContains(page, '19 new AI pictures remaining at the normal allowance')
        self.assertContains(page, '99 entry or practice attempts remaining in this dictionary')
        self.assertContains(page, 'New AI pictures use the picture allowance above.')
        self.assertEqual(page.context['capture_usage']['limit'], 100)
        self.assertEqual(page.context['image_counts']['limit'], 20)

    @override_settings(COMMUNITY_DICTIONARY_IMAGE_DAILY_LIMIT=1)
    def test_owner_one_request_allowance_survives_queue_and_cannot_replay_or_leak(self):
        self.client.force_login(self.owner)
        self.preview()
        study = self.preview(extra_image_allowance='on')
        self.assertEqual(self.images.call_count, 2)
        receipt = ImageStudy.objects.get(pk=study.result['guided']['words']['image_attempt'])
        self.assertEqual(receipt.usage['owner_allowance']['approved_by'], self.owner.pk)
        guided.run(study.pk)
        self.assertEqual(self.images.call_count, 2)
        self.assertContains(self.post_words(), 'normal AI image allowance is used up')
        self.client.force_login(self.user)
        page = self.post_words(extra_image_allowance='on')
        self.assertContains(page, 'Only a dictionary owner')
        self.assertEqual(self.images.call_count, 2)

    def test_scoped_allowance_cannot_be_copied_expired_or_used_after_owner_change(self):
        self.client.force_login(self.owner)
        first = self.start(extra_image_allowance='on')
        second = self.start(extra_image_allowance='on')
        token = first.result['guided']['words']['image_allowance']
        with self.assertRaises(Conflict):
            images.approved_allowance(token, self.d, self.owner, second.pk)
        with patch('django.core.signing.time.time', return_value=time.time()+86401):
            with self.assertRaises(Conflict):
                images.approved_allowance(token, self.d, self.owner, first.pk)
        self.d.owner = self.user; self.d.save()
        guided.run(first.pk); first.refresh_from_db()
        self.assertEqual(first.status, 'failed')
        self.images.assert_not_called()

    def test_one_request_allowance_does_not_bypass_global_pause_or_activity_allowance(self):
        self.client.force_login(self.owner)
        with override_settings(COMMUNITY_DICTIONARY_IMAGE_DAILY_LIMIT=0):
            self.assertContains(self.post_words(extra_image_allowance='on'), 'paused AI picture generation')
        self.d.capture_daily_limit = 0; self.d.save()
        self.start(extra_image_allowance='on')
        self.images.assert_not_called()
        self.assertFalse(ImageStudy.objects.exists())

    @override_settings(CREDITS_ENABLED=True)
    def test_extra_image_allowance_does_not_supply_credit(self):
        self.client.force_login(self.owner)
        study = self.start(extra_image_allowance='on')
        guided.run(study.pk)
        self.images.assert_not_called()
        self.assertFalse(ImageStudy.objects.exists())

    @override_settings(COMMUNITY_DICTIONARY_IMAGE_DAILY_LIMIT=1)
    def test_quota_consumed_while_queued_has_specific_private_failure(self):
        first, second = self.start(), self.start()
        guided.run(first.pk)
        guided.run(second.pk); second.refresh_from_db()
        self.assertEqual(second.status, 'failed')
        self.assertEqual(self.images.call_count, 1)
        self.assertContains(self.client.get(self.url('guided-detail', second.pk)),
            'separate from the entry creation and practice allowance')

    def test_image_failure_keeps_words_and_no_get_or_continue_repeats_paid_call(self):
        self.images.return_value = (None, {'prompt_tokens': 10}, 'provider_or_image_error')
        study = self.start()
        for _ in range(2): guided.run(study.pk)
        study.refresh_from_db()
        self.assertEqual(study.status, 'failed')
        self.assertEqual(study.description, RESULT['sentence'])
        self.assertContains(self.client.get(self.url('guided-detail', study.pk)), 'Start again with these words')
        self.action(study, 'continue'); guided.run(study.pk)
        self.assertEqual(self.images.call_count, 1)
        page = self.client.get(self.url('guided-start') + '?from=' + str(study.pk))
        self.assertEqual(page.context['words_form']['words'].value(), RESULT['sentence'])

    def test_retry_enrichment_keeps_image_without_buying_another(self):
        study = self.preview()
        self.ai.side_effect = TimeoutError()
        self.finish(study)
        self.ai.side_effect = None
        r = self.action(study, 'retry')
        self.assertEqual(r.status_code, 302)
        latest = PictureCapture.objects.latest('created_at')
        self.finish(latest)
        self.assertEqual(latest.status, 'saved')
        self.assertEqual(self.images.call_count, 1)

    def test_private_previews_and_mid_call_policy_change_block_publication(self):
        def revoke(*args):
            Dictionary.objects.filter(pk=self.d.pk).update(image_generation_revision=1)
            return prepare_upload(picture(), 'image'), {'prompt_tokens': 100, 'completion_tokens': 10}, ''
        self.images.side_effect = revoke
        study = self.start(); guided.run(study.pk); study.refresh_from_db()
        self.assertEqual(study.status, 'failed')
        self.assertFalse(study.file_path)
        self.assertTrue(ImageStudy.objects.get().accounted)
        self.assertEqual(Entry.objects.count(), 0)
        outsider = Client(); outsider.force_login(self.outsider)
        self.assertEqual(outsider.get(self.url('guided-detail', study.pk)).status_code, 404)

    def test_discard_clears_private_image_prompt_and_keeps_published_entry(self):
        study = self.preview()
        self.finish(study)
        image_path = study.saved_entry.selected_image.file_path
        self.assertEqual(self.action(study, 'discard').status_code, 302)
        attempt = ImageStudy.objects.get()
        self.assertEqual(attempt.status, 'discarded')
        self.assertEqual(attempt.prompt, '')
        self.assertEqual(attempt.subject, '')
        self.assertTrue(Entry.objects.filter(pk=study.saved_entry_id).exists())
        self.assertTrue(path_for(image_path).is_file())

    def test_unknown_words_recipe_cannot_spend(self):
        study = self.preview()
        study.result['guided']['consent']['words_version'] = 'unsupported-version'
        study.save()
        with self.assertRaises(Conflict): capture.allowed(study, payment=True)
        self.ai.assert_not_called()

    def test_new_controls_are_localised(self):
        for code, label in [('fr', 'Commencer par des mots'), ('sk', 'Začať slovami')]:
            self.client.cookies['community_ui_language'] = code
            self.assertContains(self.client.get(self.url('guided-start')), label)

    def test_initial_route_fieldsets_exclude_inactive_inputs_from_native_validation(self):
        class Groups(HTMLParser):
            def __init__(self): super().__init__(); self.groups = {}
            def handle_starttag(self, tag, attrs):
                if tag == 'fieldset':
                    values = dict(attrs)
                    for name in ['data-guided-picture', 'data-guided-words', 'data-guided-speak', 'data-guided-custom']:
                        if name in values: self.groups[name] = values
        parser = Groups(); parser.feed(self.client.get(self.url('guided-start')).content.decode())
        self.assertNotIn('disabled', parser.groups['data-guided-picture'])
        for name in ['data-guided-words', 'data-guided-speak', 'data-guided-custom']:
            self.assertIn('disabled', parser.groups[name])
        self.preview()
        parser = Groups(); parser.feed(self.client.get(self.url('guided-start')).content.decode())
        self.assertIn('disabled', parser.groups['data-guided-picture'])
        self.assertNotIn('disabled', parser.groups['data-guided-words'])

    def test_generate_button_native_validation_and_draft_startup(self):
        node = shutil.which('node')
        if not node or subprocess.run([node, '-e', "require('jsdom')"], capture_output=True).returncode:
            self.skipTest('Optional DOM submission check needs Node and jsdom; no production dependency is added.')
        self.client.force_login(self.owner)
        initial = self.client.get(self.url('guided-start')).content.decode()
        self.preview()
        sticky = self.client.get(self.url('guided-start')).content.decode()
        static = Path(__file__).resolve().parents[1] / 'static' / 'community_dictionary'
        payload = {'initial': initial, 'sticky': sticky,
            'app': (static / 'app.js').read_text(), 'guided': (static / 'guided_start.js').read_text()}
        result = subprocess.run([node, str(Path(__file__).with_name('guided_words_browser.cjs'))],
            input=json.dumps(payload), text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


def picture_audio():
    from django.core.files.uploadedfile import SimpleUploadedFile
    from .test_picture_capture import speech
    return SimpleUploadedFile('spoken.wav', speech(report={})[0][0], content_type='audio/wav')
