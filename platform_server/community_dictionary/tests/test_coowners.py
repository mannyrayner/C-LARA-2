"""Ownership delegation, live export checks, and unchanged contribution rights."""
import io
import json
import zipfile
from contextlib import closing
from unittest.mock import patch

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.http import Http404
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from community_dictionary import discovery, google_tts, membership, porting, word_audio
from community_dictionary.models import (
    Dictionary, DictionaryWordAudioSettings, Event, LanguagePort, Membership,
    MembershipRequest, Participation,
)
from community_dictionary.participation import restore_all, state_for, withdraw_all
from community_dictionary.permissions import is_coordinator, is_editor, is_owner
from community_dictionary.services import Conflict, accept
from . import test_workflow as workflow


class CoOwnerTests(TestCase):
    setUp = workflow.WorkflowTests.setUp
    url = workflow.WorkflowTests.url
    post = workflow.WorkflowTests.post
    create_entry = workflow.WorkflowTests.create_entry

    def grant(self, user=None):
        row = Membership.objects.get(dictionary=self.dictionary, user=user or self.member)
        row.role = 'co_owner'; row.save(update_fields=['role'])
        return row

    def change(self, member, action='role', value='co_owner'):
        return self.client.post(self.url('membership-action'), {
            'action': action, 'member_id': member.pk, 'value': value})

    def test_invitation_shows_role_but_grants_nothing_until_accepted(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(self.url('people'), {
            'action': 'invite', 'username': self.outsider.username, 'role': 'co_owner'}).status_code, 302)
        row = Membership.objects.get(dictionary=self.dictionary, user=self.outsider)
        self.assertFalse(row.accepted)
        self.client.force_login(self.outsider)
        self.assertContains(self.client.get(reverse('community_dictionary:home')), 'Co-owner')
        self.assertEqual(self.client.get(self.url('export')).status_code, 404)
        self.assertEqual(self.client.post(self.url('join')).status_code, 302)
        self.assertTrue(is_owner(self.outsider, self.dictionary))
        self.assertEqual(self.client.get(self.url('tools')).status_code, 200)

    def test_owner_promotes_and_revokes_without_transferring_ownership(self):
        row = Membership.objects.get(dictionary=self.dictionary, user=self.member)
        self.client.force_login(self.owner)
        self.assertEqual(self.change(row).status_code, 302)
        self.assertTrue(is_owner(self.member, self.dictionary))
        self.client.force_login(self.member)
        page = self.client.get(self.url('settings'))
        self.assertContains(self.client.get(self.url('dictionary')), self.url('export'))
        with closing(self.client.get(self.url('export'))) as exported:
            self.assertEqual(exported.status_code, 200)
        self.client.force_login(self.owner)
        self.assertEqual(self.change(row, value='member').status_code, 302)
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(self.url('export')).status_code, 404)
        self.dictionary.refresh_from_db(); self.assertEqual(self.dictionary.owner, self.owner)

    def test_export_has_entries_media_and_attribution_but_no_account_secrets(self):
        self.client.force_login(self.owner)
        entry = self.create_entry(word='soffa', meaning='sofa', publish_now='on')
        self.grant(); self.client.force_login(self.member)
        with closing(self.client.get(self.url('export'))) as response:
            data = b''.join(response.streaming_content)
        with zipfile.ZipFile(io.BytesIO(data)) as bundle:
            manifest = json.loads(bundle.read('manifest.json'))
            records = json.loads(bundle.read('records.json'))
            self.assertTrue(any(n.startswith('media/') for n in bundle.namelist()))
            self.assertTrue(any(r['model'] == 'community_dictionary.entry' and r['pk'] == entry.pk for r in records))
            self.assertTrue(any(r['model'] == 'community_dictionary.membership' and r['fields']['role'] == 'co_owner' for r in records))
            self.assertEqual({u['username'] for u in manifest['users']}, {'owner', 'member', 'third'})
            self.assertFalse(any(r['model'].startswith(('auth.', 'projects.')) for r in records))

    def test_settings_review_and_membership_requests_work_for_coowner(self):
        entry = self.create_entry(word='soffa')
        part = entry.contributions.get(kind='image')
        self.grant()
        self.assertTrue(is_editor(self.member, self.dictionary))
        self.assertTrue(is_coordinator(self.member, self.dictionary))
        self.assertEqual(self.client.post(self.url('review', part.pk), {'action': 'accept'}).status_code, 302)
        part.refresh_from_db(); self.assertEqual(part.status, 'accepted')
        self.assertEqual(self.client.post(self.url('settings'), {
            'name': 'Shared dictionary', 'language': 'Swedish', 'text_direction': 'auto'}).status_code, 302)
        self.dictionary.refresh_from_db(); self.assertEqual(self.dictionary.name, 'Shared dictionary')
        item = MembershipRequest.objects.create(dictionary=self.dictionary, user=self.outsider, message='Private request')
        self.assertEqual(discovery.pending_for(self.member).count(), 1)
        self.assertContains(self.client.get(reverse('community_dictionary:membership-requests')), 'Private request')
        self.assertEqual(self.client.post(reverse('community_dictionary:decide-membership-request', args=[self.dictionary.pk, item.pk]), {
            'action': 'approve', 'revision': item.revision}).status_code, 302)
        self.assertEqual(Membership.objects.get(dictionary=self.dictionary, user=self.outsider).role, 'member')

    def test_coowner_appoints_more_owners_but_cannot_remove_existing_owners(self):
        coowner = self.grant(); other = Membership.objects.get(dictionary=self.dictionary, user=self.third)
        self.assertEqual(self.change(other, value='editor').status_code, 302)
        self.assertEqual(self.change(other, value='co_owner').status_code, 302)
        for target, action, value in [(coowner, 'role', 'member'),
                                      (coowner, 'deactivate', '')]:
            self.assertEqual(self.change(target, action, value).status_code, 404)
        self.assertEqual(self.client.post(self.url('people'), {
            'action': 'invite', 'username': self.outsider.username, 'role': 'co_owner'}).status_code, 302)
        self.assertEqual(self.client.post(self.url('people'), {
            'action': 'invite', 'username': self.outsider.username, 'role': 'editor'}).status_code, 404)
        page = self.client.get(self.url('people'))
        self.assertContains(page, '<option value="co_owner"', html=False)
        self.assertNotContains(page, self.owner.password)

    def test_members_and_coordinators_cannot_self_promote_or_export(self):
        row = Membership.objects.get(dictionary=self.dictionary, user=self.member)
        for role in ['member', 'editor', 'coordinator']:
            Membership.objects.filter(pk=row.pk).update(role=role)
            self.assertFalse(is_owner(self.member, self.dictionary))
            self.assertEqual(self.change(row).status_code, 404)
            self.assertEqual(self.client.get(self.url('export')).status_code, 404)
            self.assertNotContains(self.client.get(self.url('dictionary')), self.url('export'))

    def test_coowner_appointments_still_need_two_person_approval(self):
        coowner = self.grant()
        Membership.objects.filter(dictionary=self.dictionary, user=self.third).update(role='coordinator')
        other = Membership.objects.get(dictionary=self.dictionary, user=self.third)
        self.dictionary.membership_policy = 'coordinators'; self.dictionary.save()
        self.assertEqual(self.change(other).status_code, 302)
        proposal = self.dictionary.membership_decisions.latest('pk')
        self.assertEqual(proposal.status, 'pending')
        other.refresh_from_db(); self.assertEqual(other.role, 'coordinator')
        self.client.force_login(self.third)
        self.assertEqual(self.change(other).status_code, 404)
        self.client.force_login(self.member)
        self.assertEqual(self.client.post(self.url('membership-action'), {
            'action': 'approve', 'decision_id': proposal.pk}).status_code, 409)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(self.url('membership-action'), {
            'action': 'approve', 'decision_id': proposal.pk}).status_code, 302)
        other.refresh_from_db(); self.assertEqual(other.role, 'co_owner')
        # Original owner cannot bypass two-person policy when removing co-owners.
        self.client.force_login(self.owner)
        self.assertEqual(self.change(coowner, value='member').status_code, 302)
        coowner.refresh_from_db(); self.assertEqual(coowner.role, 'co_owner')

    def test_two_person_policy_cannot_lose_its_only_other_coordinator(self):
        row = self.grant(); self.dictionary.membership_policy = 'coordinators'; self.dictionary.save()
        self.client.force_login(self.owner)
        self.assertEqual(self.change(row, value='member').status_code, 409)

    def test_inactive_withdrawn_unaccepted_and_disabled_coowners_have_no_management(self):
        row = self.grant()
        for changes, withdrawn, disabled in [({'status':'inactive'}, False, False),
                ({'accepted':False, 'status':'invited'}, False, False),
                ({'accepted':True, 'status':'active'}, True, False),
                ({'accepted':True, 'status':'active'}, False, True)]:
            Membership.objects.filter(pk=row.pk).update(**changes)
            Participation.objects.update_or_create(dictionary=self.dictionary, user=self.member, defaults={'withdrawn':withdrawn})
            self.member.is_active = not disabled; self.member.save()
            self.assertFalse(is_owner(self.member, self.dictionary))
            self.assertEqual(discovery.pending_for(self.member).count(), 0)
            for route in ['export', 'tools']:
                self.assertIn(self.client.get(self.url(route)).status_code, [302, 404])

    def test_withdrawal_preserves_original_owner_and_requires_own_restore(self):
        self.grant()
        withdraw_all(self.member, self.dictionary.pk, state_for(self.member, self.dictionary).revision)
        self.assertFalse(is_owner(self.member, self.dictionary))
        self.dictionary.refresh_from_db(); self.assertEqual(self.dictionary.owner, self.owner)
        restore_all(self.member, self.dictionary.pk, state_for(self.member, self.dictionary).revision)
        self.assertTrue(is_owner(self.member, self.dictionary))

    def test_original_owner_and_personal_collection_cannot_be_demoted_or_shared(self):
        self.grant()
        owner_row = Membership.objects.create(dictionary=self.dictionary, user=self.owner, accepted=True)
        self.assertEqual(self.change(owner_row, value='member').status_code, 409)
        self.client.force_login(self.owner)
        self.assertEqual(self.change(owner_row, value='member').status_code, 409)
        private = Dictionary.objects.create(owner=self.owner, personal=True, name='Private', language='Swedish', collection_source=self.dictionary)
        Membership.objects.create(dictionary=private, user=self.member, role='co_owner', accepted=True)
        self.assertFalse(is_owner(self.member, private))
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(reverse('community_dictionary:export', args=[private.pk])).status_code, 404)

    def test_new_coowner_management_posts_need_csrf(self):
        self.grant()
        csrf = Client(enforce_csrf_checks=True); csrf.force_login(self.member)
        other = Membership.objects.get(dictionary=self.dictionary, user=self.third)
        self.assertEqual(csrf.post(self.url('membership-action'), {'action':'deactivate', 'member_id':other.pk}).status_code, 403)

    def test_export_omits_withdrawn_contributions_for_coowners_too(self):
        self.client.force_login(self.third)
        entry = self.create_entry(word='Withdrawn secret', publish_now='on')
        for part in entry.contributions.all(): accept(part, self.owner)
        withdraw_all(self.third, self.dictionary.pk, state_for(self.third, self.dictionary).revision)
        self.grant(); self.client.force_login(self.member)
        with closing(self.client.get(self.url('export'))) as response:
            with zipfile.ZipFile(io.BytesIO(b''.join(response.streaming_content))) as bundle:
                self.assertNotIn('Withdrawn secret', bundle.read('records.json').decode())
                self.assertFalse(any(n.startswith('media/') for n in bundle.namelist()))

    @override_settings(COMMUNITY_DICTIONARY_GOOGLE_TTS_ENABLED=True)
    def test_coowner_google_consent_requires_admin_and_is_invalid_after_revocation(self):
        row = self.grant()
        with self.assertRaises(Conflict): google_tts.require_access(self.member)
        self.member.is_staff = True; self.member.save()
        choice = DictionaryWordAudioSettings.objects.create(dictionary=self.dictionary, authorised_by=self.member,
            language='Swedish', voice='sv-SE-Wavenet-A')
        chosen = word_audio.policy(self.dictionary)
        with patch('community_dictionary.google_tts.require_access') as access:
            word_audio.validate(self.dictionary, chosen)
            self.assertEqual(access.call_args.args[0].pk, self.member.pk)
        Membership.objects.filter(pk=row.pk).update(role='editor')
        with self.assertRaises(Conflict): word_audio.policy(self.dictionary)
        # Staff status itself never grants ownership.
        self.assertFalse(is_owner(self.member, self.dictionary))

    def test_coowner_cannot_take_over_another_users_private_paid_job(self):
        self.grant()
        port = LanguagePort.objects.create(source=self.dictionary, user=self.owner, name='Owner job',
            language='French', explanation_language='English')
        self.assertEqual(self.client.get(reverse('community_dictionary:port-update', args=[self.dictionary.pk, port.pk])).status_code, 404)
        self.dictionary.photo_ai_enabled = True; self.dictionary.save()
        with patch('community_dictionary.batch_descriptions.authority'):
            port.is_description_batch = True
            porting.authority(port)
        # Revocation is checked when background work rechecks its own author.
        Membership.objects.filter(dictionary=self.dictionary, user=self.member).update(role='editor')
        port.user = self.member
        with self.assertRaises(Http404): porting.authority(port)


    def test_people_controls_and_invitation_roles_are_localised(self):
        self.grant()
        for language, label, primary in [('fr', 'Copropriétaire', 'Propriétaire d’origine'),
                                         ('sk', 'Spoluvlastník', 'Pôvodný vlastník')]:
            self.client.cookies['community_ui_language'] = language
            self.client.force_login(self.owner)
            page = self.client.get(self.url('people'))
            self.assertContains(page, label)
            self.assertContains(page, primary)
            self.assertContains(page, 'value="co_owner"')
            self.client.force_login(self.member)
            self.assertContains(self.client.get(self.url('people')), 'value="co_owner"')

    def test_successive_coowners_can_invite_many_more_and_all_can_export(self):
        from django.contrib.auth import get_user_model
        self.grant()
        inviter = self.member
        for number in range(7):
            invited = get_user_model().objects.create_user(username=f'coowner{number}')
            self.client.force_login(inviter)
            page = self.client.get(self.url('people'))
            self.assertContains(page, '<option value="co_owner"')
            self.assertEqual(self.client.post(self.url('people'), {
                'action':'invite', 'username':invited.username, 'role':'co_owner'}).status_code, 302)
            self.client.force_login(invited)
            self.assertFalse(is_owner(invited, self.dictionary))
            self.assertEqual(self.client.post(self.url('people'), {
                'action':'invite', 'username':self.outsider.username, 'role':'co_owner'}).status_code, 404)
            self.assertEqual(self.client.post(self.url('join')).status_code, 302)
            self.assertTrue(is_owner(invited, self.dictionary))
            with closing(self.client.get(self.url('export'))) as response:
                self.assertEqual(response.status_code, 200)
            inviter = invited
        self.assertEqual(self.dictionary.memberships.filter(role='co_owner',accepted=True,status='active').count(), 8)
        self.client.force_login(self.owner)
        self.assertEqual(len(self.client.get(self.url('people')).context['memberships']), 9)

    def test_revoked_or_withdrawn_coowner_cannot_use_saved_invitation_form(self):
        row = self.grant()
        self.assertContains(self.client.get(self.url('people')), '<option value="co_owner"')
        Membership.objects.filter(pk=row.pk).update(role='editor')
        self.assertEqual(self.client.post(self.url('people'), {
            'action':'invite', 'username':self.outsider.username, 'role':'co_owner'}).status_code, 404)
        self.grant()
        withdraw_all(self.member, self.dictionary.pk, state_for(self.member, self.dictionary).revision)
        self.assertEqual(self.client.post(self.url('people'), {
            'action':'invite', 'username':self.outsider.username, 'role':'co_owner'}).status_code, 404)
        self.assertFalse(Membership.objects.filter(dictionary=self.dictionary,user=self.outsider).exists())


class CoOwnerMigrationTests(TransactionTestCase):
    def test_choice_migration_emits_no_schema_sql(self):
        executor = MigrationExecutor(connection)
        migration = executor.loader.disk_migrations[('community_dictionary', '0029_dictionary_coowners')]
        previous = executor.loader.project_state(('community_dictionary', '0028_word_audio_settings'))
        with connection.schema_editor(collect_sql=True, atomic=False) as editor:
            migration.apply(previous, editor)
        self.assertFalse([sql for sql in editor.collected_sql if sql.strip() and not sql.strip().startswith('--')])
