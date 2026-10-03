from datetime import timedelta
import uuid

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from community_dictionary.models import Dictionary, Entry, ImageStudy, Membership, Participation
from . import test_workflow as workflow
from .test_workflow import picture


class SettingsAndPictureTests(TestCase):
    setUp = workflow.WorkflowTests.setUp
    url = workflow.WorkflowTests.url
    post = workflow.WorkflowTests.post

    def settings_data(self, enabled=True):
        return {'name': 'Our Swedish', 'language': 'Swedish', 'explanation_language': 'English',
            'text_direction': 'auto', 'image_generation_enabled': 'on' if enabled else ''}

    def text_entry(self):
        self.client.force_login(self.owner)
        response = self.post('new', {'word': 'tekanna', 'meaning': 'teapot', 'category': 'Home',
            'consent': 'on', 'publish_now': 'on'})
        self.assertEqual(response.status_code, 200)
        return Entry.objects.latest('pk')

    def test_settings_tab_groups_controls_and_people_keeps_memberships(self):
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(self.url('dictionary')), self.url('settings'))
        people = self.client.get(self.url('people'))
        self.assertContains(people, 'Dictionary members')
        self.assertNotContains(people, 'Set up or view image style')
        self.assertNotContains(people, 'Save settings')
        self.assertEqual(self.client.post(self.url('settings'), self.settings_data()).status_code, 302)
        page = self.client.get(self.url('settings'))
        self.assertContains(page, 'Save settings')
        self.assertContains(page, self.url('image-style'))
        self.dictionary.refresh_from_db()
        self.assertTrue(self.dictionary.image_generation_enabled)
        self.assertEqual(self.dictionary.image_generation_revision, 1)

    def test_owner_only_saves_and_editor_only_style_controls(self):
        self.dictionary.image_generation_enabled = True; self.dictionary.save()
        for role in ['member', 'editor', 'coordinator']:
            with self.subTest(role=role):
                Membership.objects.filter(dictionary=self.dictionary, user=self.member).update(role=role)
                self.client.force_login(self.member)
                page = self.client.get(self.url('settings'))
                self.assertEqual(page.status_code, 404 if role == 'member' else 200)
                if role != 'member':
                    self.assertContains(page, self.url('image-style'))
                    self.assertNotContains(page, 'Save settings')
                self.assertEqual(self.client.post(self.url('settings'), self.settings_data(False)).status_code, 404)
        self.dictionary.refresh_from_db()
        self.assertTrue(self.dictionary.image_generation_enabled)

    def test_disable_generation_cancels_previews_and_legacy_settings_post_works(self):
        self.client.force_login(self.owner)
        self.dictionary.image_generation_enabled = True; self.dictionary.save()
        study = ImageStudy.objects.create(dictionary=self.dictionary, user=self.owner, kind='style',
            status='ready', subject='Teapot', prompt='Private prompt', expires_at=timezone.now()+timedelta(days=1))
        response = self.client.post(self.url('settings'), self.settings_data(False))
        self.assertRedirects(response, self.url('settings'))
        study.refresh_from_db(); self.assertEqual(study.status, 'discarded'); self.assertEqual(study.prompt, '')
        response = self.client.post(self.url('people'), {'action': 'settings', **self.settings_data(True)})
        self.assertRedirects(response, self.url('settings'))
        self.dictionary.refresh_from_db(); self.assertEqual(self.dictionary.image_generation_revision, 2)

    def test_invalid_settings_stay_visible_and_do_not_mutate_dictionary(self):
        self.client.force_login(self.owner)
        response = self.client.post(self.url('settings'), {**self.settings_data(), 'name': ''})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['settings_form'].errors)
        self.assertNotContains(response, self.url('image-style'))
        self.dictionary.refresh_from_db()
        self.assertFalse(self.dictionary.image_generation_enabled)

    def test_text_first_photo_with_ai_on_or_off_preserves_text_and_retry_receipt(self):
        entry = self.text_entry()
        pointers = (entry.current_text_id, entry.current_meaning_id, entry.current_category_id)
        for enabled in [False, True]:
            with self.subTest(ai_enabled=enabled):
                self.dictionary.image_generation_enabled = enabled; self.dictionary.save()
                self.assertContains(self.client.get(self.url('entry', entry.pk)), self.url('add-picture', entry.pk))
                page = self.client.get(self.url('add-picture', entry.pk)+'?wording=1')
                for text in ['Take photo', 'Or choose a picture', 'Save picture']:
                    self.assertContains(page, text)
                self.assertNotContains(page, 'name="word"')
                token = uuid.uuid4()
                for attempt in range(2):
                    result = self.post('add-picture', {'photo': picture(), 'consent': 'on', 'publish_now': 'on',
                        'word': 'must not replace existing wording'}, entry.pk, token=token)
                    self.assertEqual(result.status_code, 200)
                entry.refresh_from_db()
                self.assertEqual(entry.word, 'tekanna')
                self.assertEqual((entry.current_text_id, entry.current_meaning_id, entry.current_category_id), pointers)
        pictures = entry.contributions.filter(kind='image')
        self.assertEqual(pictures.count(), 2)
        self.assertEqual(entry.selected_image_id, pictures.order_by('pk').first().pk)

    def test_member_photo_requires_permission_and_remains_pending(self):
        entry = self.text_entry(); self.client.force_login(self.member)
        self.dictionary.image_generation_enabled = True; self.dictionary.save()
        self.assertContains(self.client.get(self.url('entry', entry.pk)), self.url('add-picture', entry.pk))
        self.assertEqual(self.post('add-picture', {'photo': picture()}, entry.pk).status_code, 400)
        self.assertEqual(self.post('add-picture', {'consent': 'on'}, entry.pk).status_code, 400)
        self.assertEqual(self.post('add-picture', {'photo': picture(), 'consent': 'on', 'publish_now': 'on'}, entry.pk).status_code, 200)
        image = entry.contributions.get(kind='image')
        self.assertEqual((image.status, image.author_id), ('pending', self.member.pk))

    def test_new_routes_reject_outsiders_inactive_withdrawn_and_wrong_entry(self):
        entry = self.text_entry()
        for user, state in [(self.outsider, 'outsider'), (self.member, 'inactive'), (self.member, 'withdrawn')]:
            with self.subTest(state=state):
                Membership.objects.filter(dictionary=self.dictionary, user=self.member).update(
                    status='inactive' if state == 'inactive' else 'active', role='editor')
                Participation.objects.update_or_create(dictionary=self.dictionary, user=self.member,
                    defaults={'withdrawn': state == 'withdrawn'})
                self.client.force_login(user)
                for name, args in [('settings', ()), ('add-picture', (entry.pk,))]:
                    self.assertEqual(self.client.get(self.url(name, *args)).status_code, 404)
                    self.assertEqual(self.client.post(self.url(name, *args), {}).status_code, 404)
        self.client.force_login(self.owner)
        other = Dictionary.objects.create(owner=self.owner, name='Other', language='Swedish')
        foreign = Entry.objects.create(dictionary=other, created_by=self.owner)
        self.assertEqual(self.client.get(self.url('add-picture', foreign.pk)).status_code, 404)

    def test_new_routes_keep_csrf_protection(self):
        entry = self.text_entry()
        client = Client(enforce_csrf_checks=True); client.force_login(self.owner)
        self.assertEqual(client.post(self.url('settings'), self.settings_data()).status_code, 403)
        self.assertEqual(client.post(self.url('add-picture', entry.pk), {'photo': picture(), 'consent': 'on'}).status_code, 403)
