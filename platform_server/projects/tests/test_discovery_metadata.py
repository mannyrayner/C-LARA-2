import json

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse
from unittest.mock import patch

from projects import metadata
from projects.models import Project


class DiscoveryMetadataTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="meta_user", password="pw")
        self.client = Client()
        self.client.login(username="meta_user", password="pw")
        self.project = Project.objects.create(
            owner=self.user,
            title="Metadata Story",
            source_text="This is a short story. It has simple words and short sentences.",
            language="en",
            target_language="fr",
        )

    def test_publish_generates_discovery_metadata(self):
        resp = self.client.get(reverse("project-publish", args=[self.project.pk]), follow=True)
        self.assertEqual(resp.status_code, 200)
        self.project.refresh_from_db()
        self.assertTrue(self.project.is_published)
        self.assertGreater(self.project.discovery_word_count, 0)
        self.assertTrue(self.project.discovery_summary)
        self.assertTrue(self.project.discovery_level)
        self.assertRegex(self.project.discovery_level, r"^(A1|A2|B1|B2|C1|C2)(/(A1|A2|B1|B2|C1|C2))?$")
        self.assertIsNotNone(self.project.discovery_metadata_updated_at)

    def test_owner_can_edit_discovery_metadata(self):
        resp = self.client.post(
            reverse("project-discovery-metadata", args=[self.project.pk]),
            {
                "action": "save",
                "discovery_summary": "Manual summary",
                "discovery_keywords": "dialogue, beginner, story",
                "discovery_level": "A1-A2",
                "discovery_word_count": "42",
            },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.project.refresh_from_db()
        self.assertEqual(self.project.discovery_summary, "Manual summary")
        self.assertEqual(self.project.discovery_keywords, ["dialogue", "beginner", "story"])
        self.assertEqual(self.project.discovery_keywords_en, [])
        self.assertEqual(self.project.discovery_level, "A1/A2")
        self.assertEqual(self.project.discovery_word_count, 42)

    def test_backfill_command_updates_published_projects_missing_metadata(self):
        self.project.is_published = True
        self.project.published_at = self.project.created_at
        self.project.discovery_summary = ""
        self.project.discovery_keywords = []
        self.project.discovery_keywords_en = []
        self.project.discovery_level = ""
        self.project.discovery_word_count = 0
        self.project.save(
            update_fields=[
                "is_published",
                "published_at",
                "discovery_summary",
                "discovery_keywords",
                "discovery_keywords_en",
                "discovery_level",
                "discovery_word_count",
                "updated_at",
            ]
        )

        call_command("backfill_published_metadata")
        self.project.refresh_from_db()
        self.assertTrue(self.project.discovery_summary)
        self.assertTrue(self.project.discovery_keywords)
        self.assertTrue(self.project.discovery_keywords_en)
        self.assertGreater(self.project.discovery_word_count, 0)

    def test_metadata_prefers_latest_text_gen_surface_over_initial_description(self):
        self.project.description = "Write a story about a dragon and a mountain village."
        self.project.source_text = ""
        self.project.save(update_fields=["description", "source_text", "updated_at"])
        stage_dir = self.project.artifact_dir() / "runs" / "run_demo" / "stages"
        stage_dir.mkdir(parents=True, exist_ok=True)
        (stage_dir / "text_gen.json").write_text(
            '{"surface": "Lina visits the village. She meets a dragon near the river."}',
            encoding="utf-8",
        )

        self.client.get(reverse("project-publish", args=[self.project.pk]), follow=True)
        self.project.refresh_from_db()
        self.assertGreater(self.project.discovery_word_count, 0)
        # Prompt-only terms from description should not dominate when generated surface exists.
        self.assertNotIn("mountain", [kw.lower() for kw in self.project.discovery_keywords])
        self.assertIn("village", [kw.lower() for kw in self.project.discovery_keywords])

    @patch("projects.metadata._generate_keywords_with_ai")
    @patch("projects.metadata._translate_keywords_to_english_with_ai")
    @patch("projects.metadata._generate_summary_with_ai")
    def test_publish_uses_ai_summary_and_keywords_when_available(self, mock_ai_summary, mock_ai_translate, mock_ai_keywords):
        mock_ai_summary.return_value = "A concise AI summary with punctuation."
        mock_ai_keywords.return_value = ["milo", "forest", "mink"]
        mock_ai_translate.return_value = []
        self.client.get(reverse("project-publish", args=[self.project.pk]), follow=True)
        self.project.refresh_from_db()
        self.assertEqual(self.project.discovery_summary, "A concise AI summary with punctuation.")
        self.assertEqual(self.project.discovery_keywords, ["milo", "forest", "mink"])
        self.assertEqual(self.project.discovery_keywords_en, ["milo", "forest", "mink"])
        self.assertTrue(mock_ai_summary.called)
        self.assertTrue(mock_ai_keywords.called)

    @patch("projects.metadata._generate_keywords_with_ai")
    @patch("projects.metadata._generate_summary_with_ai")
    def test_ai_summary_and_keywords_receive_text_gen_surface(self, mock_ai_summary, mock_ai_keywords):
        mock_ai_summary.return_value = "Summary from AI."
        mock_ai_keywords.return_value = ["lina", "dragon", "village"]
        self.project.description = "Prompt text only."
        self.project.source_text = ""
        self.project.save(update_fields=["description", "source_text", "updated_at"])
        stage_dir = self.project.artifact_dir() / "runs" / "run_demo" / "stages"
        stage_dir.mkdir(parents=True, exist_ok=True)
        surface = "Lina meets a dragon in the village square."
        (stage_dir / "text_gen.json").write_text(json.dumps({"surface": surface}), encoding="utf-8")

        self.client.get(reverse("project-publish", args=[self.project.pk]), follow=True)
        summary_args = mock_ai_summary.call_args[0]
        keyword_args = mock_ai_keywords.call_args[0]
        self.assertIn(surface, summary_args[1])
        self.assertIn(surface, keyword_args[1])

    def test_project_detail_renders_keywords_as_comma_separated_text(self):
        self.project.discovery_keywords = ["milo", "forest", "safe"]
        self.project.save(update_fields=["discovery_keywords", "updated_at"])
        resp = self.client.get(reverse("project-detail", args=[self.project.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'value="milo, forest, safe"')

    def test_parse_keywords_response_accepts_markdown_embedded_json(self):
        response = 'Here are keywords:\n```json\n["milo", "forest", "safe"]\n```'
        parsed = metadata._parse_keywords_response(response)
        self.assertEqual(parsed, ["milo", "forest", "safe"])

    def test_parse_keywords_response_accepts_plain_comma_list(self):
        response = "milo, forest, safe, clever mink"
        parsed = metadata._parse_keywords_response(response)
        self.assertEqual(parsed, ["milo", "forest", "safe", "clever mink"])

    @patch("projects.metadata._generate_keywords_with_ai")
    @patch("projects.metadata._translate_keywords_to_english_with_ai")
    @patch("projects.metadata._generate_summary_with_ai")
    def test_non_english_project_stores_english_keyword_translations(self, mock_ai_summary, mock_ai_translate, mock_ai_keywords):
        self.project.language = "fr"
        self.project.save(update_fields=["language", "updated_at"])
        mock_ai_summary.return_value = "Résumé."
        mock_ai_keywords.return_value = ["éléphant", "funambule", "cirque"]
        mock_ai_translate.return_value = ["elephant", "tightrope walker", "circus"]
        self.client.get(reverse("project-publish", args=[self.project.pk]), follow=True)
        self.project.refresh_from_db()
        self.assertEqual(self.project.discovery_keywords, ["éléphant", "funambule", "cirque"])
        self.assertEqual(self.project.discovery_keywords_en, ["elephant", "tightrope walker", "circus"])
