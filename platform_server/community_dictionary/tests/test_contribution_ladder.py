from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from community_dictionary.contribution_ladder import MAX_COPY_DEPTH, image_ladder
from community_dictionary.localisation import UI_COOKIE
from community_dictionary.models import (
    Contribution, Dictionary, Entry, Membership, Participation, WithdrawalHold,
)
from community_dictionary.participation import restore_all, withdraw_all


class ImageContributionLadderTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.viewer = User.objects.create_user('Manny')
        cls.cathy = User.objects.create_user('Cathy')
        cls.alice = User.objects.create_user('alice')
        cls.secret = User.objects.create_user('Private contributor')
        cls.dictionary = Dictionary.objects.create(owner=cls.viewer, name='French', language='French')
        Membership.objects.create(dictionary=cls.dictionary, user=cls.cathy, accepted=True)

    def dictionary_for(self, **kwargs):
        return Dictionary.objects.create(owner=kwargs.pop('owner', self.viewer),
            name='Another dictionary', language='English', **kwargs)

    def image(self, *, dictionary=None, author=None, entry=None, **kwargs):
        author = author or self.cathy
        entry = entry or Entry.objects.create(dictionary=dictionary or self.dictionary, created_by=author)
        return Contribution.objects.create(entry=entry, author=author, kind='image',
            status=kwargs.pop('status', 'accepted'), file_path=kwargs.pop('file_path', f'fixture/{entry.pk}.jpg'),
            **kwargs)

    def counts(self, user=None):
        return {row['username']: row['count'] for row in image_ladder(user or self.viewer)}

    def test_accepted_human_images_count_without_requiring_selection_or_files(self):
        self.image()
        self.image(provenance={'origin': 'human'})
        self.image(author=self.viewer)
        # The ladder counts contributions, not only the selected picture.
        self.assertEqual(self.counts(), {'Cathy': 2, 'Manny': 1})

    def test_only_live_accepted_media_count(self):
        self.image()
        for status in ['pending', 'rejected', 'withdrawn', 'removed', 'superseded']:
            self.image(status=status)
        self.image(file_path='')
        archived = Entry.objects.create(dictionary=self.dictionary, created_by=self.cathy, archived=True)
        self.image(entry=archived)
        Contribution.objects.create(entry=archived, author=self.cathy, kind='audio',
            status='accepted', file_path='not-a-picture.wav')
        self.assertEqual(self.counts(), {'Cathy': 1})

    def test_hidden_personal_and_archived_dictionaries_are_excluded(self):
        self.image()
        for flags in [{'hidden': True}, {'personal': True}, {'archived': True}]:
            self.image(dictionary=self.dictionary_for(**flags), author=self.secret)
        self.assertEqual(self.counts(), {'Cathy': 1})

    def test_membership_is_required_even_for_public_discoverable_dictionaries(self):
        self.image()
        public = self.dictionary_for(owner=self.alice, public_browsing_enabled=True, discoverable=True)
        self.image(dictionary=public, author=self.secret)
        self.assertEqual(self.counts(), {'Cathy': 1})
        Membership.objects.create(dictionary=public, user=self.viewer, accepted=True)
        self.assertEqual(self.counts(), {'Cathy': 1, 'Private contributor': 1})
        self.assertEqual(image_ladder(AnonymousUser()), [])

    def test_invited_inactive_and_withdrawn_viewers_do_not_gain_access(self):
        for status, accepted in [('invited', False), ('inactive', True), ('active', True)]:
            dictionary = self.dictionary_for(owner=self.alice)
            self.image(dictionary=dictionary, author=self.secret)
            Membership.objects.create(dictionary=dictionary, user=self.viewer, status=status, accepted=accepted)
            if status == 'active':
                Participation.objects.create(dictionary=dictionary, user=self.viewer, withdrawn=True)
        self.assertEqual(self.counts(), {})

    def test_explicit_copies_and_language_ports_credit_original_contributor_once(self):
        original = self.image(author=self.viewer, controlled_by=self.cathy,
            provenance={'attributed_by': self.viewer.pk, 'permission_confirmed': True})
        copy = self.image(dictionary=self.dictionary_for(), author=self.viewer, controlled_by=self.cathy,
            shared_from=original, provenance={'language_port': 2, 'copied_from': original.pk})
        self.image(dictionary=self.dictionary_for(), author=self.cathy, shared_from=copy,
            file_path='capture/new-jpeg-of-the-same-picture.jpg')
        row, = image_ladder(self.viewer)
        self.assertEqual(row, {'rank': 1, 'username': 'Cathy', 'count': 1, 'author_id': self.cathy.pk})

    def test_accepted_copy_counts_when_original_is_hidden_pending_archived_or_inaccessible(self):
        source_dictionary = self.dictionary_for(owner=self.alice, hidden=True, archived=True)
        source_entry = Entry.objects.create(dictionary=source_dictionary, created_by=self.cathy, archived=True)
        original = self.image(entry=source_entry, status='pending')
        self.image(shared_from=original)
        self.assertEqual(self.counts(), {'Cathy': 1})

    def test_reuploads_and_previous_revisions_do_not_imply_image_identity(self):
        first = self.image(file_path='same-upload.jpg')
        self.image(file_path=first.file_path)
        self.image(author=self.alice, file_path=first.file_path, previous_revision=first)
        generated = self.image(author=self.viewer, provenance={'origin': 'generated'})
        self.image(author=self.alice, previous_revision=generated)
        self.assertEqual(self.counts(), {'Cathy': 2, 'alice': 2})

    def test_generated_lineage_and_style_dependencies_cannot_earn_human_credit(self):
        for origin in ['generated', 'ai-generated', 'synthetic', 'unrecognised']:
            original = self.image(provenance={'origin': origin})
            self.image(shared_from=original, provenance={})
        style = self.image(provenance={'role': 'dictionary_style'})
        self.image(shared_from=style)
        human = self.image(author=self.viewer)
        self.image(shared_from=human, provenance={'source_style_id': human.pk})
        # A malformed/non-image dependency is not a copy of a photograph.
        text = Contribution.objects.create(entry=human.entry, author=self.cathy, kind='text', status='accepted')
        self.image(shared_from=text)
        self.assertEqual(self.counts(), {'Manny': 1})

    def test_malformed_provenance_fails_closed_without_breaking_people(self):
        for provenance in [[], {'origin': []}, {'origin': {}}, {'origin': None}]:
            self.image(provenance=provenance)
        self.assertEqual(self.counts(), {})

    def test_holds_departures_and_private_or_withdrawn_ancestors_block_stale_copies(self):
        for protection in ['hold', 'departed', 'private', 'withdrawn', 'removed']:
            source_dictionary = self.dictionary_for()
            original = self.image(dictionary=source_dictionary)
            self.image(shared_from=original)
            if protection == 'hold':
                state = Participation.objects.create(dictionary=source_dictionary, user=self.alice, withdrawn=True)
                WithdrawalHold.objects.create(participation=state, contribution=original)
            elif protection == 'departed':
                Participation.objects.create(dictionary=source_dictionary, user=self.cathy, withdrawn=True)
            elif protection == 'private':
                source_dictionary.personal = True
                source_dictionary.save(update_fields=['personal'])
            else:
                original.status = protection
                original.save(update_fields=['status'])
        held = self.image()
        state = Participation.objects.create(dictionary=self.dictionary, user=self.alice, withdrawn=True)
        WithdrawalHold.objects.create(participation=state, contribution=held)
        self.assertEqual(self.counts(), {})

    def test_dictionary_withdrawal_removes_family_and_return_restores_credit(self):
        original = self.image()
        self.image(dictionary=self.dictionary_for(), shared_from=original)
        self.assertEqual(self.counts(), {'Cathy': 1})
        withdraw_all(self.cathy, self.dictionary.pk, 0)
        self.assertEqual(self.counts(), {})
        restored, remaining = restore_all(self.cathy, self.dictionary.pk, 1)
        self.assertEqual((restored, remaining), (2, 0))
        self.assertEqual(self.counts(), {'Cathy': 1})

    def test_ties_share_rank_with_stable_name_order_and_no_zero_rows(self):
        for person, count in [(self.alice, 2), (self.cathy, 2), (self.viewer, 1)]:
            for _ in range(count):
                self.image(author=person)
        rows = image_ladder(self.viewer)
        self.assertEqual([(r['rank'], r['username'], r['count']) for r in rows],
                         [(1, 'alice', 2), (1, 'Cathy', 2), (3, 'Manny', 1)])

    def test_cyclic_and_excessively_deep_provenance_fail_closed(self):
        first = self.image(dictionary=self.dictionary_for(hidden=True))
        second = self.image(shared_from=first)
        Contribution.objects.filter(pk=first.pk).update(shared_from=second)
        current = self.image(dictionary=self.dictionary_for(hidden=True))
        for _ in range(MAX_COPY_DEPTH + 1):
            current = self.image(dictionary=self.dictionary_for(hidden=True), shared_from=current)
        self.image(shared_from=current)
        self.assertEqual(self.counts(), {})

    def test_batch_queries_do_not_grow_with_the_number_of_copies(self):
        hidden = self.dictionary_for(hidden=True)
        for _ in range(40):
            original = self.image(dictionary=hidden)
            middle = self.image(dictionary=hidden, shared_from=original)
            self.image(shared_from=middle)
        with CaptureQueriesContext(connection) as queries:
            self.assertEqual(self.counts(), {'Cathy': 40})
        self.assertEqual(len(queries), 3)

    def test_people_page_renders_member_scoped_ladder_and_preserves_access_boundary(self):
        self.image()
        self.image(dictionary=self.dictionary_for(hidden=True), author=self.secret)
        private = self.dictionary_for(owner=self.alice, public_browsing_enabled=True)
        self.image(dictionary=private, author=self.secret)
        people = reverse('community_dictionary:people', args=[self.dictionary.pk])
        self.assertEqual(self.client.get(people).status_code, 302)
        self.client.force_login(self.secret)
        self.assertEqual(self.client.get(people).status_code, 404)
        self.client.force_login(self.viewer)
        response = self.client.get(people)
        self.assertContains(response, 'Images contributed')
        self.assertContains(response, 'Rank')
        self.assertEqual(response.context['image_ladder_rows'], [
            {'rank': 1, 'username': 'Cathy', 'count': 1, 'author_id': self.cathy.pk},
        ])
        self.cathy.username = '<Cathy & co>'
        self.cathy.save(update_fields=['username'])
        self.client.cookies[UI_COOKIE] = 'fr'
        response = self.client.get(people)
        self.assertContains(response, 'Images apportées')
        self.assertContains(response, 'Classement des contributions d’images')
        self.assertContains(response, 'Rang')
        self.assertContains(response, '&lt;Cathy &amp; co&gt;')
        self.assertNotContains(response, '<Cathy & co>')
        Contribution.objects.filter(kind='image').update(status='pending')
        empty = self.client.get(people)
        self.assertEqual(empty.context['image_ladder_rows'], [])
        self.assertContains(empty, 'Aucune image apportée par une personne et validée à compter pour le moment.')
