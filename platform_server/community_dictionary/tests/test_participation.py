from contextlib import closing
import io
import uuid
import zipfile

from django.test import Client, TestCase
from django.urls import reverse

from community_dictionary.models import Contribution, Dictionary, Entry, ImageWordLink, Membership, Participation, WithdrawalHold
from community_dictionary.participation import restore_all, state_for, withdraw_all
from community_dictionary.services import Conflict, accept
from . import test_workflow as workflow, test_contribution_control as control


class ParticipationTests(TestCase):
    setUp = workflow.WorkflowTests.setUp
    url = workflow.WorkflowTests.url
    post = workflow.WorkflowTests.post
    create_entry = workflow.WorkflowTests.create_entry
    edit = control.ContributionControlTests.edit
    accept_pending = control.ContributionControlTests.accept_pending

    def mixed(self):
        entry = self.create_entry(meaning='sofa')
        self.accept_pending(entry)
        self.client.force_login(self.owner); self.edit(entry, word='soffa', category='Home')
        self.client.force_login(self.member); entry.refresh_from_db()
        return entry

    def withdraw(self, user=None, dictionary=None, **extra):
        user, dictionary = user or self.member, dictionary or self.dictionary
        state = state_for(user, dictionary)
        return self.client.post(reverse('community_dictionary:withdraw-content', args=[dictionary.pk]),
            {'revision': state.revision, 'confirm': 'yes', **extra})

    def restore(self, user=None, dictionary=None, **extra):
        user, dictionary = user or self.member, dictionary or self.dictionary
        state = state_for(user, dictionary)
        return self.client.post(reverse('community_dictionary:restore-content', args=[dictionary.pk]),
            {'revision': state.revision, **extra})

    def test_dictionary_controls_confirmation_and_read_only_view(self):
        self.mixed()
        self.assertContains(self.client.get(self.url('dictionary')), 'Withdraw my content')
        self.assertNotContains(self.client.get(self.url('dictionary')), 'Restore my content')
        confirmation = self.client.get(self.url('withdraw-content'))
        self.assertContains(confirmation, 'Confirm withdrawal')
        self.assertFalse(Participation.objects.filter(withdrawn=True).exists())
        self.assertEqual(self.withdraw(confirm='').status_code, 409)
        before = self.client.get(self.url('my-content'))
        self.assertContains(before, 'soffa')
        self.assertContains(before, 'For reference')
        self.assertNotContains(before, 'name="contributions"')
        self.assertNotContains(before, 'Share selected')

    def test_all_components_and_entries_withdraw_and_return_with_original_ids_and_approval(self):
        entry = self.mixed(); other = self.create_entry(word='katt')
        self.accept_pending(other)
        mine = list(Contribution.objects.filter(controlled_by=self.member).values_list('pk', flat=True))
        count = Contribution.objects.count()
        self.assertEqual(self.withdraw().status_code, 302)
        self.assertTrue(all(c.entry.dictionary.personal for c in Contribution.objects.filter(pk__in=mine)))
        entry.refresh_from_db(); self.assertEqual(entry.word, 'soffa'); self.assertEqual(entry.meaning, '')
        self.assertEqual(self.restore().status_code, 302)
        self.assertEqual(Contribution.objects.count(), count)
        self.assertFalse(Contribution.objects.filter(pk__in=mine, entry__dictionary__personal=True).exists())
        self.assertTrue(all(c.status == 'accepted' for c in Contribution.objects.filter(pk__in=mine)))
        entry.refresh_from_db(); self.assertEqual(entry.meaning, 'sofa'); self.assertIsNotNone(entry.selected_image_id)
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(self.url('entry', entry.pk)), 'sofa')

    def test_withdrawn_status_on_home_and_dictionary_and_only_own_private_content(self):
        entry = self.mixed(); self.withdraw()
        for url in [reverse('community_dictionary:home'), self.url('dictionary')]:
            response = self.client.get(url)
            self.assertContains(response, 'Your content is withdrawn')
            self.assertContains(response, 'Restore my content')
            self.assertNotContains(response, 'soffa')
            self.assertNotContains(response, '+ Add something')
        response = self.client.get(self.url('my-content'))
        self.assertContains(response, 'sofa')
        self.assertNotContains(response, 'soffa')
        self.assertNotContains(response, 'Home')
        self.assertNotContains(response, 'For reference')
        self.assertNotContains(response, 'name="contributions"')

    def test_all_browsing_media_export_and_writes_are_blocked_while_withdrawn(self):
        entry = self.mixed(); image = entry.contributions.get(kind='image')
        self.withdraw()
        for name, args in [('entry', [entry.pk]), ('word', [entry.pk]), ('media', [image.pk]),
                           ('new', []), ('record-audio', [entry.pk]), ('contribute', [entry.pk]),
                           ('photo-start', []), ('audio-start', [entry.pk]), ('people', []), ('queue', []), ('export', [])]:
            for method in ['get', 'post']:
                response = getattr(self.client, method)(self.url(name, *args))
                self.assertEqual(response.status_code, 404, (name, method, response.status_code))
        image.refresh_from_db()
        # Close the unconsumed file response before temporary-media cleanup.
        with closing(self.client.get(reverse('community_dictionary:own-media', args=[image.pk]))) as media_response:
            self.assertEqual(media_response.status_code, 200)
        for name, args in [('dictionary', []), ('entry', [image.entry_id]), ('new', []), ('export', [])]:
            url = reverse('community_dictionary:'+name, args=[image.entry.dictionary_id, *args])
            self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.post('new', {'word':'forged'}).status_code, 404)

    def test_old_individual_routes_and_actions_are_disabled(self):
        entry = self.mixed(); image = entry.contributions.get(kind='image')
        for name, args in [('withdraw', []), ('share', []), ('share-back', [entry.pk])]:
            self.assertEqual(self.client.post(reverse('community_dictionary:'+name, args=args),
                {'contributions':[image.pk], 'confirm':'yes', 'consent':'on', 'submission_id':str(uuid.uuid4())}).status_code, 409)
        self.assertEqual(self.client.post(self.url('review', image.pk), {'action':'withdraw'}).status_code, 409)
        self.assertEqual(self.client.post(self.url('membership-action'), {'action':'leave'}).status_code, 409)
        self.assertEqual(self.client.get(reverse('community_dictionary:mine')).status_code, 302)
        self.assertNotContains(self.client.get(self.url('entry',entry.pk)), 'Withdraw to my collection')

    def test_ownership_handover_is_required_atomic_and_not_reversed_on_return(self):
        self.client.force_login(self.owner)
        entry = self.create_entry(word='soffa', publish_now='on')
        self.assertContains(self.client.get(self.url('withdraw-content')), 'New dictionary owner')
        self.assertEqual(self.withdraw(self.owner).status_code, 409)
        self.dictionary.refresh_from_db(); self.assertEqual(self.dictionary.owner, self.owner)
        self.assertFalse(state_for(self.owner, self.dictionary).withdrawn)
        self.assertTrue(entry.contributions.exists())
        self.assertEqual(self.withdraw(self.owner, successor=self.member.pk).status_code, 302)
        self.dictionary.refresh_from_db(); self.assertEqual(self.dictionary.owner, self.member)
        self.assertFalse(entry.contributions.exists())
        self.assertEqual(self.restore(self.owner).status_code, 302)
        self.dictionary.refresh_from_db(); self.assertEqual(self.dictionary.owner, self.member)
        self.assertEqual(self.client.get(self.url('export')).status_code, 404)

    def test_successor_cannot_be_invited_inactive_withdrawn_outsider_or_self(self):
        for target in [self.owner.pk, self.outsider.pk, 999999]:
            self.client.force_login(self.owner)
            self.assertEqual(self.withdraw(self.owner, successor=target).status_code, 409)
        Membership.objects.filter(dictionary=self.dictionary, user=self.member).update(status='inactive')
        self.assertEqual(self.withdraw(self.owner, successor=self.member.pk).status_code, 409)
        Membership.objects.filter(dictionary=self.dictionary, user=self.member).update(status='active')
        Participation.objects.create(dictionary=self.dictionary, user=self.member, withdrawn=True)
        self.assertEqual(self.withdraw(self.owner, successor=self.member.pk).status_code, 409)

    def test_owner_without_successor_archives_and_can_reopen(self):
        self.client.force_login(self.owner)
        dictionary = Dictionary.objects.create(owner=self.owner, name='Solo', language='Swedish')
        entry = Entry.objects.create(dictionary=dictionary, created_by=self.owner)
        part = Contribution.objects.create(entry=entry, author=self.owner, kind='text', text_field='word', word='hej', status='accepted')
        self.assertEqual(self.withdraw(self.owner, dictionary).status_code, 302)
        dictionary.refresh_from_db(); self.assertTrue(dictionary.archived)
        self.assertEqual(self.restore(self.owner, dictionary).status_code, 302)
        dictionary.refresh_from_db(); self.assertFalse(dictionary.archived)
        part.refresh_from_db(); self.assertEqual(part.entry_id, entry.pk)

    def test_suspension_does_not_remove_withdrawal_right_or_allow_restoration(self):
        entry = self.mixed()
        Membership.objects.filter(dictionary=self.dictionary, user=self.member).update(status='inactive')
        self.assertEqual(self.withdraw().status_code, 302)
        self.assertEqual(self.restore().status_code, 409)
        self.assertContains(self.client.get(self.url('my-content')), 'sofa')
        Membership.objects.filter(dictionary=self.dictionary, user=self.member).update(status='active')
        # Reactivation by an owner does not itself restore withdrawn content.
        self.assertFalse(entry.contributions.filter(controlled_by=self.member).exists())
        self.assertTrue(state_for(self.member,self.dictionary).withdrawn)
        self.assertEqual(self.restore().status_code, 302)

    def test_repeated_cycles_and_stale_requests_do_not_duplicate_or_republish(self):
        self.mixed(); count=Contribution.objects.count()
        for cycle in range(3):
            rev=state_for(self.member,self.dictionary).revision
            self.assertEqual(self.withdraw(revision=rev).status_code,302)
            self.assertEqual(self.withdraw(revision=rev).status_code,302)
            self.assertEqual(self.restore(revision=rev+1).status_code,302)
            self.assertEqual(self.restore(revision=rev+1).status_code,302)
            self.assertEqual(self.withdraw(revision=rev).status_code,409)
        self.withdraw()
        self.assertEqual(self.restore(revision=1).status_code,409)
        self.assertTrue(state_for(self.member,self.dictionary).withdrawn)
        self.assertEqual(Contribution.objects.count(),count)

    def test_csrf_and_post_required_restore_has_no_confirmation(self):
        self.mixed()
        strict=Client(enforce_csrf_checks=True);strict.force_login(self.member)
        self.assertEqual(strict.post(self.url('withdraw-content'),{'confirm':'yes','revision':0}).status_code,403)
        self.assertEqual(self.client.get(self.url('restore-content')).status_code,405)
        self.withdraw()
        self.assertEqual(strict.post(self.url('restore-content'),{'revision':1}).status_code,403)
        self.assertEqual(self.client.post(self.url('restore-content'),{'revision':1}).status_code,302)

    def test_newer_shared_wording_wins_and_old_wording_returns_in_history(self):
        entry=self.mixed(); old=entry.current_meaning
        self.withdraw()
        self.client.force_login(self.owner);self.edit(entry,meaning='couch')
        self.client.force_login(self.member);self.restore()
        entry.refresh_from_db();old.refresh_from_db()
        self.assertEqual(entry.meaning,'couch')
        self.assertEqual(old.entry_id,entry.pk);self.assertEqual(old.status,'accepted')

    def test_overlapping_withdrawals_do_not_release_other_peoples_sources(self):
        entry=self.mixed(); old=entry.current_meaning
        self.client.force_login(self.owner);self.edit(entry,meaning='a sofa')
        entry.refresh_from_db(); dependent=entry.current_meaning
        self.client.force_login(self.member);self.withdraw()
        dependent.refresh_from_db();self.assertTrue(dependent.entry.dictionary.personal)
        self.client.force_login(self.owner);self.withdraw(self.owner,successor=self.third.pk)
        self.client.force_login(self.member);self.restore()
        old.refresh_from_db();dependent.refresh_from_db()
        self.assertFalse(old.entry.dictionary.personal);self.assertTrue(dependent.entry.dictionary.personal)
        self.client.force_login(self.owner);self.restore(self.owner)
        dependent.refresh_from_db();self.assertEqual(dependent.entry_id,entry.pk)
        self.assertFalse(WithdrawalHold.objects.exists())

    def test_reverse_order_of_overlapping_restoration_also_releases_dependents(self):
        entry=self.mixed()
        self.client.force_login(self.owner);self.edit(entry,meaning='a sofa')
        entry.refresh_from_db();dependent=entry.current_meaning
        self.client.force_login(self.member);self.withdraw()
        self.client.force_login(self.owner);self.withdraw(self.owner,successor=self.third.pk)
        self.restore(self.owner);dependent.refresh_from_db();self.assertTrue(dependent.entry.dictionary.personal)
        self.client.force_login(self.member);self.restore()
        dependent.refresh_from_db();self.assertEqual(dependent.entry_id,entry.pk)

    def test_pending_rejected_text_history_and_synthetic_audio_keep_their_meaning(self):
        entry=self.create_entry(word='katt');self.accept_pending(entry)
        word=entry.current_text
        pending=Contribution.objects.create(entry=entry,author=self.member,kind='audio')
        rejected=Contribution.objects.create(entry=entry,author=self.member,kind='image',status='rejected')
        audio=Contribution.objects.create(entry=entry,author=self.member,kind='audio',status='accepted',
            shared_from=word,provenance={'origin':'synthetic','source_text':'katt','language':'Swedish'})
        self.withdraw();self.restore()
        pending.refresh_from_db();rejected.refresh_from_db();audio.refresh_from_db()
        self.assertEqual((pending.status,rejected.status,audio.status),('pending','rejected','accepted'))
        self.assertEqual(audio.shared_from_id,word.pk)

    def test_new_contribution_cannot_be_attributed_to_withdrawn_member(self):
        self.mixed();self.withdraw();self.client.force_login(self.owner)
        response=self.post('new',{'word':'forged','contributor':self.member.pk,'contributor_permission':'on','publish_now':'on'})
        self.assertEqual(response.status_code,400)

    def test_own_content_privacy_and_export_for_remaining_owner(self):
        entry=self.mixed();image=entry.contributions.get(kind='image');self.withdraw()
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(reverse('community_dictionary:own-media',args=[image.pk])).status_code,404)
        response=self.client.get(self.url('export'))
        with zipfile.ZipFile(io.BytesIO(b''.join(response.streaming_content))) as bundle:
            self.assertFalse(any(p.startswith('media/') for p in bundle.namelist()))
            self.assertNotIn('"meaning": "sofa"',bundle.read('records.json').decode())
        self.client.force_login(self.outsider)
        for name in ['dictionary','my-content','withdraw-content','restore-content']:
            self.assertEqual(self.client.post(self.url(name)).status_code,404)

    def test_other_dictionaries_are_unaffected_except_for_dependent_copies(self):
        entry=self.mixed();root=entry.contributions.get(kind='image')
        other=Dictionary.objects.create(owner=self.member,name='Other',language='Swedish')
        e=Entry.objects.create(dictionary=other,created_by=self.member)
        copy=Contribution.objects.create(entry=e,author=self.member,kind='image',status='accepted',shared_from=root,file_path=root.file_path)
        independent=Contribution.objects.create(entry=e,author=self.member,kind='note',status='accepted',body='Independent')
        self.withdraw();copy.refresh_from_db();independent.refresh_from_db()
        self.assertTrue(copy.entry.dictionary.personal);self.assertEqual(independent.entry_id,e.pk)
        self.assertEqual(self.client.get(reverse('community_dictionary:dictionary',args=[other.pk])).status_code,200)
        self.restore();copy.refresh_from_db();self.assertEqual(copy.entry_id,e.pk)

    def test_picture_word_links_return_with_picture(self):
        entry=self.mixed();image=entry.contributions.get(kind='image')
        self.client.force_login(self.owner);word=self.create_entry(word='katt',publish_now='on')
        ImageWordLink.objects.create(image=image,word_entry=word,created_by=self.owner)
        self.client.force_login(self.member);self.withdraw();self.assertFalse(ImageWordLink.objects.filter(image=image).exists())
        self.restore();self.assertTrue(ImageWordLink.objects.filter(image=image,word_entry=word,created_by=self.owner).exists())

    def test_handover_rolls_back_if_retention_fails(self):
        from unittest.mock import patch
        self.client.force_login(self.owner);self.create_entry(word='hej',publish_now='on')
        with patch('community_dictionary.participation.withdraw',side_effect=Conflict('Retention failed')):
            self.assertEqual(self.withdraw(self.owner,successor=self.member.pk).status_code,409)
        self.dictionary.refresh_from_db();self.assertEqual(self.dictionary.owner,self.owner)
        self.assertFalse(state_for(self.owner,self.dictionary).withdrawn)
        self.assertFalse(WithdrawalHold.objects.exists())

    def test_member_can_leave_without_any_content_and_return(self):
        self.assertEqual(self.withdraw().status_code,302)
        self.assertTrue(state_for(self.member,self.dictionary).withdrawn)
        self.assertEqual(self.client.get(self.url('new')).status_code,404)
        self.assertEqual(self.restore().status_code,302)
        self.assertFalse(state_for(self.member,self.dictionary).withdrawn)
        self.assertEqual(self.client.get(self.url('new')).status_code,200)

    def test_new_owner_can_recover_second_coordinator_without_disabling_policy(self):
        Membership.objects.filter(dictionary=self.dictionary,user=self.member).update(role='coordinator')
        self.dictionary.membership_policy='coordinators';self.dictionary.save()
        self.client.force_login(self.owner);self.withdraw(self.owner,successor=self.member.pk)
        self.client.force_login(self.member)
        third=Membership.objects.get(dictionary=self.dictionary,user=self.third)
        self.assertEqual(self.client.post(self.url('membership-action'),{'action':'role','member_id':third.pk,'value':'coordinator'}).status_code,302)
        third.refresh_from_db();self.assertEqual(third.role,'coordinator')
        self.dictionary.refresh_from_db();self.assertEqual(self.dictionary.membership_policy,'coordinators')
        from community_dictionary.models import MembershipDecision
        self.client.post(self.url('membership-action'),{'action':'policy','value':'owner'})
        self.assertEqual(MembershipDecision.objects.latest('pk').status,'pending')

    def test_deliberate_empty_new_wording_is_not_overwritten_on_restore(self):
        entry=self.mixed();self.withdraw()
        self.client.force_login(self.owner);self.edit(entry,meaning='newer');self.edit(entry,meaning='')
        self.client.force_login(self.member);self.restore();entry.refresh_from_db()
        self.assertEqual(entry.meaning,'');self.assertEqual(entry.current_meaning.controlled_by_id,self.owner.pk)

    def test_request_completion_returns_and_moderated_comment_still_needs_review(self):
        from community_dictionary.models import Request
        entry=self.mixed()
        req=workflow.WorkflowTests.make_request(self,entry)
        audio=Contribution.objects.create(entry=entry,author=self.member,kind='audio',status='accepted',request=req)
        req.completed_with=audio;req.save()
        note=Contribution.objects.create(entry=entry,author=self.member,kind='note',body='A note',status='accepted')
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(self.url('review',note.pk),{'action':'remove'}).status_code,302)
        self.client.force_login(self.member);self.withdraw();req.refresh_from_db();self.assertIsNone(req.completed_with_id)
        self.restore();req.refresh_from_db();self.assertEqual(req.completed_with_id,audio.pk)
        note.refresh_from_db();self.assertEqual(note.status,'pending')
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(self.url('entry',entry.pk)),'Accept comment')
        self.assertEqual(self.client.post(self.url('review',note.pk),{'action':'accept'}).status_code,302)
        note.refresh_from_db();self.assertEqual(note.status,'accepted')

    def test_export_writes_one_media_file_for_historical_copies(self):
        entry=self.mixed();image=entry.contributions.get(kind='image')
        Contribution.objects.create(entry=entry,author=self.member,kind='image',status='superseded',
            shared_from=image,file_path=image.file_path,mime_type=image.mime_type)
        self.client.force_login(self.owner);response=self.client.get(self.url('export'))
        with zipfile.ZipFile(io.BytesIO(b''.join(response.streaming_content))) as bundle:
            media=[p for p in bundle.namelist() if p.startswith('media/')]
            self.assertEqual(len(media),len(set(media)))
