"""Regressions from shared Italian practice: routing, presentation, safe logs."""
import json
from unittest.mock import patch
from django.test import TestCase, override_settings
from community_dictionary import picture_practice as practice, practice_review, tts
from community_dictionary.models import CaptureSpeech, DictionaryWordAudioSettings, Entry, Contribution
from . import test_practice_recognition_help as help_tests
from .test_practice_recognition_help import uncertain, RAW, PROPOSED
from .test_practice_speech_review import result
from .test_picture_capture import response


@override_settings(OPENAI_API_KEY='test-only', CREDITS_ENABLED=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class InterpretationWorkflowTests(TestCase):
    url = help_tests.RecognitionHelpWorkflowTests.url
    word = help_tests.RecognitionHelpWorkflowTests.word
    image = help_tests.RecognitionHelpWorkflowTests.image
    start = help_tests.RecognitionHelpWorkflowTests.start
    attempt = help_tests.RecognitionHelpWorkflowTests.attempt
    act = help_tests.RecognitionHelpWorkflowTests.act
    unclear = help_tests.RecognitionHelpWorkflowTests.unclear
    confirmation = help_tests.RecognitionHelpWorkflowTests.confirmation

    def setUp(self):
        help_tests.RecognitionHelpWorkflowTests.setUp(self)

    def test_google_dictionary_words_do_not_intercept_private_practice_audio(self):
        DictionaryWordAudioSettings.objects.create(dictionary=self.d, voice='it-IT-Neural2-E',
            language='Italian', authorised_by=self.owner)
        with patch('community_dictionary.word_audio.policy', side_effect=AssertionError('Dictionary policy used for private practice')), \
                patch('community_dictionary.google_tts.synthesize') as google:
            study = self.unclear()
            self.assertEqual(CaptureSpeech.objects.filter(status='ready').count(), 4)
            self.assertEqual(self.tts.call_count, 4)
            self.act(study, 'use_suggestion', **self.confirmation())
            self.review.return_value = result(PROPOSED)
            practice.run(study.pk)
            self.assertEqual(self.act(study, 'listen', permission='yes').status_code, 302)
            practice.run(study.pk)
            self.assertEqual(self.tts.call_count, 5)
            self.assertEqual(CaptureSpeech.objects.filter(status='ready').count(), 5)
            google.assert_not_called()
        self.assertEqual(DictionaryWordAudioSettings.objects.get().voice, 'it-IT-Neural2-E')
        self.assertEqual((Entry.objects.count(), Contribution.objects.count()), self.before)

    def test_recogniser_spelling_is_not_presented_as_a_learner_error(self):
        raw = 'Carotte e lattuga.'
        question = 'Le mot transcrit « Carotte » était-il « carote » ?'
        data = json.loads(uncertain(raw, [{'before':'Carotte', 'word':'carote',
            'meaning':'carottes', 'phrase':'Carote e lattuga.'}]).output_text)
        data['recognition_question'] = question
        self.asr.return_value.text = raw
        self.review.return_value = response(data)
        study = self.attempt('voice'); practice.run(study.pk); study.refresh_from_db()
        info = study.result['practice']
        self.assertEqual(info['transcript'], raw)
        self.assertEqual(info['original_text'], raw)
        self.assertFalse(info['confirmed'])
        self.assertEqual(info['recognition_help']['proposed_text'], 'carote e lattuga.')
        self.assertEqual(info['recognition_question'], '')
        self.assertEqual(info['review_decision']['recognition_question'], question)
        page = self.client.get(self.url('picture-practice-detail', study.pk))
        self.assertContains(page, 'I understood…')
        self.assertNotContains(page, question)
        panel = page.content.decode().split('<div class="recognition-help">')[1].split('</div>')[0]
        self.assertNotIn('Carotte', panel)
        self.assertNotIn('→', panel)
        self.assertIn('carote', panel)
        self.assertContains(page, 'Yes, use these words')

    def test_real_meaning_question_remains_prominent(self):
        question = 'Parlez-vous de la table ou du tableau ?'
        data = json.loads(uncertain().output_text)
        data.update(meaning_unclear=True, recognition_question=question, question=question)
        self.asr.return_value.text = RAW
        self.review.return_value = response(data)
        study = self.attempt('voice'); practice.run(study.pk); study.refresh_from_db()
        self.assertEqual(study.result['practice']['recognition_question'], question)
        page = self.client.get(self.url('picture-practice-detail', study.pk))
        self.assertContains(page, 'Let me check the meaning')
        self.assertContains(page, question)

    def test_shared_audio_diagnostic_has_reason_and_stage_without_provider_text(self):
        secret = 'do-not-export-provider-message-or-key'
        def fail(*args, report, **kwargs):
            report.update(stage='speech', provider_message=secret)
            raise TimeoutError(secret)
        self.tts.side_effect = fail
        study = self.unclear()
        self.client.post(self.url('picture-practice-report', study.pk),
            {'share_log':'on', 'problem':'other', 'note':'Audio failed.'})
        self.client.force_login(self.owner)
        exported = self.client.get(self.url('picture-practice-log')+'?shared=1')
        self.assertEqual(exported.status_code, 200)
        self.assertNotContains(exported, secret)
        audio = exported.json()['attempts'][0]['recognition_audio']
        self.assertEqual(len(audio), 4)
        self.assertTrue(all(x['failure_code']=='timeout' and x['stage']=='speech' for x in audio))


class InterpretationValidationTests(TestCase):
    def test_meaning_flag_is_a_boolean(self):
        data = json.loads(uncertain().output_text)
        data['meaning_unclear'] = 'false'
        with self.assertRaises(ValueError):
            practice_review.parse(response(data), RAW, mode='voice')

    def test_unrecognised_diagnostic_values_are_not_exported(self):
        self.assertEqual(tts.public_diagnostic({'stage':'private-path-or-token',
            'failure_code':'raw-provider-error', 'provider_message':'secret'}),
            {'stage':None, 'failure_code':None})
