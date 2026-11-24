"""Game return context must preserve navigation without broadening content access."""
from pathlib import Path
import shutil
import subprocess
from urllib.parse import parse_qs, urlsplit

from django.test import TestCase
from django.utils.translation import override
from community_dictionary.models import Entry

from . import test_practice as member, test_public_practice as public


TOKEN = 'a' * 32


class GameReturnTests(TestCase):
    setUp = member.PracticeTests.setUp
    url = member.PracticeTests.url
    post = member.PracticeTests.post
    create_entry = member.PracticeTests.create_entry
    word = member.PracticeTests.word
    dataset = member.PracticeTests.dataset

    def test_control_is_optional_and_returns_to_same_dictionary_and_category(self):
        entry = self.word()
        for route in ['word', 'entry']:
            self.assertNotContains(self.client.get(self.url(route, entry.pk)), 'data-game-return')
            response = self.client.get(self.url(route, entry.pk),
                {'return_game': TOKEN, 'game_category': 'Colours & shapes'})
            self.assertContains(response, 'Back to game')
            self.assertContains(response, 'game_navigation.js')
            target = urlsplit(response.context['game_return']['url'])
            self.assertEqual(target.path, self.url('practice'))
            self.assertEqual(parse_qs(target.query), {'resume':[TOKEN], 'category':['Colours & shapes']})
            self.assertEqual(response.context['game_return']['word_prefix'], self.url('word', 0)[:-2])
            self.assertIn('no-store', response['Cache-Control'])

    def test_untrusted_tokens_cannot_supply_return_urls_or_access(self):
        entry = self.word()
        for token in ['https://evil.invalid/', '//evil.invalid', 'a'*33, '<script>', '']:
            response = self.client.get(self.url('word', entry.pk), {'return_game':token})
            self.assertNotContains(response, 'data-game-return')
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(self.url('word', entry.pk), {'return_game':TOKEN}).status_code, 404)

    def test_seed_rebuilds_recall_choice_crossword_and_scramble_without_saved_content(self):
        for word, meaning in [('katt','cat'), ('tak','roof'), ('anka','duck'), ('kanin','rabbit')]:
            self.word(word)
            entry = Entry.objects.latest('pk')
            # Distinct accepted meanings make genuine multiple-choice distractors.
            entry.meaning = meaning
            entry.current_meaning.meaning = meaning
            entry.current_meaning.save()
            entry.save()
        for params in [dict(game='flashcards',style='recall'), dict(game='flashcards',style='choice'),
                       dict(game='crossword'), dict(game='scramble')]:
            first = self.dataset(**params)
            second = self.dataset(seed=first['seed'], **params)
            self.assertEqual(first, second)
        self.assertEqual(self.client.get(self.url('practice-data'), {'seed':'bad'}).status_code, 400)
        before = self.dataset()
        self.dictionary.membership_revision += 1
        self.dictionary.save()
        self.assertNotEqual(self.dataset(seed=before['seed'])['revision'], before['revision'])

    def test_translated_controls(self):
        entry = self.word()
        for language, text in [('fr','Retour au jeu'), ('sk','Späť k hre')]:
            self.client.cookies['community_ui_language'] = language
            with override(language):
                self.assertContains(self.client.get(self.url('word', entry.pk), {'return_game':TOKEN}), text)

    def test_actual_client_navigation_and_progress_recovery(self):
        node = shutil.which('node')
        if not node:
            self.skipTest('Node is not installed')
        result = subprocess.run([node, '--test', str(Path(__file__).with_name('game_return_state.test.cjs'))],
            capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class PublicGameReturnTests(TestCase):
    setUp = public.PublicPracticeTests.setUp
    url = public.PublicPracticeTests.url
    make_entry = public.PublicPracticeTests.make_entry
    add_media = public.PublicPracticeTests.add_media
    dataset = public.PublicPracticeTests.dataset

    def test_visitors_return_only_to_public_games_and_rebuild_the_same_content(self):
        for route in ['public-word','public-entry']:
            response = self.client.get(self.url(route, self.word.pk), {'return_game':TOKEN, 'game_category':'Animals'})
            self.assertContains(response, 'Back to game')
            self.assertEqual(urlsplit(response.context['game_return']['url']).path, self.url('public-practice'))
            self.assertEqual(response.context['game_return']['entry_prefix'], self.url('public-entry', 0)[:-2])
        first = self.dataset(category='Animals')
        self.assertEqual(first, self.dataset(category='Animals', seed=first['seed']))
        self.dictionary.public_browsing_enabled = False
        self.dictionary.save()
        self.assertEqual(self.client.get(self.url('public-word', self.word.pk), {'return_game':TOKEN}).status_code, 404)
        self.assertEqual(self.client.get(self.url('public-practice-data'), {'seed':first['seed']}).status_code, 404)
