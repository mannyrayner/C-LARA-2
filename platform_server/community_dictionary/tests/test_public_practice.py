"""Anonymous games cannot broaden the accepted-only public-content boundary."""
from contextlib import closing
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from community_dictionary import practice
from community_dictionary.models import Contribution, Dictionary, Entry, ImageWordLink, WithdrawalHold, Participation
from community_dictionary.participation import withdraw_all
from . import test_public_browsing as fixtures


class PublicPracticeTests(TestCase):
    setUp = fixtures.PublicBrowsingTests.setUp
    make_entry = fixtures.PublicBrowsingTests.make_entry
    add_media = fixtures.PublicBrowsingTests.add_media
    url = fixtures.PublicBrowsingTests.url

    def dataset(self, **params):
        response = self.client.get(self.url('public-practice-data'), params)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIn('no-store', response['Cache-Control'])
        return response.json()

    def test_six_modes_without_login_ai_or_persistent_scores(self):
        before = list(Contribution.objects.values_list('pk', 'status'))
        with patch('community_dictionary.photo_ai._openai_client', side_effect=AssertionError('No AI')), \
             patch('projects.billing.apply_credit_delta', side_effect=AssertionError('No charge')):
            response = self.client.get(self.url('public-practice'))
            self.assertContains(response, 'Start flashcards')
            self.assertContains(response, self.url('public-practice-data'))
            self.assertNotContains(response, self.url('practice-data'))
            self.assertNotContains(response, 'Settings')
            for mode, _ in practice.MODES:
                cards = self.dataset(mode=mode)['cards']
                self.assertEqual(len(cards), 1)
                self.assertEqual(cards[0]['text'], 'katt')
                self.assertEqual(cards[0]['word_url'], self.url('public-word', self.word.pk))
                self.assertEqual(cards[0]['image'], self.url('public-media', self.image.pk))
        self.assertEqual(before, list(Contribution.objects.values_list('pk', 'status')))

    def test_choice_and_both_puzzles_reuse_public_word_pages_and_media(self):
        for word, meaning in [('hund', 'dog'), ('häst', 'horse'), ('hatt', 'hat')]:
            entry = self.make_entry(word, meaning, 'Animals')
            self.add_media(entry, 'image'); self.add_media(entry, 'audio')
        for mode, _ in practice.MODES:
            data = self.dataset(mode=mode, style='choice')
            self.assertTrue(data['cards'])
            self.assertGreaterEqual(len(data['cards'][0]['options']), 2)
        for game in ['crossword', 'scramble']:
            data = self.dataset(game=game)
            self.assertGreaterEqual(len(data['clues']), 2)
            self.assertTrue(all('/browse/' in c['word_url'] for c in data['clues']))

    def test_private_unlisted_hidden_archived_and_personal_access(self):
        # Listing does not grant practice; an unlisted public link does.
        Dictionary.objects.filter(pk=self.dictionary.pk).update(discoverable=False)
        self.assertEqual(self.client.get(self.url('public-practice')).status_code, 200)
        for field, value in [('public_browsing_enabled', False), ('hidden', True), ('personal', True), ('archived', True)]:
            Dictionary.objects.filter(pk=self.dictionary.pk).update(**{field: value})
            for name in ['public-practice', 'public-practice-data']:
                self.assertEqual(self.client.get(self.url(name)).status_code, 404)
            Dictionary.objects.filter(pk=self.dictionary.pk).update(**{field: not value})

    def test_current_accepted_fields_only_no_legacy_draft_or_provenance_leaks(self):
        legacy = Entry.objects.create(dictionary=self.dictionary, created_by=self.owner,
            word='LEGACY-SECRET', meaning='PRIVATE-MEANING', category='PRIVATE-CATEGORY')
        self.add_media(legacy, 'image')
        Contribution.objects.create(entry=self.word, author=self.member, kind='text', word='DRAFT-SECRET')
        self.image.provenance = {'prompt': 'PRIVATE-PROMPT'}; self.image.save()
        self.word.current_meaning.status = 'withdrawn'; self.word.current_meaning.save()
        response = self.client.get(self.url('public-practice-data'))
        for value in ['LEGACY-SECRET', 'PRIVATE-MEANING', 'PRIVATE-CATEGORY', 'DRAFT-SECRET', 'PRIVATE-PROMPT']:
            self.assertNotContains(response, value)
        self.assertEqual(self.dataset()['cards'][0]['meaning'], '')

    def test_pending_rejected_and_held_media_not_in_cards(self):
        for status in ['pending', 'rejected', 'withdrawn', 'removed']:
            Contribution.objects.filter(pk=self.image.pk).update(status=status)
            self.assertEqual(self.dataset()['cards'], [])
        Contribution.objects.filter(pk=self.image.pk).update(status='accepted')
        state = Participation.objects.create(dictionary=self.dictionary, user=self.third, withdrawn=True)
        WithdrawalHold.objects.create(participation=state, contribution=self.image)
        self.assertEqual(self.dataset()['cards'], [])

    def test_linked_picture_obeys_source_visibility_and_revocation(self):
        other = self.make_entry('soffa', 'sofa')
        ImageWordLink.objects.create(image=self.image, word_entry=other, created_by=self.owner)
        before = self.dataset()
        self.assertEqual(len(before['cards']), 2)
        Contribution.objects.filter(pk=self.image.pk).update(status='withdrawn')
        self.assertFalse(self.dataset(validate=before['revision'])['valid'])
        self.assertEqual(self.dataset()['cards'], [])
        self.assertEqual(self.client.get(self.url('public-media', self.image.pk)).status_code, 404)

    def test_public_toggle_and_withdrawal_invalidate_open_games(self):
        before = self.dataset()
        withdraw_all(self.member, self.dictionary.pk, 0)
        self.assertFalse(self.dataset(validate=before['revision'])['valid'])
        self.assertEqual(self.dataset()['cards'], [])
        Dictionary.objects.filter(pk=self.dictionary.pk).update(public_browsing_enabled=False)
        self.assertEqual(self.client.get(self.url('public-practice-data'), {'validate': before['revision']}).status_code, 404)

    def test_stale_synthetic_audio_and_category_filters(self):
        self.audio.provenance = {'origin': 'synthetic', 'source_text': 'old text', 'language': 'Swedish'}
        self.audio.save()
        self.assertEqual(self.dataset(mode='text-audio')['cards'], [])
        self.assertEqual(self.dataset(category='No such category')['cards'], [])
        self.assertEqual(len(self.dataset(category='Animals')['cards']), 1)
        self.assertEqual(self.client.get(self.url('public-media', self.audio.pk)).status_code, 404)

    def test_post_rejected_and_member_endpoints_still_require_membership(self):
        for name in ['public-practice', 'public-practice-data']:
            self.assertEqual(self.client.post(self.url(name)).status_code, 405)
        self.assertEqual(self.client.get(self.url('practice')).status_code, 302)
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(self.url('practice')).status_code, 404)
        self.assertEqual(len(self.dataset()['cards']), 1)
        for part in [self.image, self.audio]:
            with closing(self.client.get(self.url('public-media', part.pk))) as response:
                self.assertEqual(response.status_code, 200)

    def test_invalid_game_settings_fail_without_mutation(self):
        for params in [{'game': 'bad'}, {'mode': 'bad'}, {'style': 'bad'}, {'style': 'choice'}]:
            self.assertEqual(self.client.get(self.url('public-practice-data'), params).status_code, 400)
