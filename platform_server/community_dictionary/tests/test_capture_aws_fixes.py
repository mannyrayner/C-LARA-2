"""AWS report regressions; mocked providers do not assess spoken quality."""
import copy
import uuid
from unittest.mock import patch
from django.test import TestCase, SimpleTestCase, override_settings
from community_dictionary import capture, pronunciation, tts
from community_dictionary.models import Entry, Contribution, AudioStudy, ImageWordLink
from community_dictionary.services import add_contributions
from community_dictionary.storage import prepare_upload
from . import test_picture_capture as base
from .test_tts_guidance import provider, quiet
from .test_entry_media import speech_fixture

SENTENCE = 'En katt tittar på ett schackparti på teve.'


class SentenceSpeechTests(SimpleTestCase):
    def say(self, text=SENTENCE, **kwargs):
        return tts.synthesize(text, language='sv', model=tts.MODEL, voice='marin',
            api_key='test-only', speech_kind='sentence', **kwargs)

    def test_sentence_homograph_does_not_request_lexical_guidance(self):
        self.assertEqual(len(SENTENCE), 42)
        self.assertIn('en', pronunciation.homographs(SENTENCE, 'sv'))
        with provider() as (coach, speech, factory):
            report = {}; self.say(report=report)
            coach.assert_not_called()
            self.assertEqual(speech.call_args.kwargs['input'], SENTENCE)
            self.assertEqual(speech.call_args.kwargs['instructions'], pronunciation.sentence_instructions('sv'))
            self.assertEqual(report['speech_kind'], 'sentence')
            self.assertEqual(report['guidance_cost_usd'], '0')
            self.assertEqual(report['stage'], 'complete')
            self.assertEqual(factory.call_args.kwargs['timeout'], 60)
            self.assertEqual(factory.call_args.kwargs['max_retries'], 0)

    def test_sentence_limits_and_quiet_retry(self):
        text = 'En katt. ' * 28  # 252 characters: well above the reported example.
        with provider([quiet(), speech_fixture()[0][0]]) as (coach, speech, _):
            report = {}; self.say(text, report=report)
            coach.assert_not_called(); self.assertEqual(speech.call_count, 2)
            self.assertEqual([r['outcome'] for r in report['attempts']], ['near_silent', 'usable'])
        with self.assertRaises(ValueError): self.say('a' * 256)

    def test_timeout_not_retried_and_diagnostic_has_no_private_message(self):
        with provider([TimeoutError('secret-provider-message')]) as (_, speech, _):
            report = {}
            try: self.say(report=report)
            except TimeoutError as exc: tts.record_failure(report, exc)
            self.assertEqual(speech.call_count, 1)
            self.assertEqual(report['failure_code'], 'timeout')
            self.assertEqual(report['stage'], 'speech')
            self.assertNotIn('secret-provider-message', str(report))
            self.assertIn('too long', tts.failure_message(report))


