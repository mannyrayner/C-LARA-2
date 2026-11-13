"""Offline coverage of capability routing, consent, paid-call gates and receipts."""
import base64
from decimal import Decimal
from datetime import timedelta
from unittest.mock import Mock, patch

from django.test import TestCase, override_settings
from django.utils import timezone
from community_dictionary import google_fallback as fallback, google_tts, tts, word_audio
from community_dictionary.forms import DictionaryForm
from community_dictionary.models import AudioStudy, Contribution, Dictionary, LanguagePort, PortRun
from community_dictionary.services import Conflict, add_contributions
from projects.models import AIUsageCharge
from . import test_entry_media as media

SESSION_FACTORY = fallback.session


@override_settings(COMMUNITY_DICTIONARY_GOOGLE_TTS_ENABLED=True,
    COMMUNITY_DICTIONARY_GOOGLE_TTS_PROJECT='community-dictionaries-tts',
    OPENAI_API_KEY='', CREDITS_ENABLED=False)
class GoogleFallbackTests(TestCase):
    url = media.EntryMediaTests.url
    generate = media.EntryMediaTests.generate

    def setUp(self):
        media.EntryMediaTests.setUp(self)
        self.owner.is_staff = True
        self.owner.save(update_fields=['is_staff'])
        self.dictionary.language = 'Igbo'
        self.dictionary.save(update_fields=['language'])
        add_contributions(self.entry, self.owner, {'word': 'ụlọ', 'meaning': 'house'}, [], publish=True)
        self.entry.refresh_from_db()
        self.connection = Mock()
        self.response = Mock(status_code=200)
        self.response.json.return_value = {
            'usageMetadata': {'promptTokenCount': 80, 'candidatesTokenCount': 25},
            'candidates': [{'finishReason': 'STOP', 'content': {'parts': [{'inlineData': {
                'mimeType': 'audio/wav', 'data': base64.b64encode(media.speech_fixture()[0][0]).decode()}}]}}],
        }
        self.connection.post.return_value = self.response
        adapter = patch.object(fallback, 'session', return_value=self.connection)
        adapter.start(); self.addCleanup(adapter.stop)

    def request(self, **changes):
        policy = word_audio.policy(self.dictionary)
        report = {}
        result = word_audio.synthesize('ụlọ', dictionary=self.dictionary, expected=policy,
            language='ig', model=tts.MODEL, voice='marin', api_key='', report=report,
            before_request=Mock(), **changes)
        return result, report

    def test_dictionary_form_accepts_documented_fallback_but_keeps_unknown_language_guard(self):
        form = DictionaryForm(data={'name': 'Igbo test', 'language': 'Igbo', 'tts_enabled': 'on'})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(tts.language_code(' IGBO '), 'ig')
        self.assertEqual(tts.language_code('ig'), 'ig')
        self.assertEqual(tts.language_code('Hausa'), 'ha')
        self.assertNotIn('ig', tts.LANGUAGES.values())
        form = DictionaryForm(data={'name': 'Unknown', 'language': 'Pitjantjatjara', 'tts_enabled': 'on'})
        self.assertFalse(form.is_valid())
        self.assertIn('tts_enabled', form.errors)

    def test_openai_languages_keep_the_existing_provider(self):
        self.dictionary.language = 'French'; self.dictionary.save(update_fields=['language'])
        self.assertEqual(word_audio.policy(self.dictionary), {})
        word_audio.synthesize('maison', dictionary=self.dictionary, expected={}, language='fr',
            model=tts.MODEL, voice='marin', api_key='test-only')
        self.speech.assert_called_once()
        self.connection.post.assert_not_called()

    def test_openai_failure_does_not_trigger_another_paid_provider(self):
        self.dictionary.language = 'French'; self.dictionary.save(update_fields=['language'])
        self.speech.side_effect = TimeoutError
        with self.assertRaises(TimeoutError):
            word_audio.synthesize('maison', dictionary=self.dictionary, expected={}, language='fr',
                model=tts.MODEL, voice='marin', api_key='test-only')
        self.connection.post.assert_not_called()

    def test_google_request_uses_existing_project_exact_transcript_and_bounded_single_call(self):
        result, report = self.request()
        self.speech.assert_not_called()
        self.assertEqual(report['provider'], 'google')
        self.assertEqual(report['model'], fallback.MODEL)
        self.assertEqual(report['voice'], 'Kore')
        self.assertEqual(report['speech_cost_usd'], '0.000530')
        self.assertEqual(report['cost_basis'], 'google_gemini_returned_tokens')
        self.assertEqual(result[0][1], 'audio/wav')
        self.connection.post.assert_called_once()
        call = self.connection.post.call_args
        self.assertIn('/projects/community-dictionaries-tts/locations/global/', call.args[0])
        self.assertEqual(call.kwargs['json']['contents'][0]['parts'][0]['text'], 'ụlọ')
        self.assertIn('igbo', call.kwargs['json']['contents'][0]['parts'][0]['speechMetadata']['style'])
        self.assertEqual(call.kwargs['json']['generationConfig']['speechConfig']['voiceConfig']['voice'], 'Kore')
        self.assertEqual(call.kwargs['timeout'], (15, 60))
        self.assertIs(call.kwargs['allow_redirects'], False)
        self.connection.close.assert_called_once()

    def test_existing_google_credentials_are_refreshed_with_bounded_transport(self):
        class Credentials:
            def refresh(self, request):
                request(url='https://oauth2.googleapis.com/token', method='POST')
        auth = Credentials()
        transport = Mock()
        with patch.object(google_tts, 'credentials', return_value=auth), \
             patch('google.auth.transport.requests.Request', return_value=transport), \
             patch('google.auth.transport.requests.AuthorizedSession', return_value='authorized') as authorized, \
             patch('requests.Session'):
            self.assertEqual(SESSION_FACTORY(), 'authorized')
        self.assertEqual(transport.call_args.kwargs['timeout'], 30)
        authorized.assert_called_once_with(auth, max_refresh_attempts=0)

    def test_sentence_fallback_and_openai_explanation_feedback_use_the_correct_language(self):
        self.request(speech_kind='sentence')
        self.assertEqual(self.connection.post.call_count, 1)
        word_audio.synthesize('This is a house.', dictionary=self.dictionary,
            expected=word_audio.policy(self.dictionary), language='en', model=tts.MODEL,
            voice='marin', api_key='test-only', speech_kind='sentence')
        self.speech.assert_called_once()
        self.assertEqual(self.connection.post.call_count, 1)

    def test_entry_and_sentence_preview_save_google_voice_model_and_billing(self):
        for kind in ['word', 'sentence']:
            with self.subTest(kind=kind):
                self.entry.entry_type = kind; self.entry.save(update_fields=['entry_type'])
                page = self.client.get(self.url('audio-start', self.entry.pk))
                self.assertContains(page, fallback.MODEL)
                self.assertNotContains(page, 'OpenAI will create a synthetic recording')
                self.assertEqual(page.context['form']['voice'].value(), 'Kore')
                with patch.object(tts, 'api_credentials', side_effect=AssertionError('Google must not need OpenAI credentials')):
                    response = self.generate(voice='Kore')
                self.assertEqual(response.status_code, 302)
                study = AudioStudy.objects.latest('created_at')
                self.assertEqual(study.status, 'ready', study.synthesis)
                self.assertEqual(study.model, fallback.MODEL)
                self.assertFalse(study.personal_key)
                self.assertEqual(study.synthesis['speech_kind'], 'sentence' if kind == 'sentence' else 'entry')
                saved = self.client.post(self.url('audio-action', study.pk),
                    {'action': 'save', 'consent': 'on', 'publish_now': 'on'})
                self.assertEqual(saved.status_code, 302)
                audio = Contribution.objects.get(pk=AudioStudy.objects.get(pk=study.pk).saved_contribution_id)
                self.assertEqual(audio.provenance['provider'], 'google')
                self.assertEqual(audio.provenance['voice'], 'Kore')
        self.assertEqual(AIUsageCharge.objects.filter(provider='google', model=fallback.MODEL).count(), 2)

    def test_owner_authorization_host_flag_and_project_changes_block_before_paid_call(self):
        expected = word_audio.policy(self.dictionary)
        for context in [override_settings(COMMUNITY_DICTIONARY_GOOGLE_TTS_ENABLED=False),
                        override_settings(COMMUNITY_DICTIONARY_GOOGLE_TTS_PROJECT='different-project')]:
            with context, self.assertRaises(Conflict):
                word_audio.synthesize('ụlọ', dictionary=self.dictionary, expected=expected, language='ig')
        self.owner.is_staff = False; self.owner.save(update_fields=['is_staff'])
        with self.assertRaises(Conflict):
            word_audio.synthesize('ụlọ', dictionary=self.dictionary, expected=expected, language='ig')
        self.connection.post.assert_not_called()

    @override_settings(CREDITS_ENABLED=True)
    def test_google_requires_credit_even_if_an_openai_personal_key_would_bypass_it(self):
        with patch('projects.billing.get_user_balance_usd', return_value=Decimal('0')):
            with self.assertRaisesMessage(Conflict, 'personal OpenAI key does not pay Google'):
                tts.configuration(self.owner, self.dictionary)
        self.connection.post.assert_not_called()

    def test_permission_failure_is_actionable_uncharged_and_does_not_retry_or_switch_provider(self):
        self.response.status_code = 403
        self.response.text = 'PRIVATE PROVIDER ERROR'
        response = self.generate(voice='Kore')
        self.assertEqual(response.status_code, 302)
        study = AudioStudy.objects.latest('created_at')
        self.assertEqual(study.status, 'failed')
        self.assertEqual(study.cost_usd, Decimal('0'))
        self.assertFalse(study.synthesis['uncertain_cost'])
        self.assertIn('prediction permission', tts.failure_message(study.synthesis))
        self.assertNotIn('PRIVATE PROVIDER ERROR', str(study.synthesis))
        self.connection.post.assert_called_once()
        self.speech.assert_not_called()

    def test_missing_usage_uses_labelled_duration_estimate_and_invalid_audio_is_not_saved(self):
        del self.response.json.return_value['usageMetadata']
        _, report = self.request()
        self.assertEqual(report['cost_basis'], 'google_gemini_tokens_or_duration_estimate')
        self.assertNotIn('usage', report)
        self.assertGreater(Decimal(report['speech_cost_usd']), 0)
        self.response.json.return_value['candidates'][0]['content']['parts'][0]['inlineData']['data'] = 'not base64'
        with self.assertRaises(ValueError):
            self.request()

    def test_silent_completed_audio_is_accounted_without_a_second_attempt(self):
        from .test_workflow import recording
        self.response.json.return_value['candidates'][0]['content']['parts'][0]['inlineData']['data'] = base64.b64encode(recording().read()).decode()
        self.generate(voice='Kore')
        study = AudioStudy.objects.latest('created_at')
        self.assertEqual(study.status, 'failed')
        self.assertEqual(study.cost_usd, Decimal('0.000530'))
        self.assertEqual(len(study.synthesis['attempts']), 1)
        self.assertNotIn('Both audio attempts', tts.failure_message(study.synthesis))
        self.connection.post.assert_called_once()

    def test_transport_timeout_remains_uncertain_without_automatic_retry(self):
        from requests.exceptions import ReadTimeout
        self.connection.post.side_effect = ReadTimeout('PRIVATE TRANSPORT ERROR')
        self.generate(voice='Kore')
        study = AudioStudy.objects.latest('created_at')
        self.assertTrue(study.synthesis['uncertain_cost'])
        self.assertEqual(study.synthesis['google_access_code'], 'connection')
        self.assertNotIn('PRIVATE TRANSPORT ERROR', str(study.synthesis))
        self.connection.post.assert_called_once()
        self.speech.assert_not_called()

    def test_new_destination_batch_freezes_policy_before_dictionary_creation(self):
        port = LanguagePort.objects.create(source=self.dictionary, user=self.owner,
            name='Hausa', language='Hausa', explanation_language='English')
        run = PortRun.objects.create(port=port, stage='sentences', model='fixture',
            source_language='Igbo', source_explanation_language='English', prices={},
            payer='server', expires_at=timezone.now() + timedelta(hours=1))
        expected = word_audio.run_policy(run)
        self.assertEqual(expected['language'], 'Hausa')
        self.assertEqual(expected['method'], 'google_gemini')
        port.destination = Dictionary.objects.create(name='Hausa', language='Hausa',
            owner=self.owner, tts_enabled=True)
        port.save(update_fields=['destination'])
        word_audio.validate(port.destination, expected)
        with patch.object(fallback, 'INPUT_RATE', Decimal('2')), self.assertRaises(Conflict):
            word_audio.validate(port.destination, expected)
        self.connection.post.assert_not_called()

    @override_settings(OPENAI_API_KEY='fixture-only')
    def test_picture_page_discloses_google_and_extends_consent_before_processing(self):
        self.dictionary.sentence_capture_enabled = True
        self.dictionary.save(update_fields=['sentence_capture_enabled'])
        response = self.client.get(self.url('capture-start'))
        self.assertContains(response, 'Google Gemini supplies word and sentence audio')
        self.assertContains(response, 'I have permission for the OpenAI processing described here and to send the relevant text to Google')
        self.connection.post.assert_not_called()
