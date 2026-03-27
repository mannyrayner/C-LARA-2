from unittest.mock import patch
import base64

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import Client, TestCase
from django.urls import reverse

from projects.models import Project, ProjectImageElement, ProjectImagePage, ProjectImageStyle


class FakeImageClient:
    def __init__(self):
        self.prompts: list[str] = []

    def generate_image(self, prompt, **kwargs):
        self.prompts.append(prompt)
        return {
            "bytes": base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aRX0AAAAASUVORK5CYII="
            ),
            "revised_prompt": "Page revised prompt",
            "model": kwargs.get("model", "gpt-image-1"),
        }


class ProjectImagePagesViewTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="pager", password="pw")
        self.project = Project.objects.create(
            owner=self.user,
            title="Paged Book",
            source_text="Page one text.\n\nPage two text.",
            language="en",
            target_language="fr",
        )
        ProjectImageStyle.objects.create(
            project=self.project,
            style_brief="storybook",
            expanded_style_description="Warm watercolor style.",
            status=ProjectImageStyle.STATUS_APPROVED,
            ai_model="gpt-4o",
        )
        ProjectImageElement.objects.create(
            project=self.project,
            name="Celine",
            element_type="character",
            page_refs="1,2",
            expanded_description="A recurring student",
            expanded_prompt="Draw Celine with curly hair",
            image_path="images/elements/celine/reference.png",
        )
        self.client = Client()
        self.client.login(username="pager", password="pw")

    def _page_form_payload(self):
        rows = list(ProjectImagePage.objects.filter(project=self.project).order_by("page_number", "id"))
        payload = {
            "form-TOTAL_FORMS": str(len(rows)),
            "form-INITIAL_FORMS": str(len(rows)),
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "1000",
        }
        for idx, row in enumerate(rows):
            payload[f"form-{idx}-id"] = str(row.id)
            payload[f"form-{idx}-page_number"] = str(row.page_number)
            payload[f"form-{idx}-page_text"] = row.page_text
            payload[f"form-{idx}-generation_prompt"] = row.generation_prompt
            payload[f"form-{idx}-image_model"] = row.image_model
            payload[f"form-{idx}-image_revised_prompt"] = row.image_revised_prompt
            payload[f"form-{idx}-status"] = row.status
        return payload

    def test_get_pages_view_shows_controls(self):
        resp = self.client.get(reverse("project-image-pages", args=[self.project.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Generate page images")
        self.assertEqual(ProjectImagePage.objects.filter(project=self.project).count(), 2)

    @patch("projects.views._build_ai_client")
    def test_generate_page_images_persists_output(self, mock_build_ai_client):
        fake_client = FakeImageClient()
        mock_build_ai_client.return_value = fake_client
        self.client.get(reverse("project-image-pages", args=[self.project.pk]))

        payload = self._page_form_payload()
        payload["action"] = "generate_images"
        payload["image_model"] = "gpt-image-1"
        resp = self.client.post(
            reverse("project-image-pages", args=[self.project.pk]),
            payload,
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)

        page = ProjectImagePage.objects.get(project=self.project, page_number=1)
        self.assertTrue(page.image_path.endswith("page_001/image.png"))
        self.assertIn("Style description:", page.generation_prompt)
        self.assertIn("Reference image path: images/elements/celine/reference.png", page.generation_prompt)

        msgs = [m.message for m in get_messages(resp.wsgi_request)]
        self.assertTrue(any("Generated 2 page images with gpt-image-1." in msg for msg in msgs))
        self.assertFalse(any("Generating page images" in msg for msg in msgs))
