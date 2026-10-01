"""Picture/word navigation reuses accepted vocabulary without copying media."""
import io
import json
import tempfile
import uuid
import zipfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core import serializers
from django.core.exceptions import ValidationError
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from community_dictionary.models import Contribution, Dictionary, Entry, Event, ImageWordLink, Membership
from community_dictionary.storage import path_for
from .test_workflow import picture, recording


class LexiconTests(TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        settings = override_settings(
            COMMUNITY_DICTIONARY_MEDIA_ROOT=Path(temporary.name) / 'private',
            MEDIA_ROOT=Path(temporary.name) / 'public',
        )
        settings.enable()
        self.addCleanup(settings.disable)
        User = get_user_model()
        self.owner = User.objects.create_user(username='owner')
        self.editor = User.objects.create_user(username='editor')
        self.member = User.objects.create_user(username='member')
        self.outsider = User.objects.create_user(username='outsider')
        self.dictionary = Dictionary.objects.create(name='Our Swedish', language='Swedish', owner=self.owner)
        Membership.objects.create(dictionary=self.dictionary, user=self.editor, role='editor', accepted=True)
        Membership.objects.create(dictionary=self.dictionary, user=self.member, accepted=True)
        self.client.force_login(self.owner)
        self.sofa = self.create_entry('soffa', 'sofa')
        self.cat = self.create_entry('katt', 'cat')
        self.sleep = self.create_entry('sova', 'sleep', photo=False)
        self.sofa_photo = self.sofa.contributions.get(kind='image')
        self.cat_photo = self.cat.contributions.get(kind='image')

    def url(self, name, *args):
        return reverse('community_dictionary:' + name, args=[self.dictionary.pk, *args])

    def create_entry(self, word, meaning='', photo=True):
        data = {'submission_id': uuid.uuid4(), 'consent': 'on', 'publish_now': 'on',
                'word': word, 'meaning': meaning, 'audio': recording()}
        if photo:
            data['photo'] = picture()
        response = self.client.post(self.url('new'), data, HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        return Entry.objects.latest('pk')

    def link(self, word=None, image=None, action='link'):
        word = word or self.cat
        image = image or self.sofa_photo
        return self.client.post(self.url('image-words', image.entry_id, image.pk),
                                {'action': action, 'word_entry': word.pk})

    def test_existing_words_automatically_have_original_pictures_and_audio(self):
        self.assertFalse(ImageWordLink.objects.exists())
        response = self.client.get(self.url('word', self.cat.pk))
        self.assertEqual(list(response.context['pictures']), [self.cat_photo])
        self.assertEqual(response.context['row']['audio'], self.cat.contributions.get(kind='audio'))
        self.assertContains(response, self.url('entry', self.cat.pk) + '?picture=' + str(self.cat_photo.pk))
        self.assertNotContains(response, '<details class="word-translation" open')
        self.assertContains(response, '<summary>Translation</summary>')
        self.assertEqual(self.client.get(self.url('dictionary')).context['mode'], 'pictures')

    def test_multiple_words_and_pictures_leave_original_material_unchanged(self):
        before = list(Contribution.objects.values_list('pk', 'file_path', 'word', 'status'))
        self.assertEqual(self.link().status_code, 302)
        self.assertEqual(self.link(self.sleep).status_code, 302)
        self.assertEqual(self.link(self.sleep, self.cat_photo).status_code, 302)
        response = self.client.get(self.url('entry', self.sofa.pk))
        self.assertEqual([r['entry'] for r in response.context['linked_words']], [self.cat, self.sleep])
        self.assertEqual(response.context['image'], self.sofa_photo)
        self.assertCountEqual(self.client.get(self.url('word', self.cat.pk)).context['pictures'], [self.sofa_photo, self.cat_photo])
        self.assertCountEqual(self.client.get(self.url('word', self.sleep.pk)).context['pictures'], [self.sofa_photo, self.cat_photo])
        self.assertEqual(before, list(Contribution.objects.values_list('pk', 'file_path', 'word', 'status')))
        self.sofa.refresh_from_db()
        self.assertEqual((self.sofa.word, self.sofa.meaning), ('soffa', 'sofa'))

    def test_retry_and_incremental_unlink_do_not_overwrite_other_links(self):
        self.link()
        self.link()
        self.link(self.sleep)
        self.assertEqual(ImageWordLink.objects.count(), 2)
        self.assertEqual(Event.objects.filter(action='link_picture_word').count(), 2)
        self.link(action='unlink')
        self.link(action='unlink')
        self.assertEqual(list(ImageWordLink.objects.values_list('word_entry_id', flat=True)), [self.sleep.pk])
        self.assertEqual(Event.objects.filter(action='unlink_picture_word').count(), 1)
        self.assertTrue(path_for(self.sofa_photo.file_path).exists())
        self.assertEqual(list(self.client.get(self.url('word', self.cat.pk)).context['pictures']), [self.cat_photo])

    def test_editor_can_link_but_members_can_only_explore(self):
        self.client.force_login(self.editor)
        self.assertEqual(self.link().status_code, 302)
        self.assertEqual(ImageWordLink.objects.get().created_by, self.editor)
        self.client.force_login(self.member)
        for action in ['link', 'unlink']:
            self.assertEqual(self.link(action=action).status_code, 404)
        response = self.client.get(self.url('entry', self.sofa.pk))
        self.assertContains(response, 'data-word-listen')
        self.assertNotContains(response, 'Link more words')
        self.assertEqual(self.client.get(self.url('word', self.cat.pk)).status_code, 200)
        audio = response.context['linked_words'][0]['audio']
        playback = self.client.get(self.url('media', audio.pk), HTTP_RANGE='bytes=0-19')
        self.assertEqual(playback.status_code, 206)
        self.assertEqual(len(b''.join(playback.streaming_content)), 20)

    def test_outsider_and_unaccepted_invitee_cannot_use_new_pages_or_links(self):
        self.link()
        self.client.force_login(self.outsider)
        for invited in [False, True]:
            if invited:
                Membership.objects.create(dictionary=self.dictionary, user=self.outsider)
            for url in [self.url('word', self.cat.pk), self.url('dictionary') + '?view=words', self.url('entry', self.sofa.pk) + '?picture=' + str(self.sofa_photo.pk)]:
                self.assertEqual(self.client.get(url).status_code, 404)
            self.assertEqual(self.link().status_code, 404)
            self.assertEqual(self.client.get(self.url('media', self.cat_photo.pk)).status_code, 404)

    def test_cross_dictionary_targets_and_images_are_rejected(self):
        other = Dictionary.objects.create(name='Private', language='Italian', owner=self.outsider)
        foreign = Entry.objects.create(dictionary=other, word='privato', created_by=self.outsider)
        foreign_photo = Contribution.objects.create(entry=foreign, kind='image', status='accepted', file_path='secret.jpg', author=self.outsider)
        self.assertEqual(self.link(foreign).status_code, 400)
        self.assertEqual(self.link(image=foreign_photo).status_code, 404)
        self.assertEqual(self.client.get(self.url('word', foreign.pk)).status_code, 404)
        self.assertEqual(self.client.get(self.url('entry', self.sofa.pk), {'picture': foreign_photo.pk}).status_code, 404)
        self.assertFalse(ImageWordLink.objects.exists())
        # Even a malformed externally imported link must not cross the boundary.
        ImageWordLink.objects.create(image=self.sofa_photo, word_entry=foreign, created_by=self.owner)
        ImageWordLink.objects.create(image=foreign_photo, word_entry=self.cat, created_by=self.owner)
        self.assertEqual(self.client.get(self.url('entry', self.sofa.pk)).context['linked_words'], [])
        self.assertEqual(list(self.client.get(self.url('word', self.cat.pk)).context['pictures']), [self.cat_photo])
        self.assertNotContains(self.client.get(self.url('dictionary'), {'view': 'words'}), 'privato')

    def test_menu_excludes_primary_existing_links_and_unaccepted_words(self):
        self.link()
        pending = Entry.objects.create(dictionary=self.dictionary, created_by=self.member)
        Contribution.objects.create(entry=pending, author=self.member, kind='text', word='hidden proposal')
        response = self.client.get(self.url('entry', self.sofa.pk))
        self.assertEqual(list(response.context['link_form'].fields['word_entry'].queryset), [self.sleep])
        self.assertEqual(self.link(self.sofa).status_code, 400)
        self.assertEqual(self.link(pending).status_code, 400)
        self.assertEqual(self.client.get(self.url('word', pending.pk)).status_code, 404)
        self.assertNotContains(self.client.get(self.url('dictionary'), {'view': 'words'}), 'hidden proposal')

    def test_only_accepted_nonempty_image_contributions_can_receive_links(self):
        for kind, status, file_path in [('audio', 'accepted', 'voice.wav'), ('image', 'pending', 'test.jpg'), ('image', 'rejected', 'test.jpg'), ('image', 'removed', ''), ('image', 'accepted', '')]:
            with self.subTest(kind=kind, status=status, path=file_path):
                image = Contribution.objects.create(entry=self.sofa, author=self.owner, kind=kind, status=status, file_path=file_path)
                self.assertEqual(self.link(image=image).status_code, 404)
        self.assertFalse(ImageWordLink.objects.exists())

    def test_model_validation_and_unique_constraint_describe_link_boundaries(self):
        link = ImageWordLink(image=self.sofa_photo, word_entry=self.cat, created_by=self.owner)
        link.full_clean()
        link.save()
        with self.assertRaises(ValidationError):
            ImageWordLink(image=self.sofa_photo, word_entry=self.cat, created_by=self.owner).full_clean()
        with self.assertRaises(ValidationError):
            ImageWordLink(image=self.sofa_photo, word_entry=self.sofa, created_by=self.owner).full_clean()

    def test_alternate_picture_links_survive_main_picture_selection(self):
        self.client.post(self.url('contribute', self.sofa.pk), {'submission_id': uuid.uuid4(), 'photo': picture(), 'consent': 'on', 'publish_now': 'on'})
        second = self.sofa.contributions.filter(kind='image').latest('pk')
        self.link(image=second)
        self.client.post(self.url('review', self.sofa_photo.pk), {'action': 'select'})
        self.assertEqual(self.client.get(self.url('entry', self.sofa.pk)).context['linked_words'], [])
        response = self.client.get(self.url('entry', self.sofa.pk), {'picture': second.pk})
        self.assertEqual(response.context['image'], second)
        self.assertEqual(response.context['linked_words'][0]['entry'], self.cat)
        self.assertCountEqual(self.client.get(self.url('word', self.sofa.pk)).context['pictures'], [self.sofa_photo, second])
        for invalid in [self.cat_photo.pk, 'abc', 0, -1, str(2**99)]:
            self.assertEqual(self.client.get(self.url('entry', self.sofa.pk), {'picture': invalid}).status_code, 404)

    def test_word_updates_are_shared_and_outdated_tts_is_not_offered(self):
        self.link()
        old_audio = self.cat.contributions.get(kind='audio')
        old_audio.provenance = {'origin': 'synthetic', 'source_text': 'katt', 'language': 'Swedish'}
        old_audio.save()
        self.client.post(self.url('contribute', self.cat.pk), {
            'submission_id': uuid.uuid4(), 'edit_text': 'on', 'word': 'en katt', 'meaning': 'a cat',
            'base_version': self.cat.text_version, 'publish_now': 'on',
        })
        response = self.client.get(self.url('entry', self.sofa.pk))
        row = response.context['linked_words'][0]
        self.assertEqual((row['entry'].word, row['entry'].meaning), ('en katt', 'a cat'))
        self.assertIsNone(row['audio'])
        self.assertEqual(self.client.get(self.url('word', self.cat.pk)).context['word_audio'], [])
        # Pending and wrong-language TTS are also excluded; human audio remains.
        Contribution.objects.create(entry=self.cat, author=self.owner, kind='audio', status='pending', file_path='pending.wav')
        Contribution.objects.create(entry=self.cat, author=self.owner, kind='audio', status='accepted', file_path='wrong.wav', provenance={'origin': 'synthetic', 'source_text': 'en katt', 'language': 'Italian'})
        self.assertIsNone(self.client.get(self.url('word', self.cat.pk)).context['row']['audio'])
        self.client.post(self.url('contribute', self.cat.pk), {'submission_id': uuid.uuid4(), 'audio': recording(), 'consent': 'on', 'publish_now': 'on'})
        newest = self.cat.contributions.filter(kind='audio').latest('pk')
        self.assertEqual(self.client.get(self.url('entry', self.sofa.pk)).context['linked_words'][0]['audio'], newest)

    def test_search_finds_linked_words_and_translations_in_picture_mode(self):
        self.link()
        for query in ['katt', 'cat']:
            response = self.client.get(self.url('dictionary'), {'q': query})
            self.assertCountEqual([c['entry'] for c in response.context['cards']], [self.cat, self.sofa])
            response = self.client.get(self.url('dictionary'), {'view': 'words', 'q': query})
            self.assertEqual([r['entry'] for r in response.context['words']], [self.cat])
        self.assertContains(response, 'view=pictures&amp;q=cat')

    def test_word_pagination_preserves_mode_and_does_not_merge_homographs(self):
        self.create_entry('katt', 'different use', photo=False)
        for number in range(26):
            Entry.objects.create(dictionary=self.dictionary, created_by=self.owner, word=f'test {number:02}', category='Test')
        response = self.client.get(self.url('dictionary'), {'view': 'words', 'q': 'katt'})
        self.assertEqual(len(response.context['words']), 2)
        self.assertEqual({r['entry'].meaning for r in response.context['words']}, {'cat', 'different use'})
        response = self.client.get(self.url('dictionary'), {'view': 'words', 'q': 'test', 'category': 'Test'})
        self.assertEqual(len(response.context['words']), 24)
        self.assertContains(response, 'view=words&amp;show=accepted&amp;q=test&amp;category=Test&amp;page=2')
        response = self.client.get(self.url('dictionary'), {'view': 'words', 'q': 'test', 'category': 'Test', 'page': 2})
        self.assertEqual(len(response.context['words']), 2)

    def test_image_removal_deletes_links_but_keeps_words(self):
        self.link()
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(self.url('review', self.sofa_photo.pk), {'action': 'remove'})
        self.assertFalse(ImageWordLink.objects.exists())
        self.assertTrue(Entry.objects.filter(pk=self.cat.pk).exists())
        self.assertFalse(path_for(self.sofa_photo.file_path).exists())
        self.assertEqual(list(self.client.get(self.url('word', self.cat.pk)).context['pictures']), [self.cat_photo])
        self.assertEqual(self.client.get(self.url('entry', self.sofa.pk), {'picture': self.sofa_photo.pk}).status_code, 404)

    def test_word_entry_deletion_does_not_delete_associated_foreign_entry_picture(self):
        self.link()
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(self.url('remove-entry', self.cat.pk))
        self.assertFalse(ImageWordLink.objects.exists())
        self.assertTrue(path_for(self.sofa_photo.file_path).exists())
        self.assertEqual(self.client.get(self.url('entry', self.sofa.pk)).status_code, 200)

    def test_removing_accepted_wording_hides_links_until_wording_is_restored(self):
        self.link()
        self.client.post(self.url('review', self.cat.current_text_id), {'action': 'remove'})
        self.assertEqual(self.client.get(self.url('entry', self.sofa.pk)).context['linked_words'], [])
        self.assertEqual(self.client.get(self.url('word', self.cat.pk)).status_code, 404)
        self.assertEqual(ImageWordLink.objects.count(), 1)

    def test_export_restore_preserves_link_attribution_without_duplicate_media(self):
        self.client.force_login(self.editor)
        self.link()
        self.client.force_login(self.owner)
        response = self.client.get(self.url('export'))
        with zipfile.ZipFile(io.BytesIO(b''.join(response.streaming_content))) as archive:
            self.assertEqual(json.loads(archive.read('manifest.json'))['version'], 2)
            records = archive.read('records.json').decode()
            self.assertIn('community_dictionary.imagewordlink', records)
            self.assertEqual(len([p for p in archive.namelist() if p.startswith('media/')]), Contribution.objects.exclude(file_path='').count())
        self.dictionary.delete()
        for record in serializers.deserialize('json', records):
            record.save()
        self.dictionary = Dictionary.objects.get(name='Our Swedish')
        restored = ImageWordLink.objects.get()
        self.assertEqual((restored.image_id, restored.word_entry_id, restored.created_by_id), (self.sofa_photo.pk, self.cat.pk, self.editor.pk))
        self.assertCountEqual(self.client.get(self.url('word', self.cat.pk)).context['pictures'], [self.cat_photo, self.sofa_photo])

    def test_link_mutations_require_post_and_csrf(self):
        url = self.url('image-words', self.sofa.pk, self.sofa_photo.pk)
        self.assertEqual(self.client.get(url).status_code, 405)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(client.post(url, {'action': 'link', 'word_entry': self.cat.pk}).status_code, 403)
        self.assertFalse(ImageWordLink.objects.exists())
