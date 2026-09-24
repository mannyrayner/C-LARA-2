import io
import json
import tempfile
import uuid
import wave
import zipfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import serializers
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from community_dictionary.checks import private_media_location
from community_dictionary.models import Contribution, Dictionary, Entry, Event, Membership, Partner, Partnership, Request, Submission
from community_dictionary.services import Conflict, accept
from community_dictionary.storage import path_for


def picture():
    stream = io.BytesIO()
    Image.new('RGB', (40, 30), 'green').save(stream, 'PNG')
    return SimpleUploadedFile('camera.png', stream.getvalue(), content_type='image/png')


def recording():
    stream = io.BytesIO()
    with wave.open(stream, 'wb') as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(8000)
        audio.writeframes(b'\0\0' * 800)
    return SimpleUploadedFile('voice.wav', stream.getvalue(), content_type='audio/wav')


class WorkflowTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.settings_override = override_settings(
            COMMUNITY_DICTIONARY_MEDIA_ROOT=Path(self.temp.name) / 'private',
            MEDIA_ROOT=Path(self.temp.name) / 'public',
            PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        User = get_user_model()
        self.owner = User.objects.create_user(username='owner', password='test-only')
        self.member = User.objects.create_user(username='member', password='test-only')
        self.third = User.objects.create_user(username='third', password='test-only')
        self.outsider = User.objects.create_user(username='outsider', password='test-only')
        self.dictionary = Dictionary.objects.create(name='Everyday Swedish', language='Swedish', owner=self.owner)
        Membership.objects.create(dictionary=self.dictionary, user=self.member, accepted=True)
        Membership.objects.create(dictionary=self.dictionary, user=self.third, accepted=True)
        self.group = Partnership.objects.create(dictionary=self.dictionary, name='Our words', created_by=self.owner)
        for user in [self.owner, self.member, self.third]:
            Partner.objects.create(partnership=self.group, user=user, accepted=True)
        self.client.force_login(self.member)

    def url(self, name, *args):
        return reverse('community_dictionary:' + name, args=[self.dictionary.pk, *args])

    def post(self, name, data=None, *args, token=None):
        data = {'submission_id': token or str(uuid.uuid4()), **(data or {})}
        return self.client.post(self.url(name, *args), data, HTTP_ACCEPT='application/json')

    def create_entry(self, **values):
        response = self.post('new', {'consent': 'on', 'photo': picture(), **values})
        self.assertEqual(response.status_code, 200, response.content)
        return Entry.objects.latest('pk')

    def make_request(self, entry, kind='audio'):
        response = self.post('ask', {'kind': kind, 'partnership': self.group.pk, 'note': 'What do we call this?'}, entry.pk)
        self.assertEqual(response.status_code, 200, response.content)
        return Request.objects.latest('pk')

    def test_photo_request_record_discuss_review_without_ai(self):
        with patch('projects.views._build_ai_client', side_effect=AssertionError('No AI in this app')):
            entry = self.create_entry()
            self.assertEqual(entry.word, '')
            photo = entry.contributions.get(kind='image')
            self.assertEqual(photo.status, 'pending')
            req = self.make_request(entry)
            self.client.force_login(self.third)
            self.assertContains(self.client.get(self.url('queue')), 'Needs recording')
            response = self.post('respond', {'audio': recording(), 'consent': 'on', 'label': 'My pronunciation'}, req.pk)
            self.assertEqual(response.status_code, 200, response.content)
            req.refresh_from_db()
            self.assertEqual(req.progress, 'awaiting')
            audio = req.responses.get(kind='audio')
            self.assertEqual(audio.author, self.third)
            self.assertEqual(Entry.objects.count(), 1)
            self.assertEqual(self.post('comment', {'body': 'This is the word we use.'}, entry.pk).status_code, 200)
            self.client.force_login(self.owner)
            self.assertEqual(self.client.post(self.url('review', audio.pk), {'action': 'accept'}).status_code, 302)
            self.client.post(self.url('review', photo.pk), {'action': 'accept'})
            req.refresh_from_db()
            self.assertEqual(req.progress, 'complete')
            self.assertNotContains(self.client.get(self.url('queue')), 'My pronunciation')
            self.assertContains(self.client.get(self.url('entry', entry.pk)), 'This is the word we use.')
            self.assertContains(self.client.get(self.url('dictionary')), 'Entry ' + str(entry.pk))

    def test_audio_first_and_spoken_request_and_comment(self):
        result = self.post('new', {'audio': recording(), 'consent': 'on'})
        self.assertEqual(result.status_code, 200)
        entry = Entry.objects.latest('pk')
        result = self.post('ask', {'partnership': self.group.pk, 'kind': 'image', 'audio': recording(), 'consent': 'on'}, entry.pk)
        self.assertEqual(result.status_code, 200)
        req = Request.objects.latest('pk')
        self.assertEqual(req.responses.get(kind='note').mime_type, 'audio/wav')
        self.client.force_login(self.third)
        self.assertEqual(self.post('respond', {'photo': picture(), 'consent': 'on'}, req.pk).status_code, 200)
        self.assertEqual(self.post('comment', {'audio': recording(), 'consent': 'on'}, entry.pk).status_code, 200)
        self.assertEqual(entry.contributions.filter(kind='note').count(), 2)

    def test_retry_creates_one_entry_and_one_media_file(self):
        token = str(uuid.uuid4())
        for _ in range(2):
            response = self.post('new', {'photo': picture(), 'consent': 'on'}, token=token)
            self.assertEqual(response.status_code, 200)
        self.assertEqual(Entry.objects.count(), 1)
        self.assertEqual(Contribution.objects.count(), 1)
        self.assertEqual(Submission.objects.count(), 1)
        self.assertEqual(len(list((Path(self.temp.name) / 'private').rglob('*.jpg'))), 1)
        response = self.post('new', {'photo': picture(), 'consent': 'on', 'word': 'changed'}, token=token)
        self.assertEqual(response.status_code, 409)

    def test_retry_after_immediate_acceptance_completes_only_once(self):
        entry = self.create_entry()
        req = self.make_request(entry)
        self.client.force_login(self.owner)
        token = str(uuid.uuid4())
        for _ in range(2):
            response = self.post('respond', {'audio': recording(), 'consent': 'on', 'publish_now': 'on'}, req.pk, token=token)
            self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(req.responses.filter(kind='audio').count(), 1)

    def test_failed_transaction_leaves_no_entry_receipt_or_file(self):
        with patch('community_dictionary.services.event', side_effect=RuntimeError('Simulated failure')):
            with self.assertRaises(RuntimeError):
                self.post('new', {'photo': picture(), 'consent': 'on'})
        self.assertFalse(Entry.objects.exists())
        self.assertFalse(Submission.objects.exists())
        self.assertEqual(list((Path(self.temp.name) / 'private').rglob('*.jpg')), [])

    def test_multiple_replies_remain_separate_and_rejection_reopens(self):
        entry = self.create_entry()
        req = self.make_request(entry)
        for user in [self.member, self.third]:
            self.client.force_login(user)
            self.post('respond', {'audio': recording(), 'consent': 'on'}, req.pk)
        self.assertEqual(req.responses.count(), 2)
        self.client.force_login(self.owner)
        for reply in req.responses.all():
            self.client.post(self.url('review', reply.pk), {'action': 'reject', 'reason': 'Please try once more.'})
        req.refresh_from_db()
        self.assertEqual(req.progress, 'open')
        self.assertEqual(Event.objects.filter(action='reject').count(), 2)

    def test_wording_conflict_and_restore_preserve_history(self):
        self.client.force_login(self.owner)
        entry = self.create_entry(word='katt', publish_now='on')
        original = entry.current_text
        for word in ['katten', 'en katt']:
            self.post('contribute', {'edit_text': 'on', 'word': word, 'base_version': 1}, entry.pk)
        proposals = list(entry.contributions.filter(kind='text', status='pending').order_by('pk'))
        accept(proposals[0], self.owner)
        with self.assertRaises(Conflict):
            accept(proposals[1], self.owner)
        entry.refresh_from_db()
        self.assertEqual(entry.word, 'katten')
        self.assertEqual(entry.text_version, 2)
        result = self.client.post(self.url('review', original.pk), {'action': 'restore', 'version': 2})
        self.assertEqual(result.status_code, 302)
        entry.refresh_from_db()
        self.assertEqual(entry.word, 'katt')
        self.assertEqual(entry.text_version, 3)
        self.assertEqual(entry.contributions.filter(kind='text').count(), 4)
        stale = self.client.post(self.url('review', original.pk), {'action': 'restore', 'version': 2})
        self.assertEqual(stale.status_code, 409)

    def test_member_cannot_publish_review_or_export(self):
        entry = self.create_entry(publish_now='on')
        media = entry.contributions.get()
        self.assertEqual(media.status, 'pending')
        self.assertEqual(self.client.post(self.url('review', media.pk), {'action': 'accept'}).status_code, 404)
        self.assertEqual(self.client.get(self.url('export')).status_code, 404)
        self.assertEqual(self.client.post(self.url('remove-entry', entry.pk)).status_code, 404)

    def test_add_words_to_media_entry_then_find_in_either_language(self):
        self.client.force_login(self.owner)
        entry = self.create_entry(audio=recording(), publish_now='on')
        media = list(entry.contributions.values_list('pk', 'file_path', 'status'))
        self.assertContains(self.client.get(self.url('entry', entry.pk)), 'Add words')
        edit_url = self.url('contribute', entry.pk) + '?wording=1'
        self.assertContains(self.client.get(edit_url), 'Word or phrase in Swedish')
        result = self.post('contribute', {
            'edit_text': 'on', 'base_version': 0, 'word': 'katt',
            'meaning': 'cat', 'category': 'Animals', 'publish_now': 'on',
        }, entry.pk)
        self.assertEqual(result.status_code, 200, result.content)
        entry.refresh_from_db()
        self.assertEqual((entry.word, entry.meaning, entry.category), ('katt', 'cat', 'Animals'))
        for query in ['katt', 'cat']:
            result = self.client.get(self.url('dictionary'), {'q': query, 'category': 'Animals'})
            self.assertEqual([card['entry'].pk for card in result.context['cards']], [entry.pk])
        self.assertEqual(list(entry.contributions.exclude(kind='text').values_list('pk', 'file_path', 'status')), media)
        self.assertContains(self.client.get(self.url('entry', entry.pk)), 'Edit words')
        # A member's revision still requires review and must not erase accepted text or media.
        self.client.force_login(self.member)
        result = self.post('contribute', {
            'edit_text': 'on', 'base_version': 1, 'word': 'katten', 'meaning': 'the cat',
        }, entry.pk)
        self.assertEqual(result.status_code, 200)
        entry.refresh_from_db()
        self.assertEqual(entry.word, 'katt')
        self.assertEqual(entry.contributions.get(kind='text', status='pending').word, 'katten')

    def test_outsider_and_pending_invitation_cannot_access_any_content(self):
        entry = self.create_entry()
        media = entry.contributions.get()
        req = self.make_request(entry)
        self.client.force_login(self.outsider)
        Membership.objects.create(dictionary=self.dictionary, user=self.outsider, accepted=False)
        for name, args in [('dictionary', []), ('entry', [entry.pk]), ('media', [media.pk]), ('people', []), ('queue', []), ('export', []), ('respond', [req.pk])]:
            self.assertEqual(self.client.get(self.url(name, *args)).status_code, 404, name)
        self.assertEqual(self.post('new', {'word': 'wrong'}).status_code, 404)
        self.assertEqual(self.post('comment', {'body': 'wrong'}, entry.pk).status_code, 404)
        self.assertEqual(self.client.post(self.url('join')).status_code, 302)
        self.assertEqual(self.client.get(self.url('entry', entry.pk)).status_code, 200)
        self.assertEqual(self.client.get(self.url('respond', req.pk)).status_code, 404)

    def test_cross_dictionary_ids_do_not_grant_access(self):
        other = Dictionary.objects.create(name='Private', language='Icelandic', owner=self.outsider)
        entry = Entry.objects.create(dictionary=other, created_by=self.outsider)
        self.assertEqual(self.client.get(self.url('entry', entry.pk)).status_code, 404)
        self.assertEqual(self.post('comment', {'body': 'injected'}, entry.pk).status_code, 404)

    def test_partnership_invite_accept_third_partner_and_revoke(self):
        self.client.force_login(self.owner)
        Partner.objects.filter(partnership=self.group, user=self.third).delete()
        result = self.client.post(self.url('people'), {'action': 'invite_partner', 'group_id': self.group.pk, 'username': 'third'})
        self.assertEqual(result.status_code, 302)
        membership = Partner.objects.get(partnership=self.group, user=self.third)
        self.assertFalse(membership.accepted)
        self.client.force_login(self.third)
        self.assertEqual(self.client.post(self.url('people'), {'action': 'join_group', 'partner_id': membership.pk}).status_code, 302)
        membership.refresh_from_db()
        self.assertTrue(membership.accepted)
        self.assertEqual(Membership.objects.get(dictionary=self.dictionary, user=self.third).role, 'member')
        self.client.force_login(self.owner)
        self.client.post(self.url('people'), {'action': 'remove_member', 'member_id': Membership.objects.get(dictionary=self.dictionary, user=self.third).pk})
        self.assertFalse(Partner.objects.filter(partnership=self.group, user=self.third).exists())
        self.client.force_login(self.third)
        self.assertEqual(self.client.get(self.url('dictionary')).status_code, 404)

    def test_group_creation_rejects_people_outside_dictionary(self):
        response = self.client.post(self.url('people'), {'action': 'create_group', 'name': 'Wrong group', 'partners': [self.outsider.pk]})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Partnership.objects.count(), 1)
        response = self.client.post(self.url('people'), {'action': 'create_group', 'name': 'Another group', 'partners': [self.owner.pk, self.third.pk]})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Partnership.objects.get(name='Another group').partners.count(), 3)

    def test_media_serves_ranges_and_rejects_invalid_ranges(self):
        self.post('new', {'audio': recording(), 'consent': 'on'})
        audio = Contribution.objects.get(kind='audio')
        response = self.client.get(self.url('media', audio.pk), HTTP_RANGE='bytes=0-19')
        self.assertEqual(response.status_code, 206)
        self.assertEqual(len(b''.join(response.streaming_content)), 20)
        self.assertEqual(response['Cache-Control'], 'private, no-store')
        suffix = self.client.get(self.url('media', audio.pk), HTTP_RANGE='bytes=-10')
        self.assertEqual(len(b''.join(suffix.streaming_content)), 10)
        self.assertEqual(self.client.get(self.url('media', audio.pk), HTTP_RANGE='bytes=999999-').status_code, 416)

    def test_unsafe_upload_and_missing_consent_are_rejected(self):
        fake = SimpleUploadedFile('voice.wav', b'<script>alert(1)</script>', content_type='audio/wav')
        self.assertEqual(self.post('new', {'audio': fake, 'consent': 'on'}).status_code, 400)
        self.assertEqual(self.post('new', {'photo': picture()}).status_code, 400)
        self.assertFalse(Entry.objects.exists())

    def test_removal_deletes_media_and_reopens_request(self):
        entry = self.create_entry()
        req = self.make_request(entry)
        self.client.force_login(self.owner)
        self.post('respond', {'audio': recording(), 'consent': 'on', 'publish_now': 'on'}, req.pk)
        audio = req.responses.get(kind='audio')
        path = path_for(audio.file_path)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(self.url('review', audio.pk), {'action': 'remove'})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(path.exists())
        self.assertEqual(self.client.get(self.url('media', audio.pk)).status_code, 404)
        req.refresh_from_db()
        self.assertEqual(req.progress, 'open')

    def test_export_and_fixture_restore_preserve_attribution_and_media(self):
        entry = self.create_entry()
        self.make_request(entry)
        self.client.force_login(self.owner)
        self.client.post(self.url('review', entry.contributions.get().pk), {'action': 'accept'})
        response = self.client.get(self.url('export'))
        data = b''.join(response.streaming_content)
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            manifest = json.loads(archive.read('manifest.json'))
            self.assertEqual(manifest['users'][1]['username'], 'member')
            records = archive.read('records.json').decode()
            self.assertIn('community_dictionary.request', records)
            media = {name.removeprefix('media/'): archive.read(name) for name in archive.namelist() if name.startswith('media/')}
        # A database fixture and private-media backup restore the same records,
        # when user accounts with the original IDs are retained.
        counts = (Entry.objects.count(), Contribution.objects.count(), Request.objects.count())
        Dictionary.objects.all().delete()
        for item in serializers.deserialize('json', records):
            item.save()
        self.assertEqual((Entry.objects.count(), Contribution.objects.count(), Request.objects.count()), counts)
        restored = Contribution.objects.get(kind='image')
        self.assertEqual(restored.author.username, 'member')
        for name, payload in media.items():
            path_for(name).unlink(missing_ok=True)
            path_for(name).write_bytes(payload)
        self.assertEqual(path_for(restored.file_path).read_bytes(), media[restored.file_path])

    def test_pages_render_attributed_user_content_safely(self):
        entry = self.create_entry(word='<script>bad()</script>')
        for name, args in [('dictionary', []), ('entry', [entry.pk]), ('people', []), ('queue', []), ('new', []), ('ask', [entry.pk])]:
            response = self.client.get(self.url(name, *args))
            self.assertEqual(response.status_code, 200, name)
            self.assertEqual(response['Cache-Control'], 'private, no-store')
            self.assertNotContains(response, '<script>bad()</script>')
        self.assertContains(self.client.get(self.url('entry', entry.pk)), '&lt;script&gt;bad()&lt;/script&gt;')

    def test_csrf_is_required_and_private_storage_cannot_be_public(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.member)
        self.assertEqual(client.post(self.url('new'), {'word': 'injected'}).status_code, 403)
        with override_settings(COMMUNITY_DICTIONARY_MEDIA_ROOT=Path(self.temp.name) / 'public' / 'unsafe'):
            self.assertEqual(private_media_location(None)[0].id, 'community_dictionary.E001')

    def test_only_owner_can_change_dictionary_settings(self):
        settings = {'action': 'settings', 'name': 'Our Swedish', 'language': 'Swedish', 'text_direction': 'auto'}
        self.assertEqual(self.client.post(self.url('people'), settings).status_code, 404)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(self.url('people'), settings).status_code, 302)
        self.dictionary.refresh_from_db()
        self.assertEqual(self.dictionary.name, 'Our Swedish')

    def test_withdrawn_wording_is_hidden_and_removal_erases_content(self):
        entry = self.create_entry(word='A private withdrawn proposal')
        proposal = entry.contributions.get(kind='text')
        self.client.post(self.url('review', proposal.pk), {'action': 'withdraw'})
        self.client.force_login(self.third)
        self.assertNotContains(self.client.get(self.url('entry', entry.pk)), proposal.word)
        self.client.force_login(self.owner)
        self.client.post(self.url('review', proposal.pk), {'action': 'remove'})
        proposal.refresh_from_db()
        self.assertEqual(proposal.word, '')
        self.assertEqual(proposal.status, 'removed')
