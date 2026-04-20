from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from projects.models import Project


class ContentNaturalLanguageTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="nl_user", password="pw")
        self.client = Client()
        self.client.login(username="nl_user", password="pw")
        self.project = Project.objects.create(
            owner=self.user,
            title="Village Adventure",
            source_text="Story text",
            language="fr",
            target_language="en",
            is_published=True,
            published_at=timezone.now(),
            discovery_summary="A short adventure in a village market.",
            discovery_keywords=["village", "adventure", "market"],
            discovery_level="B1-B2",
        )
        self.other = Project.objects.create(
            owner=self.user,
            title="Sarah im Supermarkt",
            source_text="Story text",
            language="de",
            target_language="en",
            is_published=True,
            published_at=timezone.now(),
            discovery_summary="Shopping in a supermarket.",
            discovery_keywords=["supermarket", "shopping"],
            discovery_level="A2",
        )

    @patch("projects.views._parse_nl_content_request")
    def test_content_list_supports_nl_query_and_justifications(self, mock_parse):
        mock_parse.return_value = {
            "title": "",
            "text_language": "fr",
            "annotation_language": "en",
            "date_posted": "any",
            "level": "B1-B2",
            "keywords": ["village"],
            "max_results": 5,
        }
        resp = self.client.get(
            reverse("content-list"),
            {"nl_query": "Find me an intermediate French village story", "dialogue_language": "en"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Village Adventure")
        self.assertNotContains(resp, "Sarah im Supermarkt")
        self.assertContains(resp, "Keyword &#x27;village&#x27; matched metadata.")
        self.assertContains(resp, "Level matched (B1-B2).")

    def test_content_list_renders_language_dropdowns(self):
        resp = self.client.get(reverse("content-list"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '<select id="text_language" name="text_language">', html=False)
        self.assertContains(resp, '<select id="annotation_language" name="annotation_language">', html=False)
