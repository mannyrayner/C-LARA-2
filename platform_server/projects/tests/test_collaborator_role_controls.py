"""Owners can update existing collaborators through the visible project form."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from projects.models import Project, ProjectCollaborator


class CollaboratorRoleControlTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.owner = users.objects.create_user(username='owner')
        self.reader = users.objects.create_user(username='reader')
        self.project = Project.objects.create(owner=self.owner, title='Private test',
            language='it', target_language='en', source_text='Il gatto dorme.',
            access_scope=Project.ACCESS_PRIVATE, audio_mode=Project.AUDIO_MODE_NONE)
        self.membership = ProjectCollaborator.objects.create(project=self.project,
            user=self.reader, role=ProjectCollaborator.ROLE_VIEWER)

    def test_owner_can_promote_existing_viewer_using_the_displayed_control(self):
        self.client.force_login(self.owner)
        page = self.client.get(reverse('project-detail', args=[self.project.pk]))
        self.assertContains(page, 'Update role for reader')
        self.assertContains(page, f'<label for="collab_role_{self.membership.pk}">Role for reader:</label>')
        self.assertContains(page, 'value="viewer" selected')
        self.assertEqual(self.client.post(reverse('project-collaborators', args=[self.project.pk]),
            {'username':'reader', 'role':'owner'}).status_code, 302)
        self.membership.refresh_from_db()
        self.assertEqual(self.membership.role, ProjectCollaborator.ROLE_OWNER)
        self.assertEqual(self.project.collaborators.count(), 1)
        self.client.force_login(self.reader)
        page = self.client.get(reverse('project-annotation-home', args=[self.project.pk]))
        self.assertContains(page, 'Save audio setting')
        self.assertEqual(self.client.post(reverse('project-processing-options', args=[self.project.pk]),
            {'audio_mode':Project.AUDIO_MODE_TTS}).status_code, 302)
        self.project.refresh_from_db()
        self.assertEqual(self.project.audio_mode, Project.AUDIO_MODE_TTS)

    def test_viewer_does_not_gain_role_or_audio_setting_controls(self):
        self.client.force_login(self.reader)
        page = self.client.get(reverse('project-detail', args=[self.project.pk]))
        self.assertNotContains(page, 'Update role for reader')
        self.assertNotContains(page, 'Save audio setting')
        for name, data in [('project-collaborators', {'username':'reader', 'role':'owner'}),
                           ('project-processing-options', {'audio_mode':Project.AUDIO_MODE_TTS})]:
            # Projects outside the required role are deliberately concealed.
            self.assertEqual(self.client.post(reverse(name, args=[self.project.pk]), data).status_code, 404)
        self.membership.refresh_from_db(); self.project.refresh_from_db()
        self.assertEqual(self.membership.role, ProjectCollaborator.ROLE_VIEWER)
        self.assertEqual(self.project.audio_mode, Project.AUDIO_MODE_NONE)