@override_settings(OPENAI_API_KEY='test-only', CREDITS_ENABLED=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class CaptureAWSFixesTests(TestCase):
    setUp = base.PictureCaptureTests.setUp
    url = base.PictureCaptureTests.url
    start = base.PictureCaptureTests.start
    ready = base.PictureCaptureTests.ready
    action = base.PictureCaptureTests.action
    publish = base.PictureCaptureTests.publish
    word = base.PictureCaptureTests.word

    def original(self):
        entry = Entry.objects.create(dictionary=self.d, created_by=self.owner)
        return add_contributions(entry, self.owner,
            {'prepared_photo': prepare_upload(base.picture(), 'image')}, [], publish=True)[0]

    def describe(self, image):
        result = copy.deepcopy(base.RESULT); result['sentence'] = SENTENCE
        result['words'] = [{'surface': 'katt', 'lemma': 'katt', 'meaning': 'cat', 'existing_id': 0}]
        self.ai.return_value = base.response(result)
        response = self.client.post(self.url('capture-image', image.pk), {
            'submission_id': uuid.uuid4(), 'description': 'A cat watches chess on TV.',
            'input_language': 'English', 'input_mode': 'text', 'voice': 'marin', 'ai_consent': 'on'})
        self.assertEqual(response.status_code, 302)
        s = base.PictureCapture.objects.latest('created_at')
        self.action(s, 'process'); s.refresh_from_db()
        return s, self.publish(s)

    def visible(self, suffix=''):
        return set(e.pk for e in self.client.get(self.url('dictionary') + suffix).context['page'])

    def test_existing_image_source_hidden_only_in_normal_picture_view(self):
        image = self.original()
        self.assertIn(image.entry_id, self.visible())
        study, sentence = self.describe(image)
        self.assertNotIn(image.entry_id, self.visible())
        self.assertIn(sentence.pk, self.visible())
        self.assertIn(image.entry_id, self.visible('?show=all'))
        self.assertNotIn(image.entry_id, self.visible('?view=words'))
        self.assertTrue(Entry.objects.filter(pk=image.entry_id, archived=False).exists())
        self.assertContains(self.client.get(self.url('entry', sentence.pk)), 'Original picture and discussion')
        self.assertEqual(self.client.get(self.url('entry', image.entry_id)).status_code, 200)
        self.action(study, 'discard')  # Browsing depends on published data, not expiring previews.
        self.assertNotIn(image.entry_id, self.visible())

    def test_source_reappears_if_sentence_text_or_image_withdrawn_or_archived(self):
        image = self.original(); _, sentence = self.describe(image)
        for part in [sentence.current_text, sentence.selected_image]:
            Contribution.objects.filter(pk=part.pk).update(status='withdrawn')
            self.assertIn(image.entry_id, self.visible())
            Contribution.objects.filter(pk=part.pk).update(status='accepted')
            self.assertNotIn(image.entry_id, self.visible())
        sentence.archived = True; sentence.save()
        self.assertIn(image.entry_id, self.visible())

    def test_independent_material_and_undescribed_second_image_preserve_source(self):
        image = self.original(); self.describe(image)
        extra = add_contributions(image.entry, self.owner,
            {'prepared_photo': prepare_upload(base.picture(), 'image')}, [], publish=True)[0]
        self.assertIn(image.entry_id, self.visible())
        Contribution.objects.filter(pk=extra.pk).update(status='removed')
        note = Contribution.objects.create(entry=image.entry, author=self.owner, kind='note', status='accepted', body='Keep discussion')
        self.assertIn(image.entry_id, self.visible())
        note.delete()
        word = self.word('vin', 'wine')
        link = ImageWordLink.objects.create(image=image, word_entry=word, created_by=self.owner)
        self.assertIn(image.entry_id, self.visible())
        link.delete()
        add_contributions(image.entry, self.owner, {'word': 'teve', 'meaning': 'TV'}, [], publish=True)
        self.assertIn(image.entry_id, self.visible())

    def test_pending_image_and_other_dictionary_do_not_hide_source(self):
        image = self.original(); _, sentence = self.describe(image)
        second = self.original()
        self.assertIn(second.entry_id, self.visible())
        Contribution.objects.filter(pk=image.pk).update(status='pending')
        self.assertIn(image.entry_id, self.visible('?show=review'))
        Contribution.objects.filter(pk=image.pk).update(status='accepted')
        other = base.Dictionary.objects.create(owner=self.owner, name='Other', language='Swedish')
        sentence.dictionary = other; sentence.save()
        self.assertIn(image.entry_id, self.visible())

    def test_capture_sentence_and_words_choose_separate_speech_modes(self):
        study, sentence = self.describe(self.original())
        capture.run_audio(str(study.pk))
        calls = {call.args[0]: call.kwargs['speech_kind'] for call in self.tts.call_args_list}
        self.assertEqual(calls[SENTENCE], 'sentence')
        self.assertEqual(calls['katt'], 'entry')
        for _ in range(3): self.client.get(self.url('capture-detail', study.pk))
        self.assertEqual(self.tts.call_count, 2)  # Status reads never generate or retry.

    def test_feedback_uses_sentence_mode(self):
        s = self.ready(); clip = base.CaptureSpeech.objects.create(capture=s, kind='feedback',
            text='The cat is lying on the sofa.', language='English')
        capture.speak(clip.pk)
        self.assertEqual(self.tts.call_args.kwargs['speech_kind'], 'sentence')

    def test_failed_sentence_is_readable_and_manual_retry_uses_sentence_mode(self):
        study, sentence = self.describe(self.original())
        self.tts.side_effect = TimeoutError('private-provider-detail')
        clip = study.speech.get(entry=sentence)
        capture.speak(clip.pk)
        clip.refresh_from_db(); self.assertEqual(clip.status, 'failed')
        page = self.client.get(self.url('capture-detail', study.pk))
        self.assertContains(page, 'too long to respond')
        self.assertNotContains(page, 'private-provider-detail')
        self.assertContains(page, self.url('audio-start', sentence.pk))
        self.assertEqual(self.tts.call_count, 1)
        self.tts.side_effect = base.speech
        token = uuid.uuid4()
        for _ in range(2):
            response = self.client.post(self.url('audio-start', sentence.pk), {
                'submission_id': token, 'source_text_id': sentence.current_text_id,
                'source_text_version': sentence.text_version, 'ai_consent': 'on', 'voice': 'marin'})
            self.assertEqual(response.status_code, 302)
        self.assertEqual(self.tts.call_count, 2)
        self.assertEqual(self.tts.call_args.kwargs['speech_kind'], 'sentence')
        audio = AudioStudy.objects.get()
        self.assertEqual(audio.status, 'ready')
        self.assertEqual(audio.source_meaning, '')
        self.assertNotContains(self.client.get(self.url('audio-start', sentence.pk)), 'Check pronunciation')
        self.assertNotContains(self.client.get(self.url('audio-study', audio.pk)), 'Check pronunciation')
