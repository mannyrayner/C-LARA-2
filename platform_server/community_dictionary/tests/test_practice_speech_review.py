import json
from copy import deepcopy
from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase, Client, override_settings
from django.utils import timezone
from community_dictionary import practice_review, picture_practice as practice
from community_dictionary.models import PictureCapture, Membership, Participation
from community_dictionary.picture_practice_views import consent_key
from .test_picture_practice import ORIGINAL, CORRECTED, FEEDBACK
from . import test_picture_practice as base
from .test_picture_capture import response


def result(text, *, heard=None, corrected=None, kind=None, question='', suspects=None):
    data = {'outcome': 'clarify' if question else 'ready', 'text': corrected or heard or text,
        'heard': heard or text, 'understood': 'A short description.', 'question': question,
        'recognition_question': question, 'suspect_words': suspects or [], 'suggestions': [], 'corrections': [],
        'recognition_candidates': [], 'meaning_unclear': False}
    if kind:
        data['corrections'] = [{'before': text, 'after': corrected or heard, 'kind': kind,
            'reason': 'A correction explanation.'}]
    return response(data)


class SpeechReviewGateTests(TestCase):
    def test_swedish_tv_notation_is_normalised_without_criticising_speech(self):
        for kind in ['written_form', 'grammar']:
            with self.subTest(kind=kind):
                parsed = practice_review.parse(result('tvn', heard='tv:n', corrected='tv:n', kind=kind), 'tvn', mode='voice')
                self.assertEqual(parsed['outcome'], 'feedback')
                self.assertEqual(parsed['feedback']['text'], 'tv:n')
                self.assertEqual(parsed['feedback']['corrections'], [])
                self.assertEqual(len(parsed['diagnostics']['suppressed_written_form']), 1)

    def test_lexical_normalisation_cannot_silently_rewrite_swedish_examples(self):
        for before, after in [('bordstuk', 'bordsduk'), ('smicke', 'smycke'), ('a', 'å')]:
            with self.subTest(before=before):
                parsed = practice_review.parse(result(before, heard=after), before, mode='voice')
                self.assertEqual(parsed['outcome'], 'recognition')
                self.assertEqual(parsed['heard'], before)
                self.assertIn('lexical_normalisation_blocked', parsed['diagnostics']['gates'])
                self.assertNotIn('feedback', parsed)

    def test_lexical_spelling_or_word_correction_becomes_a_recognition_question(self):
        for before, after in [('bordstuk', 'bordsduk'), ('smicke', 'smycke')]:
            for kind in ['written_form', 'word_choice', 'recognition']:
                parsed = practice_review.parse(result(before, corrected=after, kind=kind), before, mode='voice')
                self.assertEqual(parsed['outcome'], 'recognition', (before,kind))
                self.assertNotIn('feedback', parsed)

    def test_real_grammar_is_preserved_for_review_and_unusual_valid_words_are_allowed(self):
        data = deepcopy(FEEDBACK)
        parsed = practice_review.parse(response(data), ORIGINAL, mode='voice')
        self.assertEqual(parsed['heard'], ORIGINAL)
        self.assertEqual(parsed['feedback']['text'], CORRECTED)
        self.assertEqual(len(parsed['feedback']['corrections']), 1)
        for text in ['bordsduk', 'smycke', 'Den palimpsestiska berättelsen är fascinerande.']:
            self.assertEqual(practice_review.parse(result(text), text, mode='voice')['feedback']['text'], text)

    def test_typed_spelling_is_still_useful_feedback(self):
        parsed = practice_review.parse(result('tvn', corrected='tv:n', kind='written_form'), 'tvn', mode='text')
        self.assertEqual(len(parsed['feedback']['corrections']), 1)

    def test_mode_and_self_reported_level_reach_the_actual_provider_payload(self):
        from .test_workflow import picture
        from community_dictionary.storage import prepare_upload
        with patch('community_dictionary.writing_ai._openai_client') as client:
            practice_review.review(prepare_upload(picture(), 'image')[0], text=ORIGINAL, language='Italian',
                feedback_language='English', model='test', api_key='test', mode='voice', level='advanced', confirmed=False)
            args = client.return_value.__enter__.return_value.responses.create.call_args.kwargs
            data = json.loads(args['input'][0]['content'][0]['text'])
            self.assertEqual(data['practice_context']['input_mode'], 'voice')
            self.assertEqual(data['practice_context']['proficiency'], 'advanced')
            self.assertFalse(data['practice_context']['speech_confirmed'])
            self.assertIn('NEVER use it to decide', args['instructions'])
            self.assertFalse(args['store'])


