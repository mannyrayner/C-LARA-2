"""Permission and account-disclosure boundaries for the simplified saving UI."""
import tempfile
import uuid
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from community_dictionary.models import Dictionary, Entry, Membership
from .test_workflow import picture


class SaveAndInvitationTests(TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        settings = override_settings(COMMUNITY_DICTIONARY_MEDIA_ROOT=Path(temporary.name))
        settings.enable()
        self.addCleanup(settings.disable)
        User = get_user_model()
        self.owner = User.objects.create_user(username='owner')
        self.member = User.objects.create_user(username='member')
        self.candidate = User.objects.create_user(username='candidate', email='private@example.com')
        self.inactive = User.objects.create_user(username='inactive', is_active=False)
        self.dictionary = Dictionary.objects.create(owner=self.owner, name='Our words', language='Italian')
        Membership.objects.create(dictionary=self.dictionary, user=self.member, accepted=True, role='editor')
        self.people_url = reverse('community_dictionary:people', args=[self.dictionary.pk])
        self.new_url = reverse('community_dictionary:new', args=[self.dictionary.pk])

    def test_single_save_still_requires_explicit_media_permission(self):
        self.client.force_login(self.owner)
        response = self.client.post(self.new_url, {
            'submission_id': str(uuid.uuid4()), 'photo': picture(),
        }, HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Entry.objects.exists())
        response = self.client.post(self.new_url, {
            'submission_id': str(uuid.uuid4()), 'photo': picture(),
            'consent': 'on', 'publish_now': 'on',
        }, HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['saved'])
        entry = Entry.objects.get()
        self.assertIsNotNone(entry.selected_image)

    def test_account_picker_is_owner_only_and_excludes_inactive_accounts(self):
        self.client.force_login(self.owner)
        response = self.client.get(self.people_url)
        self.assertEqual(list(response.context['invite_accounts']), ['candidate', 'member'])
        self.assertNotContains(response, 'private@example.com')
        self.client.force_login(self.member)
        response = self.client.get(self.people_url)
        self.assertEqual(list(response.context['invite_accounts']), [])
        self.assertNotContains(response, 'candidate')
        response = self.client.post(self.people_url, {'action': 'invite', 'username': 'candidate'})
        self.assertEqual(response.status_code, 404)
        self.assertFalse(Membership.objects.filter(user=self.candidate).exists())

    def test_picker_invitation_still_requires_acceptance_and_role_changes_preserve_it(self):
        self.client.force_login(self.owner)
        response = self.client.post(self.people_url, {'action': 'invite', 'username': 'candidate', 'role': 'member'})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Membership.objects.get(user=self.candidate).accepted)
        response = self.client.post(self.people_url, {'action': 'invite', 'username': 'member', 'role': 'member'})
        self.assertEqual(response.status_code, 302)
        membership = Membership.objects.get(user=self.member)
        self.assertTrue(membership.accepted)
        self.assertEqual(membership.role, 'member')
        response = self.client.post(self.people_url, {'action': 'invite', 'username': 'inactive'})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Membership.objects.filter(user=self.inactive).exists())
