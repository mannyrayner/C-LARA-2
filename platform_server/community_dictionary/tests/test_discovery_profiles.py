"""Discovery consent, membership boundaries and separation of public/private profiles."""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from projects.models import Profile
from community_dictionary import discovery, image_copy
from community_dictionary.models import (
    CommunityProfile, Contribution, Dictionary, Entry, Event, Membership,
    MembershipRequest, Participation,
)
from community_dictionary.services import accept
from community_dictionary.storage import prepare_upload, write_upload
from . import test_workflow as workflow


def url(name, *args):
    return reverse('community_dictionary:' + name, args=args)


class DiscoveryTests(TestCase):
    def setUp(self):
        workflow.WorkflowTests.setUp(self)
        self.owner_client = Client(); self.owner_client.force_login(self.owner)
        self.applicant = Client(); self.applicant.force_login(self.outsider)
        self.guest = Client()
        self.dictionary.discoverable = True
        self.dictionary.save()
        self.entry = Entry.objects.create(dictionary=self.dictionary, created_by=self.owner)
        word = Contribution.objects.create(entry=self.entry, author=self.owner,
            kind='text', text_field='word', word='SECRET-CONTENT')
        accept(word, self.owner)
        Contribution.objects.create(entry=self.entry, author=self.owner, kind='note', body='PRIVATE-NOTE')
        self.owner.email = 'PRIVATE-EMAIL@example.org'; self.owner.save()

    def change(self, enabled, client=None, **extra):
        self.dictionary.refresh_from_db()
        return (client or self.owner_client).post(url('discovery-setting', self.dictionary.pk), {
            'action': 'enable' if enabled else 'disable',
            'revision': self.dictionary.discovery_revision, **extra})

    def ask(self, client=None, **data):
        return (client or self.applicant).post(url('request-membership', self.dictionary.pk), data)

    def decision(self, action='approve', client=None, item=None, **extra):
        item = item or MembershipRequest.objects.get(dictionary=self.dictionary, user=self.outsider)
        return (client or self.owner_client).post(url('decide-membership-request', self.dictionary.pk, item.pk), {
            'action': action, 'revision': item.revision, **extra})

    def test_new_dictionaries_and_image_copies_default_unlisted(self):
        d = Dictionary.objects.create(name='New private', owner=self.owner, language='Swedish')
        self.assertFalse(d.discoverable)
        Contribution.objects.create(entry=self.entry, author=self.owner, kind='image', status='accepted',
            **write_upload(prepare_upload(workflow.picture(), 'image'), self.dictionary.pk, []))
        self.assertFalse(image_copy.create(self.dictionary, self.owner, 'Copy').discoverable)

    def test_discoverable_private_metadata_never_grants_content_access(self):
        for name, args in [('public-home', []), ('discover-dictionary', [self.dictionary.pk])]:
            response = self.guest.get(url(name, *args))
            self.assertContains(response, self.dictionary.name)
            self.assertContains(response, '1 accepted entry')
            for secret in ['SECRET-CONTENT', 'PRIVATE-NOTE', 'PRIVATE-EMAIL', 'src="/community-dictionaries/browse/']:
                self.assertNotContains(response, secret)
            self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(self.guest.get(url('public-dictionary', self.dictionary.pk)).status_code, 404)
        self.assertEqual(self.applicant.get(url('dictionary', self.dictionary.pk)).status_code, 404)

    def test_discovery_and_public_browsing_are_independent(self):
        for listed in [False, True]:
            for public in [False, True]:
                Dictionary.objects.filter(pk=self.dictionary.pk).update(discoverable=listed, public_browsing_enabled=public)
                listing = self.guest.get(url('public-home'))
                self.assertEqual(self.dictionary.name in listing.content.decode(), listed)
                self.assertEqual(self.guest.get(url('public-dictionary', self.dictionary.pk)).status_code, 200 if public else 404)
                self.assertEqual(self.guest.get(url('discover-dictionary', self.dictionary.pk)).status_code, 200 if listed else 404)

    def test_pending_text_is_not_counted_or_disclosed(self):
        entry = Entry.objects.create(dictionary=self.dictionary, created_by=self.member)
        Contribution.objects.create(entry=entry, author=self.member, kind='text', word='PENDING-SECRET')
        response = self.guest.get(url('discover-dictionary', self.dictionary.pk))
        self.assertContains(response, '1 accepted entry')
        self.assertNotContains(response, 'PENDING-SECRET')

    def test_hidden_personal_and_archived_never_listed(self):
        for field in ['hidden', 'personal', 'archived']:
            Dictionary.objects.filter(pk=self.dictionary.pk).update(**{field: True})
            self.assertNotContains(self.guest.get(url('public-home')), self.dictionary.name)
            self.assertEqual(self.guest.get(url('discover-dictionary', self.dictionary.pk)).status_code, 404)
            self.assertEqual(self.ask().status_code, 404)
            Dictionary.objects.filter(pk=self.dictionary.pk).update(**{field: False})

    def test_hide_disables_both_and_unhide_does_not_republish(self):
        Dictionary.objects.filter(pk=self.dictionary.pk).update(public_browsing_enabled=True)
        for visibility in ['hidden', 'visible']:
            self.owner_client.post(url('visibility', self.dictionary.pk), {'visibility': visibility})
            self.dictionary.refresh_from_db()
            self.assertFalse(self.dictionary.discoverable)
            self.assertFalse(self.dictionary.public_browsing_enabled)

    def test_owner_only_post_csrf_and_stale_settings(self):
        for role in ['member', 'editor', 'coordinator']:
            Membership.objects.filter(dictionary=self.dictionary, user=self.member).update(role=role)
            self.assertEqual(self.change(False, self.client).status_code, 404)
        self.assertEqual(self.change(False, self.applicant).status_code, 404)
        self.assertEqual(self.change(False, self.guest).status_code, 302)
        csrf = Client(enforce_csrf_checks=True); csrf.force_login(self.owner)
        self.assertEqual(self.change(False, csrf).status_code, 403)
        self.assertEqual(self.owner_client.get(url('discovery-setting', self.dictionary.pk)).status_code, 405)
        self.assertEqual(self.change(False).status_code, 302)
        self.assertEqual(self.change(True, revision=0).status_code, 409)
        self.dictionary.refresh_from_db(); self.assertFalse(self.dictionary.discoverable)

    def test_toggle_retry_is_idempotent_and_hidden_cannot_enable(self):
        for _ in range(2):
            self.assertEqual(self.change(False, revision=0).status_code, 302)
        self.assertEqual(Event.objects.filter(action='dictionary_discovery').count(), 1)
        Dictionary.objects.filter(pk=self.dictionary.pk).update(hidden=True)
        self.assertEqual(self.change(True).status_code, 409)

    def test_request_duplicate_private_message_and_approval(self):
        for _ in range(2):
            self.assertEqual(self.ask(message='<script>PRIVATE-MESSAGE</script>').status_code, 302)
        item = MembershipRequest.objects.get(); self.assertEqual(item.status, 'pending')
        self.assertFalse(Membership.objects.filter(user=self.outsider).exists())
        response = self.owner_client.get(url('membership-requests'))
        self.assertContains(response, '&lt;script&gt;PRIVATE-MESSAGE&lt;/script&gt;')
        self.assertNotContains(response, '<script>PRIVATE-MESSAGE</script>')
        for client in [self.applicant, self.client]:
            self.assertNotContains(client.get(url('membership-requests')), 'PRIVATE-MESSAGE')
        self.assertEqual(self.decision().status_code, 302)
        self.assertEqual(self.decision().status_code, 302)
        member = Membership.objects.get(user=self.outsider)
        self.assertEqual((member.role, member.status, member.accepted), ('member', 'active', True))
        self.assertEqual(self.applicant.get(url('dictionary', self.dictionary.pk)).status_code, 200)
        self.assertEqual(self.applicant.get(url('settings', self.dictionary.pk)).status_code, 404)

    def test_request_needs_login_post_and_csrf(self):
        self.assertEqual(self.ask(self.guest).status_code, 302)
        self.assertEqual(self.applicant.get(url('request-membership', self.dictionary.pk)).status_code, 405)
        csrf = Client(enforce_csrf_checks=True); csrf.force_login(self.outsider)
        self.assertEqual(self.ask(csrf).status_code, 403)
        self.assertEqual(MembershipRequest.objects.count(), 0)

    def test_request_validation_and_pending_limit(self):
        self.assertEqual(self.ask(message='x'*1001).status_code, 400)
        for i in range(20):
            d = Dictionary.objects.create(owner=self.owner, name=str(i), language='Swedish')
            MembershipRequest.objects.create(dictionary=d, user=self.outsider)
        self.assertEqual(self.ask().status_code, 429)
        self.assertEqual(MembershipRequest.objects.count(), 20)

    def test_existing_membership_or_withdrawal_cannot_be_bypassed(self):
        self.assertEqual(self.ask(self.owner_client).status_code, 409)
        for status, accepted in [('active', True), ('invited', False), ('inactive', True)]:
            Membership.objects.filter(user=self.member, dictionary=self.dictionary).update(status=status, accepted=accepted)
            self.assertEqual(self.ask(self.client).status_code, 409)
        Participation.objects.create(user=self.outsider, dictionary=self.dictionary, withdrawn=True)
        self.assertEqual(self.ask().status_code, 409)
        self.assertContains(self.applicant.get(url('discover-dictionary', self.dictionary.pk)), 'Your contributions are withdrawn')
        self.assertEqual(MembershipRequest.objects.count(), 0)

    def test_approval_cannot_reactivate_restore_or_enable_disabled_account(self):
        self.ask()
        member = Membership.objects.create(dictionary=self.dictionary, user=self.outsider, accepted=True, status='inactive')
        self.assertEqual(self.decision().status_code, 409)
        member.delete()
        state = Participation.objects.create(dictionary=self.dictionary, user=self.outsider, withdrawn=True)
        self.assertEqual(self.decision().status_code, 409)
        state.delete()
        self.outsider.is_active = False; self.outsider.save()
        self.assertEqual(self.decision().status_code, 409)
        self.assertFalse(Membership.objects.filter(user=self.outsider).exists())

    def test_existing_invitation_or_role_survives_approval(self):
        self.ask()
        member = Membership.objects.create(dictionary=self.dictionary, user=self.outsider, role='editor')
        self.assertEqual(self.decision().status_code, 302)
        member.refresh_from_db()
        self.assertEqual((member.role, member.status, member.accepted), ('editor', 'invited', False))
        self.assertContains(self.applicant.get(url('discover-dictionary', self.dictionary.pk)), 'already have an invitation')

    def test_owner_decisions_are_private_scoped_post_and_csrf(self):
        self.ask(); item = MembershipRequest.objects.get()
        for client in [self.client, self.applicant]:
            self.assertEqual(self.decision(client=client).status_code, 404)
        other = Dictionary.objects.create(name='Other', owner=self.owner, language='Swedish')
        self.assertEqual(self.owner_client.post(url('decide-membership-request', other.pk, item.pk), {'action': 'approve', 'revision': item.revision}).status_code, 404)
        self.assertEqual(self.owner_client.get(url('decide-membership-request', self.dictionary.pk, item.pk)).status_code, 405)
        csrf = Client(enforce_csrf_checks=True); csrf.force_login(self.owner)
        self.assertEqual(self.decision(client=csrf).status_code, 403)
        self.assertEqual(self.decision(revision=-1).status_code, 409)
        self.assertEqual(self.decision(action='promote').status_code, 400)

    def test_decline_cannot_be_resubmitted_or_approved_from_stale_form(self):
        self.ask(); item = MembershipRequest.objects.get()
        self.assertEqual(self.decision('decline').status_code, 302)
        self.assertEqual(self.decision('approve', item=item).status_code, 409)
        self.assertEqual(self.ask().status_code, 409)
        self.assertFalse(Membership.objects.filter(user=self.outsider).exists())

    def test_cancel_and_reapply_invalidates_old_owner_form(self):
        self.ask(); old = MembershipRequest.objects.get()
        path = url('cancel-membership-request', old.pk)
        self.assertEqual(self.owner_client.post(path, {'revision': old.revision}).status_code, 404)
        self.assertEqual(self.applicant.get(path).status_code, 405)
        csrf = Client(enforce_csrf_checks=True); csrf.force_login(self.outsider)
        self.assertEqual(csrf.post(path, {'revision': old.revision}).status_code, 403)
        self.assertEqual(self.applicant.post(path, {'revision': -1}).status_code, 409)
        self.assertEqual(self.applicant.post(path, {'revision': old.revision}).status_code, 302)
        self.assertEqual(self.ask(message='Revised').status_code, 302)
        self.assertEqual(self.decision(item=old).status_code, 409)
        self.assertEqual(MembershipRequest.objects.count(), 1)
        self.assertEqual(self.decision().status_code, 302)

    def test_pending_requests_follow_current_owner_and_survive_unlisting(self):
        self.ask(message='PRIVATE-REQUEST')
        self.change(False)
        self.assertEqual(self.ask().status_code, 404)
        self.assertNotContains(self.applicant.get(url('profile')), self.dictionary.name)
        Dictionary.objects.filter(pk=self.dictionary.pk).update(owner=self.member)
        self.assertNotContains(self.owner_client.get(url('membership-requests')), 'PRIVATE-REQUEST')
        self.assertContains(self.client.get(url('membership-requests')), 'PRIVATE-REQUEST')
        self.assertEqual(self.decision().status_code, 404)
        item = MembershipRequest.objects.get()
        self.assertEqual(self.applicant.post(url('cancel-membership-request', item.pk), {'revision': item.revision}).status_code, 302)