@override_settings(OPENAI_API_KEY='test-only', CREDITS_ENABLED=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class PracticeRevisionTests(TestCase):
    url = base.PicturePracticeTests.url
    word = base.PicturePracticeTests.word
    image = base.PicturePracticeTests.image
    start = base.PicturePracticeTests.start
    attempt = base.PicturePracticeTests.attempt
    act = base.PicturePracticeTests.act
    feedback = base.PicturePracticeTests.feedback

    def setUp(self):
        base.PicturePracticeTests.setUp(self)

    def test_speech_goes_straight_to_feedback_and_records_real_stage_boundaries(self):
        study = self.attempt('voice', level='advanced')
        for _ in range(2): practice.run(study.pk)
        study.refresh_from_db()
        self.assertEqual(study.status, 'feedback')
        self.assertEqual(self.asr.call_count, 1)
        self.assertEqual(self.review.call_count, 1)
        context = self.review.call_args.kwargs['context']
        self.assertEqual(context['input_mode'], 'voice')
        self.assertEqual(context['proficiency'], 'advanced')
        events = study.result['practice']['diagnostics']['events']
        self.assertEqual([(e['stage'], e['state']) for e in events],
            [('transcribe','started'),('transcribe','finished'),('review','started'),('review','finished')])
        self.assertTrue(all(e['elapsed_ms'] >= 0 for e in events if e['state']=='finished'))
        page = self.client.get(self.url('picture-practice-detail', study.pk))
        self.assertNotContains(page, 'Let me check what I heard')

    def test_session_permission_is_scoped_expires_and_ends_without_a_paid_request(self):
        page = self.client.get(self.url('picture-practice')+f'?image={self.photo.pk}')
        self.assertContains(page, 'name="permission"')
        self.attempt()
        page = self.client.get(self.url('picture-practice')+f'?image={self.photo.pk}')
        self.assertNotContains(page, 'name="permission"')
        self.assertEqual(self.start(permission='').status_code, 302)
        self.client.post(self.url('picture-practice-end'))
        self.assertEqual(self.start(permission='').status_code, 200)
        self.review.assert_not_called()
        self.attempt()
        session=self.client.session
        session[consent_key(self.d)]={**session[consent_key(self.d)],'expires':0};session.save()
        self.assertEqual(self.start(permission='').status_code, 200)
        self.attempt()
        self.d.capture_revision += 1;self.d.save()
        self.assertEqual(self.start(permission='').status_code, 200)

    def test_uncertainty_hides_model_criticism_then_confirmed_review_is_accounted_separately(self):
        self.asr.return_value.text='bordstuk'
        self.review.return_value = result('bordstuk', corrected='bordsduk', kind='word_choice')
        study = self.attempt('voice')
        practice.run(study.pk)
        study.refresh_from_db()
        self.assertEqual(study.status, 'transcript')
        page=self.client.get(self.url('picture-practice-detail', study.pk))
        self.assertNotContains(page, 'A correction explanation.')
        self.assertNotContains(page, 'name="permission"')
        self.assertIn('practice_feedback', study.usage)
        from django.core import signing
        from community_dictionary.picture_practice_views import SALT
        self.review.return_value=result('bordsduk')
        self.assertEqual(self.act(study,'check',mode='text',description='bordsduk',feedback_language='English',
            voice='marin',quote=signing.dumps(practice.quote(self.user,self.d),salt=SALT)).status_code,302)
        practice.run(study.pk);study.refresh_from_db()
        self.assertEqual(study.status,'feedback')
        self.assertEqual(study.result['practice']['transcript'],'bordstuk')
        self.assertEqual(study.result['practice']['original_text'],'bordsduk')
        self.assertIn('practice_feedback_confirmed',study.usage)
        self.assertEqual(self.asr.call_count,1)
        self.assertTrue(self.review.call_args.kwargs['context']['speech_confirmed'])

    def test_reports_and_exports_are_private_and_owners_need_attempt_specific_opt_in(self):
        study=self.feedback()
        own=self.client.get(self.url('picture-practice-log'))
        self.assertEqual(len(own.json()['attempts']),1)
        self.assertIn('no-store',own['Cache-Control'])
        self.assertNotIn('file_path',own.content.decode())
        self.assertNotIn('test-only',own.content.decode())
        self.assertEqual(self.client.get(self.url('picture-practice-log')+'?shared=1').status_code,404)
        other=Client();other.force_login(self.owner)
        self.assertEqual(other.get(self.url('picture-practice-log')+'?shared=1').json()['attempts'],[])
        self.assertEqual(other.post(self.url('picture-practice-report',study.pk),{'problem':'helpful'}).status_code,404)
        self.client.post(self.url('picture-practice-report',study.pk),
            {'problem':'recognition','intended':'Il gatto è felice.','note':'I said this.','share_log':'on'})
        rows=other.get(self.url('picture-practice-log')+'?shared=1').json()['attempts']
        self.assertEqual(rows[0]['user_report']['intended_text'],'Il gatto è felice.')
        self.assertTrue(rows[0]['reviews'])
        self.client.post(self.url('picture-practice-report',study.pk),{'problem':'helpful'})
        self.assertEqual(other.get(self.url('picture-practice-log')+'?shared=1').json()['attempts'],[])
        self.assertEqual(self.client.get(self.url('picture-practice-report',study.pk)).status_code,405)

    def test_shared_logs_disappear_on_withdrawal_or_clear(self):
        study=self.feedback()
        self.client.post(self.url('picture-practice-report',study.pk),{'problem':'helpful','share_log':'on'})
        other=Client();other.force_login(self.owner)
        self.photo.status='withdrawn';self.photo.save()
        self.assertEqual(other.get(self.url('picture-practice-log')+'?shared=1').json()['attempts'],[])
        self.photo.status='accepted';self.photo.save()
        self.act(study,'discard')
        self.assertEqual(other.get(self.url('picture-practice-log')+'?shared=1').json()['attempts'],[])

    def test_bad_provider_output_retains_private_diagnostic_and_never_repeats_the_call(self):
        self.review.return_value.output_text='Invalid JSON'
        study=self.attempt()
        practice.run(study.pk);practice.run(study.pk)
        study.refresh_from_db()
        self.assertEqual(study.status,'failed')
        self.assertEqual(study.result['practice']['review_log'][0]['output'],'Invalid JSON')
        self.assertEqual(self.review.call_count,1)

    def test_editing_transcript_creates_idempotent_new_review_without_repeating_asr(self):
        study=self.feedback()
        from django.core import signing
        from community_dictionary.picture_practice_views import SALT
        import uuid
        data={'mode':'text','description':ORIGINAL,'feedback_language':'English','voice':'marin',
            'quote':signing.dumps(practice.quote(self.user,self.d),salt=SALT),'submission_id':str(uuid.uuid4())}
        a=self.act(study,'revise',**data);b=self.act(study,'revise',**data)
        self.assertEqual(a.status_code,302)
        self.assertEqual(a.url,b.url)
        self.assertEqual(PictureCapture.objects.count(),2)
        new=PictureCapture.objects.exclude(pk=study.pk).get()
        practice.run(new.pk)
        self.asr.assert_not_called()
        self.assertEqual(self.review.call_count,2)
