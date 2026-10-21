"""A third interface keeps content, access and remembered choices independent."""
import gettext as catalog_gettext
import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core import serializers
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import translation

from community_dictionary.localisation import PREFIX, UI_COOKIE, language_key
from community_dictionary.models import Contribution, Dictionary, Entry, Event, Membership, Participation
from community_dictionary.services import accept


def url(name, *args):
    return reverse('community_dictionary:' + name, args=args)


class SlovakLocalisationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.owner = User.objects.create_user('owner')
        cls.member = User.objects.create_user('Ivana')
        cls.other = User.objects.create_user('other')
        cls.dictionary = Dictionary.objects.create(owner=cls.owner, name='Existing Slovak',
            language='Slovak', explanation_language='English')
        Membership.objects.create(dictionary=cls.dictionary, user=cls.member, accepted=True)

    def setUp(self):
        self.client.force_login(self.member)

    def make_dictionary(self, name, language='English', explanations='Slovak', **values):
        return Dictionary.objects.create(name=name, language=language,
            explanation_language=explanations, **{'owner': self.other,
            'discoverable': True, 'public_browsing_enabled': True, **values})

    def choose(self, language='sk', client=None, destination=None, **values):
        return (client or self.client).post(url('set-language'), {
            'language': language, 'next': destination or url('home'), **values})

    def names(self, response):
        return [row['name'] for row in response.context['learning_recommendations']]

    def content_snapshot(self):
        return serializers.serialize('json', [
            *Dictionary.objects.order_by('pk'), *Entry.objects.order_by('pk'),
            *Contribution.objects.order_by('pk'), *Event.objects.order_by('pk'),
        ])

    def test_slovak_selector_and_scoped_preference_work_for_members_and_visitors(self):
        for client, destination in [(self.client, url('home')), (Client(), url('public-home'))]:
            response = client.get(destination)
            self.assertContains(response, '<option value="sk" lang="sk">Slovenčina</option>')
            chosen = self.choose(client=client, destination=destination)
            self.assertEqual(chosen['Location'], destination)
            cookie = chosen.cookies[UI_COOKIE]
            self.assertEqual(cookie.value, 'sk')
            self.assertEqual(cookie['path'], PREFIX)
            self.assertTrue(cookie['httponly'])
            self.assertEqual(cookie['samesite'], 'Lax')
            self.assertGreater(int(cookie['max-age']), 30 * 24 * 60 * 60)
            page = client.get(destination)
            self.assertEqual(page['Content-Language'], 'sk')
            self.assertContains(page, '<html lang="sk">')
            self.assertIn('Cookie', page['Vary'])
        self.client.post(url('logout'))
        self.assertEqual(self.client.get(url('public-home'))['Content-Language'], 'sk')
        self.assertNotIn('Content-Language', self.client.get('/accounts/login/'))

    def test_slovak_preference_preserves_secure_cookie_csrf_and_redirect_boundaries(self):
        current = url('dictionary', self.dictionary.pk) + '?view=words&q=strom'
        response = self.client.post(url('set-language'), {'language': 'sk', 'next': current}, secure=True)
        self.assertEqual(response['Location'], current)
        self.assertTrue(response.cookies[UI_COOKIE]['secure'])
        for destination in ['https://example.org/', '//example.org/', '/accounts/login/',
                            '/community-dictionaries/\\example.org/']:
            self.assertEqual(self.choose(destination=destination)['Location'], url('home'))
        csrf = Client(enforce_csrf_checks=True)
        self.assertEqual(self.choose(client=csrf).status_code, 403)
        csrf.get(url('public-home'))
        response = self.choose(client=csrf, csrfmiddlewaretoken=csrf.cookies['csrftoken'].value)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.cookies[UI_COOKIE].value, 'sk')
        self.assertEqual(self.choose('sl').status_code, 400)
        self.assertEqual(self.choose('SK').status_code, 400)

    def test_matching_accepts_slovak_names_accents_and_codes_without_confusing_slovenian(self):
        for spelling in ['Slovak', 'slovaque', ' Slovenčina ', 'SLOVENCINA', 'sk', 'sk_SK', 'sk-SK']:
            self.assertEqual(language_key(spelling), 'sk', spelling)
        for spelling in ['angličtina', 'anglictina', 'English', 'en-GB']:
            self.assertEqual(language_key(spelling), 'en', spelling)
        for spelling in ['francúzština', 'francuzstina', 'French', 'Français']:
            self.assertEqual(language_key(spelling), 'fr', spelling)
        for spelling in ['Slovenian', 'slovenščina', 'sl']:
            self.assertNotEqual(language_key(spelling), 'sk', spelling)
        self.assertEqual(language_key('', explanation=True), 'en')

    def test_new_dictionary_explanation_defaults_are_canonical_for_each_interface(self):
        for ui, expected in [('en', 'English'), ('fr', 'French'), ('sk', 'Slovak')]:
            self.choose(ui)
            response = self.client.get(url('home'))
            self.assertEqual(response.context['form']['explanation_language'].value(), expected)
        response = self.client.post(url('home'), {'name': 'Ivana’s dictionary',
            'language': 'English', 'explanation_language': 'Slovak'})
        self.assertEqual(response.status_code, 302)
        created = Dictionary.objects.get(name='Ivana’s dictionary')
        self.assertEqual((created.language, created.explanation_language), ('English', 'Slovak'))

    def test_slovak_interface_prefers_available_english_with_matching_explanations(self):
        expected = [self.make_dictionary('English ' + str(index), language='angličtina', explanations=spelling)
            for index, spelling in enumerate(['Slovak', 'sk-SK', 'slovenčina', 'slovencina'])]
        self.make_dictionary('French for Slovak speakers', 'French', 'sk')
        legacy = self.make_dictionary('Legacy English explanations', 'German', '')
        self.choose()
        response = self.client.get(url('home'))
        self.assertEqual(response.context['learning_language'], 'en')
        self.assertEqual(set(dict(response.context['learning_choices'])), {'en', 'fr'})
        self.assertEqual(self.names(response), [item.name for item in expected])
        self.assertContains(response, self.dictionary.name)
        self.assertContains(response, legacy.name)

    def test_slovak_fallback_uses_available_language_and_handles_no_matching_dictionary(self):
        guest = Client()
        self.choose(client=guest, destination=url('public-home'))
        response = guest.get(url('public-home'))
        self.assertEqual(response.context['learning_language'], '')
        self.assertEqual(response.context['learning_recommendations'], [])
        german = self.make_dictionary('German only', 'German')
        response = guest.get(url('public-home'))
        self.assertEqual(response.context['learning_language'], 'de')
        self.assertEqual(self.names(response), [german.name])

    def test_learning_choices_are_remembered_separately_for_three_interfaces(self):
        self.make_dictionary('English for Slovak speakers')
        german = self.make_dictionary('German for Slovak speakers', 'German')
        self.make_dictionary('English for French speakers', 'English', 'French')
        french = self.make_dictionary('French for English speakers', 'French', 'English')
        self.choose()
        self.assertEqual(self.names(self.client.get(url('home'), {'learning': 'de'})), [german.name])
        self.choose('fr')
        self.assertEqual(self.client.get(url('home')).context['learning_language'], 'en')
        self.choose('en')
        self.assertEqual(self.names(self.client.get(url('home'))), [french.name])
        self.choose()
        self.assertEqual(self.client.get(url('home')).context['learning_language'], 'de')
        self.client.get(url('home'), {'learning': 'invalid'})
        self.assertEqual(self.client.get(url('home')).context['learning_language'], 'de')
        all_languages = self.client.get(url('home'), {'learning': 'all'})
        self.assertEqual(set(self.names(all_languages)), {'English for Slovak speakers', german.name})
        self.assertEqual(self.client.get(url('home')).context['learning_language'], 'all')

    def test_slovak_recommendations_retain_member_visibility_and_access_rules(self):
        public = self.make_dictionary('Public English')
        own = self.make_dictionary('Member English', owner=self.member, discoverable=False,
                                   public_browsing_enabled=False)
        for flag in ['hidden', 'archived', 'personal']:
            self.make_dictionary('Excluded ' + flag, **{flag: True})
        private = self.make_dictionary('Unlisted English', discoverable=False,
                                       public_browsing_enabled=False)
        for status in ['invited', 'inactive', 'withdrawn']:
            restricted = self.make_dictionary('Private ' + status, discoverable=False,
                                              public_browsing_enabled=False)
            Membership.objects.create(dictionary=restricted, user=self.member,
                accepted=status != 'invited', status='inactive' if status == 'inactive' else 'active')
            if status == 'withdrawn':
                Participation.objects.create(dictionary=restricted, user=self.member, withdrawn=True)
        self.choose()
        response = self.client.get(url('home'))
        self.assertEqual({row['name']: row['url'] for row in response.context['learning_recommendations']}, {
            own.name: url('dictionary', own.pk), public.name: url('public-dictionary', public.pk)})
        self.assertEqual(self.client.get(url('dictionary', private.pk)).status_code, 404)
        guest = Client(); self.choose(client=guest, destination=url('public-home'))
        self.assertEqual(self.names(guest.get(url('public-home'))), [public.name])

    def test_interface_switching_preserves_existing_dictionary_text_media_and_direct_selection(self):
        entry = Entry.objects.create(dictionary=self.dictionary, created_by=self.owner)
        word = Contribution.objects.create(entry=entry, author=self.owner,
            kind='text', text_field='word', word='strom')
        accept(word, self.owner)
        Contribution.objects.create(entry=entry, author=self.owner, kind='audio',
            status='accepted', file_path='existing-recording.wav')
        other = self.make_dictionary('Other English dictionary', 'English', 'French')
        before = self.content_snapshot()
        for ui in ['sk', 'fr', 'en', 'sk']:
            self.choose(ui)
            self.client.get(url('home'))
            self.assertContains(self.client.get(url('dictionary', self.dictionary.pk), {'view': 'words'}), 'strom')
            self.assertContains(self.client.get(url('public-dictionary', other.pk)), other.name)
        self.assertEqual(self.content_snapshot(), before)

    def test_slovak_translation_context_is_restored_outside_the_app(self):
        self.choose()
        with translation.override('de'):
            self.assertEqual(self.client.get(url('home'))['Content-Language'], 'sk')
            self.assertEqual(translation.get_language(), 'de')
        self.assertNotIn('Content-Language', self.client.get('/accounts/login/'))

    def test_slovak_public_and_member_pages_use_the_compiled_interface_catalog(self):
        english = self.make_dictionary('English with Slovak explanations')
        entry = Entry.objects.create(dictionary=english, created_by=self.other)
        for field, value in [('word', 'tree'), ('meaning', 'strom')]:
            part = Contribution.objects.create(entry=entry, author=self.other,
                kind='text', text_field=field, **{field: value})
            accept(part, self.other)
        self.choose()
        with translation.override('sk'):
            heading = translation.gettext('Community dictionaries')
            english_label = translation.gettext('English')
            for count, expected in [(1, '1 slovo'), (2, '2 slová'), (4, '4 slová'), (5, '5 slov'), (21, '21 slov')]:
                self.assertEqual(translation.ngettext('%(count)s word', '%(count)s words', count) %
                                 {'count': count}, expected)
        self.assertNotEqual(heading, 'Community dictionaries')
        home = self.client.get(url('home'))
        self.assertContains(home, heading)
        self.assertContains(home, english_label)
        guest = Client(); self.choose(client=guest, destination=url('public-home'))
        for page in [url('public-home'), url('public-dictionary', english.pk),
                     url('public-entry', english.pk, entry.pk)]:
            response = guest.get(page)
            self.assertEqual(response['Content-Language'], 'sk')
            self.assertContains(response, '<html lang="sk">')
            self.assertContains(response, heading)
        entry_page = guest.get(url('public-entry', english.pk, entry.pk))
        self.assertContains(entry_page, 'tree')
        self.assertContains(entry_page, 'strom')

    def test_slovak_javascript_catalog_contains_translated_connection_feedback(self):
        self.choose()
        locale = Path(__file__).resolve().parents[1] / 'locale'
        messages = catalog_gettext.translation('djangojs', localedir=locale, languages=['sk'])
        source = 'Connection interrupted.'
        expected = messages.gettext(source)
        self.assertNotEqual(expected, source)
        response = self.client.get(url('javascript-catalog'))
        self.assertEqual(response['Content-Language'], 'sk')
        self.assertContains(response, json.dumps(source) + ': ' + json.dumps(expected))
