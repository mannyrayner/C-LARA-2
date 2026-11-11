"""Learning choices stay separate from dictionary management and access rights."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from community_dictionary.models import Dictionary, Membership, Participation


def url(name):
    return reverse('community_dictionary:' + name)


class LearningHomeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user('learner')
        cls.other = get_user_model().objects.create_user('other')
        cls.french = Dictionary.objects.create(owner=cls.owner, name='Private French',
            language='French', explanation_language='English')
        cls.german = Dictionary.objects.create(owner=cls.owner, name='Private German',
            language='German', explanation_language='English')
        cls.public = Dictionary.objects.create(owner=cls.other, name='Public French',
            language='fr-CA', explanation_language='', discoverable=True,
            public_browsing_enabled=True)
        cls.slovak_explanations = Dictionary.objects.create(owner=cls.other,
            name='French explained in Slovak', language='French', explanation_language='Slovak',
            discoverable=True, public_browsing_enabled=True)

    def setUp(self):
        self.client.force_login(self.owner)

    def test_first_visit_has_languages_and_no_dictionary_cards_or_creation_form(self):
        response = self.client.get(url('home'))
        self.assertContains(response, 'Which language would you like to learn?')
        self.assertContains(response, 'name="learning" value="fr"')
        self.assertContains(response, 'name="learning" value="de"')
        self.assertNotContains(response, self.french.name)
        self.assertNotContains(response, self.public.name)
        self.assertNotContains(response, 'name="explanation_language"')
        self.assertContains(response, '<details class="account-menu">')
        self.assertContains(response, url('manage'))

    def test_selected_language_is_the_only_dictionary_list(self):
        response = self.client.get(url('home'), {'learning': 'fr'})
        self.assertContains(response, self.french.name, count=1)
        self.assertContains(response, self.public.name, count=1)
        self.assertNotContains(response, self.german.name)
        self.assertContains(response, self.slovak_explanations.name, count=1)
        self.assertContains(response, 'Change language')
        self.assertNotContains(response, 'Create a dictionary')
        self.assertEqual({r['url'] for r in response.context['page']}, {
            reverse('community_dictionary:dictionary', args=[self.french.pk]),
            reverse('community_dictionary:public-dictionary', args=[self.public.pk]),
            reverse('community_dictionary:public-dictionary', args=[self.slovak_explanations.pk])})

    def test_remembered_language_and_change_language_are_independent(self):
        self.client.get(url('home'), {'learning': 'de'})
        self.assertContains(self.client.get(url('home')), self.german.name)
        chooser = self.client.get(url('home'), {'choose': '1'})
        self.assertTrue(chooser.context['choosing_language'])
        self.assertNotContains(chooser, self.german.name)
        self.assertContains(self.client.get(url('home')), self.german.name)
        self.assertContains(self.client.get(url('home'), {'learning': 'invalid'}), self.german.name)

    def test_lists_page_only_the_selected_language(self):
        Dictionary.objects.bulk_create([Dictionary(owner=self.other, name=f'French {n}',
            language='French', explanation_language='English', discoverable=True)
            for n in range(13)])
        response = self.client.get(url('home'), {'learning': 'fr', 'page': 2})
        self.assertEqual(response.context['page'].paginator.count, 16)
        self.assertEqual(len(response.context['page']), 4)
        self.assertContains(response, 'learning=fr')
        self.assertNotContains(response, self.german.name)

    def test_management_keeps_inventory_creation_and_invitations(self):
        invited = Dictionary.objects.create(owner=self.other, name='Invited Swedish', language='Swedish')
        Membership.objects.create(dictionary=invited, user=self.owner, status='invited', accepted=False)
        home = self.client.get(url('home'))
        self.assertEqual(home.context['invitation_count'], 1)
        self.assertNotContains(home, invited.name)
        management = self.client.get(url('manage'))
        for name in (self.french.name, self.german.name, invited.name, 'Create a dictionary'):
            self.assertContains(management, name)

    def test_hidden_and_withdrawn_dictionaries_stay_out_of_learning_results(self):
        self.french.hidden = True
        self.french.save(update_fields=['hidden'])
        Participation.objects.create(dictionary=self.german, user=self.owner, withdrawn=True)
        response = self.client.get(url('home'), {'learning': 'all'})
        self.assertNotContains(response, self.french.name)
        self.assertNotContains(response, self.german.name)
        self.assertContains(response, self.public.name)

    def test_existing_create_post_still_works_and_errors_show_management_form(self):
        self.assertContains(self.client.post(url('home'), {'name': ''}), 'Create a dictionary')
        response = self.client.post(url('home'), {'name': 'New French', 'language': 'French',
                                                 'explanation_language': 'English'})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Dictionary.objects.filter(owner=self.owner, name='New French').exists())

    def test_member_home_and_management_require_login(self):
        self.client.logout()
        for name in ('home', 'manage'):
            self.assertEqual(self.client.get(url(name)).status_code, 302)

    def test_both_italian_dictionaries_appear_despite_different_explanation_languages(self):
        own = Dictionary.objects.create(owner=self.owner, name="Manny's Italian",
            language=' Italiano ', explanation_language='French')
        shared = Dictionary.objects.create(owner=self.other, name="Finley's Italian",
            language='it-IT', explanation_language='English')
        Membership.objects.create(dictionary=shared, user=self.owner, accepted=True,
            status='active', role='co_owner')
        for ui in ('en', 'fr', 'sk'):
            self.client.cookies['community_ui_language'] = ui
            response = self.client.get(url('home'), {'learning': 'it'})
            self.assertEqual({r['name'] for r in response.context['page']}, {own.name, shared.name})
            self.assertEqual({r['url'] for r in response.context['page']}, {
                reverse('community_dictionary:dictionary', args=[own.pk]),
                reverse('community_dictionary:dictionary', args=[shared.pk])})

    def test_management_uses_saved_language_for_all_dictionary_lists_and_pagination(self):
        italian = Dictionary.objects.create(owner=self.owner, name='Own Italian', language='Italian')
        hidden = Dictionary.objects.create(owner=self.owner, name='Hidden Italian', language='it', hidden=True)
        other_hidden = Dictionary.objects.create(owner=self.owner, name='Hidden German', language='de', hidden=True)
        invites = [Dictionary.objects.create(owner=self.other, name=name, language=language)
            for name, language in [('Invited Italian', 'italiano'), ('Invited German', 'German')]]
        for item in invites:
            Membership.objects.create(dictionary=item, user=self.owner, status='invited', accepted=False)
        Dictionary.objects.bulk_create([Dictionary(owner=self.other, name=f'Listed Italian {n}',
            language='it-IT', explanation_language='Slovak', discoverable=True) for n in range(13)])
        self.client.get(url('home'), {'learning': 'it'})
        response = self.client.get(url('manage'))
        self.assertEqual(response.context['learning_language'], 'it')
        self.assertEqual([r['dictionary'].pk for r in response.context['projects']], [italian.pk])
        self.assertEqual([r['dictionary'].pk for r in response.context['hidden_projects']], [hidden.pk])
        self.assertEqual([i.dictionary_id for i in response.context['invitations']], [invites[0].pk])
        for item in (self.french, self.german, self.public, other_hidden, invites[1]):
            self.assertNotContains(response, item.name)
        self.assertEqual(response.context['page'].paginator.count, 13)
        self.assertContains(response, 'learning=it')
        second = self.client.get(url('manage'), {'page': 2})
        self.assertEqual(len(second.context['discovery_rows']), 1)
        self.assertTrue(all(r['language'] == 'it-IT' for r in second.context['discovery_rows']))

    def test_management_switch_and_all_languages_are_shared_with_home(self):
        italian = Dictionary.objects.create(owner=self.owner, name='Own Italian', language='Italian')
        self.client.get(url('home'), {'learning': 'it'})
        selected = self.client.get(url('manage'), {'learning': 'fr'})
        self.assertContains(selected, self.french.name)
        self.assertNotContains(selected, italian.name)
        self.assertEqual(self.client.get(url('home')).context['learning_language'], 'fr')
        all_languages = self.client.get(url('manage'), {'learning': 'all'})
        for item in (self.french, self.german, italian):
            self.assertContains(all_languages, item.name)
        self.assertEqual(self.client.get(url('home')).context['learning_language'], 'all')

    def test_management_can_select_languages_only_present_in_hidden_or_invited_dictionaries(self):
        hidden = Dictionary.objects.create(owner=self.owner, name='Only hidden Italian', language='Italian', hidden=True)
        invited = Dictionary.objects.create(owner=self.other, name='Only invited Icelandic', language='Icelandic')
        Membership.objects.create(dictionary=invited, user=self.owner, status='invited', accepted=False)
        response = self.client.get(url('manage'), {'learning': 'it'})
        self.assertEqual(response.context['learning_language'], 'it')
        self.assertContains(response, hidden.name)
        self.assertNotContains(response, invited.name)
        response = self.client.get(url('manage'), {'learning': 'is'})
        self.assertEqual(response.context['learning_language'], 'is')
        self.assertContains(response, invited.name)
        self.assertNotContains(response, hidden.name)
