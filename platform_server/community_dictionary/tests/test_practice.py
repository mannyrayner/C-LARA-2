"""Games must be useful without copying content out of its withdrawal boundary."""
from unittest.mock import patch

from django.test import Client, TestCase
from django.urls import reverse

from community_dictionary import practice
from community_dictionary.models import Contribution, Dictionary, Entry, ImageWordLink, Membership, Participation
from community_dictionary.participation import withdraw_all, restore_all
from . import test_workflow as workflow


class PracticeTests(TestCase):
    setUp = workflow.WorkflowTests.setUp
    url = workflow.WorkflowTests.url
    post = workflow.WorkflowTests.post
    create_entry = workflow.WorkflowTests.create_entry

    def word(self, word='katt', **extra):
        self.client.force_login(self.owner)
        return self.create_entry(word=word, meaning='cat', audio=workflow.recording(), publish_now='on', **extra)

    def dataset(self, **params):
        response = self.client.get(self.url('practice-data'), params)
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def test_six_directions_and_read_only_member_access_without_ai(self):
        self.word()
        self.client.force_login(self.member)
        before = list(Contribution.objects.values_list('pk', 'status', 'file_path'))
        with patch('projects.views._build_ai_client', side_effect=AssertionError('No AI')):
            response = self.client.get(self.url('practice'))
            self.assertContains(response, 'Start word scramble')
            self.assertEqual(len(response.context['practice_modes']), 6)
            self.assertIn('no-store', response['Cache-Control'])
            for mode, _ in practice.MODES:
                with self.subTest(mode=mode):
                    result = self.dataset(mode=mode)
                    self.assertEqual(len(result['cards']), 1)
                    self.assertEqual(result['mode'], mode)
                    self.assertEqual(result['cards'][0]['text'], 'katt')
        self.assertEqual(before, list(Contribution.objects.values_list('pk', 'status', 'file_path')))

    def test_missing_modalities_and_audio_image_cards_without_words(self):
        self.client.force_login(self.owner)
        self.create_entry(audio=workflow.recording(), publish_now='on')
        self.assertEqual(len(self.dataset(mode='image-audio')['cards']), 1)
        self.assertEqual(len(self.dataset(mode='audio-image')['cards']), 1)
        for mode in ['image-text', 'text-image', 'audio-text', 'text-audio']:
            self.assertEqual(self.dataset(mode=mode)['cards'], [])

    def test_no_pending_rejected_archived_or_hidden_style_content(self):
        entry = self.word()
        entry.archived = True
        entry.save()
        self.client.force_login(self.member)
        self.create_entry(word='pending secret', audio=workflow.recording())
        self.assertEqual(self.dataset()['cards'], [])
        for part in entry.contributions.all():
            self.assertEqual(self.client.get(self.url('practice-media', part.pk)).status_code, 404)

    def test_tts_must_match_current_word_and_language(self):
        entry = self.word()
        audio = entry.contributions.get(kind='audio')
        audio.provenance = {'origin': 'synthetic', 'source_text': 'en katt', 'language': 'Swedish'}
        audio.save()
        self.assertEqual(self.dataset(mode='text-audio')['cards'], [])
        self.assertEqual(self.client.get(self.url('practice-media', audio.pk)).status_code, 404)
        audio.provenance['source_text'] = 'katt'; audio.save()
        self.assertTrue(self.dataset(mode='text-audio')['cards'][0]['audio_synthetic'])
        self.dictionary.language = 'Icelandic'; self.dictionary.save()
        self.assertEqual(self.dataset(mode='text-audio')['cards'], [])

    def test_linked_picture_used_without_copying_and_archived_source_excluded(self):
        sofa = self.word('soffa')
        picture = sofa.contributions.get(kind='image')
        cat = Entry.objects.create(dictionary=self.dictionary, created_by=self.owner, word='katt')
        ImageWordLink.objects.create(image=picture, word_entry=cat, created_by=self.owner)
        cards = self.dataset()['cards']
        self.assertEqual(len(cards), 2)
        self.assertEqual(cards[0]['image'], cards[1]['image'])
        sofa.archived = True; sofa.save()
        self.assertEqual(self.dataset()['cards'], [])

    def test_cross_dictionary_links_and_media_never_leak(self):
        entry = self.word()
        other = Dictionary.objects.create(owner=self.outsider, language='Italian', name='Private')
        foreign = Entry.objects.create(dictionary=other, created_by=self.outsider, word='segreto')
        picture = Contribution.objects.create(entry=foreign, author=self.outsider, kind='image', status='accepted', file_path='secret.jpg')
        ImageWordLink.objects.create(image=picture, word_entry=entry, created_by=self.outsider)
        entry.contributions.filter(kind='image').delete()
        self.assertEqual(self.dataset()['cards'], [])
        self.assertEqual(self.client.get(self.url('practice-media', picture.pk)).status_code, 404)

    def test_category_filter_and_ten_card_limit(self):
        for i in range(12):
            self.word(f'katt {i}', category='Home')
        self.word('hund', category='Outside')
        self.assertEqual(len(self.dataset()['cards']), 10)
        result = self.dataset(category='Outside')
        self.assertEqual([r['text'] for r in result['cards']], ['hund'])
        self.assertEqual(self.dataset(category='missing')['cards'], [])
        response = self.client.get(self.url('practice'), {'category': 'Outside'})
        self.assertEqual(response.context['categories'], ['Home', 'Outside'])

    def test_permissions_for_all_routes_and_after_departure(self):
        entry = self.word()
        image = entry.contributions.get(kind='image')
        urls = [self.url('practice'), self.url('practice-data'), self.url('practice-media', image.pk)]
        self.client.logout()
        for url in urls: self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.outsider)
        for invited in [False, True]:
            if invited: Membership.objects.create(dictionary=self.dictionary, user=self.outsider)
            for url in urls: self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.member)
        member = Membership.objects.get(dictionary=self.dictionary, user=self.member)
        member.status='inactive'; member.save()
        for url in urls: self.assertEqual(self.client.get(url).status_code, 404)
        member.status='active'; member.save()
        Participation.objects.create(dictionary=self.dictionary, user=self.member, withdrawn=True)
        for url in urls: self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.owner)
        self.dictionary.personal=True; self.dictionary.save()
        for url in urls: self.assertEqual(self.client.get(url).status_code, 404)

    def test_withdrawal_invalidates_open_game_and_restore_makes_cards_available(self):
        entry = self.word()
        self.client.force_login(self.member)
        old = self.dataset()
        image = entry.contributions.get(kind='image')
        self.assertTrue(self.dataset(validate=old['revision'])['valid'])
        withdraw_all(self.owner, self.dictionary.pk, 0, successor_id=self.member.pk)
        self.assertFalse(self.dataset(validate=old['revision'])['valid'])
        self.assertEqual(self.dataset()['cards'], [])
        self.assertEqual(self.client.get(self.url('practice-media', image.pk)).status_code, 404)
        restore_all(self.owner, self.dictionary.pk, 1)
        self.assertEqual(len(self.dataset()['cards']), 1)

    def test_edits_and_review_changes_invalidate_game(self):
        entry = self.word()
        old = self.dataset()['revision']
        self.post('contribute', {'edit_text': 'on', 'word': 'katten', 'base_version': 1, 'publish_now': 'on'}, entry.pk)
        self.assertFalse(self.dataset(validate=old)['valid'])
        entry.refresh_from_db()
        old = self.dataset()['revision']
        entry.contributions.filter(kind='image').update(status='rejected')
        self.assertFalse(self.dataset(validate=old)['valid'])

    def test_media_range_and_nonaccepted_media_blocked(self):
        entry = self.word()
        audio = entry.contributions.get(kind='audio')
        url = self.url('practice-media', audio.pk)
        response = self.client.get(url, HTTP_RANGE='bytes=0-9')
        try:
            self.assertEqual(response.status_code, 206)
            self.assertEqual(len(b''.join(response.streaming_content)), 10)
            self.assertIn('no-store', response['Cache-Control'])
        finally: response.close()
        for status in ['pending', 'rejected', 'withdrawn', 'removed']:
            audio.status=status; audio.save()
            self.assertEqual(self.client.get(url).status_code, 404)

    def test_grid_normalization_keeps_accents_and_rejects_unsupported_words(self):
        for word, expected in [('en häst','ENHÄST'), ('árbol','ÁRBOL'), ('ṉaṟa','ṈAṞA'), ('l\u2019été','LÉTÉ'), ('te-kanna','TEKANNA'), ('a',''), ('abc123',''), ('a\u0331b',''), ('x'*13,'')]:
            self.assertEqual(practice.grid_answer(word), expected)

    def test_puzzles_have_correct_paths_numbers_and_current_picture_clues(self):
        for word in ['katt', 'tak', 'anka', 'kanin', 'häst', 'häst']:
            self.word(word)
        for game in ['crossword','scramble']:
            data = self.dataset(game=game)
            self.assertGreaterEqual(len(data['clues']), 2)
            answers = [c['answer'] for c in data['clues']]
            self.assertEqual(len(answers), len(set(answers)))
            self.assertLessEqual(len(data['grid']), 12)
            for clue in data['clues']:
                self.assertEqual(''.join(data['grid'][p['row']][p['col']] for p in clue['path']), clue['answer'])
                self.assertTrue(clue['image'].startswith(self.url('practice')+'media/'))
                self.assertTrue(clue['number'])

    def test_empty_puzzles_bad_parameters_and_post_rejected(self):
        response = self.client.get(self.url('practice'))
        self.assertContains(response, 'No cards are ready')
        self.assertFalse(response.context['has_cards'])
        for params in [{'game':'crossword'}, {'game':'scramble'}, {'game':'unknown'}, {'mode':'audio-audio'}]:
            self.assertEqual(self.client.get(self.url('practice-data'), params).status_code, 400)
        for name in ['practice', 'practice-data']:
            self.assertEqual(self.client.post(self.url(name)).status_code, 405)

    def test_generated_picture_label_and_no_secret_style_prompts(self):
        entry = self.word()
        image = entry.contributions.get(kind='image')
        image.provenance={'origin':'generated','prompt':'secret generation prompt'}; image.save()
        result = self.client.get(self.url('practice-data'))
        self.assertTrue(result.json()['cards'][0]['image_generated'])
        self.assertNotContains(result, 'secret generation prompt')

    def test_invalid_current_pointer_not_used_as_accepted_word(self):
        entry = self.word()
        entry.current_text.status='withdrawn'; entry.current_text.save()
        self.assertEqual(self.dataset()['cards'], [])
