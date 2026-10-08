"""Hiding is reversible presentation, never a withdrawal or access change."""
from contextlib import closing

from django.test import Client, TestCase
from django.urls import reverse

from community_dictionary import image_copy
from community_dictionary.models import Dictionary, Event, Membership, Participation
from community_dictionary.participation import state_for
from . import test_workflow as workflow


class DictionaryVisibilityTests(TestCase):
    setUp = workflow.WorkflowTests.setUp
    url = workflow.WorkflowTests.url
    post = workflow.WorkflowTests.post
    create_entry = workflow.WorkflowTests.create_entry

    def visibility(self, value):
        return self.client.post(self.url('visibility'), {'visibility': value})

    def test_owner_can_hide_restore_and_repeated_submission_is_harmless(self):
        self.client.force_login(self.owner)
        self.assertFalse(self.dictionary.hidden)
        self.assertContains(self.client.get(self.url('settings')), 'Hide dictionary')
        before = (self.dictionary.capture_revision, self.dictionary.membership_revision,
                  self.dictionary.image_generation_revision)
        for _ in range(2):
            self.assertRedirects(self.visibility('hidden'), self.url('settings'))
        self.dictionary.refresh_from_db()
        self.assertTrue(self.dictionary.hidden)
        self.assertFalse(self.dictionary.archived)
        self.assertEqual(before, (self.dictionary.capture_revision, self.dictionary.membership_revision,
                                  self.dictionary.image_generation_revision))
        self.assertEqual(Event.objects.filter(action='dictionary_visibility').count(), 1)
        self.assertContains(self.client.get(self.url('settings')), 'Make dictionary visible')
        for user in [self.owner, self.member]:
            self.client.force_login(user)
            home = self.client.get(reverse('community_dictionary:home'))
            self.assertEqual(home.context['projects'], [])
            self.assertEqual([r['dictionary'] for r in home.context['hidden_projects']], [self.dictionary])
            self.assertContains(home, '<details class="panel" id="hidden-dictionaries">')
            self.assertContains(self.client.get(self.url('dictionary')), 'Hidden dictionary.')
        self.client.force_login(self.owner)
        self.assertRedirects(self.visibility('visible'), self.url('settings'))
        home = self.client.get(reverse('community_dictionary:home'))
        self.assertEqual([r['dictionary'] for r in home.context['projects']], [self.dictionary])
        self.assertEqual(home.context['hidden_projects'], [])
        self.assertNotContains(self.client.get(self.url('dictionary')), 'Hidden dictionary.')

    def test_only_current_owner_can_change_and_editor_has_no_control(self):
        for role in ['member', 'editor', 'coordinator']:
            Membership.objects.filter(dictionary=self.dictionary, user=self.member).update(role=role)
            self.client.force_login(self.member)
            self.assertEqual(self.visibility('hidden').status_code, 404)
            if role != 'member':
                self.assertNotContains(self.client.get(self.url('settings')), 'Hide dictionary')
        self.outsider.is_staff = self.outsider.is_superuser = True
        self.outsider.save()
        self.client.force_login(self.outsider)
        self.assertEqual(self.visibility('hidden').status_code, 404)
        self.client.force_login(self.owner)
        # Ownership may have changed since this owner opened Settings.
        Dictionary.objects.filter(pk=self.dictionary.pk).update(owner=self.member)
        self.assertEqual(self.visibility('hidden').status_code, 404)
        self.client.force_login(self.member)
        self.assertEqual(self.visibility('hidden').status_code, 302)

    def test_post_csrf_and_explicit_state_are_required(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(self.url('visibility')).status_code, 405)
        self.assertEqual(self.visibility('toggle').status_code, 400)
        self.assertEqual(self.client.post(self.url('visibility'), {}).status_code, 400)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.owner)
        self.assertEqual(csrf.post(self.url('visibility'), {'visibility': 'hidden'}).status_code, 403)
        self.dictionary.refresh_from_db()
        self.assertFalse(self.dictionary.hidden)
        self.assertFalse(Event.objects.filter(action='dictionary_visibility').exists())

    def test_member_keeps_media_and_withdraw_restore_rights_in_hidden_dictionary(self):
        entry = self.create_entry()
        image = entry.contributions.get(kind='image')
        self.client.force_login(self.owner)
        self.client.post(self.url('review', image.pk), {'action': 'accept'})
        self.visibility('hidden')
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(self.url('entry', entry.pk)).status_code, 200)
        with closing(self.client.get(self.url('media', image.pk))) as response:
            self.assertEqual(response.status_code, 200)
        state = state_for(self.member, self.dictionary)
        self.assertEqual(self.client.post(self.url('withdraw-content'),
            {'revision': state.revision, 'confirm': 'yes'}).status_code, 302)
        home = self.client.get(reverse('community_dictionary:home'))
        self.assertEqual(home.context['projects'], [])
        self.assertContains(home, 'Your content is withdrawn')
        self.assertContains(home, 'Restore my content')
        self.assertEqual(self.client.get(self.url('my-content')).status_code, 200)
        self.assertEqual(self.client.get(self.url('entry', entry.pk)).status_code, 404)
        state = state_for(self.member, self.dictionary)
        self.assertEqual(self.client.post(self.url('restore-content'), {'revision': state.revision}).status_code, 302)
        image.refresh_from_db(); self.dictionary.refresh_from_db()
        self.assertEqual(image.entry_id, entry.pk)
        self.assertEqual(image.status, 'accepted')
        self.assertTrue(self.dictionary.hidden)

    def test_hidden_invitations_and_inactive_members_remain_separate_from_main_list(self):
        Membership.objects.create(dictionary=self.dictionary, user=self.outsider)
        self.client.force_login(self.owner); self.visibility('hidden')
        self.client.force_login(self.outsider)
        home = self.client.get(reverse('community_dictionary:home'))
        self.assertEqual(home.context['invitations'], [])
        self.assertEqual(len(home.context['hidden_invitations']), 1)
        self.assertEqual(self.client.get(self.url('dictionary')).status_code, 404)
        Membership.objects.filter(dictionary=self.dictionary, user=self.member).update(status='inactive')
        self.client.force_login(self.member)
        home = self.client.get(reverse('community_dictionary:home'))
        self.assertEqual(len(home.context['hidden_projects']), 1)
        self.assertContains(home, 'Membership inactive')
        self.assertContains(self.client.get(self.url('dictionary')), 'Your membership is inactive')
        # No hidden metadata is disclosed to an unrelated user.
        Membership.objects.filter(dictionary=self.dictionary, user=self.outsider).delete()
        self.client.force_login(self.outsider)
        self.assertNotContains(self.client.get(reverse('community_dictionary:home')), self.dictionary.name)

    def test_hiding_source_preserves_visible_image_copy_and_provenance(self):
        entry = self.create_entry()
        image = entry.contributions.get(kind='image')
        self.client.force_login(self.owner)
        self.client.post(self.url('review', image.pk), {'action': 'accept'})
        target = image_copy.create(self.dictionary, self.owner, 'New Swedish dictionary')
        self.visibility('hidden')
        copied = target.entries.get().selected_image
        self.assertEqual(copied.shared_from_id, image.pk)
        self.assertEqual(copied.status, 'pending')
        self.assertFalse(target.hidden)
        self.assertEqual(self.client.get(reverse('community_dictionary:dictionary', args=[target.pk])).status_code, 200)
        # A fresh copy made after hiding the source also starts visible.
        self.dictionary.refresh_from_db()
        self.assertFalse(image_copy.create(self.dictionary, self.owner, 'Another copy').hidden)

    def test_archived_withdrawn_or_personal_owner_cannot_use_visibility_endpoint(self):
        self.client.force_login(self.owner)
        for field in ['archived', 'personal']:
            Dictionary.objects.filter(pk=self.dictionary.pk).update(**{field: True})
            self.assertEqual(self.visibility('hidden').status_code, 404)
            Dictionary.objects.filter(pk=self.dictionary.pk).update(**{field: False})
        Participation.objects.create(dictionary=self.dictionary, user=self.owner, withdrawn=True)
        self.assertEqual(self.visibility('hidden').status_code, 404)
