from unittest.mock import patch
import inspect
import base64
import json
import re

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import Client, TestCase
from django.urls import reverse

from projects import views
from projects.models import (
    Community,
    PictureDictionary,
    PictureDictionaryEntry,
    Project,
    ProjectImageElement,
    ProjectImagePage,
    ProjectImagePageVariant,
    ProjectImageStyle,
)


class FakeImageClient:
    def __init__(self):
        self.prompts: list[str] = []
        self.text_prompts: list[str] = []

    async def chat_text(self, prompt, **kwargs):  # noqa: ARG002
        text = str(prompt)
        self.text_prompts.append(text)
        json_start = text.find("{")
        if json_start >= 0:
            try:
                payload = json.loads(text[json_start:])
                base_prompt = str(payload.get("base_prompt") or "").strip()
                if base_prompt:
                    return base_prompt
            except Exception:
                pass
        return "Constructed prompt for image generation."

    def generate_image(self, prompt, **kwargs):
        self.prompts.append(prompt)
        return {
            "bytes": base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aRX0AAAAASUVORK5CYII="
            ),
            "revised_prompt": "Page revised prompt",
            "model": kwargs.get("model", "gpt-image-1"),
        }


class TimeoutImageClient:
    async def chat_text(self, prompt, **kwargs):  # noqa: ARG002
        return "Constructed prompt for image generation."

    def generate_image(self, prompt, **kwargs):
        raise TimeoutError("simulated timeout")


