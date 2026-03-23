from unittest.mock import patch
import base64

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from projects.models import Project, ProjectImageStyle


class FakeAIClient:
    def __init__(self, response):
        self.response = response
        self.prompts = []

    async def chat_json(self, prompt, **kwargs):
        self.prompts.append(prompt)
        return self.response

    def generate_image(self, prompt, **kwargs):
        self.prompts.append(prompt)
        return {
            "bytes": base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aRX0AAAAASUVORK5CYII="
            ),
            "revised_prompt": "Revised provider prompt",
            "model": kwargs.get("model", "gpt-image-1"),
            "size": kwargs.get("size", "1024x1024"),
            "quality": kwargs.get("quality", "medium"),
            "output_format": kwargs.get("output_format", "png"),
        }


class ProjectImageStyleViewTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="styler", password="pw")
        self.project = Project.objects.create(
            owner=self.user,
            title="Picture Book",
            source_text="Celine visits Adelaide and meets her host mother.",
            description="A short illustrated story.",
            language="en",
            target_language="fr",
        )
        self.client = Client()
        self.client.login(username="styler", password="pw")

    def test_get_style_page_creates_draft_record(self):
        resp = self.client.get(reverse("project-image-style", args=[self.project.pk]))
        self.assertEqual(resp.status_code, 200)

        style = ProjectImageStyle.objects.get(project=self.project)
        self.assertEqual(style.status, ProjectImageStyle.STATUS_DRAFT)
        self.assertContains(resp, "Generate style draft")

    @patch("projects.views._build_ai_client")
    def test_generate_style_persists_outputs_and_artifacts(self, mock_build_ai_client):
        fake_client = FakeAIClient(
            {
                "expanded_style_description": "A warm watercolor storybook style with soft edges.",
                "representative_excerpt": "Celine arrives in Adelaide and meets her host mother.",
                "sample_image_prompt": "Illustrate Celine arriving in Adelaide in a warm watercolor storybook style.",
            }
        )
        mock_build_ai_client.return_value = fake_client

        resp = self.client.post(
            reverse("project-image-style", args=[self.project.pk]),
            {
                "style_brief": "soft watercolor storybook",
                "expanded_style_description": "",
                "sample_image_prompt": "",
                "ai_model": "gpt-4o",
                "sample_image_model": "gpt-image-1",
                "status": "draft",
                "action": "generate",
            },
        )
        self.assertEqual(resp.status_code, 302)

        style = ProjectImageStyle.objects.get(project=self.project)
        self.assertEqual(style.status, ProjectImageStyle.STATUS_GENERATED)
        self.assertIn("warm watercolor storybook", style.expanded_style_description)
        self.assertTrue(fake_client.prompts)

        style_dir = self.project.artifact_dir() / "images" / "style"
        self.assertTrue((style_dir / "style_brief.txt").exists())
        self.assertTrue((style_dir / "style_expansion_prompt.json").exists())
        self.assertTrue((style_dir / "style_expansion_response.json").exists())
        self.assertEqual(
            (style_dir / "sample_image_prompt.txt").read_text(encoding="utf-8"),
            style.sample_image_prompt,
        )

    def test_approve_style_updates_status(self):
        style = ProjectImageStyle.objects.create(
            project=self.project,
            style_brief="storybook",
            expanded_style_description="Expanded",
            sample_image_prompt="Prompt",
            ai_model="gpt-4o",
        )

        resp = self.client.post(
            reverse("project-image-style", args=[self.project.pk]),
            {
                "style_brief": style.style_brief,
                "expanded_style_description": style.expanded_style_description,
                "sample_image_prompt": style.sample_image_prompt,
                "ai_model": style.ai_model,
                "sample_image_model": style.sample_image_model,
                "status": style.status,
                "action": "approve",
            },
        )
        self.assertEqual(resp.status_code, 302)
        style.refresh_from_db()
        self.assertEqual(style.status, ProjectImageStyle.STATUS_APPROVED)

    @patch("projects.views._build_ai_client")
    def test_generate_sample_image_persists_file_and_metadata(self, mock_build_ai_client):
        fake_client = FakeAIClient({})
        mock_build_ai_client.return_value = fake_client
        style = ProjectImageStyle.objects.create(
            project=self.project,
            style_brief="storybook",
            expanded_style_description="Expanded",
            sample_image_prompt="Paint a warm watercolor arrival scene.",
            ai_model="gpt-4o",
        )

        resp = self.client.post(
            reverse("project-image-style", args=[self.project.pk]),
            {
                "style_brief": style.style_brief,
                "expanded_style_description": style.expanded_style_description,
                "sample_image_prompt": style.sample_image_prompt,
                "ai_model": style.ai_model,
                "sample_image_model": style.sample_image_model,
                "status": style.status,
                "action": "generate_image",
            },
        )
        self.assertEqual(resp.status_code, 302)

        style.refresh_from_db()
        self.assertEqual(style.sample_image_model, "gpt-image-1")
        self.assertEqual(style.sample_image_revised_prompt, "Revised provider prompt")
        self.assertTrue(style.sample_image_path.endswith("style_sample_image.png"))

        image_path = self.project.artifact_dir() / style.sample_image_path
        self.assertTrue(image_path.exists())
        self.assertGreater(image_path.stat().st_size, 0)
