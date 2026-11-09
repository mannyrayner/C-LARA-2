"""Provider contracts and limits, not claims about live-model accuracy."""
import copy
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

from community_dictionary import capture_ai, capture_vocabulary, port_vocabulary_ai, vocabulary_policy
from community_dictionary.models import EvaluationRating, EvaluationSession
from . import test_picture_capture as capture_base
from .test_evaluation import EvaluationTests, url


class VocabularyPolicyContracts(SimpleTestCase):
    def test_twelve_generated_items_parse_in_both_routes_thirteen_do_not(self):
        words = [{'surface': str(i), 'lemma': str(i), 'meaning': str(i), 'existing_id': 0}
                 for i in range(13)]
        sentence = ' '.join(w['surface'] for w in words)
        value = copy.deepcopy(capture_base.RESULT)
        value.update(sentence=sentence, words=words[:12])
        self.assertEqual(len(capture_ai.parse(capture_base.response(value))['words']), 12)
        self.assertEqual(len(port_vocabulary_ai.parse(capture_base.response({'words': words[:12]}),
                         {'sentence': sentence})['words']), 12)
        value['words'] = words
        with self.assertRaises(ValueError):
            capture_ai.parse(capture_base.response(value))
        with self.assertRaises(ValueError):
            port_vocabulary_ai.parse(capture_base.response({'words': words}), {'sentence': sentence})

    def test_actual_provider_requests_share_policy_and_matching_schema_budget(self):
        data = {'target_language': 'English', 'sentence': 'Three cats sleep.', 'vocabulary': []}
        with patch('community_dictionary.capture_ai._openai_client') as client:
            api = client.return_value.__enter__.return_value
            for mode in ['text', 'ai', 'approved-writing']:
                capture_ai.interpret(capture_base.picture().read(), {**data, 'input_mode': mode},
                                     model='fixture-model', api_key='fixture-key')
                call = api.responses.create.call_args.kwargs
                self.assertIn('learner-vocabulary policy v2', call['instructions'])
                self.assertIn('canonical lemma there be', call['instructions'])
                self.assertNotIn('up to six', call['instructions'])
                self.assertEqual(call['text']['format']['schema']['properties']['words']['maxItems'], 12)
                self.assertEqual(call['max_output_tokens'], vocabulary_policy.MAX_OUTPUT_TOKENS)
        with patch('community_dictionary.port_vocabulary_ai._openai_client') as client:
            port_vocabulary_ai.analyse(data, None, model='fixture-model', api_key='fixture-key')
            call = client.return_value.__enter__.return_value.responses.create.call_args.kwargs
            self.assertIn(vocabulary_policy.COMMON, call['instructions'])
            self.assertEqual(call['text']['format']['schema']['properties']['words']['maxItems'], 12)

    def test_english_exception_is_not_applied_to_other_languages(self):
        for language in ['French', 'Swedish', 'German', 'Japanese', 'Chinese', 'Korean', 'unknown-language']:
            guidance = capture_vocabulary.mwe_guidance(language)
            self.assertIn(vocabulary_policy.COMMON, guidance)
            self.assertNotIn('canonical lemma there be', guidance)
        self.assertIn('est garé', capture_vocabulary.mwe_guidance('French'))
        self.assertIn('sträcker … ut sig', capture_vocabulary.mwe_guidance('Swedish'))
        self.assertTrue(capture_vocabulary.aligned_surface('猫', '猫が寝ている。'))
        self.assertFalse(capture_vocabulary.aligned_surface('cat', '猫 and caterpillar'))

    def test_french_existential_guidance_reaches_both_requests_and_modal_spans_align(self):
        sentence = 'Il peut y avoir un problème.'
        data = {'target_language': 'French', 'sentence': sentence, 'vocabulary': []}
        with patch('community_dictionary.capture_ai._openai_client') as capture_client, \
                patch('community_dictionary.port_vocabulary_ai._openai_client') as rebuild_client:
            capture_ai.interpret(capture_base.picture().read(), {**data, 'input_mode': 'text'},
                                 model='fixture-model', api_key='fixture-key')
            port_vocabulary_ai.analyse(data, None, model='fixture-model', api_key='fixture-key')
            for client in (capture_client, rebuild_client):
                call = client.return_value.__enter__.return_value.responses.create.call_args.kwargs
                self.assertIn('canonical lemma il y a', call['instructions'])
                self.assertIn('"Il … y avoir"', call['instructions'])

        self.assertTrue(capture_vocabulary.aligned_surface('Il … y avoir', sentence))
        self.assertNotIn('French existential convention:', vocabulary_policy.guidance('de'))


