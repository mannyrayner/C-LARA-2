from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse

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
        self.assertEqual(self.project.discovery_level, "A1-A2")
        self.assertEqual(self.project.discovery_word_count, 42)

    def test_backfill_command_updates_published_projects_missing_metadata(self):
        self.project.is_published = True
        self.project.published_at = self.project.created_at
        self.project.discovery_summary = ""
        self.project.discovery_keywords = []
        self.project.discovery_level = ""
        self.project.discovery_word_count = 0
        self.project.save(
            update_fields=[
                "is_published",
                "published_at",
                "discovery_summary",
                "discovery_keywords",
                "discovery_level",
                "discovery_word_count",
                "updated_at",
            ]
        )

        call_command("backfill_published_metadata")
        self.project.refresh_from_db()
        self.assertTrue(self.project.discovery_summary)
        self.assertTrue(self.project.discovery_keywords)
        self.assertGreater(self.project.discovery_word_count, 0)
