"""Entry context must aid recognition without granting custody or extra access."""
from html.parser import HTMLParser

from django.test import TestCase
from django.urls import reverse

from community_dictionary.collections import withdraw
from community_dictionary.models import Contribution, Entry, ImageWordLink, Membership
from . import test_contribution_control as control, test_workflow as workflow
from .test_workflow import recording


class Inputs(HTMLParser):
    def __init__(self, response):
        super().__init__()
        self.ids = set()
        self.feed(response.content.decode())

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'input' and attrs.get('name') == 'contributions':
            self.ids.add(int(attrs['value']))


class ContributionDisplayTests(TestCase):
    setUp = workflow.WorkflowTests.setUp
    url = workflow.WorkflowTests.url
    post = workflow.WorkflowTests.post
    create_entry = workflow.WorkflowTests.create_entry
    edit = control.ContributionControlTests.edit
    accept_pending = control.ContributionControlTests.accept_pending
    mine = control.ContributionControlTests.mine

    def mixed_entry(self):
        entry = self.create_entry(meaning='sofa')
        self.accept_pending(entry)
        self.client.force_login(self.owner)
        self.edit(entry, word='soffa', meaning='sofa', category='Home')
        response = self.post('record-audio', {'audio': recording(), 'consent': 'on', 'publish_now': 'on'}, entry.pk)
        self.assertEqual(response.status_code, 200)
        entry.refresh_from_db()
        self.client.force_login(self.member)
        return entry

    def assert_selectable(self, response, parts):
        self.assertEqual(Inputs(response).ids, {p.pk for p in parts})

    def test_shared_card_groups_all_components_and_only_own_parts_are_selectable(self):
        entry = self.mixed_entry()
        response = self.mine()
        self.assertEqual(len(response.context['cards']), 1)
        for value in ['soffa', 'sofa', 'Home', 'Contributor: owner', 'For reference']:
            self.assertContains(response, value)
        own = entry.contributions.filter(controlled_by=self.member)
        self.assert_selectable(response, own)
        audio = entry.contributions.get(kind='audio')
        self.assertContains(response, self.url('media', audio.pk))
        self.assertEqual(self.client.get(self.url('media', audio.pk)).status_code, 200)
        # Context cannot be turned into a withdrawal by editing the submitted IDs.
        url = reverse('community_dictionary:withdraw')
        self.assertEqual(self.client.post(url, {'contributions': [audio.pk]}).status_code, 404)

    def test_owner_sees_members_picture_and_translation_for_reference(self):
        entry = self.mixed_entry()
        self.client.force_login(self.owner)
        response = self.mine()
        self.assertContains(response, 'sofa')
        image = entry.contributions.get(kind='image')
        self.assertContains(response, self.url('media', image.pk))
        card = response.context['cards'][0]
        self.assertTrue(card['image']['reference'])
        self.assertFalse(card['image']['selectable'])
        self.assert_selectable(response, entry.contributions.filter(controlled_by=self.owner))

    def test_inactive_member_keeps_own_material_without_foreign_text_or_media(self):
        entry = self.mixed_entry()
        Membership.objects.filter(dictionary=self.dictionary, user=self.member).update(status='inactive')
        response = self.mine()
        self.assertContains(response, 'sofa')
        self.assertNotContains(response, 'soffa')
        self.assertNotContains(response, 'Home')
        self.assertNotContains(response, 'Contributor: owner')
        self.assertNotContains(response, self.url('media', entry.contributions.get(kind='audio').pk))
        self.assertNotContains(response, self.url('entry', entry.pk))
        image = entry.contributions.get(kind='image')
        self.assertContains(response, reverse('community_dictionary:own-media', args=[image.pk]))
        self.assert_selectable(response, entry.contributions.filter(controlled_by=self.member))

    def test_private_collection_uses_live_shared_context_and_never_selects_it(self):
        entry = self.mixed_entry()
        image = entry.contributions.get(kind='image')
        withdraw(self.member, [image.pk])
        response = self.mine(view='private')
        self.assertContains(response, 'soffa')
        self.assertContains(response, 'sofa')  # Still shared by the same member: reference only here.
        self.assertContains(response, 'not part of your private collection')
        self.assert_selectable(response, [image])
        self.client.force_login(self.owner)
        self.edit(entry, word='en soffa')
        self.client.force_login(self.member)
        self.assertContains(self.mine(view='private'), 'en soffa')
        Membership.objects.filter(dictionary=self.dictionary, user=self.member).update(status='inactive')
        response = self.mine(view='private')
        self.assertNotContains(response, 'soffa')
        self.assertNotContains(response, 'Home')
        self.assertNotContains(response, self.url('entry', entry.pk))
        self.assert_selectable(response, [image])

        # A private word can differ from the source. Keep the source recording
        # beside its own wording rather than presenting it as the private word.
        Membership.objects.filter(dictionary=self.dictionary, user=self.member).update(status='active')
        image.refresh_from_db()
        private = image.entry
        private_text = Contribution.objects.create(entry=private, author=self.member, kind='text',
            text_field='word', word='min soffa', status='accepted')
        private.word = private_text.word
        private.current_text = private_text
        private.save()
        card = self.mine(view='private').context['cards'][0]
        self.assertEqual(card['title'], 'min soffa')
        self.assertEqual(card['audio'], [])
        self.assertEqual(len(card['source_audio']), 1)

    def test_other_peoples_withdrawn_and_rejected_material_is_not_reference_context(self):
        entry = self.mixed_entry()
        audio = entry.contributions.get(kind='audio')
        Contribution.objects.create(entry=entry, author=self.owner, kind='note', status='rejected', body='REJECTED-PRIVATE')
        withdraw(self.owner, [audio.pk, entry.current_text_id])
        response = self.mine()
        self.assertNotContains(response, 'soffa')
        self.assertNotContains(response, 'REJECTED-PRIVATE')
        self.assertNotContains(response, self.url('media', audio.pk))
        self.assertNotContains(response, reverse('community_dictionary:own-media', args=[audio.pk]))
        self.client.force_login(self.owner)
        # Nor is somebody else's personal collection listed for the owner.
        self.assertEqual(len(self.mine(view='private').context['cards']), 1)
        self.client.force_login(self.member)
        self.assertEqual(len(self.mine(view='private').context['cards']), 0)

    def test_kind_filter_keeps_context_but_only_matching_own_material_selectable(self):
        entry = self.mixed_entry()
        response = self.mine(kind='image', dictionary=self.dictionary.pk)
        self.assertContains(response, 'soffa')
        self.assertContains(response, 'sofa')
        self.assertContains(response, 'outside this filter')
        self.assert_selectable(response, entry.contributions.filter(kind='image'))
        response = self.mine(kind='audio')
        self.assertEqual(len(response.context['cards']), 0)  # Only the owner's audio exists.

    def test_picture_word_links_remain_reference_and_require_current_membership(self):
        entry = self.mixed_entry()
        image = entry.contributions.get(kind='image')
        self.client.force_login(self.owner)
        word = self.create_entry(word='katt', meaning='cat', publish_now='on')
        ImageWordLink.objects.create(image=image, word_entry=word, created_by=self.owner)
        self.client.force_login(self.member)
        response = self.mine()
        self.assertContains(response, 'katt')
        self.assertContains(response, 'cat')
        self.assertContains(response, self.url('word', word.pk))
        self.assert_selectable(response, entry.contributions.filter(controlled_by=self.member))
        Membership.objects.filter(dictionary=self.dictionary, user=self.member).update(status='inactive')
        self.assertNotContains(self.mine(), 'katt')

    def test_pagination_counts_entries_and_never_splits_their_contributions(self):
        entries = []
        for i in range(13):
            entry = Entry.objects.create(dictionary=self.dictionary, created_by=self.member)
            entries.append(entry)
            for j in range(4):
                Contribution.objects.create(entry=entry, author=self.member, kind='note', status='accepted', body=f'Note {i}-{j}')
        first, second = self.mine(), self.mine(page=2)
        self.assertEqual(first.context['page'].paginator.count, 13)
        self.assertEqual(len(first.context['cards']), 12)
        self.assertEqual(len(second.context['cards']), 1)
        first_ids = {card['entry'].pk for card in first.context['cards']}
        second_ids = {card['entry'].pk for card in second.context['cards']}
        self.assertFalse(first_ids & second_ids)
        self.assertEqual(first_ids | second_ids, {e.pk for e in entries})
        self.assert_selectable(first, Contribution.objects.filter(entry_id__in=first_ids))
        self.assert_selectable(second, Contribution.objects.filter(entry_id__in=second_ids))

    def test_current_word_and_audio_are_separate_from_owned_history(self):
        self.client.force_login(self.owner)
        entry = self.create_entry(word='en häst', publish_now='on')
        entry.refresh_from_db()
        old = entry.current_text
        audio = Contribution.objects.create(entry=entry, author=self.owner, kind='audio', status='accepted',
            provenance={'origin': 'synthetic', 'source_text': 'en häst', 'language': 'Swedish'})
        self.edit(entry, word='häst')
        rejected = Contribution.objects.create(entry=entry, author=self.owner, kind='note', status='rejected', body='Rejected but still mine')
        response = self.mine()
        card = response.context['cards'][0]
        self.assertEqual(card['title'], 'häst')
        self.assertEqual(card['audio'], [])
        self.assertEqual({c['part'].pk for c in card['history']}, {old.pk, audio.pk, rejected.pk})
        self.assert_selectable(response, entry.contributions.all())

    def test_pending_only_and_archived_entries_do_not_lose_owned_controls(self):
        entry = self.create_entry(word='Pending word', meaning='Pending translation')
        response = self.mine()
        self.assertContains(response, 'Pending word')
        self.assertContains(response, 'Pending translation')
        self.assertContains(response, 'Awaiting review')
        self.assert_selectable(response, entry.contributions.all())
        self.client.force_login(self.owner)
        self.edit(entry, word='HIDDEN-ARCHIVED-WORD')
        Entry.objects.filter(pk=entry.pk).update(archived=True)
        self.client.force_login(self.member)
        response = self.mine()
        self.assertNotContains(response, 'HIDDEN-ARCHIVED-WORD')
        self.assertNotContains(response, self.url('entry', entry.pk))
        self.assert_selectable(response, entry.contributions.filter(controlled_by=self.member))
