from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from projects.models import Profile, Project


class ProjectDialogueEntryTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="dialogue_user", password="pw")
        Profile.objects.create(user=self.user, timezone="UTC", dialogue_language="en")
        self.client = Client()
        self.client.login(username="dialogue_user", password="pw")
        self.project = Project.objects.create(
            owner=self.user,
            title="Elephant Story",
            source_text="source",
            language="fr",
            target_language="en",
        )

    @patch("projects.views._parse_nl_project_open_request")
    def test_project_list_supports_nl_open_request_box(self, mock_parse):
        mock_parse.return_value = {
            "title": "Elephant",
            "text_language": "fr",
            "annotation_language": "en",
            "keywords": ["elephant"],
        }
        resp = self.client.get(
            reverse("project-list"),
            {"nl_open_query": "open my french elephant project", "dialogue_language": "en"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Dialogue: find/open existing project")
        self.assertContains(resp, "Interpreted request")
        self.assertContains(resp, "Elephant Story")

    @patch("projects.views._parse_nl_project_create_request")
    def test_project_create_prefills_form_from_nl_request(self, mock_parse):
        mock_parse.return_value = {
            "title": "My NL Draft",
            "language": "en",
            "target_language": "fr",
            "input_mode": Project.INPUT_DESCRIPTION,
            "description": "A short story about a fox.",
            "source_text": "",
        }
        resp = self.client.get(
            reverse("project-create"),
            {"nl_new_query": "Create an English project with French glosses from a short description", "dialogue_language": "en"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Dialogue: create new project")
        self.assertContains(resp, "Interpreted project setup")
        self.assertContains(resp, 'value="My NL Draft"')
        self.assertContains(resp, "A short story about a fox.")
