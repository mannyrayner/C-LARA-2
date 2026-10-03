"""Multiple-choice practice uses real, current, non-conflicting alternatives."""
import random
from unittest.mock import patch

from django.test import TestCase

from community_dictionary import practice
from community_dictionary.models import Entry, ImageWordLink
from community_dictionary.participation import withdraw_all
from . import test_workflow as workflow


class PracticeChoiceTests(TestCase):
    setUp = workflow.WorkflowTests.setUp
    url = workflow.WorkflowTests.url
    post = workflow.WorkflowTests.post
    create_entry = workflow.WorkflowTests.create_entry

    def word(self, word, meaning=None, category=''):
        self.client.force_login(self.owner)
        return self.create_entry(word=word, meaning=meaning or word, category=category,
            audio=workflow.recording(), publish_now='on')

    def deck(self, **params):
        response = self.client.get(self.url('practice-data'), {'style':'choice', **params})
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def seed(self):
        return [self.word(word) for word in ['katt','fisk','elefant','tekanna','skor','stol']]

    def test_all_six_modes_have_four_real_unique_choices_and_one_answer(self):
        entries = self.seed()
        self.client.force_login(self.member)
        with patch('projects.views._build_ai_client', side_effect=AssertionError('No paid generation')):
            for mode, _ in practice.MODES:
                data = self.deck(mode=mode)
                self.assertEqual(data['style'], 'choice')
                for card in data['cards']:
                    self.assertEqual(len(card['options']), 4)
                    ids = [row['id'] for row in card['options']]
                    self.assertEqual(ids.count(card['id']), 1)
                    self.assertEqual(len(ids), len(set(ids)))
                    self.assertTrue(set(ids) <= {e.pk for e in entries})
                    self.assertTrue(all(row[mode.split('-')[1]] for row in card['options']))

    def test_duplicate_words_and_variants_are_never_wrong_options(self):
        entries = [self.word(word) for word in ['häst',' HÄST ','en häst','hästen','elefant','tekanna']]
        horse_ids = {entry.pk for entry in entries[:4]}
        for card in self.deck()['cards']:
            if card['id'] in horse_ids:
                self.assertEqual({o['id'] for o in card['options']} & horse_ids, {card['id']})

    def test_same_translation_is_not_a_distractor(self):
        a = self.word('soffa','sofa')
        b = self.word('divan',' SOFA ')
        self.word('elefant')
        for card in self.deck()['cards']:
            if card['id'] == a.pk:
                self.assertNotIn(b.pk, [o['id'] for o in card['options']])

    def test_extra_word_link_excluded_even_when_both_have_their_own_photos(self):
        sofa = self.word('soffa')
        cat = self.word('katt')
        self.word('elefant')
        original = self.deck()
        ImageWordLink.objects.create(image=sofa.contributions.get(kind='image'), word_entry=cat, created_by=self.owner)
        self.assertFalse(self.client.get(self.url('practice-data'), {'validate':original['revision']}).json()['valid'])
        for mode, _ in practice.MODES:
            for card in self.deck(mode=mode)['cards']:
                if card['id'] in [sofa.pk, cat.pk]:
                    self.assertEqual({o['id'] for o in card['options']} & {sofa.pk,cat.pk}, {card['id']})

    def test_small_dictionary_has_two_options_or_a_clear_recall_suggestion(self):
        self.word('katt')
        response = self.client.get(self.url('practice-data'), {'style':'choice'})
        self.assertEqual(response.status_code, 400)
        self.assertIn('Reveal the answer', response.json()['error'])
        self.word('elefant')
        for card in self.deck()['cards']:
            self.assertEqual(len(card['options']), 2)
        response = self.client.get(self.url('practice-data'), {'style':'recall'})
        self.assertEqual(len(response.json()['cards']), 2)
        self.assertTrue(all('options' not in card for card in response.json()['cards']))

    def test_distractors_stay_within_category_and_accepted_material(self):
        home = {self.word('katt',category='Home').pk, self.word('tekanna',category='Home').pk}
        self.word('elefant',category='Outside')
        self.client.force_login(self.member)
        self.create_entry(word='secret proposal', audio=workflow.recording(), category='Home')
        for card in self.deck(category='Home')['cards']:
            self.assertEqual({o['id'] for o in card['options']}, home)

    def test_withdrawal_of_a_distractor_invalidates_game_and_blocks_its_media(self):
        entries = self.seed()
        self.client.force_login(self.member)
        old = self.deck()
        url = old['cards'][0]['options'][0]['audio']
        withdraw_all(self.owner, self.dictionary.pk, 0, successor_id=self.member.pk)
        self.assertFalse(self.client.get(self.url('practice-data'), {'validate':old['revision']}).json()['valid'])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.get(self.url('practice-data'), {'style':'choice'}).status_code, 400)

    def test_answer_positions_are_shuffled_and_deck_size_bounded(self):
        for word in ['katt','fisk','elefant','tekanna','skor','stol','skrivbord','apelsin','telefon','gardin','bokhylla','spegel']:
            self.word(word)
        rows, _, _ = practice.catalogue(self.dictionary)
        positions = set()
        for seed in range(4):
            cards = practice.choice_cards(rows, 'image-text', random.Random(seed))
            self.assertEqual(len(cards), 10)
            positions.update(next(i for i,o in enumerate(c['options']) if o['id']==c['id']) for c in cards)
        self.assertEqual(positions, {0,1,2,3})

    def test_stale_tts_is_neither_question_nor_answer_option(self):
        entries = self.seed()
        old = entries[0].contributions.get(kind='audio')
        old.provenance={'origin':'synthetic','source_text':'wrong word','language':'Swedish'};old.save()
        data = self.deck(mode='text-audio')
        self.assertNotIn(entries[0].pk, [c['id'] for c in data['cards']])
        self.assertNotIn(entries[0].pk, [o['id'] for c in data['cards'] for o in c['options']])

    def test_invalid_style_and_default_interface(self):
        response=self.client.get(self.url('practice'))
        self.assertContains(response, '<option value="choice">Multiple choice</option>', html=True)
        self.assertEqual(self.client.get(self.url('practice-data'), {'style':'unknown'}).status_code, 400)
