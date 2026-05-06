from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
import re

from projects.models import IssueSuggestion


class IssueSuggestionTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="suggest_user", password="pw")
        self.admin = user_model.objects.create_user(username="suggest_admin", password="pw", is_staff=True)

    def test_authenticated_user_can_open_issues_home(self):
        client = Client()
        client.login(username="suggest_user", password="pw")
        response = client.get(reverse("issues-home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Open current issues overview")
        self.assertContains(response, "Suggest an issue")
        self.assertContains(response, reverse("issue-suggestion-submit"))
        self.assertContains(response, "https://github.com/mannyrayner/C-LARA-2/blob/main/docs/issues/overview.md")
        self.assertContains(response, 'target="_blank"')
        self.assertNotContains(response, "## Focus order")

    def test_authenticated_user_can_submit_suggestion(self):
        client = Client()
        client.login(username="suggest_user", password="pw")
        response = client.post(
            reverse("issue-suggestion-submit"),
            {"title": "Potential issue", "description": "Something looks wrong."},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        suggestion = IssueSuggestion.objects.get()
        self.assertEqual(suggestion.title, "Potential issue")
        self.assertEqual(suggestion.submitter, self.user)
        self.assertEqual(suggestion.status, IssueSuggestion.STATUS_NEW)

    def test_authenticated_user_can_open_issues_overview_page(self):
        client = Client()
        client.login(username="suggest_user", password="pw")
        response = client.get(reverse("issues-home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Issues")
        self.assertContains(response, "Suggest an issue")

    def test_non_admin_cannot_open_admin_suggestion_list(self):
        client = Client()
        client.login(username="suggest_user", password="pw")
        response = client.get(reverse("admin-issue-suggestions"))
        self.assertEqual(response.status_code, 404)

    def test_admin_can_view_admin_suggestion_list(self):
        IssueSuggestion.objects.create(
            title="Title",
            description="Description",
            submitter=self.user,
        )
        client = Client()
        client.login(username="suggest_admin", password="pw")
        response = client.get(reverse("admin-issue-suggestions"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Issue suggestions")
        self.assertContains(response, "Title")
        self.assertContains(response, "Prepared text for Codex")
        self.assertContains(response, "docs/roadmap/issue-tracking-and-human-suggestions.md")
        self.assertContains(response, "Suggestion 1")

    def test_admin_can_remove_currently_displayed_suggestions_without_removing_new_ones(self):
        first = IssueSuggestion.objects.create(title="Old 1", description="D1", submitter=self.user)
        second = IssueSuggestion.objects.create(title="Old 2", description="D2", submitter=self.user)
        client = Client()
        client.login(username="suggest_admin", password="pw")
        response = client.get(reverse("admin-issue-suggestions"))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        match = re.search(r'name="displayed_suggestion_ids" value="([^"]*)"', html)
        self.assertIsNotNone(match)
        displayed_ids = match.group(1)
        self.assertIn(str(first.id), displayed_ids)
        self.assertIn(str(second.id), displayed_ids)

        new_after_display = IssueSuggestion.objects.create(title="New", description="D3", submitter=self.user)
        client.post(
            reverse("admin-issue-suggestions"),
            {"action": "clear_displayed", "displayed_suggestion_ids": displayed_ids},
            follow=True,
        )
        remaining_titles = list(IssueSuggestion.objects.order_by("id").values_list("title", flat=True))
        self.assertEqual(remaining_titles, [new_after_display.title])
