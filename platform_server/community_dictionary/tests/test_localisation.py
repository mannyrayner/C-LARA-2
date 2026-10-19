"""Interface preferences select useful dictionaries without changing their contents."""
from django.core import serializers
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import translation

from community_dictionary.localisation import PREFIX, UI_COOKIE
from community_dictionary.models import (
    Contribution, Dictionary, Entry, Event, Membership, Participation,
)
from community_dictionary.services import accept
from . import test_workflow as workflow


def url(name, *args):
    return reverse('community_dictionary:' + name, args=args)


class LocalisationTests(TestCase):
    setUp = workflow.WorkflowTests.setUp

    def make_dictionary(self, name, language='English', explanations='French', **values):
        return Dictionary.objects.create(
            name=name, language=language, explanation_language=explanations,
            **{'owner': self.outsider, 'discoverable': True,
               'public_browsing_enabled': True, **values})

    def choose(self, language, client=None, destination=None, **extra):
        return (client or self.client).post(url('set-language'), {
            'language': language, 'next': destination or url('home'), **extra})

    def names(self, response):
        return [row['name'] for row in response.context['learning_recommendations']]

    def content_snapshot(self):
        return serializers.serialize('json', [
            *Dictionary.objects.order_by('pk'), *Entry.objects.order_by('pk'),
            *Contribution.objects.order_by('pk'), *Event.objects.order_by('pk'),
        ])

    def test_default_and_invalid_cookie_use_english_only_in_dictionary_app(self):
        guest = Client()
        for preference in ['', 'unknown', 'FR']:
            guest.cookies[UI_COOKIE] = preference
            response = guest.get(url('public-home'))
            self.assertEqual(response['Content-Language'], 'en')
            self.assertContains(response, '<html lang="en">')
            self.assertContains(response, 'Find dictionaries')
            self.assertIn('Cookie', response['Vary'])
        guest.cookies[UI_COOKIE] = 'fr'
        self.assertNotIn('Content-Language', guest.get('/accounts/login/'))

    def test_dictionary_locale_restores_the_previous_translation_context(self):
        self.choose('fr')
        with translation.override('de'):
            response = self.client.get(url('home'))
            self.assertEqual(response['Content-Language'], 'fr')
            self.assertEqual(translation.get_language(), 'de')

    def test_selector_is_available_to_visitors_and_members(self):
        for client, destination in [(Client(), url('public-home')), (self.client, url('home'))]:
            response = client.get(destination)
            self.assertContains(response, 'Français')
            self.assertContains(response, 'English')
            self.assertContains(response, url('set-language'))
            self.assertContains(response, 'name="language"')

    def test_choice_is_a_scoped_cookie_and_remains_after_logout(self):
        response = self.choose('fr')
        self.assertRedirects(response, url('home'), fetch_redirect_response=False)
        cookie = response.cookies[UI_COOKIE]
        self.assertEqual(cookie.value, 'fr')
        self.assertEqual(cookie['path'], PREFIX)
        self.assertEqual(cookie['samesite'], 'Lax')
        self.assertTrue(cookie['httponly'])
        self.assertGreater(int(cookie['max-age']), 30 * 24 * 60 * 60)
        self.assertEqual(self.client.get(url('home'))['Content-Language'], 'fr')
        self.client.post(url('logout'))
        self.assertEqual(self.client.get(url('public-home'))['Content-Language'], 'fr')

    def test_https_preference_cookie_is_secure(self):
        response = self.client.post(url('set-language'), {'language': 'fr'}, secure=True)
        self.assertTrue(response.cookies[UI_COOKIE]['secure'])

    def test_selector_requires_post_csrf_and_a_supported_language(self):
        self.assertEqual(self.client.get(url('set-language'), {'language': 'fr'}).status_code, 405)
        self.assertEqual(self.choose('de').status_code, 400)
        self.assertNotIn(UI_COOKIE, self.client.cookies)
        csrf = Client(enforce_csrf_checks=True)
        self.assertEqual(self.choose('fr', csrf).status_code, 403)
        csrf.get(url('public-home'))
        response = self.choose('fr', csrf, csrfmiddlewaretoken=csrf.cookies['csrftoken'].value)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.cookies[UI_COOKIE].value, 'fr')

    def test_redirect_retains_current_dictionary_search_and_rejects_other_destinations(self):
        current = url('dictionary', self.dictionary.pk) + '?view=words&q=katt&category=Animals'
        self.assertEqual(self.choose('fr', destination=current)['Location'], current)
        for destination in [
            'https://example.org/community-dictionaries/', '//example.org/',
            'https://testserver/community-dictionaries/', '/accounts/login/',
            '/community-dictionaries/\\example.org/',
        ]:
            self.assertEqual(self.choose('fr', destination=destination)['Location'], url('home'))
            self.assertEqual(self.choose('fr', Client(), destination)['Location'], url('public-home'))

    def test_english_default_prefers_french_and_blank_explanations_mean_english(self):
        french = self.make_dictionary('French for English speakers', 'French', 'English')
        german = self.make_dictionary('German with legacy explanations', 'German', '')
        wrong = self.make_dictionary('English for French speakers')
        response = self.client.get(url('home'))
        self.assertEqual(response.context['learning_language'], 'fr')
        self.assertEqual(self.names(response), [french.name])
        self.assertEqual(set(dict(response.context['learning_choices'])), {'fr', 'de', 'sv'})
        # The original member list and discovery selection remain available.
        self.assertContains(response, self.dictionary.name)
        self.assertContains(response, wrong.name)
        response = self.client.get(url('home'), {'learning': 'de'})
        self.assertEqual(self.names(response), [german.name])

    def test_french_default_prefers_english_and_matches_language_names_and_codes(self):
        expected = [self.make_dictionary('English ' + str(index), 'English', spelling)
                    for index, spelling in enumerate(['French', 'fr-CA', ' Français '])]
        self.make_dictionary('German for French speakers', 'German', 'fr')
        other = self.make_dictionary('Swedish for English speakers', 'Swedish', '')
        self.choose('fr')
        response = self.client.get(url('home'))
        self.assertEqual(response.context['learning_language'], 'en')
        self.assertEqual(response.context['form']['explanation_language'].value(), 'French')
        self.assertEqual(self.names(response), [item.name for item in expected])
        self.assertEqual(set(dict(response.context['learning_choices'])), {'en', 'de'})
        self.assertContains(response, other.name)
        self.assertContains(response, self.dictionary.name)

    def test_explicit_learning_choice_is_remembered_separately_for_each_interface(self):
        self.make_dictionary('English with French explanations')
        german = self.make_dictionary('German with French explanations', 'German', 'French')
        self.make_dictionary('French with English explanations', 'French', 'English')
        self.choose('fr')
        response = self.client.get(url('home'), {'learning': 'de'})
        self.assertEqual(self.names(response), [german.name])
        self.assertEqual(self.client.get(url('home')).context['learning_language'], 'de')
        self.choose('en')
        self.assertEqual(self.client.get(url('home')).context['learning_language'], 'fr')
        self.choose('fr')
        self.assertEqual(self.client.get(url('home')).context['learning_language'], 'de')
        self.client.get(url('home'), {'learning': 'not-a-language'})
        self.assertEqual(self.client.get(url('home')).context['learning_language'], 'de')

    def test_all_learning_languages_preserves_matching_explanation_boundary(self):
        english = self.make_dictionary('English with French explanations')
        german = self.make_dictionary('German with French explanations', 'German', 'French')
        self.make_dictionary('French with English explanations', 'French', 'English')
        self.choose('fr')
        response = self.client.get(url('home'), {'learning': 'all'})
        self.assertEqual(set(self.names(response)), {english.name, german.name})
        self.assertEqual(response.context['learning_language'], 'all')
        self.assertEqual(self.client.get(url('home')).context['learning_language'], 'all')

    def test_fallback_uses_an_available_language_and_empty_list_is_valid(self):
        guest = Client()
        self.choose('fr', guest)
        empty = guest.get(url('public-home'))
        self.assertEqual(empty.context['learning_choices'], [])
        self.assertEqual(empty.context['learning_recommendations'], [])
        self.assertEqual(empty.context['learning_language'], '')
        german = self.make_dictionary('German only', 'German', 'French')
        response = guest.get(url('public-home'))
        self.assertEqual(response.context['learning_language'], 'de')
        self.assertEqual(self.names(response), [german.name])

    def test_recommendations_respect_visibility_membership_and_discovery_boundaries(self):
        public = self.make_dictionary('Public English')
        private_listed = self.make_dictionary('Listed private English', public_browsing_enabled=False)
        own = self.make_dictionary('Own private English', owner=self.member,
                                   discoverable=False, public_browsing_enabled=False)
        blocked = []
        for field in ['hidden', 'archived', 'personal']:
            blocked.append(self.make_dictionary('Excluded ' + field, **{field: True}))
        blocked.append(self.make_dictionary('Unlisted English', discoverable=False))
        for state in ['invited', 'inactive', 'withdrawn']:
            item = self.make_dictionary('Private ' + state, discoverable=False,
                                       public_browsing_enabled=False)
            Membership.objects.create(dictionary=item, user=self.member,
                accepted=state != 'invited', status='inactive' if state == 'inactive' else 'active')
            if state == 'withdrawn':
                Participation.objects.create(dictionary=item, user=self.member, withdrawn=True)
            blocked.append(item)
        self.choose('fr')
        response = self.client.get(url('home'))
        recommendations = {row['name']: row['url'] for row in response.context['learning_recommendations']}
        self.assertEqual(recommendations, {
            own.name: url('dictionary', own.pk), public.name: url('public-dictionary', public.pk),
            private_listed.name: url('discover-dictionary', private_listed.pk),
        })
        guest = Client(); self.choose('fr', guest)
        self.assertEqual(set(self.names(guest.get(url('public-home')))), {public.name, private_listed.name})
        self.assertEqual(guest.get(url('public-dictionary', private_listed.pk)).status_code, 404)
        self.assertEqual(self.client.get(url('dictionary', blocked[-1].pk)).status_code, 200)
        # A withdrawn participant gets the existing status page, never new content access.
        self.assertNotContains(self.client.get(url('dictionary', blocked[-1].pk)), 'Browse this dictionary')

    def test_locale_does_not_rewrite_dictionary_content_or_limit_direct_selection(self):
        entry = Entry.objects.create(dictionary=self.dictionary, created_by=self.owner)
        part = Contribution.objects.create(entry=entry, author=self.owner,
            kind='text', text_field='word', word='katt')
        accept(part, self.owner)
        other = self.make_dictionary('Public mismatched explanations', 'Italian', 'English')
        before = self.content_snapshot()
        self.choose('fr')
        self.client.get(url('home'), {'learning': 'en'})
        self.assertContains(self.client.get(url('dictionary', self.dictionary.pk), {'view': 'words'}), 'katt')
        guest = Client(); self.choose('fr', guest)
        self.assertContains(guest.get(url('public-dictionary', other.pk)), other.name)
        self.assertEqual(self.content_snapshot(), before)

    def test_french_navigation_and_javascript_catalog_are_served_in_french(self):
        self.choose('fr')
        response = self.client.get(url('home'))
        self.assertContains(response, '<html lang="fr">')
        self.assertContains(response, 'Dictionnaires communautaires')
        self.assertContains(response, url('javascript-catalog'))
        catalog = self.client.get(url('javascript-catalog'))
        self.assertEqual(catalog.status_code, 200)
        self.assertEqual(catalog['Content-Language'], 'fr')
        self.assertContains(catalog, 'Connexion interrompue.')
