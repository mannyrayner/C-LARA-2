"""Existing-entry pronunciation, review boundaries and direct dictionary logout."""
import tempfile
import uuid
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from community_dictionary.models import Contribution, Dictionary, Entry, Membership
from .test_workflow import picture, recording


class RecordAndLogoutTests(TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        settings = override_settings(COMMUNITY_DICTIONARY_MEDIA_ROOT=Path(temporary.name))
        settings.enable()
        self.addCleanup(settings.disable)
        User = get_user_model()
        self.owner = User.objects.create_user('owner', password='local-test-only')
        self.member = User.objects.create_user('member', password='local-test-only')
        self.outsider = User.objects.create_user('outsider', password='local-test-only')
        self.dictionary = Dictionary.objects.create(owner=self.owner, name='Our Swedish', language='Swedish', explanation_language='English')
        Membership.objects.create(dictionary=self.dictionary, user=self.member, accepted=True)
        self.entry = Entry.objects.create(dictionary=self.dictionary, created_by=self.member, word='katt', meaning='cat')
        self.record_url = reverse('community_dictionary:record-audio', args=[self.dictionary.pk, self.entry.pk])
        self.entry_url = reverse('community_dictionary:entry', args=[self.dictionary.pk, self.entry.pk])
        self.logout_url = reverse('community_dictionary:logout')
        self.login_url = reverse('community_dictionary:login')

    def post_audio(self, **extra):
        return self.client.post(self.record_url, {
            'submission_id': str(uuid.uuid4()), 'audio': recording(), 'consent': 'on', **extra,
        }, HTTP_ACCEPT='application/json')

    def test_editor_saves_entry_audio_and_retry_does_not_duplicate_or_change_words(self):
        self.client.force_login(self.owner)
        token = str(uuid.uuid4())
        for _ in range(2):
            response = self.post_audio(submission_id=token, publish_now='on', word='unwanted', meaning='overwrite', edit_text='on')
            self.assertEqual(response.status_code, 200, response.content)
            self.assertTrue(response.json()['saved'])
            self.assertEqual(response.json()['url'], self.entry_url)
        audio = Contribution.objects.get()
        self.assertEqual((audio.kind, audio.status, audio.author), ('audio', 'accepted', self.owner))
        self.entry.refresh_from_db()
        self.assertEqual((self.entry.word, self.entry.meaning), ('katt', 'cat'))
        response = self.client.get(self.entry_url)
        self.assertEqual(list(response.context['audio']), [audio])
        self.assertEqual(list(response.context['notes']), [])

    def test_member_audio_awaits_review_even_if_publish_is_forged(self):
        self.client.force_login(self.member)
        self.assertEqual(self.post_audio(publish_now='on').status_code, 200)
        audio = Contribution.objects.get()
        self.assertEqual(audio.status, 'pending')
        self.assertEqual(list(self.client.get(self.entry_url).context['audio']), [])
        self.client.force_login(self.owner)
        response = self.client.post(reverse('community_dictionary:review', args=[self.dictionary.pk, audio.pk]), {'action': 'accept'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(list(self.client.get(self.entry_url).context['audio']), [audio])

    def test_audio_is_required_and_permission_is_still_required(self):
        self.client.force_login(self.owner)
        response = self.post_audio(consent='')
        self.assertEqual(response.status_code, 400)
        self.assertIn('Confirm permission', response.json()['error'])
        response = self.client.post(self.record_url, {
            'submission_id': str(uuid.uuid4()), 'photo': picture(), 'word': 'katt', 'consent': 'on',
        }, HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('Record or choose an audio file', response.json()['error'])
        self.assertFalse(Contribution.objects.exists())

    def test_private_dictionary_membership_is_required_for_get_and_post(self):
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(self.record_url).status_code, 404)
        self.assertEqual(self.post_audio().status_code, 404)
        self.client.force_login(self.member)
        Membership.objects.filter(user=self.member).update(accepted=False)
        self.assertEqual(self.client.get(self.record_url).status_code, 404)
        self.assertFalse(Contribution.objects.exists())

    def test_recording_and_comment_controls_have_distinct_destinations(self):
        self.client.force_login(self.owner)
        response = self.client.get(self.entry_url)
        self.assertContains(response, self.record_url)
        self.assertContains(response, 'Record a spoken comment')
        self.assertContains(response, 'Save comment')
        response = self.client.get(self.record_url)
        self.assertContains(response, '>Save audio</button>', count=2)
        self.assertNotContains(response, 'name="photo"')
        self.assertNotContains(response, 'name="word"')
        response = self.client.post(reverse('community_dictionary:comment', args=[self.dictionary.pk, self.entry.pk]), {
            'submission_id': str(uuid.uuid4()), 'audio': recording(), 'consent': 'on',
        })
        self.assertRedirects(response, self.entry_url)
        self.assertEqual(Contribution.objects.get().kind, 'note')

    def test_logout_is_post_and_csrf_protected_and_ends_the_shared_session(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(client.get(self.logout_url).status_code, 405)
        self.assertEqual(client.post(self.logout_url).status_code, 403)
        self.assertEqual(client.get(self.entry_url).status_code, 200)
        response = client.post(self.logout_url, {'csrfmiddlewaretoken': client.cookies['csrftoken'].value})
        self.assertRedirects(response, self.login_url)
        self.assertNotIn('_auth_user_id', client.session)
        self.assertEqual(client.get(self.entry_url).status_code, 302)
        self.assertEqual(client.get(reverse('profile')).status_code, 302)

    def test_dictionary_login_returns_to_dictionary_and_rejects_external_redirects(self):
        response = self.client.get(self.login_url)
        self.assertContains(response, 'Community dictionaries')
        self.assertNotContains(response, '>Logout</button>')
        response = self.client.post(self.login_url, {'username': 'owner', 'password': 'local-test-only', 'next': 'https://example.invalid/'})
        self.assertRedirects(response, reverse('community_dictionary:home'))
        self.assertContains(self.client.get(self.entry_url), self.logout_url)
