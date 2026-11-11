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
        cls.wrong_explanations = Dictionary.objects.create(owner=cls.other,
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
        self.assertNotContains(response, self.wrong_explanations.name)
        self.assertContains(response, 'Change language')
        self.assertNotContains(response, 'Create a dictionary')
        self.assertEqual({r['url'] for r in response.context['page']}, {
            reverse('community_dictionary:dictionary', args=[self.french.pk]),
            reverse('community_dictionary:public-dictionary', args=[self.public.pk])})

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
        self.assertEqual(response.context['page'].paginator.count, 15)
        self.assertEqual(len(response.context['page']), 3)
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
