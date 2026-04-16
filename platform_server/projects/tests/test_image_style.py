from unittest.mock import patch
import asyncio
import base64

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
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


class UsageReportingStyleAIClient:
    def __init__(self, response, usage_reporter=None):
        self.response = response
        self.usage_reporter = usage_reporter

    async def chat_json(self, prompt, **kwargs):  # noqa: ARG002
        if self.usage_reporter:
            self.usage_reporter(
                {
                    "model": kwargs.get("model", "gpt-4o-mini"),
                    "operation": "chat_json",
                    "prompt_tokens": 15,
                    "completion_tokens": 9,
                    "total_tokens": 24,
                }
            )
        return self.response


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
        self.assertContains(resp, "Expand style brief")
        self.assertContains(resp, "To fill “Expanded style description” and “Sample image prompt”")
        self.assertContains(resp, "style-processing-indicator")
        self.assertContains(resp, "Expanding style brief...")
        self.assertContains(resp, "Style telemetry")
        self.assertContains(resp, "Generate sample image is disabled until a sample image prompt is available.")
        self.assertContains(resp, "name=\"action\" value=\"generate_image\"")
        self.assertContains(resp, "disabled title=\"Generate or enter a sample image prompt first\"")
        self.assertContains(resp, "Save draft</strong> stores manual edits")

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
        self.assertIn("notice=done", resp["Location"])

        style = ProjectImageStyle.objects.get(project=self.project)
        self.assertEqual(style.status, ProjectImageStyle.STATUS_GENERATED)
        self.assertIn("warm watercolor storybook", style.expanded_style_description)
        self.assertTrue(fake_client.prompts)
        self.assertIn("Do NOT include named characters", fake_client.prompts[0])
        self.assertIn("Text policy for final images:", fake_client.prompts[0])

        style_dir = self.project.artifact_dir() / "images" / "style"
        self.assertTrue((style_dir / "style_brief.txt").exists())
        self.assertTrue((style_dir / "style_expansion_prompt.json").exists())
        self.assertTrue((style_dir / "style_expansion_response.json").exists())
        self.assertTrue((style_dir / "telemetry.jsonl").exists())
        telemetry_lines = (style_dir / "telemetry.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertGreaterEqual(len(telemetry_lines), 2)
        self.assertTrue(any("style expansion request start" in line for line in telemetry_lines))
        self.assertTrue(any("style expansion response received" in line for line in telemetry_lines))
        self.assertEqual(
            (style_dir / "sample_image_prompt.txt").read_text(encoding="utf-8"),
            style.sample_image_prompt,
        )
        resp_get = self.client.get(reverse("project-image-style", args=[self.project.pk]))
        self.assertContains(resp_get, "Style telemetry")

    @patch("projects.views._build_ai_client")
    def test_generate_style_uses_action_intent_fallback(self, mock_build_ai_client):
        fake_client = FakeAIClient(
            {
                "expanded_style_description": "Line-art storybook style.",
                "representative_excerpt": "Celine arrives in Adelaide.",
                "sample_image_prompt": "Line-art scene of Celine arriving.",
            }
        )
        mock_build_ai_client.return_value = fake_client
        resp = self.client.post(
            reverse("project-image-style", args=[self.project.pk]),
            {
                "style_brief": "line art",
                "expanded_style_description": "",
                "sample_image_prompt": "",
                "ai_model": "gpt-4o",
                "sample_image_model": "gpt-image-1",
                "status": "draft",
                "action_intent": "generate",
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.assertIn("notice=done", resp["Location"])
        style = ProjectImageStyle.objects.get(project=self.project)
        self.assertEqual(style.status, ProjectImageStyle.STATUS_GENERATED)
        self.assertTrue(style.sample_image_prompt)

    @patch("projects.views._build_ai_client")
    def test_generate_style_truncates_overlong_expanded_style_description(self, mock_build_ai_client):
        fake_client = FakeAIClient(
            {
                "expanded_style_description": "S" * 2600,
                "representative_excerpt": "Excerpt",
                "sample_image_prompt": "Sample prompt",
            }
        )
        mock_build_ai_client.return_value = fake_client
        self.client.post(
            reverse("project-image-style", args=[self.project.pk]),
            {
                "style_brief": "watercolor",
                "expanded_style_description": "",
                "sample_image_prompt": "",
                "ai_model": "gpt-4o",
                "sample_image_model": "gpt-image-1",
                "status": "draft",
                "action": "generate",
            },
        )
        style = ProjectImageStyle.objects.get(project=self.project)
        self.assertIn("style description truncated", style.expanded_style_description)
        self.assertLessEqual(len(style.expanded_style_description), 1400)

    @patch("projects.views.record_openai_usage_and_charge")
    @patch("projects.views._build_ai_client")
    def test_generate_style_records_usage_outside_async_context(
        self, mock_build_ai_client, mock_record_openai_usage_and_charge
    ):
        mock_build_ai_client.side_effect = lambda **kwargs: UsageReportingStyleAIClient(
            {
                "expanded_style_description": "A warm watercolor style.",
                "representative_excerpt": "Celine arrives in Adelaide.",
                "sample_image_prompt": "Warm watercolor sample prompt.",
            },
            usage_reporter=kwargs.get("usage_reporter"),
        )

        def _assert_sync_context(**kwargs):  # noqa: ARG001
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                return
            raise AssertionError("record_openai_usage_and_charge called in async context")

        mock_record_openai_usage_and_charge.side_effect = _assert_sync_context

        resp = self.client.post(
            reverse("project-image-style", args=[self.project.pk]),
            {
                "style_brief": "watercolor storybook",
                "expanded_style_description": "",
                "sample_image_prompt": "",
                "ai_model": "gpt-4o",
                "sample_image_model": "gpt-image-1",
                "status": "draft",
                "action": "generate",
            },
        )
        self.assertEqual(resp.status_code, 302)
        mock_record_openai_usage_and_charge.assert_called_once()

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

    def test_generate_sample_image_button_enabled_when_prompt_exists(self):
        ProjectImageStyle.objects.create(
            project=self.project,
            style_brief="storybook",
            expanded_style_description="Expanded",
            sample_image_prompt="Prompt exists",
            ai_model="gpt-4o",
        )
        resp = self.client.get(reverse("project-image-style", args=[self.project.pk]))
        self.assertContains(resp, "name=\"action\" value=\"generate_image\"")
        self.assertNotContains(resp, "disabled title=\"Generate or enter a sample image prompt first\"")

    @patch("projects.views._build_ai_client")
    def test_generate_style_adds_completion_message(self, mock_build_ai_client):
        fake_client = FakeAIClient(
            {
                "expanded_style_description": "Painterly style",
                "representative_excerpt": "Celine arrives.",
                "sample_image_prompt": "Paint Celine arriving.",
            }
        )
        mock_build_ai_client.return_value = fake_client

        resp = self.client.post(
            reverse("project-image-style", args=[self.project.pk]),
            {
                "style_brief": "watercolor",
                "expanded_style_description": "",
                "sample_image_prompt": "",
                "ai_model": "gpt-4o",
                "sample_image_model": "gpt-image-1",
                "status": "draft",
                "action": "generate",
            },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        msgs = [m.message for m in get_messages(resp.wsgi_request)]
        self.assertTrue(any("Style expansion completed" in msg for msg in msgs))

    @patch("projects.views._build_ai_client")
    def test_generate_style_failure_sets_error_notice(self, mock_build_ai_client):
        class FailingClient:
            async def chat_json(self, prompt, **kwargs):  # noqa: ARG002
                raise RuntimeError("boom")

        mock_build_ai_client.return_value = FailingClient()
        resp = self.client.post(
            reverse("project-image-style", args=[self.project.pk]),
            {
                "style_brief": "watercolor",
                "expanded_style_description": "",
                "sample_image_prompt": "",
                "ai_model": "gpt-4o",
                "sample_image_model": "gpt-image-1",
                "status": "draft",
                "action": "generate",
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.assertIn("notice=error", resp["Location"])

    def test_invalid_style_submit_adds_error_message(self):
        resp = self.client.post(
            reverse("project-image-style", args=[self.project.pk]),
            {
                "style_brief": "",
                "expanded_style_description": "",
                "sample_image_prompt": "",
                "ai_model": "gpt-4o",
                "sample_image_model": "gpt-image-1",
                "status": "draft",
                "action": "save",
            },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        msgs = [m.message for m in get_messages(resp.wsgi_request)]
        self.assertTrue(any("Could not process the style request" in msg for msg in msgs))
        self.assertTrue(any("Style form error (style_brief)" in msg for msg in msgs))
        telemetry_path = self.project.artifact_dir() / "images" / "style" / "telemetry.jsonl"
        self.assertTrue(telemetry_path.exists())
        telemetry_lines = telemetry_path.read_text(encoding="utf-8").splitlines()
        self.assertTrue(any("style form invalid" in line for line in telemetry_lines))
