import json
import uuid
from copy import deepcopy
from django.core import signing
from django.test import Client, TestCase, override_settings
from projects.models import CreditAccount
from community_dictionary import picture_practice as practice, practice_review, practice_recognition
from community_dictionary.models import CaptureSpeech, Contribution, Entry
from community_dictionary.picture_practice_views import SALT
from . import test_picture_practice as base
from .test_picture_capture import response
from .test_practice_speech_review import result


TARGETS = [
    {'before': 'Ce', 'word': "C'è", 'meaning': 'there is', 'phrase': "C'è un tavolo."},
    {'before': 'tabolo', 'word': 'tavolo', 'meaning': 'table', 'phrase': 'Un tavolo per due.'},
]
RAW = 'Ce un tabolo.'
PROPOSED = "C'è un tavolo."


def uncertain(text=RAW, targets=None):
    data = json.loads(result(text, question='Did you mean these words?').output_text)
    data['recognition_candidates'] = deepcopy(TARGETS if targets is None else targets)
    return response(data)


class RecognitionCandidateTests(TestCase):
    def test_italian_candidates_remain_explicit_and_never_become_feedback(self):
        parsed = practice_review.parse(uncertain(), RAW, mode='voice')
        self.assertEqual(parsed['outcome'], 'recognition')
        self.assertEqual(parsed['heard'], RAW)
        self.assertEqual(parsed['recognition_help']['proposed_text'], PROPOSED)
        self.assertEqual(len(parsed['recognition_help']['targets']), 2)
        self.assertNotIn('feedback', parsed)

    def test_only_local_replacements_are_applied_preserving_real_grammar(self):
        text = RAW + ' I gatti è felice.'
        parsed = practice_review.parse(uncertain(text), text, mode='voice')
        self.assertEqual(parsed['recognition_help']['proposed_text'], PROPOSED + ' I gatti è felice.')
        data = json.loads(uncertain().output_text)
        data.update(outcome='ready', question='', recognition_question='')
        # Even a model that forgets to ask must not slip a candidate into feedback.
        self.assertEqual(practice_review.parse(response(data), RAW, mode='voice')['outcome'], 'recognition')

    def test_ambiguous_unaligned_overlapping_or_unrelated_examples_are_omitted(self):
        cases = [
            ('tabolo tabolo', [TARGETS[1]]),
            (RAW, [{**TARGETS[1], 'before': 'not present'}]),
            (RAW, [{**TARGETS[1], 'phrase': 'Un gatto.'}]),
            (RAW, [TARGETS[1], {**TARGETS[1], 'before': 'un tabolo'}]),
        ]
        for text, targets in cases:
            with self.subTest(text=text, targets=targets):
                help_data = practice_recognition.prepare(targets, text)
                self.assertTrue(help_data['rejected'])
                self.assertLess(len(help_data['targets']), len(targets))

    def test_typed_input_cannot_create_recognition_help(self):
        with self.assertRaises(ValueError): practice_review.parse(uncertain(), RAW, mode='text')
        with self.assertRaises(ValueError): practice_recognition.prepare([{'word': 'tavolo'}], RAW)

    def test_optional_help_is_bounded_and_never_silently_truncates_an_attempt(self):
        target = {**TARGETS[1], 'before': 'x', 'word': 'tavolo', 'phrase': 'Un tavolo.'}
        self.assertEqual(practice_recognition.prepare([target], 'x' + 'a'*254)['targets'], [])
        with self.assertRaises(ValueError): practice_recognition.prepare(TARGETS * 2, RAW)