class ModerationRetryImageClient(FakeImageClient):
    def __init__(self):
        super().__init__()
        self.calls = 0

    def generate_image(self, prompt, **kwargs):
        self.calls += 1
        if self.calls == 1:
            raise Exception(
                "Error code: 400 - {'error': {'message': 'rejected by the safety system req_demo123.', 'code': 'moderation_blocked'}}"
            )
        return super().generate_image(prompt, **kwargs)


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
        self.assertContains(resp, "fan-out/fan-in")
        self.assertContains(resp, reverse("project-detail", args=[self.project.pk]))
        self.assertContains(resp, reverse("project-images-home", args=[self.project.pk]))
        self.assertEqual(ProjectImagePage.objects.filter(project=self.project).count(), 2)
        self.assertContains(resp, "Status from elements step:")
        self.assertContains(resp, "1/1")
        self.assertNotContains(resp, "Discourage visible text in images")

    def test_images_home_shows_shared_model_controls(self):
        resp = self.client.get(reverse("project-images-home", args=[self.project.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Style AI model:")
        self.assertContains(resp, "Image model (style/elements/pages):")

    def test_get_pages_view_shows_billing_telemetry_link_when_present(self):
        billing_path = self.project.artifact_dir() / "images" / "billing_telemetry.jsonl"
        billing_path.parent.mkdir(parents=True, exist_ok=True)
        billing_path.write_text('{"event":"billing_usage_recorded"}\n', encoding="utf-8")
        resp = self.client.get(reverse("project-image-pages", args=[self.project.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Image billing telemetry")
        self.assertContains(resp, "/compiled/images/billing_telemetry.jsonl")

    def test_images_home_can_switch_page_text_source_to_translation(self):
        run_dir = self.project.artifact_dir() / "runs" / "run_translation" / "stages"
        run_dir.mkdir(parents=True, exist_ok=True)
        translation_payload = {
            "pages": [
                {"segments": [{"annotations": {"translation": "Bonjour"}}, {"annotations": {"translation": "le monde"}}]},
                {"segments": [{"annotations": {"translation": "Deuxieme page"}}]},
            ]
        }
        (run_dir / "translation.json").write_text(json.dumps(translation_payload), encoding="utf-8")

        resp = self.client.post(
            reverse("project-images-home", args=[self.project.pk]),
            {"generate_page_images_from_translations": "1"},
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.project.refresh_from_db()
        self.assertEqual(self.project.page_image_text_source, "translation")
        self.assertEqual(self.project.image_generation_pivot_language, "fr")
        self.assertContains(resp, "Saved image settings")
        page1 = ProjectImagePage.objects.get(project=self.project, page_number=1)
        page2 = ProjectImagePage.objects.get(project=self.project, page_number=2)
        self.assertEqual(page1.page_text, "Bonjour le monde")
        self.assertEqual(page2.page_text, "Deuxieme page")

    def test_images_home_defaults_page_text_source_to_segmentation(self):
        self.project.page_image_text_source = "translation"
        self.project.image_generation_pivot_language = "fr"
        self.project.save(update_fields=["page_image_text_source", "image_generation_pivot_language", "updated_at"])

        resp = self.client.post(
            reverse("project-images-home", args=[self.project.pk]),
            {},
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.project.refresh_from_db()
        self.assertEqual(self.project.page_image_text_source, "segmentation")
        self.assertEqual(self.project.image_generation_pivot_language, "")

    def test_images_home_shows_compile_html_suggestion_when_page_images_exist(self):
        ProjectImagePage.objects.create(
            project=self.project,
            page_number=1,
            page_text="Page one text.",
            generation_prompt="Prompt",
            image_path="images/pages/page_001/image.png",
            status=ProjectImagePage.STATUS_GENERATED,
        )
        resp = self.client.get(reverse("project-images-home", args=[self.project.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Dialogue assistant suggestion")
        self.assertContains(resp, "Compile HTML now")
        self.assertContains(resp, reverse("project-annotation-home", args=[self.project.pk]))

    def test_images_home_treats_empty_style_record_as_no_style_data(self):
        style = ProjectImageStyle.objects.get(project=self.project)
        style.style_brief = ""
        style.expanded_style_description = ""
        style.sample_image_prompt = ""
        style.sample_image_path = ""
        style.status = ProjectImageStyle.STATUS_DRAFT
        style.save(
            update_fields=[
                "style_brief",
                "expanded_style_description",
                "sample_image_prompt",
                "sample_image_path",
                "status",
                "updated_at",
            ]
        )
        resp = self.client.get(reverse("project-images-home", args=[self.project.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "No style data yet.")
        self.assertNotContains(resp, "Style data exists")

    def test_images_home_exposes_pivot_language_context(self):
        resp = self.client.get(reverse("project-images-home", args=[self.project.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("pivot_language_choices", resp.context)
        self.assertIn("selected_image_generation_pivot_language", resp.context)
        self.assertEqual(resp.context["selected_image_generation_pivot_language"], self.project.image_generation_pivot_language)
        self.assertIn("discourage_text_in_images_default", resp.context)
        self.assertContains(resp, "Discourage visible text in images")

    def test_images_home_can_toggle_discourage_text_setting(self):
        style = ProjectImageStyle.objects.get(project=self.project)
        self.assertFalse(style.discourage_text_in_images)

        resp = self.client.post(
            reverse("project-images-home", args=[self.project.pk]),
            {"discourage_text_in_images": "1"},
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        style.refresh_from_db()
        self.assertTrue(style.discourage_text_in_images)

        resp = self.client.post(
            reverse("project-images-home", args=[self.project.pk]),
            {},
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        style.refresh_from_db()
        self.assertFalse(style.discourage_text_in_images)

    def test_images_home_view_source_contains_pivot_language_assignment_and_validation(self):
        view_source = inspect.getsource(views.project_images_home)
        self.assertIn("valid_pivot_languages", view_source)
        self.assertIn("selected_image_generation_pivot_language", view_source)
        self.assertIn("project.image_generation_pivot_language", view_source)

    def test_images_home_view_source_validates_pivot_language_when_using_translations(self):
        view_source = inspect.getsource(views.project_images_home)
        self.assertIn("text_source == Project.PAGE_IMAGE_TEXT_SOURCE_TRANSLATION", view_source)
        self.assertIn("Unknown pivot language for image generation.", view_source)

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
        self.assertTrue(page.image_path.endswith("page_001/variant_001.png"))
        self.assertIn("Style description:", page.generation_prompt)
        self.assertEqual(ProjectImagePageVariant.objects.filter(page=page).count(), 1)
        self.assertContains(resp, "Prompt used for this variant:")
        self.assertContains(resp, "Style description:")

        msgs = [m.message for m in get_messages(resp.wsgi_request)]
        self.assertTrue(any("Generated 2 page image variant(s) with gpt-image-1." in msg for msg in msgs))
        self.assertFalse(any("Generating page images" in msg for msg in msgs))

    @patch("projects.views._build_ai_client")
    def test_generate_page_images_uses_dictionary_mode_prompt_for_dictionary_project(self, mock_build_ai_client):
        fake_client = FakeImageClient()
        mock_build_ai_client.return_value = fake_client
        self.client.get(reverse("project-image-pages", args=[self.project.pk]))
        dictionary = PictureDictionary.objects.create(
            community=Community.objects.create(name="Dict Community", language=self.project.language),
            project=self.project,
            organiser=self.user,
            language=self.project.language,
        )
        page1 = ProjectImagePage.objects.get(project=self.project, page_number=1)
        PictureDictionaryEntry.objects.create(
            dictionary=dictionary,
            surface="chat",
            lemma="chat",
            pos="NOUN",
            is_active=True,
            current_page_number=page1.page_number,
        )
        page1.page_text = "chat"
        page1.save(update_fields=["page_text", "updated_at"])

        payload = self._page_form_payload()
        payload["action"] = "generate_images"
        payload["image_model"] = "gpt-image-1"
        resp = self.client.post(reverse("project-image-pages", args=[self.project.pk]), payload, follow=True)
        self.assertEqual(resp.status_code, 200)
        page1.refresh_from_db()
        self.assertIn("Create one picture-dictionary illustration.", page1.generation_prompt)
        self.assertIn("Target lemma: chat", page1.generation_prompt)

    @patch("projects.views._build_ai_client")
    def test_generate_page_images_uses_dictionary_mode_prompt_with_surface_fallback(self, mock_build_ai_client):
        fake_client = FakeImageClient()
        mock_build_ai_client.return_value = fake_client
        self.client.get(reverse("project-image-pages", args=[self.project.pk]))
        dictionary = PictureDictionary.objects.create(
            community=Community.objects.create(name="Dict Community 2", language=self.project.language),
            project=self.project,
            organiser=self.user,
            language=self.project.language,
        )
        page1 = ProjectImagePage.objects.get(project=self.project, page_number=1)
        page1.page_text = "chat"
        page1.save(update_fields=["page_text", "updated_at"])
        PictureDictionaryEntry.objects.create(
            dictionary=dictionary,
            surface="chat",
            lemma="chat",
            pos="NOUN",
            is_active=True,
            current_page_number=None,
        )

        payload = self._page_form_payload()
        payload["action"] = "generate_images"
        payload["image_model"] = "gpt-image-1"
        resp = self.client.post(reverse("project-image-pages", args=[self.project.pk]), payload, follow=True)
        self.assertEqual(resp.status_code, 200)
        page1.refresh_from_db()
        self.assertIn("Create one picture-dictionary illustration.", page1.generation_prompt)
        self.assertIn("Target lemma: chat", page1.generation_prompt)

    @patch("projects.views._build_ai_client")
    def test_generate_multiple_variants_and_set_preferred_variant(self, mock_build_ai_client):
        fake_client = FakeImageClient()
        mock_build_ai_client.return_value = fake_client
        self.client.get(reverse("project-image-pages", args=[self.project.pk]))

        payload = self._page_form_payload()
        payload["action"] = "generate_images"
        payload["image_model"] = "gpt-image-1"
        payload["variants_per_page"] = "3"
        resp = self.client.post(reverse("project-image-pages", args=[self.project.pk]), payload, follow=True)
        self.assertEqual(resp.status_code, 200)
        page = ProjectImagePage.objects.get(project=self.project, page_number=1)
        variants = list(ProjectImagePageVariant.objects.filter(page=page).order_by("variant_index"))
        self.assertEqual(len(variants), 3)
        self.assertEqual(page.preferred_variant_id, variants[0].id)
        self.assertTrue(page.image_path.endswith("page_001/variant_001.png"))

        save_payload = self._page_form_payload()
        save_payload["action"] = "set_preferred"
        save_payload[f"preferred_variant_{page.id}"] = str(variants[2].id)
        resp2 = self.client.post(reverse("project-image-pages", args=[self.project.pk]), save_payload, follow=True)
        self.assertEqual(resp2.status_code, 200)
        page.refresh_from_db()
        self.assertEqual(page.preferred_variant_id, variants[2].id)
        self.assertTrue(page.image_path.endswith("page_001/variant_003.png"))

    @patch("projects.views._build_ai_client")
    def test_clear_generated_page_images_and_prompts(self, mock_build_ai_client):
        fake_client = FakeImageClient()
        mock_build_ai_client.return_value = fake_client
        self.client.get(reverse("project-image-pages", args=[self.project.pk]))

        payload = self._page_form_payload()
        payload["action"] = "generate_images"
        payload["image_model"] = "gpt-image-1"
        resp = self.client.post(reverse("project-image-pages", args=[self.project.pk]), payload, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(ProjectImagePageVariant.objects.filter(page__project=self.project).exists())

        clear_payload = self._page_form_payload()
        clear_payload["action"] = "clear_generated"
        cleared = self.client.post(reverse("project-image-pages", args=[self.project.pk]), clear_payload, follow=True)
        self.assertEqual(cleared.status_code, 200)
        self.assertFalse(ProjectImagePageVariant.objects.filter(page__project=self.project).exists())

        for page in ProjectImagePage.objects.filter(project=self.project):
            self.assertEqual(page.image_path, "")
            self.assertEqual(page.generation_prompt, "")
            self.assertEqual(page.image_revised_prompt, "")
            self.assertIsNone(page.preferred_variant_id)

    @patch("projects.views._build_ai_client")
    def test_generate_page_images_trims_long_prompts_and_writes_telemetry(self, mock_build_ai_client):
        fake_client = FakeImageClient()
        mock_build_ai_client.return_value = fake_client
        self.project.source_text = "A" * 90000
        self.project.save(update_fields=["source_text", "updated_at"])
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
        self.assertLessEqual(len(page.generation_prompt), 12000)

        telemetry_path = self.project.artifact_dir() / "images" / "pages" / "telemetry.jsonl"
        self.assertTrue(telemetry_path.exists())
        lines = [json.loads(line) for line in telemetry_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        request_events = [line for line in lines if line.get("event") == "page_image_request"]
        self.assertTrue(request_events)
        self.assertIn("prompt", request_events[0])
        self.assertIn("prompt_length", request_events[0])
        self.assertIn("prompt_meta", request_events[0])
        self.assertIn("reference_images_sent_in_request", request_events[0])
        response_events = [line for line in lines if line.get("event") == "page_image_response"]
        self.assertTrue(response_events)
        self.assertIn("elapsed_s", response_events[0])
        construction_events = [line for line in lines if line.get("event") == "page_image_prompt_construction"]
        self.assertTrue(construction_events)
        self.assertIn("request_payload", construction_events[0])
        self.assertIn("response_prompt_final", construction_events[0])

    @patch("projects.views._build_ai_client")
    def test_generate_page_images_can_discourage_text_in_image(self, mock_build_ai_client):
        fake_client = FakeImageClient()
        mock_build_ai_client.return_value = fake_client
        style = ProjectImageStyle.objects.get(project=self.project)
        style.discourage_text_in_images = True
        style.save(update_fields=["discourage_text_in_images", "updated_at"])
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
        self.assertIn("comic-style sound effects", page.generation_prompt)

        telemetry_path = self.project.artifact_dir() / "images" / "pages" / "telemetry.jsonl"
        lines = [json.loads(line) for line in telemetry_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        request_events = [line for line in lines if line.get("event") == "page_image_request"]
        self.assertTrue(any(event.get("discourage_text_in_image") is True for event in request_events))

    @patch("projects.views._build_ai_client")
    def test_generate_page_images_discourage_text_adds_strict_constraints_in_any_language(self, mock_build_ai_client):
        fake_client = FakeImageClient()
        mock_build_ai_client.return_value = fake_client
        style = ProjectImageStyle.objects.get(project=self.project)
        style.discourage_text_in_images = True
        style.save(update_fields=["discourage_text_in_images", "updated_at"])
        self.project.language = "fr"
        self.project.save(update_fields=["language", "updated_at"])
        self.client.get(reverse("project-image-pages", args=[self.project.pk]))

        payload = self._page_form_payload()
        payload["action"] = "generate_images"
        payload["image_model"] = "gpt-image-1"
        self.client.post(
            reverse("project-image-pages", args=[self.project.pk]),
            payload,
            follow=True,
        )
        page = ProjectImagePage.objects.get(project=self.project, page_number=1)
        self.assertIn("EXIGENCES DE SUPPRESSION DU TEXTE (PRIORITÉ ÉLEVÉE) :", page.generation_prompt)
        self.assertIn("N’affiche aucun mot lisible", page.generation_prompt)
        self.assertNotIn("TEXT SUPPRESSION REQUIREMENTS (HIGH PRIORITY):", page.generation_prompt)

    @patch("projects.views._build_ai_client")
    def test_generate_page_images_filters_element_text_to_current_page(self, mock_build_ai_client):
        fake_client = FakeImageClient()
        mock_build_ai_client.return_value = fake_client
        element = ProjectImageElement.objects.get(project=self.project, name="Celine")
        element.expanded_description = "Page 1: calm pose.\nPage 2: explosion and large poster text."
        element.expanded_prompt = "For page 1 use calm close-up. For page 2 add giant sign text."
        element.save(update_fields=["expanded_description", "expanded_prompt", "updated_at"])
        self.client.get(reverse("project-image-pages", args=[self.project.pk]))

        payload = self._page_form_payload()
        payload["action"] = "generate_images"
        payload["image_model"] = "gpt-image-1"
        self.client.post(
            reverse("project-image-pages", args=[self.project.pk]),
            payload,
            follow=True,
        )
        page = ProjectImagePage.objects.get(project=self.project, page_number=1)
        self.assertIn("Page 1: calm pose.", page.generation_prompt)
        self.assertNotIn("Page 2: explosion and large poster text.", page.generation_prompt)

    @patch("projects.views._build_ai_client")
    def test_generate_page_images_uses_localized_prompt_language(self, mock_build_ai_client):
        fake_client = FakeImageClient()
        mock_build_ai_client.return_value = fake_client
        self.project.language = "fr"
        self.project.save(update_fields=["language", "updated_at"])
        self.client.get(reverse("project-image-pages", args=[self.project.pk]))

        payload = self._page_form_payload()
        payload["action"] = "generate_images"
        payload["image_model"] = "gpt-image-1"
        self.client.post(
            reverse("project-image-pages", args=[self.project.pk]),
            payload,
            follow=True,
        )
        page = ProjectImagePage.objects.get(project=self.project, page_number=1)
        self.assertIn("Crée une illustration", page.generation_prompt)

    @patch("projects.views._build_ai_client")
    def test_generate_page_images_uses_translation_language_when_translation_source_selected(self, mock_build_ai_client):
        fake_client = FakeImageClient()
        mock_build_ai_client.return_value = fake_client
        self.project.language = "am"
        self.project.target_language = "fr"
        self.project.page_image_text_source = "translation"
        self.project.save(update_fields=["language", "target_language", "page_image_text_source", "updated_at"])
        self.client.get(reverse("project-image-pages", args=[self.project.pk]))

        payload = self._page_form_payload()
        payload["action"] = "generate_images"
        payload["image_model"] = "gpt-image-1"
        self.client.post(
            reverse("project-image-pages", args=[self.project.pk]),
            payload,
            follow=True,
        )
        page = ProjectImagePage.objects.get(project=self.project, page_number=1)
        self.assertIn("Crée une illustration", page.generation_prompt)

    @patch("projects.views._build_ai_client")
    def test_generate_page_images_uses_pivot_language_when_present(self, mock_build_ai_client):
        fake_client = FakeImageClient()
        mock_build_ai_client.return_value = fake_client
        self.project.language = "am"
        self.project.target_language = "fr"
        self.project.page_image_text_source = "translation"
        self.project.image_generation_pivot_language = "de"
        self.project.save(
            update_fields=[
                "language",
                "target_language",
                "page_image_text_source",
                "image_generation_pivot_language",
                "updated_at",
            ]
        )
        self.client.get(reverse("project-image-pages", args=[self.project.pk]))

        payload = self._page_form_payload()
        payload["action"] = "generate_images"
        payload["image_model"] = "gpt-image-1"
        self.client.post(
            reverse("project-image-pages", args=[self.project.pk]),
            payload,
            follow=True,
        )
        page = ProjectImagePage.objects.get(project=self.project, page_number=1)
        self.assertIn("Erstelle eine einzelne illustrierte Geschichten-Seite", page.generation_prompt)

    @patch("projects.views._build_ai_client")
    def test_generate_page_images_logs_timeout_telemetry(self, mock_build_ai_client):
        mock_build_ai_client.return_value = TimeoutImageClient()
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
        msgs = [m.message for m in get_messages(resp.wsgi_request)]
        self.assertTrue(any("Generated 0 page image variant(s)" in msg for msg in msgs))

        telemetry_path = self.project.artifact_dir() / "images" / "pages" / "telemetry.jsonl"
        lines = [json.loads(line) for line in telemetry_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        timeout_events = [line for line in lines if line.get("event") == "page_image_timeout"]
        self.assertTrue(timeout_events)
        self.assertTrue(all(event.get("is_timeout") is True for event in timeout_events))
        failed_variants = list(ProjectImagePageVariant.objects.filter(page__project=self.project, image_path=""))
        self.assertTrue(failed_variants)
        self.assertTrue(any((variant.image_revised_prompt or "").startswith("ERROR:") for variant in failed_variants))
        self.assertContains(resp, "Image generation failed:")
        self.assertContains(resp, "ERROR:")

    @patch("projects.views._build_ai_client")
    def test_generate_page_images_retries_once_after_moderation_block(self, mock_build_ai_client):
        fake_client = ModerationRetryImageClient()
        mock_build_ai_client.return_value = fake_client
        self.client.get(reverse("project-image-pages", args=[self.project.pk]))
        payload = self._page_form_payload()
        payload["action"] = "generate_images"
        payload["image_model"] = "gpt-image-1"
        resp = self.client.post(reverse("project-image-pages", args=[self.project.pk]), payload, follow=True)
        self.assertEqual(resp.status_code, 200)
        msgs = [m.message for m in get_messages(resp.wsgi_request)]
        self.assertTrue(any("Generated 2 page image variant(s)" in msg for msg in msgs))
        telemetry_path = self.project.artifact_dir() / "images" / "pages" / "telemetry.jsonl"
        lines = [json.loads(line) for line in telemetry_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        blocked_events = [line for line in lines if line.get("event") == "page_image_moderation_blocked"]
        retry_events = [line for line in lines if line.get("event") == "page_image_retry_success"]
        self.assertTrue(blocked_events)
        self.assertTrue(retry_events)

    def test_discourage_text_guideline_known_language_mentions_signs_and_sfx(self):
        guideline = views._discourage_text_guideline_for_language("en")
        self.assertIn("meaningful sign", guideline)
        self.assertIn("comic-style sound effects", guideline)

    @patch("projects.views._build_ai_client")
    def test_discourage_text_guideline_unknown_language_uses_cached_ai_translation(self, mock_build_ai_client):
        class FakeTranslator:
            def __init__(self):
                self.calls = 0

            async def chat_text(self, prompt, **kwargs):  # noqa: ARG002
                self.calls += 1
                return "Texte minimal; autoriser seulement les panneaux importants."

        fake_translator = FakeTranslator()
        mock_build_ai_client.return_value = fake_translator
        views._translate_discourage_text_guideline.cache_clear()

        first = views._discourage_text_guideline_for_language("eo")
        second = views._discourage_text_guideline_for_language("eo")
        self.assertEqual(first, second)
        self.assertIn("panneaux importants", first)
        self.assertEqual(fake_translator.calls, 1)
