import io
import json
import uuid
import zipfile

from django.core import signing
from django.test import Client
from django.urls import reverse

from community_dictionary.collections import withdraw
from community_dictionary.models import Contribution, Dictionary, Entry, ImageWordLink, Membership, MembershipDecision
from community_dictionary.services import accept
from community_dictionary.text import field_snapshot
from django.test import TestCase
from . import test_workflow as workflow
from .test_workflow import picture, recording


class ContributionControlTests(TestCase):
    setUp = workflow.WorkflowTests.setUp
    url = workflow.WorkflowTests.url
    post = workflow.WorkflowTests.post
    create_entry = workflow.WorkflowTests.create_entry
    def edit(self, entry, **fields):
        entry.refresh_from_db()
        snapshot = signing.dumps({'entry': entry.pk, 'fields': field_snapshot(entry)}, salt='community-text-fields')
        return self.post('contribute', {'edit_text': 'on', 'text_snapshot': snapshot, 'publish_now': 'on', **fields}, entry.pk)

    def accept_pending(self, entry):
        for part in entry.contributions.filter(status='pending').order_by('pk'):
            accept(part, self.owner)
        entry.refresh_from_db()

    def mine(self, **query):
        return self.client.get(self.url('my-content'), query)

    def withdraw_url(self):
        return reverse('community_dictionary:withdraw')

    def withdraw_all_request(self):
        from django.contrib.auth import get_user_model
        from community_dictionary.participation import state_for
        user = get_user_model().objects.get(pk=self.client.session['_auth_user_id'])
        state = state_for(user, self.dictionary)
        return self.client.post(self.url('withdraw-content'), {'confirm': 'yes', 'revision': state.revision,
            'successor': self.member.pk if user == self.owner else ''})

    def inactive(self, member=None):
        member = member or self.member
        self.client.force_login(self.owner)
        m = Membership.objects.get(dictionary=self.dictionary, user=member)
        result = self.client.post(self.url('membership-action'), {'action': 'deactivate', 'member_id': m.pk})
        self.assertEqual(result.status_code, 302, result.content)
        return m

    def test_cathy_translation_keeps_attribution_when_manny_adds_word_and_category(self):
        entry = self.create_entry(meaning='sofa')
        self.accept_pending(entry)
        translation = entry.current_meaning
        self.client.force_login(self.owner)
        response = self.edit(entry, word='soffa', meaning='sofa', category='Home')
        self.assertEqual(response.status_code, 200, response.content)
        entry.refresh_from_db()
        self.assertEqual(entry.current_meaning_id, translation.pk)
        self.assertEqual(entry.current_meaning.author, self.member)
        self.assertEqual(entry.current_text.author, self.owner)
        self.assertEqual(entry.current_category.author, self.owner)
        self.assertEqual(entry.contributions.filter(text_field='meaning').count(), 1)

    def test_disjoint_edits_survive_but_same_field_conflicts(self):
        entry = self.create_entry()
        entry.refresh_from_db()
        snapshot = signing.dumps({'entry': entry.pk, 'fields': field_snapshot(entry)}, salt='community-text-fields')
        self.client.force_login(self.owner)
        self.assertEqual(self.edit(entry, meaning='chair').status_code, 200)
        result = self.post('contribute', {'edit_text': 'on', 'text_snapshot': snapshot, 'word': 'stol', 'meaning': '', 'category': '', 'publish_now': 'on'}, entry.pk)
        self.assertEqual(result.status_code, 200, result.content)
        entry.refresh_from_db()
        self.assertEqual((entry.word, entry.meaning), ('stol', 'chair'))
        result = self.post('contribute', {'edit_text': 'on', 'text_snapshot': snapshot, 'meaning': 'seat', 'publish_now': 'on'}, entry.pk)
        self.assertEqual(result.status_code, 409)

    def test_signed_snapshot_cannot_be_forged_or_reused_for_other_entry(self):
        entry = self.create_entry()
        other = self.create_entry()
        snapshot = signing.dumps({'entry': other.pk, 'fields': field_snapshot(other)}, salt='community-text-fields')
        self.assertEqual(self.post('contribute', {'edit_text': 'on', 'word': 'x', 'text_snapshot': snapshot}, entry.pk).status_code, 409)
        self.assertEqual(self.post('contribute', {'edit_text': 'on', 'word': 'x', 'text_snapshot': 'forged'}, entry.pk).status_code, 409)

    def test_translation_change_keeps_word_version_and_matching_tts(self):
        self.client.force_login(self.owner)
        entry = self.create_entry(word='soffa', meaning='sofa', publish_now='on')
        before = (entry.current_text_id, entry.text_version)
        audio = Contribution.objects.create(entry=entry, author=self.owner, kind='audio', status='accepted',
            provenance={'origin': 'synthetic', 'source_text': 'soffa', 'language': 'Swedish'})
        self.assertEqual(self.edit(entry, meaning='couch').status_code, 200)
        entry.refresh_from_db()
        self.assertEqual((entry.current_text_id, entry.text_version), before)
        from community_dictionary.lexicon import outdated_tts
        self.assertFalse(outdated_tts(audio, entry, self.dictionary))

    def test_inactive_member_can_withdraw_without_access_to_other_material(self):
        entry = self.create_entry(meaning='PRIVATE-TRANSLATION')
        self.accept_pending(entry)
        picture_part = entry.contributions.get(kind='image')
        self.inactive()
        self.client.force_login(self.member)
        for name, args in [('entry', [entry.pk]), ('people', []), ('media', [picture_part.pk]), ('export', [])]:
            self.assertEqual(self.client.get(self.url(name, *args)).status_code, 404)
        self.assertContains(self.mine(), 'PRIVATE-TRANSLATION')
        response = self.withdraw_all_request()
        self.assertEqual(response.status_code, 302)
        entry.refresh_from_db()
        self.assertEqual(entry.meaning, '')
        self.assertFalse(entry.contributions.filter(kind='image').exists())
        self.assertContains(self.mine(view='private'), 'PRIVATE-TRANSLATION')
        self.assertEqual(self.client.post(self.url('join')).status_code, 404)

    def test_owner_cannot_read_withdrawn_records_media_search_or_export(self):
        entry = self.create_entry(meaning='SECRET-SOFA')
        self.accept_pending(entry)
        image = entry.contributions.get(kind='image')
        text = entry.current_meaning
        self.withdraw_all_request()
        image.refresh_from_db()
        self.assertTrue(image.entry.dictionary.personal)
        self.client.force_login(self.owner)
        for url in [self.url('media', image.pk), reverse('community_dictionary:media', args=[image.entry.dictionary_id, image.pk]), reverse('community_dictionary:own-media', args=[image.pk]), reverse('community_dictionary:entry', args=[image.entry.dictionary_id, image.entry_id])]:
            self.assertEqual(self.client.get(url).status_code, 404, url)
        self.assertNotContains(self.client.get(self.url('entry', entry.pk)), 'SECRET-SOFA')
        self.assertEqual(len(self.client.get(self.url('dictionary'), {'q': 'SECRET-SOFA'}).context['cards']), 0)
        response = self.client.get(self.url('export'))
        with zipfile.ZipFile(io.BytesIO(b''.join(response.streaming_content))) as bundle:
            self.assertNotIn('SECRET-SOFA', bundle.read('records.json').decode())
            self.assertFalse(any(name.startswith('media/') for name in bundle.namelist()))
        self.assertEqual(self.client.post(self.url('review', text.pk), {'action': 'restore', 'version': 1}).status_code, 404)

    def test_withdrawing_images_keeps_other_peoples_words_and_audio(self):
        entry = self.create_entry()
        self.accept_pending(entry)
        self.client.force_login(self.owner)
        self.edit(entry, word='soffa')
        self.post('record-audio', {'audio': recording(), 'consent': 'on', 'publish_now': 'on'}, entry.pk)
        audio = entry.contributions.get(kind='audio')
        self.client.force_login(self.member)
        self.withdraw_all_request()
        entry.refresh_from_db()
        self.assertEqual(entry.word, 'soffa')
        self.assertEqual(entry.contributions.get(kind='audio'), audio)
        self.assertIsNone(entry.selected_image_id)

    def test_component_history_withdrawal_cannot_be_undone_by_restore(self):
        entry = self.create_entry(meaning='couch')
        self.accept_pending(entry)
        old = entry.current_meaning
        self.client.force_login(self.owner)
        self.edit(entry, meaning='sofa')
        entry.refresh_from_db()
        newer = entry.current_meaning
        self.assertEqual(newer.previous_revision_id, old.pk)
        self.client.force_login(self.member)
        self.withdraw_all_request()
        entry.refresh_from_db()
        self.assertEqual(entry.meaning, '')
        newer.refresh_from_db()
        self.assertEqual(newer.entry.dictionary.owner, self.owner)
        self.assertTrue(newer.entry.dictionary.personal)
        self.client.force_login(self.owner)
        # A revision dependent on somebody else's withdrawn text cannot be reshared.
        response = self.client.post(reverse('community_dictionary:share'), {'contributions': [newer.pk],
            'target_dictionary': self.dictionary.pk, 'confirm': 'yes', 'consent': 'on', 'submission_id': uuid.uuid4()})
        self.assertEqual(response.status_code, 409)

    def test_reactivation_restores_membership_but_not_private_material(self):
        entry = self.create_entry(meaning='sofa')
        m = self.inactive()
        self.client.force_login(self.member)
        self.withdraw_all_request()
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(self.url('membership-action'), {'action': 'reactivate', 'member_id': m.pk}).status_code, 302)
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(self.url('dictionary')).status_code, 200)
        self.assertFalse(entry.contributions.exists())
        self.assertContains(self.mine(view='private'), 'sofa')

    def test_private_dictionary_cannot_be_shared_by_inviting_other_accounts(self):
        entry = self.create_entry()
        self.withdraw_all_request()
        private = Dictionary.objects.get(personal=True)
        Membership.objects.create(dictionary=private, user=self.owner, accepted=True, role='editor')
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(reverse('community_dictionary:dictionary', args=[private.pk])).status_code, 404)
        self.client.force_login(self.member)
        self.assertEqual(self.client.post(reverse('community_dictionary:people', args=[private.pk]), {'action': 'invite', 'username': self.owner.username}).status_code, 404)

    def test_two_coordinators_required_for_status_role_and_policy_changes(self):
        m = Membership.objects.get(dictionary=self.dictionary, user=self.member)
        m.role = 'coordinator'; m.save()
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(self.url('membership-action'), {'action': 'policy', 'value': 'coordinators'}).status_code, 302)
        third = Membership.objects.get(dictionary=self.dictionary, user=self.third)
        for action, value in [('deactivate', ''), ('reactivate', ''), ('role', 'editor'), ('policy', 'owner')]:
            data = {'action': action, 'member_id': third.pk, 'value': value}
            self.client.force_login(self.owner)
            self.assertEqual(self.client.post(self.url('membership-action'), data).status_code, 302)
            decision = MembershipDecision.objects.latest('pk')
            self.assertEqual(decision.status, 'pending')
            self.assertEqual(self.client.post(self.url('membership-action'), {'action': 'approve', 'decision_id': decision.pk}).status_code, 409)
            self.client.force_login(self.member)
            self.assertEqual(self.client.post(self.url('membership-action'), {'action': 'approve', 'decision_id': decision.pk}).status_code, 302)
            decision.refresh_from_db()
            self.assertEqual(decision.status, 'applied')

    def test_inactive_invitation_cannot_bypass_status_decision(self):
        m = self.inactive()
        self.client.post(self.url('people'), {'action': 'invite', 'username': self.member.username, 'role': 'member'})
        m.refresh_from_db()
        self.assertEqual(m.status, 'inactive')
        self.client.force_login(self.member)
        self.assertEqual(self.client.post(self.url('join')).status_code, 404)
        self.assertNotContains(self.client.get(reverse('community_dictionary:home')), 'Join dictionary')

    def test_old_removal_endpoint_no_longer_deletes_membership(self):
        m = Membership.objects.get(dictionary=self.dictionary, user=self.member)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(self.url('people'), {'action': 'remove_member', 'member_id': m.pk}).status_code, 409)
        self.assertTrue(Membership.objects.filter(pk=m.pk).exists())

    def test_withdrawal_requires_csrf_and_post(self):
        entry = self.create_entry()
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.member)
        self.assertEqual(client.get(self.withdraw_url()).status_code, 405)
        self.assertEqual(client.post(self.withdraw_url(), {'contributions': [entry.contributions.get().pk]}).status_code, 403)

    def test_photo_and_tts_previews_are_discarded_on_withdrawal(self):
        from community_dictionary.models import PhotoStudy, AudioStudy
        from django.utils import timezone
        from datetime import timedelta
        entry = self.create_entry(word='katt')
        self.accept_pending(entry)
        image = entry.contributions.get(kind='image')
        photo = PhotoStudy.objects.create(dictionary=self.dictionary, user=self.third, source_entry=entry,
            source_image_id=image.pk, expires_at=timezone.now()+timedelta(days=1), status='candidate',
            result={'word': 'sensitive'}, language='Swedish', explanation_language='English', model='mock')
        audio = AudioStudy.objects.create(dictionary=self.dictionary, entry=entry, user=self.third,
            expires_at=timezone.now()+timedelta(days=1), status='ready', source_text='katt', source_text_id=entry.current_text_id,
            source_text_version=entry.text_version, language='Swedish', language_code='sv', model='mock', voice='mock')
        self.withdraw_all_request()
        photo.refresh_from_db(); audio.refresh_from_db()
        self.assertEqual((photo.status, photo.result), ('discarded', {}))
        self.assertEqual((audio.status, audio.source_text), ('discarded', ''))


    def test_editor_can_record_permission_and_credit_material_to_another_member(self):
        self.client.force_login(self.owner)
        response = self.post('new', {'meaning': 'sofa', 'contributor': self.member.pk})
        self.assertEqual(response.status_code, 400)
        response = self.post('new', {'meaning': 'sofa', 'contributor': self.member.pk, 'contributor_permission': 'on', 'publish_now': 'on'})
        self.assertEqual(response.status_code, 200)
        part = Contribution.objects.get(text_field='meaning')
        self.assertEqual(part.author, self.owner)
        self.assertEqual(part.controlled_by, self.member)
        self.client.force_login(self.member)
        self.assertEqual(self.withdraw_all_request().status_code, 302)
        part.refresh_from_db()
        self.assertEqual(part.entry.dictionary.owner, self.member)

    def test_ordinary_member_cannot_transfer_custody_by_forging_editor_field(self):
        response = self.post('new', {'word': 'soffa', 'contributor': self.third.pk, 'contributor_permission': 'on'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Contribution.objects.get(text_field='word').controlled_by, self.member)

    def test_withdrawal_revokes_copies_in_other_dictionaries(self):
        entry = self.create_entry()
        self.accept_pending(entry)
        root = entry.contributions.get(kind='image')
        other = Dictionary.objects.create(owner=self.owner, name='Another dictionary', language='Swedish')
        copy_entry = Entry.objects.create(dictionary=other, created_by=self.owner)
        copied = Contribution.objects.create(entry=copy_entry, author=self.member, controlled_by=self.member,
            kind='image', status='accepted', shared_from=root, file_path=root.file_path, mime_type=root.mime_type)
        self.withdraw_all_request()
        copied.refresh_from_db()
        self.assertTrue(copied.entry.dictionary.personal)
        self.assertEqual(copied.entry.dictionary.owner, self.member)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(reverse('community_dictionary:media', args=[other.pk, copied.pk])).status_code, 404)

    def test_partner_request_text_is_withdrawable_and_not_left_in_queue(self):
        entry = self.create_entry()
        workflow.WorkflowTests.make_request(self, entry)
        from community_dictionary.models import Request
        req = Request.objects.get()
        note = req.responses.get(kind='note')
        self.withdraw_all_request()
        req.refresh_from_db()
        self.assertEqual(req.note, '')
        self.assertTrue(req.withdrawn)

    def test_stale_governance_proposal_cannot_change_policy(self):
        m = Membership.objects.get(dictionary=self.dictionary, user=self.member)
        m.role = 'coordinator'; m.save()
        self.dictionary.membership_policy = 'coordinators'; self.dictionary.save()
        self.client.force_login(self.owner)
        self.client.post(self.url('membership-action'), {'action': 'policy', 'value': 'owner'})
        proposal = MembershipDecision.objects.latest('pk')
        self.dictionary.membership_revision += 1; self.dictionary.save()
        self.client.force_login(self.member)
        self.assertEqual(self.client.post(self.url('membership-action'), {'action': 'approve', 'decision_id': proposal.pk}).status_code, 409)
        self.dictionary.refresh_from_db()
        self.assertEqual(self.dictionary.membership_policy, 'coordinators')