@override_settings(OPENAI_API_KEY='test-only', CREDITS_ENABLED=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class RecognitionHelpWorkflowTests(TestCase):
    url = base.PicturePracticeTests.url
    word = base.PicturePracticeTests.word
    image = base.PicturePracticeTests.image
    start = base.PicturePracticeTests.start
    attempt = base.PicturePracticeTests.attempt
    act = base.PicturePracticeTests.act

    def setUp(self):
        base.PicturePracticeTests.setUp(self)

    def unclear(self):
        self.asr.return_value.text = RAW
        self.review.return_value = uncertain()
        study = self.attempt('voice')
        practice.run(study.pk); study.refresh_from_db()
        self.assertEqual(study.status, 'transcript')
        return study

    def confirmation(self, **extra):
        return {'mode': 'text', 'description': RAW, 'feedback_language': 'English', 'voice': 'marin',
            'quote': signing.dumps(practice.quote(self.user, self.d), salt=SALT), **extra}

    def test_panel_is_compact_and_read_only_visits_do_not_buy_audio(self):
        study = self.unclear()
        page = self.client.get(self.url('picture-practice-detail', study.pk))
        self.assertContains(page, 'Did you mean…?')
        self.assertContains(page, 'Listen to the word', count=2)
        self.assertContains(page, 'Listen in a phrase', count=2)
        self.assertContains(page, 'Yes, use these words')
        self.assertContains(page, 'Use different words')
        self.assertContains(page, 'Example phrase:')
        self.assertNotContains(page, 'A correction explanation.')
        self.assertEqual(CaptureSpeech.objects.count(), 0)
        self.tts.assert_not_called()
        self.assertEqual((Entry.objects.count(), Contribution.objects.count()), self.before)

    def test_suggestion_confirmation_uses_server_text_and_is_idempotent(self):
        study = self.unclear()
        data = self.confirmation(description='Ignore the suggestion and publish this.', submission_id=str(uuid.uuid4()))
        first = self.act(study, 'use_suggestion', **data)
        again = self.act(study, 'use_suggestion', **data)
        self.assertEqual(first.status_code, 302)
        self.assertEqual(first.url, again.url)
        self.review.return_value = result(PROPOSED)
        practice.run(study.pk); practice.run(study.pk); study.refresh_from_db()
        info = study.result['practice']
        self.assertEqual(info['transcript'], RAW)
        self.assertEqual(info['original_text'], PROPOSED)
        self.assertEqual(info['confirmed_text'], PROPOSED)
        self.assertEqual(info['recognition_confirmation']['method'], 'suggestion')
        self.assertEqual(info['recognition_help']['proposed_text'], PROPOSED)
        self.assertEqual(self.asr.call_count, 1)
        self.assertEqual(self.review.call_count, 2)
        self.assertEqual(study.status, 'feedback')

    def test_manual_intention_and_unchanged_words_remain_available(self):
        for text, method in [('Ce un gatto.', 'edited'), (RAW, 'unchanged')]:
            study = self.unclear()
            self.assertEqual(self.act(study, 'check', **self.confirmation(description=text)).status_code, 302)
            study.refresh_from_db()
            self.assertEqual(study.result['practice']['confirmed_text'], text)
            self.assertEqual(study.result['practice']['recognition_confirmation']['method'], method)

    def test_word_and_phrase_playback_are_independent_bounded_and_accounted(self):
        study = self.unclear()
        for part in ['word', 'phrase']:
            for _ in range(2):
                self.assertEqual(self.act(study, 'listen_help', target=2, part=part, permission='yes',
                    text='Client-supplied text is ignored.').status_code, 302)
            practice.run(study.pk); practice.run(study.pk)
        self.assertEqual(CaptureSpeech.objects.count(), 2)
        self.assertEqual(self.tts.call_count, 2)
        self.assertEqual(self.tts.call_args.kwargs['speech_kind'], 'sentence')
        self.assertEqual(self.review.call_count, 1)
        self.assertEqual(self.asr.call_count, 1)
        clips = list(CaptureSpeech.objects.order_by('pk'))
        self.assertEqual([clip.text for clip in clips], ['tavolo', 'Un tavolo per due.'])
        self.assertTrue(all(clip.status == 'ready' and not clip.entry_id for clip in clips))
        self.assertEqual(self.tts.call_args_list[0].kwargs['speech_kind'], 'entry')
        page = self.client.get(self.url('picture-practice-detail', study.pk))
        self.assertContains(page, 'Suggested word pronunciation')
        self.assertContains(page, 'Example phrase pronunciation')
        for clip in clips:
            media = self.client.get(self.url('picture-practice-help-audio', study.pk, clip.pk))
            self.assertEqual(media.status_code, 200)
            self.assertIn('no-store', media['Cache-Control']); media.close()

    @override_settings(CREDITS_ENABLED=True)
    def test_pronunciation_charges_fit_production_billing_reference_limits(self):
        CreditAccount.objects.update_or_create(user=self.user, defaults={'balance_usd': '100'})
        with base.PicturePracticeTests.strict_charge_save(self):
            study = self.unclear()
            for part in ['word', 'phrase']:
                self.assertEqual(self.act(study, 'listen_help', target=2, part=part, permission='yes').status_code, 302)
                practice.run(study.pk)
        self.assertEqual(CaptureSpeech.objects.filter(status='ready').count(), 2)

    def test_playback_failure_is_not_automatically_retried(self):
        study = self.unclear()
        self.tts.side_effect = TimeoutError()
        self.act(study, 'listen_help', target=2, part='word', permission='yes')
        practice.run(study.pk)
        self.assertEqual(CaptureSpeech.objects.get().status, 'failed')
        self.act(study, 'listen_help', target=2, part='word', permission='yes')
        practice.run(study.pk)
        self.assertEqual(self.tts.call_count, 1)
        self.assertContains(self.client.get(self.url('picture-practice-detail', study.pk)), 'will not be retried automatically')

    def test_generated_word_clips_do_not_prevent_final_sentence_audio(self):
        study = self.unclear()
        self.act(study, 'listen_help', target=2, part='word', permission='yes')
        practice.run(study.pk)
        self.act(study, 'use_suggestion', **self.confirmation())
        self.review.return_value = result(PROPOSED)
        practice.run(study.pk)
        self.assertEqual(self.act(study, 'listen', permission='yes').status_code, 302)
        practice.run(study.pk)
        self.assertEqual(CaptureSpeech.objects.filter(kind='feedback', status='ready').count(), 1)
        self.assertEqual(self.tts.call_count, 2)

    def test_invalid_or_unapproved_playback_requests_do_not_create_clips(self):
        study = self.unclear()
        for data in [{'target': 9, 'part': 'word', 'permission': 'yes'},
                     {'target': 2, 'part': 'other', 'permission': 'yes'},
                     {'target': 2, 'part': 'word'}, {'target': 'bad', 'part': 'word', 'permission': 'yes'}]:
            self.assertEqual(self.act(study, 'listen_help', **data).status_code, 409)
        self.assertEqual(CaptureSpeech.objects.count(), 0)
        self.tts.assert_not_called()

    def test_shared_diagnostics_include_hypotheses_and_choice_but_not_audio_access(self):
        study = self.unclear()
        self.act(study, 'listen_help', target=2, part='word', permission='yes'); practice.run(study.pk)
        clip = CaptureSpeech.objects.get()
        self.act(study, 'use_suggestion', **self.confirmation())
        other = Client(); other.force_login(self.owner)
        self.assertEqual(other.get(self.url('picture-practice-log')+'?shared=1').json()['attempts'], [])
        self.client.post(self.url('picture-practice-report', study.pk),
            {'share_log': 'on', 'problem': 'recognition', 'intended': PROPOSED})
        row = other.get(self.url('picture-practice-log')+'?shared=1').json()['attempts'][0]
        self.assertEqual(row['raw_transcript'], RAW)
        self.assertEqual(row['confirmed_text'], PROPOSED)
        self.assertEqual(row['recognition_confirmation']['method'], 'suggestion')
        self.assertEqual(row['recognition_help']['proposed_text'], PROPOSED)
        self.assertEqual(row['recognition_audio'], [{'target': 2, 'part': 'word', 'status': 'ready'}])
        self.assertEqual(other.get(self.url('picture-practice-help-audio', study.pk, clip.pk)).status_code, 404)
        self.assertNotIn('file_path', json.dumps(row))

    def test_changed_suggestion_or_withdrawn_source_blocks_private_audio(self):
        study = self.unclear()
        self.act(study, 'listen_help', target=2, part='word', permission='yes'); practice.run(study.pk)
        clip = CaptureSpeech.objects.get()
        study.refresh_from_db()
        study.result['practice']['recognition_help']['targets'][1]['word'] = 'gatto'
        study.save(update_fields=['result'])
        self.assertEqual(self.client.get(self.url('picture-practice-help-audio', study.pk, clip.pk)).status_code, 404)
        self.photo.status = 'withdrawn'; self.photo.save()
        self.assertEqual(self.client.get(self.url('picture-practice-help-audio', study.pk, clip.pk)).status_code, 404)
