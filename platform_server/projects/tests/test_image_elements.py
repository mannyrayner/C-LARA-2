from unittest.mock import patch
import asyncio
import base64

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
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

    def generate_image(self, prompt, **kwargs):
        return {
            "bytes": base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aRX0AAAAASUVORK5CYII="
            ),
            "revised_prompt": "Element revised prompt",
            "model": kwargs.get("model", "gpt-image-1"),
        }




class UsageReportingAIClient:
    def __init__(self, usage_reporter=None):
        self.usage_reporter = usage_reporter

    async def chat_json(self, prompt, **kwargs):
        if self.usage_reporter:
            self.usage_reporter(
                {
                    "model": kwargs.get("model", "gpt-4o-mini"),
                    "operation": "chat_json",
                    "prompt_tokens": 12,
                    "completion_tokens": 8,
                    "total_tokens": 20,
                }
            )
        return {
            "expanded_description": "Expanded element description.",
            "expanded_prompt": "Expanded element prompt.",
        }


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
        self.assertContains(resp, "Text model:")
        self.assertContains(resp, "Generate element images")
        self.assertContains(resp, "fan-out/fan-in")
        self.assertContains(resp, "Elements telemetry")

    def test_get_elements_page_shows_generated_image(self):
        ProjectImageElement.objects.create(
            project=self.project,
            name="Celine",
            element_type="character",
            image_path="images/elements/celine/reference.png",
        )
        resp = self.client.get(reverse("project-image-elements", args=[self.project.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Generated reference image")
        self.assertContains(resp, "/compiled/images/elements/celine/reference.png")

    @patch("projects.views._build_ai_client")
    def test_discover_elements_creates_rows(self, mock_build_ai_client):
        self.project.source_text = "Page one with Celine.\n\nPage two with host mother."
        self.project.save(update_fields=["source_text"])
        mock_build_ai_client.side_effect = [
            FakeAIClient(
                [
                    {
                        "elements": [
                            {"name": "Celine", "type": "character"},
                            {"name": "host mother", "type": "character"},
                        ]
                    }
                ]
            ),
            FakeAIClient(
                [
                    {
                        "page_refs": [1, 2],
                        "why_consistency_matters": "Main character",
                        "type": "character",
                    }
                ]
            ),
            FakeAIClient(
                [
                    {
                        "page_refs": [1, 2],
                        "why_consistency_matters": "Recurring supporting role",
                        "type": "character",
                    }
                ]
            ),
        ]

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
        prompt_payload = (self.project.artifact_dir() / "images" / "elements" / "elements_discovery_prompt.json").read_text(
            encoding="utf-8"
        )
        self.assertIn("phase_1_prompt", prompt_payload)
        self.assertNotIn("Approved style description", prompt_payload)

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
                "form-0-image_model": "gpt-image-1",
                "form-0-image_revised_prompt": "",
                "action": "expand",
            },
        )
        self.assertEqual(resp.status_code, 302)

        element.refresh_from_db()
        self.assertIn("curly hair", element.expanded_description)
        self.assertEqual(element.status, ProjectImageElement.STATUS_EXPANDED)
        telemetry_path = self.project.artifact_dir() / "images" / "elements" / "telemetry.jsonl"
        self.assertTrue(telemetry_path.exists())
        telemetry_lines = telemetry_path.read_text(encoding="utf-8").splitlines()
        self.assertTrue(any("element expansion request start" in line for line in telemetry_lines))

    @patch("projects.views._build_ai_client")
    def test_expand_elements_uses_selected_ai_model(self, mock_build_ai_client):
        element = ProjectImageElement.objects.create(
            project=self.project,
            name="Host mother",
            element_type="character",
            page_refs="2,3",
            why_consistency_matters="Recurring supporting role",
            ai_model="gpt-4o",
        )
        mock_build_ai_client.return_value = FakeAIClient(
            [{"expanded_description": "Expanded", "expanded_prompt": "Prompt"}]
        )
        self.client.post(
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
                "form-0-image_model": "gpt-image-1",
                "form-0-image_revised_prompt": "",
                "action": "expand",
                "ai_model": "gpt-4o-mini",
            },
        )
        self.style.refresh_from_db()
        self.assertEqual(self.style.ai_model, "gpt-4o-mini")

    @patch("projects.views.record_openai_usage_and_charge")
    @patch("projects.views._build_ai_client")
    def test_expand_elements_records_usage_outside_async_context(
        self, mock_build_ai_client, mock_record_openai_usage_and_charge
    ):
        element = ProjectImageElement.objects.create(
            project=self.project,
            name="Celine",
            element_type="character",
            page_refs="1,2",
            why_consistency_matters="Main character",
            ai_model="gpt-4o",
        )

        def _build_client(**kwargs):
            return UsageReportingAIClient(usage_reporter=kwargs.get("usage_reporter"))

        mock_build_ai_client.side_effect = _build_client

        def _assert_sync_context(**kwargs):
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                return
            raise AssertionError("record_openai_usage_and_charge called in async context")

        mock_record_openai_usage_and_charge.side_effect = _assert_sync_context

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
                "form-0-image_model": "gpt-image-1",
                "form-0-image_revised_prompt": "",
                "action": "expand",
            },
        )

        self.assertEqual(resp.status_code, 302)
        mock_record_openai_usage_and_charge.assert_called_once()


    @patch("projects.views._build_ai_client")
    def test_discover_elements_adds_processing_message(self, mock_build_ai_client):
        mock_build_ai_client.side_effect = [FakeAIClient([{"elements": []}])]
        resp = self.client.post(
            reverse("project-image-elements", args=[self.project.pk]),
            {
                "form-TOTAL_FORMS": "0",
                "form-INITIAL_FORMS": "0",
                "form-MIN_NUM_FORMS": "0",
                "form-MAX_NUM_FORMS": "1000",
                "action": "discover",
            },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        msgs = [m.message for m in get_messages(resp.wsgi_request)]
        self.assertTrue(any("Discovering recurring elements" in msg for msg in msgs))

    def test_invalid_elements_submit_adds_error_message(self):
        element = ProjectImageElement.objects.create(
            project=self.project,
            name="Celine",
            element_type="character",
            page_refs="1,2",
            why_consistency_matters="Main character",
        )
        resp = self.client.post(
            reverse("project-image-elements", args=[self.project.pk]),
            {
                "form-TOTAL_FORMS": "1",
                "form-INITIAL_FORMS": "1",
                "form-MIN_NUM_FORMS": "0",
                "form-MAX_NUM_FORMS": "1000",
                "form-0-id": str(element.id),
                "form-0-name": "",
                "form-0-element_type": element.element_type,
                "form-0-page_refs": element.page_refs,
                "form-0-why_consistency_matters": element.why_consistency_matters,
                "form-0-expanded_description": "",
                "form-0-expanded_prompt": "",
                "form-0-image_model": "gpt-image-1",
                "form-0-image_revised_prompt": "",
                "action": "save",
            },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        msgs = [m.message for m in get_messages(resp.wsgi_request)]
        self.assertTrue(any("Could not process the elements request" in msg for msg in msgs))

    @patch("projects.views._build_ai_client")
    def test_generate_element_images_persists_image(self, mock_build_ai_client):
        element = ProjectImageElement.objects.create(
            project=self.project,
            name="Celine",
            element_type="character",
            expanded_prompt="Portrait of Celine",
        )
        mock_build_ai_client.return_value = FakeAIClient([{"elements": []}])
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
                "form-0-expanded_description": element.expanded_description,
                "form-0-expanded_prompt": element.expanded_prompt,
                "form-0-image_model": "gpt-image-1",
                "form-0-image_revised_prompt": "",
                "action": "generate_images",
                "image_model": "gpt-image-1",
            },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        element.refresh_from_db()
        self.assertTrue(element.image_path.endswith("reference.png"))
        self.assertEqual(element.image_model, "gpt-image-1")

    @patch("projects.views._build_ai_client")
    def test_generate_element_images_invalid_model_warns_and_falls_back(self, mock_build_ai_client):
        element = ProjectImageElement.objects.create(
            project=self.project,
            name="Celine",
            element_type="character",
            expanded_prompt="Portrait of Celine",
        )
        mock_build_ai_client.return_value = FakeAIClient([{"elements": []}])
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
                "form-0-expanded_description": element.expanded_description,
                "form-0-expanded_prompt": element.expanded_prompt,
                "form-0-image_model": "gpt-image-1",
                "form-0-image_revised_prompt": "",
                "action": "generate_images",
                "image_model": "not-a-real-model",
            },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        msgs = [m.message for m in get_messages(resp.wsgi_request)]
        self.assertTrue(any("Using gpt-image-1 instead." in msg for msg in msgs))
        element.refresh_from_db()
        self.assertEqual(element.image_model, "gpt-image-1")
