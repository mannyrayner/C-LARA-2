"""Entry context must aid recognition without granting custody or extra access."""
from contextlib import closing
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
        self.displayed = set()
        self.feed(response.content.decode())

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get('data-contribution-id'):
            self.displayed.add(int(attrs['data-contribution-id']))
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

    def assert_readonly(self, response, parts):
        self.assertEqual(Inputs(response).ids, set())
        self.assertTrue({p.pk for p in parts}.issubset(Inputs(response).displayed))

    def test_shared_card_groups_components_with_read_only_own_and_reference_labels(self):
        entry = self.mixed_entry()
        response = self.mine()
        self.assertEqual(len(response.context['cards']), 1)
        for value in ['soffa', 'sofa', 'Home', 'Contributor: owner', 'For reference']:
            self.assertContains(response, value)
        own = entry.contributions.filter(controlled_by=self.member)
        self.assert_readonly(response, own)
        audio = entry.contributions.get(kind='audio')
        self.assertContains(response, self.url('media', audio.pk))
        # A status-only check does not consume/close a streaming response.
        # Release its file before TemporaryDirectory cleanup on Windows.
        with closing(self.client.get(self.url('media', audio.pk))) as media_response:
            self.assertEqual(media_response.status_code, 200)
        # Context cannot be turned into a withdrawal by editing the submitted IDs.
        url = reverse('community_dictionary:withdraw')
        self.assertEqual(self.client.post(url, {'contributions': [audio.pk]}).status_code, 409)

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
        self.assert_readonly(response, entry.contributions.filter(controlled_by=self.owner))

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
        self.assert_readonly(response, entry.contributions.filter(controlled_by=self.member))

    def test_withdrawn_view_shows_only_own_content_and_blocks_personal_editing(self):
        from community_dictionary.participation import withdraw_all
        entry = self.mixed_entry()
        own = list(entry.contributions.filter(controlled_by=self.member))
        withdraw_all(self.member, self.dictionary.pk, 0)
        response = self.mine()
        self.assertContains(response, 'sofa')
        self.assertNotContains(response, 'soffa')
        self.assertNotContains(response, 'Home')
        self.assertNotContains(response, 'For reference')
        self.assert_readonly(response, own)
        own[0].refresh_from_db()
        for route in ['new', 'people']:
            self.assertEqual(self.client.get(reverse('community_dictionary:'+route, args=[own[0].entry.dictionary_id])).status_code, 404)

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
        self.assertEqual(len(self.mine().context['cards']), 2)
        self.client.force_login(self.member)
        self.assertEqual(len(self.mine().context['cards']), 1)

    def test_obsolete_component_filters_do_not_hide_material(self):
        entry = self.mixed_entry()
        response = self.mine(kind='image', dictionary=self.dictionary.pk)
        self.assertContains(response, 'soffa')
        self.assertContains(response, 'sofa')
        self.assertNotContains(response, 'outside this filter')
        self.assert_readonly(response, entry.contributions.filter(controlled_by=self.member))
        self.assertEqual(len(self.mine(kind='audio').context['cards']), 1)

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
        self.assert_readonly(response, entry.contributions.filter(controlled_by=self.member))
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
        self.assert_readonly(first, Contribution.objects.filter(entry_id__in=first_ids))
        self.assert_readonly(second, Contribution.objects.filter(entry_id__in=second_ids))

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
        self.assert_readonly(response, entry.contributions.all())

    def test_pending_only_and_archived_entries_do_not_lose_owned_controls(self):
        entry = self.create_entry(word='Pending word', meaning='Pending translation')
        response = self.mine()
        self.assertContains(response, 'Pending word')
        self.assertContains(response, 'Pending translation')
        self.assertContains(response, 'Awaiting review')
        self.assert_readonly(response, entry.contributions.all())
        self.client.force_login(self.owner)
        self.edit(entry, word='HIDDEN-ARCHIVED-WORD')
        Entry.objects.filter(pk=entry.pk).update(archived=True)
        self.client.force_login(self.member)
        response = self.mine()
        self.assertNotContains(response, 'HIDDEN-ARCHIVED-WORD')
        self.assertNotContains(response, self.url('entry', entry.pk))
        self.assert_readonly(response, entry.contributions.filter(controlled_by=self.member))