class SentenceFollowupTests(TestCase):
    setUp = EvaluationTests.setUp
    skills = EvaluationTests.skills
    make_entry = EvaluationTests.make_entry
    link = EvaluationTests.link
    batch = EvaluationTests.batch
    close = EvaluationTests.close

    def repeat(self, batch, token=None, client=None):
        import uuid
        return (client or self.owner_client).post(url('evaluation-repeat-sentences',
            self.dictionary.pk, batch.pk), {'token': token or uuid.uuid4()})

    def test_followup_preserves_pages_order_frozen_ratings_and_new_vocabulary(self):
        import uuid
        self.make_entry('En annan katt sover.', 'Another cat sleeps.')
        batch = self.batch(sampling='random', size=2)
        original_ids = list(batch.items.values_list('entry_id', flat=True))
        old = batch.items.get(entry=self.sentence)
        session = EvaluationSession.objects.create(evaluation_set=batch, user=self.owner,
            dimensions=['vocabulary'], involvement='yes')
        rating = EvaluationRating.objects.create(session=session,
            unit=old.units.get(dimension='vocabulary'), score='minor', comment='BASELINE_PRIVATE_RATING')
        self.close(batch)
        extra = self.make_entry('soffa', 'sofa', kind='word', image=False)
        self.link(self.sentence, extra, 'soffan')
        token = uuid.uuid4()
        response = self.repeat(batch, token)
        self.assertEqual(response.status_code, 302)
        from community_dictionary.models import EvaluationSet
        followup = EvaluationSet.objects.get(pk=token)
        self.assertEqual(followup.based_on_id, batch.pk)
        self.assertEqual(list(followup.items.values_list('entry_id', flat=True)), original_ids)
        self.assertEqual(len(followup.items.get(entry=self.sentence).snapshot['words']), 2)
        old.refresh_from_db(); rating.refresh_from_db()
        self.assertEqual(len(old.snapshot['words']), 1)
        self.assertEqual((rating.score, rating.comment), ('minor', 'BASELINE_PRIVATE_RATING'))
        self.assertFalse(followup.sessions.exists())
        self.assertEqual(self.repeat(batch, token).url, response.url)
        self.assertNotContains(self.owner_client.get(response.url), 'BASELINE_PRIVATE_RATING')

    def test_open_sets_nonowners_and_unavailable_pages_cannot_repeat(self):
        batch = self.batch()
        self.assertEqual(self.repeat(batch).status_code, 409)
        self.close(batch)
        self.assertEqual(self.repeat(batch, client=self.client).status_code, 404)
        self.sentence.archived = True; self.sentence.save()
        self.assertEqual(self.repeat(batch).status_code, 409)

    def test_followup_can_be_named_for_the_new_policy(self):
        import uuid
        from community_dictionary.models import EvaluationSet
        batch = self.batch(); self.close(batch)
        token = uuid.uuid4()
        endpoint = url('evaluation-repeat-sentences', self.dictionary.pk, batch.pk)
        self.assertEqual(self.owner_client.post(endpoint,
            {'token': token, 'name': 'x' * 161}).status_code, 409)
        self.assertFalse(EvaluationSet.objects.filter(pk=token).exists())
        response = self.owner_client.post(endpoint,
            {'token': token, 'name': '  Word extraction pilot 2 — policy v2  '})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(EvaluationSet.objects.get(pk=token).name,
                         'Word extraction pilot 2 — policy v2')
