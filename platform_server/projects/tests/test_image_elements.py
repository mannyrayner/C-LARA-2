from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from projects.models import Project, ProjectImageElement, ProjectImageStyle


class FakeAIClient:
    def __init__(self, responses):
        self.responses = responses
        self.calls = 0

    async def chat_json(self, prompt, **kwargs):
        response = self.responses[min(self.calls, len(self.responses) - 1)]
        self.calls += 1
        return response


class ProjectImageElementsViewTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="elementer", password="pw")
        self.project = Project.objects.create(
            owner=self.user,
            title="Element Book",
            source_text="Celine visits Adelaide. Celine meets her host mother.",
            language="en",
            target_language="fr",
        )
        self.style = ProjectImageStyle.objects.create(
            project=self.project,
            style_brief="storybook",
            expanded_style_description="Warm watercolor style.",
            status=ProjectImageStyle.STATUS_APPROVED,
            ai_model="gpt-4o",
        )
        self.client = Client()
        self.client.login(username="elementer", password="pw")

    def test_get_elements_page(self):
        resp = self.client.get(reverse("project-image-elements", args=[self.project.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Discover elements")

    @patch("projects.views._build_ai_client")
    def test_discover_elements_creates_rows(self, mock_build_ai_client):
        mock_build_ai_client.return_value = FakeAIClient(
            [
                {
                    "elements": [
                        {
                            "name": "Celine",
                            "type": "character",
                            "page_refs": [1, 2],
                            "why_consistency_matters": "Main character",
                        },
                        {
                            "name": "host mother",
                            "type": "character",
                            "page_refs": [2, 3],
                            "why_consistency_matters": "Recurring supporting role",
                        },
                    ]
                }
            ]
        )

        resp = self.client.post(
            reverse("project-image-elements", args=[self.project.pk]),
            {
                "form-TOTAL_FORMS": "0",
                "form-INITIAL_FORMS": "0",
                "form-MIN_NUM_FORMS": "0",
                "form-MAX_NUM_FORMS": "1000",
                "action": "discover",
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(ProjectImageElement.objects.filter(project=self.project).count(), 2)

    @patch("projects.views._build_ai_client")
    def test_expand_elements_sets_expanded_fields(self, mock_build_ai_client):
        element = ProjectImageElement.objects.create(
            project=self.project,
            name="Celine",
            element_type="character",
            page_refs="1,2",
            why_consistency_matters="Main character",
            ai_model="gpt-4o",
        )
        mock_build_ai_client.return_value = FakeAIClient(
            [
                {
                    "expanded_description": "Teenage student with curly hair and warm expression.",
                    "expanded_prompt": "Illustrate Celine consistently with curly hair and warm expression.",
                }
            ]
        )

        resp = self.client.post(
            reverse("project-image-elements", args=[self.project.pk]),
            {
                "form-TOTAL_FORMS": "1",
                "form-INITIAL_FORMS": "1",
                "form-MIN_NUM_FORMS": "0",
                "form-MAX_NUM_FORMS": "1000",
                "form-0-id": str(element.id),
                "form-0-name": element.name,
                "form-0-element_type": element.element_type,
                "form-0-page_refs": element.page_refs,
                "form-0-why_consistency_matters": element.why_consistency_matters,
                "form-0-expanded_description": "",
                "form-0-expanded_prompt": "",
                "action": "expand",
            },
        )
        self.assertEqual(resp.status_code, 302)

        element.refresh_from_db()
        self.assertIn("curly hair", element.expanded_description)
        self.assertEqual(element.status, ProjectImageElement.STATUS_EXPANDED)
