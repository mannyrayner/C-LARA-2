from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from projects.models import Project, ProjectCollaborator


class ProjectRenameTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username="rename_owner", password="pw")
        self.collaborator = User.objects.create_user(username="rename_collaborator", password="pw")
        self.project = Project.objects.create(owner=self.owner, title="Old project name")
        self.rename_url = reverse("project-rename", args=[self.project.pk])

    def test_owner_sees_rename_control_and_can_rename_project(self):
        self.client.force_login(self.owner)

        detail_response = self.client.get(reverse("project-detail", args=[self.project.pk]))
        rename_response = self.client.post(self.rename_url, {"title": "  New project name  "}, follow=True)

        self.assertContains(detail_response, "Rename project")
        self.assertRedirects(rename_response, reverse("project-detail", args=[self.project.pk]))
        self.project.refresh_from_db()
        self.assertEqual(self.project.title, "New project name")
        self.assertContains(rename_response, "Renamed project &#x27;Old project name&#x27; to &#x27;New project name&#x27;.")

    def test_owner_cannot_rename_project_to_an_existing_name(self):
        Project.objects.create(owner=self.owner, title="Existing project name")
        self.client.force_login(self.owner)

        response = self.client.post(self.rename_url, {"title": "Existing project name"}, follow=True)

        self.project.refresh_from_db()
        self.assertEqual(self.project.title, "Old project name")
        self.assertContains(response, "You already have a project with that name.")

    def test_owner_cannot_give_project_an_empty_name(self):
        self.client.force_login(self.owner)

        response = self.client.post(self.rename_url, {"title": "   "}, follow=True)

        self.project.refresh_from_db()
        self.assertEqual(self.project.title, "Old project name")
        self.assertContains(response, "Project name cannot be empty.")

    def test_collaborator_cannot_rename_project_or_see_control(self):
        ProjectCollaborator.objects.create(
            project=self.project,
            user=self.collaborator,
            role=ProjectCollaborator.ROLE_ANNOTATOR,
        )
        self.client.force_login(self.collaborator)

        detail_response = self.client.get(reverse("project-detail", args=[self.project.pk]))
        rename_response = self.client.post(self.rename_url, {"title": "Not permitted"})

        self.assertEqual(detail_response.status_code, 200)
        self.assertNotContains(detail_response, "Rename project")
        self.assertEqual(rename_response.status_code, 404)
        self.project.refresh_from_db()
        self.assertEqual(self.project.title, "Old project name")