class CommunityProfileTests(TestCase):
    def setUp(self):
        workflow.WorkflowTests.setUp(self)
        self.client.force_login(self.owner)
        self.guest = Client()
        self.owner.email = 'private-account@example.org'; self.owner.save()
        self.common, _ = Profile.objects.get_or_create(user=self.owner)
        self.common.openai_api_key = 'SECRET-API-KEY'
        self.common.dialogue_memory = {'private': 'SECRET-MEMORY'}
        self.common.dialogue_language = 'fr'
        self.common.save()

    def listing(self, listed=True, **extra):
        profile, _ = CommunityProfile.objects.get_or_create(user=self.owner)
        return self.client.post(url('profile'), {'action': 'contributor', 'public_name': 'Public Pseudonym',
            'introduction': 'I enjoy Swedish.', 'revision': profile.revision,
            **({'list_as_contributor': 'on'} if listed else {}), **extra})

    def test_profile_is_private_and_public_listing_is_opt_in(self):
        self.assertEqual(self.guest.get(url('profile')).status_code, 302)
        response = self.client.get(url('profile'))
        self.assertContains(response, self.owner.email)
        self.assertNotContains(response, 'SECRET-API-KEY')
        self.assertNotContains(response, 'SECRET-MEMORY')
        self.assertIn('no-store', response['Cache-Control'])
        self.assertFalse(CommunityProfile.objects.get(user=self.owner).list_as_contributor)
        self.assertEqual(self.guest.get(url('contributor', self.owner.pk)).status_code, 404)
        self.assertNotContains(self.guest.get(url('about')), self.owner.email)

    def test_listing_requires_chosen_name_and_excludes_private_identity(self):
        self.listing(public_name='')
        self.assertFalse(CommunityProfile.objects.get(user=self.owner).list_as_contributor)
        self.assertEqual(self.listing().status_code, 302)
        for name, args in [('about', []), ('contributor', [self.owner.pk])]:
            response = self.guest.get(url(name, *args))
            self.assertContains(response, 'Public Pseudonym')
            for secret in [self.owner.email, 'SECRET-API-KEY', 'SECRET-MEMORY', self.dictionary.name]:
                self.assertNotContains(response, secret)
            self.assertIn('no-store', response['Cache-Control'])

    def test_public_profile_only_links_owned_discoverable_dictionaries(self):
        self.listing()
        Dictionary.objects.filter(pk=self.dictionary.pk).update(discoverable=True)
        response = self.guest.get(url('contributor', self.owner.pk))
        self.assertContains(response, self.dictionary.name)
        self.assertContains(self.guest.get(url('public-home')), 'Public Pseudonym')
        Dictionary.objects.filter(pk=self.dictionary.pk).update(hidden=True)
        self.assertNotContains(self.guest.get(url('contributor', self.owner.pk)), self.dictionary.name)

    def test_opt_out_removes_all_hosted_public_identity_and_stale_form_cannot_restore(self):
        self.listing()
        Dictionary.objects.filter(pk=self.dictionary.pk).update(discoverable=True)
        self.listing(False)
        self.assertEqual(self.listing(revision=1).status_code, 409)
        self.assertEqual(self.guest.get(url('contributor', self.owner.pk)).status_code, 404)
        for name in ['about', 'public-home']:
            self.assertNotContains(self.guest.get(url(name)), 'Public Pseudonym')

    def test_disabled_account_is_not_listed_and_html_is_escaped(self):
        self.listing(public_name='<script>public</script>')
        self.assertContains(self.guest.get(url('about')), '&lt;script&gt;public&lt;/script&gt;')
        self.assertNotContains(self.guest.get(url('about')), '<script>public</script>')
        self.owner.is_active = False; self.owner.save()
        self.assertEqual(self.guest.get(url('contributor', self.owner.pk)).status_code, 404)
        self.assertNotContains(self.guest.get(url('about')), '&lt;script&gt;public&lt;/script&gt;')

    def test_contributor_save_cannot_change_other_account_fields(self):
        self.listing(email='attacker@example.org', openai_api_key='REPLACEMENT', user=self.member.pk)
        self.common.refresh_from_db(); self.owner.refresh_from_db()
        self.assertEqual(self.common.openai_api_key, 'SECRET-API-KEY')
        self.assertEqual(self.owner.email, 'private-account@example.org')
        self.assertFalse(CommunityProfile.objects.filter(user=self.member).exists())

    def test_preferences_keep_secret_and_unrelated_fields_then_allow_explicit_removal(self):
        response = self.client.post(url('profile'), {'action': 'preferences', 'timezone': 'Europe/Paris',
            'openai_api_key': '', 'use_personal_openai_key': 'on', 'dialogue_memory': '{}', 'dialogue_language': 'en'})
        self.assertEqual(response.status_code, 302)
        self.common.refresh_from_db()
        self.assertEqual(self.common.openai_api_key, 'SECRET-API-KEY')
        self.assertTrue(self.common.use_personal_openai_key)
        self.assertEqual(self.common.dialogue_memory, {'private': 'SECRET-MEMORY'})
        self.assertEqual(self.common.dialogue_language, 'fr')
        self.client.post(url('profile'), {'action': 'preferences', 'timezone': 'UTC', 'clear_key': 'on'})
        self.common.refresh_from_db(); self.assertEqual(self.common.openai_api_key, '')
        self.assertFalse(self.common.use_personal_openai_key)

    def test_personal_key_validation_and_csrf(self):
        self.client.post(url('profile'), {'action': 'preferences', 'timezone': 'UTC', 'clear_key': 'on', 'use_personal_openai_key': 'on'})
        self.common.refresh_from_db(); self.assertEqual(self.common.openai_api_key, 'SECRET-API-KEY')
        response = self.client.post(url('profile'), {'action': 'preferences', 'timezone': 'UTC', 'clear_key': 'on', 'openai_api_key': 'NEW-SECRET'})
        self.assertNotContains(response, 'NEW-SECRET')
        self.common.refresh_from_db(); self.assertEqual(self.common.openai_api_key, 'SECRET-API-KEY')
        csrf = Client(enforce_csrf_checks=True); csrf.force_login(self.owner)
        self.assertEqual(csrf.post(url('profile'), {'action': 'contributor'}).status_code, 403)

    def test_community_password_change_reuses_policy_and_preserves_session(self):
        path = url('password-change')
        self.assertContains(self.client.get(path), 'Community dictionaries')
        response = self.client.post(path, {'old_password': 'wrong', 'new_password1': 'New-private-phrase-998', 'new_password2': 'New-private-phrase-998'})
        self.assertEqual(response.status_code, 200)
        self.owner.refresh_from_db(); self.assertTrue(self.owner.check_password('test-only'))
        response = self.client.post(path, {'old_password': 'test-only', 'new_password1': 'New-private-phrase-998', 'new_password2': 'New-private-phrase-998'})
        self.assertRedirects(response, url('profile'))
        self.owner.refresh_from_db(); self.assertTrue(self.owner.check_password('New-private-phrase-998'))
        self.assertEqual(self.client.get(url('profile')).status_code, 200)

    def test_about_publication_links_and_public_get_only(self):
        response = self.guest.get(url('about'))
        self.assertContains(response, 'Community Dictionaries: Everyday Pictures, Rapid Human–AI Development')
        self.assertContains(response, 'https://airaxiv.com/papers/view/2610.0032/')
        self.assertContains(response, 'https://www.researchgate.net/publication/415734280_Community_Dictionaries_Everyday_Pictures_Rapid_Human-AI_Development')
        self.assertNotContains(response, 'in preparation')
        self.assertContains(response, 'List me as a contributor')
        self.assertNotContains(response, 'USD 10')
        self.assertEqual(self.guest.post(url('about')).status_code, 405)
