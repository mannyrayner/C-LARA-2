"""Publication is opt-in; visitors get only live accepted learning material."""
from contextlib import closing
from unittest.mock import patch

from django.test import Client, TestCase
from django.urls import reverse

from community_dictionary import image_copy
from community_dictionary.models import (
    Contribution, Dictionary, Entry, Event, ImageWordLink, Membership,
    Participation, SentenceWord, WithdrawalHold,
)
from community_dictionary.participation import restore_all, withdraw_all
from community_dictionary.services import accept
from community_dictionary.storage import prepare_upload, write_upload
from . import test_workflow as workflow


class PublicBrowsingTests(TestCase):
    def setUp(self):
        workflow.WorkflowTests.setUp(self)
        self.client.logout()
        self.dictionary.public_browsing_enabled = True
        self.dictionary.save()
        self.word = self.make_entry('katt', 'cat', 'Animals')
        self.image = self.add_media(self.word, 'image')
        self.audio = self.add_media(self.word, 'audio')
        self.owner_client = Client()
        self.owner_client.force_login(self.owner)

    def url(self, name, *args):
        return reverse('community_dictionary:' + name, args=[self.dictionary.pk, *args])

    def make_entry(self, word='', meaning='', category='', kind='word', author=None):
        author = author or self.member
        entry = Entry.objects.create(dictionary=self.dictionary, created_by=author, entry_type=kind)
        for field, value in [('word', word), ('meaning', meaning), ('category', category)]:
            if value:
                part = Contribution.objects.create(entry=entry, author=author, kind='text',
                    text_field=field, **{field: value})
                accept(part, self.owner)
        entry.refresh_from_db()
        return entry

    def add_media(self, entry, kind, status='accepted', author=None, **extra):
        upload = workflow.picture() if kind == 'image' else workflow.recording()
        media = write_upload(prepare_upload(upload, kind), self.dictionary.pk, [])
        part = Contribution.objects.create(entry=entry, author=author or self.member,
            kind=kind, status=status, **media, **extra)
        if kind == 'image' and status == 'accepted':
            entry.selected_image = part
            entry.save(update_fields=['selected_image'])
        return part

    def change(self, action, client=None, **extra):
        self.dictionary.refresh_from_db()
        return (client or self.owner_client).post(self.url('public-access'),
            {'action': action, 'revision': self.dictionary.public_browsing_revision, **extra})

    def test_default_is_private_and_copy_is_private(self):
        private = Dictionary.objects.create(owner=self.owner, name='Secret dictionary', language='Swedish')
        self.assertFalse(private.public_browsing_enabled)
        self.assertNotContains(self.client.get(reverse('community_dictionary:public-home')), private.name)
        self.assertEqual(self.client.get(reverse('community_dictionary:public-dictionary', args=[private.pk])).status_code, 404)
        copy = image_copy.create(self.dictionary, self.owner, 'Private copy')
        self.assertFalse(copy.public_browsing_enabled)

    def test_owner_enable_needs_permission_and_explicit_action(self):
        self.change('disable')
        self.assertEqual(self.change('enable').status_code, 400)
        self.assertEqual(self.change('invalid', permission='on').status_code, 400)
        self.assertEqual(self.change('enable', permission='on').status_code, 302)
        self.dictionary.refresh_from_db()
        self.assertTrue(self.dictionary.public_browsing_enabled)
        self.assertEqual(Event.objects.filter(action='public_browsing').count(), 2)

    def test_owner_only_csrf_and_stale_form_protection(self):
        for user, role in [(self.member, 'member'), (self.member, 'editor'),
                           (self.member, 'coordinator'), (self.outsider, 'member')]:
            Membership.objects.filter(dictionary=self.dictionary, user=self.member).update(role=role)
            client = Client(); client.force_login(user)
            self.assertEqual(self.change('disable', client).status_code, 404)
        self.assertEqual(self.change('disable', self.client).status_code, 302)
        csrf = Client(enforce_csrf_checks=True); csrf.force_login(self.owner)
        self.assertEqual(self.change('disable', csrf).status_code, 403)
        self.assertEqual(self.owner_client.get(self.url('public-access')).status_code, 405)
        self.change('disable')
        self.assertEqual(self.change('enable', permission='on', revision=0).status_code, 409)
        self.dictionary.refresh_from_db(); self.assertFalse(self.dictionary.public_browsing_enabled)

    def test_duplicate_toggle_and_ordinary_settings_cannot_publish(self):
        self.change('disable')
        data = {'action': 'enable', 'revision': 1, 'permission': 'on'}
        for _ in range(2):
            self.assertEqual(self.owner_client.post(self.url('public-access'), data).status_code, 302)
        self.dictionary.refresh_from_db(); self.assertEqual(self.dictionary.public_browsing_revision, 2)
        self.change('disable')
        self.owner_client.post(self.url('settings'), {'name': self.dictionary.name,
            'language': 'Swedish', 'text_direction': 'auto', 'public_browsing_enabled': 'on'})
        self.dictionary.refresh_from_db(); self.assertFalse(self.dictionary.public_browsing_enabled)

    def test_hidden_archived_personal_dictionaries_never_public_even_with_flag(self):
        for field in ['hidden', 'archived', 'personal']:
            Dictionary.objects.filter(pk=self.dictionary.pk).update(**{field: True})
            self.assertNotContains(self.client.get(reverse('community_dictionary:public-home')), self.dictionary.name)
            for path in [self.url('public-dictionary'), self.url('public-entry', self.word.pk),
                         self.url('public-word', self.word.pk), self.url('public-media', self.image.pk)]:
                with closing(self.client.get(path)) as response:
                    self.assertEqual(response.status_code, 404, (field, path))
            Dictionary.objects.filter(pk=self.dictionary.pk).update(**{field: False})

    def test_hiding_turns_off_public_access_and_unhiding_does_not_republish(self):
        for visibility in ['hidden', 'visible']:
            self.owner_client.post(self.url('visibility'), {'visibility': visibility})
            self.dictionary.refresh_from_db()
            self.assertFalse(self.dictionary.public_browsing_enabled)
            self.assertEqual(self.client.get(self.url('public-entry', self.word.pk)).status_code, 404)
        self.assertEqual(self.dictionary.public_browsing_revision, 1)
        self.assertEqual(self.owner_client.get(self.url('entry', self.word.pk)).status_code, 200)

    def test_list_counts_search_and_modes_use_only_accepted_text(self):
        sentence = self.make_entry('Katten sover.', 'The cat sleeps.', kind='sentence')
        self.add_media(sentence, 'image')
        draft = self.make_entry()
        Contribution.objects.create(entry=draft, author=self.member, kind='text', word='SECRET-DRAFT')
        self.add_media(draft, 'image', status='pending')
        response = self.client.get(reverse('community_dictionary:public-home'))
        self.assertContains(response, '1 sentence')
        self.assertContains(response, '1 word')
        self.assertContains(self.client.get(self.url('public-dictionary'), {'view': 'sentences'}), 'Katten sover.')
        self.assertContains(self.client.get(self.url('public-dictionary'), {'view': 'words', 'q': 'cat'}), 'katt')
        self.assertContains(self.client.get(self.url('public-dictionary'), {'category': 'Animals'}), 'katt')
        for query in [{'show': 'review'}, {'show': 'all'}]:
            self.assertNotContains(self.client.get(self.url('public-dictionary'), query), 'SECRET-DRAFT')
        self.assertEqual(self.client.get(self.url('public-dictionary'), {'q': 'SECRET-DRAFT'}).context['rows'], [])
        self.assertEqual(self.client.get(self.url('public-entry', draft.pk)).status_code, 404)

    def test_accepted_picture_with_pending_title_has_no_title_fallback(self):
        entry = self.make_entry()
        self.add_media(entry, 'image')
        Contribution.objects.create(entry=entry, author=self.member, kind='text', word='PRIVATE-PROPOSAL')
        for name, args in [('public-dictionary', []), ('public-entry', [entry.pk])]:
            response = self.client.get(self.url(name, *args))
            self.assertContains(response, 'Picture')
            self.assertNotContains(response, 'PRIVATE-PROPOSAL')

    def test_pending_and_historical_fields_never_leak_through_text_search_or_categories(self):
        for field in ['word', 'meaning', 'category']:
            Contribution.objects.create(entry=self.word, author=self.member,
                kind='text', text_field=field, **{field: 'PRIVATE-' + field})
        Contribution.objects.create(entry=self.word, author=self.member,
            kind='text', text_field='word', word='OLD-WORD', status='accepted')
        for name, args in [('public-dictionary', []), ('public-entry', [self.word.pk]), ('public-word', [self.word.pk])]:
            response = self.client.get(self.url(name, *args))
            for hidden in ['PRIVATE-word', 'PRIVATE-meaning', 'PRIVATE-category', 'OLD-WORD']:
                self.assertNotContains(response, hidden)
        result = self.client.get(self.url('public-dictionary'), {'q': 'PRIVATE'})
        self.assertEqual(result.context['rows'], [])

    def test_invalid_text_pointers_or_status_do_not_expose_cached_fields(self):
        self.word.current_meaning.status = 'withdrawn'; self.word.current_meaning.save()
        self.word.current_category.status = 'pending'; self.word.current_category.save()
        response = self.client.get(self.url('public-word', self.word.pk))
        self.assertNotContains(response, '>cat<')
        self.assertNotContains(response, 'Animals')
        other = self.make_entry('private-other')
        Entry.objects.filter(pk=self.word.pk).update(current_text=other.current_text, word='private-other')
        self.assertEqual(self.client.get(self.url('public-word', self.word.pk)).status_code, 404)
        self.assertNotContains(self.client.get(self.url('public-entry', self.word.pk)), 'private-other')

    def test_notes_personal_information_and_generation_metadata_are_excluded(self):
        note = self.add_media(self.word, 'audio')
        note.kind = 'note'; note.body = 'SECRET-DISCUSSION'; note.save()
        self.image.provenance = {'prompt': 'SECRET-PROMPT'}; self.image.label = 'SECRET-CAPTION'; self.image.save()
        response = self.client.get(self.url('public-entry', self.word.pk))
        for hidden in ['SECRET-DISCUSSION', 'SECRET-PROMPT', 'SECRET-CAPTION', self.member.username,
                       'For our group', 'Show more options', 'Describe this picture', 'Settings', 'Check pronunciation']:
            self.assertNotContains(response, hidden)
        self.assertEqual(self.client.get(self.url('public-media', note.pk)).status_code, 404)

    def test_only_accepted_media_is_served_and_picture_query_cannot_bypass(self):
        for status in ['pending', 'rejected', 'removed', 'withdrawn', 'superseded']:
            image = self.add_media(self.word, 'image', status=status)
            self.assertEqual(self.client.get(self.url('public-media', image.pk)).status_code, 404)
            self.assertEqual(self.client.get(self.url('public-entry', self.word.pk), {'picture': image.pk}).status_code, 404)
        self.assertEqual(self.client.get(self.url('public-entry', self.word.pk), {'picture': 'not-a-number'}).status_code, 404)
        Entry.objects.filter(pk=self.word.pk).update(archived=True)
        self.assertEqual(self.client.get(self.url('public-media', self.image.pk)).status_code, 404)

    def test_cross_dictionary_guessed_urls_are_rejected(self):
        other = Dictionary.objects.create(owner=self.owner, name='Other', language='Swedish', public_browsing_enabled=True)
        for name, arg in [('public-entry', self.word.pk), ('public-word', self.word.pk), ('public-media', self.image.pk)]:
            response = self.client.get(reverse('community_dictionary:' + name, args=[other.pk, arg]))
            self.assertEqual(response.status_code, 404)

    def test_range_head_and_cache_headers(self):
        url = self.url('public-media', self.audio.pk)
        with closing(self.client.get(url, HTTP_RANGE='bytes=0-9')) as response:
            self.assertEqual(response.status_code, 206)
            self.assertEqual(len(b''.join(response.streaming_content)), 10)
            self.assertIn('no-store', response['Cache-Control'])
            self.assertIn('noindex', response['X-Robots-Tag'])
            self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        with closing(self.client.head(url)) as response:
            self.assertEqual(response.status_code, 200)
            self.assertEqual(b''.join(response.streaming_content), b'')
        response = self.client.get(url, HTTP_RANGE='bytes=99999999-')
        self.assertEqual(response.status_code, 416)
        self.assertIn('no-store', response['Cache-Control'])
        response = self.client.get(self.url('public-entry', self.word.pk))
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(response['Referrer-Policy'], 'same-origin')

    def test_revocation_blocks_bookmarked_pages_and_media(self):
        url = self.url('public-media', self.image.pk)
        with closing(self.client.get(url)) as response:
            self.assertEqual(response.status_code, 200)
        self.change('disable')
        for path in [url, self.url('public-entry', self.word.pk), self.url('public-dictionary')]:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 404)
            self.assertIn('no-store', response['Cache-Control'])

    def test_withdraw_restore_and_personal_collection_urls(self):
        withdraw_all(self.member, self.dictionary.pk, 0)
        self.image.refresh_from_db(); private_id = self.image.entry.dictionary_id
        self.assertEqual(self.client.get(self.url('public-media', self.image.pk)).status_code, 404)
        self.assertEqual(self.client.get(self.url('public-word', self.word.pk)).status_code, 404)
        self.assertEqual(self.client.get(reverse('community_dictionary:public-media', args=[private_id, self.image.pk])).status_code, 404)
        restore_all(self.member, self.dictionary.pk, 1)
        self.assertContains(self.client.get(self.url('public-word', self.word.pk)), 'katt')
        with closing(self.client.get(self.url('public-media', self.image.pk))) as response:
            self.assertEqual(response.status_code, 200)

    def test_withdrawal_hold_or_departure_blocks_even_inconsistent_accepted_rows(self):
        state = Participation.objects.create(dictionary=self.dictionary, user=self.third, withdrawn=True)
        WithdrawalHold.objects.create(participation=state, contribution=self.image)
        self.assertEqual(self.client.get(self.url('public-media', self.image.pk)).status_code, 404)
        Participation.objects.create(dictionary=self.dictionary, user=self.member, withdrawn=True)
        self.assertEqual(self.client.get(self.url('public-word', self.word.pk)).status_code, 404)

    def test_synthetic_audio_must_match_current_word_language_and_meaning(self):
        self.audio.provenance = {'origin': 'synthetic', 'source_text': 'katt', 'language': 'Swedish',
                                 'source_meaning_id': self.word.current_meaning_id}
        self.audio.save()
        with closing(self.client.get(self.url('public-media', self.audio.pk))) as response:
            self.assertEqual(response.status_code, 200)
        for change in [{'source_text': 'hund'}, {'language': 'English'}, {'source_meaning_id': 999999}]:
            original = dict(self.audio.provenance)
            self.audio.provenance.update(change); self.audio.save()
            self.assertEqual(self.client.get(self.url('public-media', self.audio.pk)).status_code, 404)
            self.assertNotContains(self.client.get(self.url('public-word', self.word.pk)), self.url('public-media', self.audio.pk))
            self.audio.provenance = original

    def test_words_images_and_sentences_link_both_ways_without_draft_links(self):
        sentence = self.make_entry('Katten sover.', 'The cat sleeps.', kind='sentence')
        picture = self.add_media(sentence, 'image')
        SentenceWord.objects.create(sentence_text=sentence.current_text, word_entry=self.word,
            word_text=self.word.current_text, surface='Katten')
        ImageWordLink.objects.create(image=picture, word_entry=self.word, created_by=self.owner,
                                    sentence_text=sentence.current_text)
        response = self.client.get(self.url('public-entry', sentence.pk))
        self.assertContains(response, self.url('public-word', self.word.pk))
        self.assertContains(response, self.url('public-media', self.audio.pk))
        response = self.client.get(self.url('public-word', self.word.pk))
        self.assertContains(response, self.url('public-entry', sentence.pk))
        self.assertContains(response, self.url('public-media', picture.pk))
        sentence.current_text.status = 'pending'; sentence.current_text.save()
        self.assertNotContains(self.client.get(self.url('public-word', self.word.pk)), 'Katten sover.')

    def test_all_public_routes_are_read_only_and_never_schedule_ai(self):
        before = (Entry.objects.count(), Contribution.objects.count(), Event.objects.count())
        urls = [reverse('community_dictionary:public-home'), self.url('public-dictionary'),
                self.url('public-entry', self.word.pk), self.url('public-word', self.word.pk),
                self.url('public-media', self.image.pk)]
        with patch('django_q.tasks.async_task', side_effect=AssertionError('Visitors must never enqueue work')):
            for url in urls:
                for method in ['post', 'put', 'patch', 'delete']:
                    self.assertEqual(getattr(self.client, method)(url).status_code, 405)
                with closing(self.client.get(url)) as response:
                    self.assertEqual(response.status_code, 200)
        self.assertEqual(before, (Entry.objects.count(), Contribution.objects.count(), Event.objects.count()))

    def test_member_endpoints_stay_private_for_guests_and_signed_in_outsiders(self):
        paths = [self.url('dictionary'), self.url('entry', self.word.pk), self.url('word', self.word.pk),
                 self.url('media', self.image.pk), self.url('people'), self.url('queue'),
                 self.url('settings'), self.url('export'), self.url('practice'), self.url('new'),
                 self.url('photo-start'), self.url('capture-start')]
        for path in paths:
            self.assertEqual(self.client.get(path).status_code, 302, path)
        self.client.force_login(self.outsider)
        for path in paths:
            self.assertEqual(self.client.get(path).status_code, 404, path)
        self.assertContains(self.client.get(self.url('public-word', self.word.pk)), 'katt')

    def test_login_discovery_and_member_preview_are_clear(self):
        response = self.client.get(reverse('community_dictionary:login'))
        self.assertContains(response, 'Browse without logging in')
        response = self.owner_client.get(self.url('settings'))
        self.assertContains(response, 'Turn off public browsing')
        self.assertContains(response, 'Link to share')
        self.assertContains(self.owner_client.get(self.url('public-dictionary')), 'Member view')
        self.assertNotContains(self.client.get(self.url('public-dictionary')), 'Member view')
