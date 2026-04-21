from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse

from projects import views
from projects.models import Profile, Project


class _StubProjectCreateClient:
    def __init__(self, payload):
        self.payload = payload

    async def chat_json(self, _prompt, model=None):
        return self.payload


class ProjectDialogueEntryTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="dialogue_user", password="pw")
        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])
        Profile.objects.create(user=self.user, timezone="UTC", dialogue_language="en")
        self.client = Client()
        self.client.login(username="dialogue_user", password="pw")
        self.project = Project.objects.create(
            owner=self.user,
            title="Elephant Story",
            source_text="source",
            language="fr",
            target_language="en",
            discovery_keywords=["éléphant", "cirque"],
            discovery_keywords_en=["elephant", "circus"],
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
        profile_obj = Profile.objects.get(user=self.user)
        self.assertEqual(profile_obj.dialogue_memory.get("project_open", {}).get("last_nl_query"), "open my french elephant project")

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
        profile_obj = Profile.objects.get(user=self.user)
        self.assertEqual(profile_obj.dialogue_memory.get("project_create", {}).get("last_nl_query"), "Create an English project with French glosses from a short description")

    @patch("projects.views._parse_nl_project_open_request")
    def test_project_list_keyword_match_uses_discovery_keywords(self, mock_parse):
        mock_parse.return_value = {
            "title": "",
            "text_language": "",
            "annotation_language": "",
            "keywords": ["elephant"],
        }
        resp = self.client.get(
            reverse("project-list"),
            {"nl_open_query": "open project about elephant", "dialogue_language": "en"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Elephant Story")

    @patch("projects.views._parse_nl_project_open_request")
    def test_project_open_parsing_receives_previous_profile_context(self, mock_parse):
        profile_obj = Profile.objects.get(user=self.user)
        profile_obj.dialogue_memory = {
            "project_open": {
                "last_nl_query": "Open my French project",
                "last_nl_plan": {"text_language": "fr"},
            }
        }
        profile_obj.save(update_fields=["dialogue_memory", "updated_at"])
        mock_parse.return_value = {"title": "", "text_language": "fr", "annotation_language": "", "keywords": []}
        self.client.get(reverse("project-list"), {"nl_open_query": "now open the elephant one"})
        kwargs = mock_parse.call_args.kwargs
        self.assertEqual(kwargs.get("previous_query"), "Open my French project")
        self.assertEqual(kwargs.get("previous_plan"), {"text_language": "fr"})

    def test_admin_only_backfill_keywords_command(self):
        self.project.discovery_keywords = []
        self.project.discovery_keywords_en = []
        self.project.discovery_word_count = 0
        self.project.discovery_metadata_updated_at = None
        self.project.save(
            update_fields=[
                "discovery_keywords",
                "discovery_keywords_en",
                "discovery_word_count",
                "discovery_metadata_updated_at",
                "updated_at",
            ]
        )
        call_command("backfill_project_discovery_keywords", admin_username="dialogue_user")
        self.project.refresh_from_db()
        self.assertTrue(self.project.discovery_keywords)
        self.assertTrue(self.project.discovery_keywords_en)

    def test_postprocess_project_open_plan_maps_language_mentions_to_filter(self):
        parsed = {
            "title": "German project",
            "text_language": "non",
            "annotation_language": "",
            "keywords": [],
        }
        normalized = views._postprocess_project_open_plan(
            nl_query="Where is my German project?",
            parsed=parsed,
        )
        self.assertEqual(normalized["text_language"], "de")
        self.assertEqual(normalized["title"], "")

    @patch("projects.views._build_ai_client")
    def test_nl_project_create_prefers_dialogue_language_for_gloss_when_not_explicit(self, mock_build_client):
        mock_build_client.return_value = _StubProjectCreateClient(
            {
                "title": "Draft",
                "language": "en",
                "target_language": "en",
                "input_mode": "description",
                "description": "draft",
                "source_text": "",
            }
        )
        plan = views._parse_nl_project_create_request(
            nl_query="Create an English project from a short description",
            dialogue_language="de",
        )
        self.assertEqual(plan.get("language"), "en")
        self.assertEqual(plan.get("target_language"), "de")
