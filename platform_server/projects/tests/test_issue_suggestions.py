from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from projects.models import IssueSuggestion, IssueUpdateSuggestion


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
        self.assertContains(response, "Suggest a new issue")
        self.assertContains(response, reverse("issue-suggestion-submit"))
        self.assertContains(response, "Suggest an update to an existing issue")
        self.assertContains(response, reverse("issue-update-suggestion-submit"))
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

    def test_authenticated_user_can_submit_issue_update_suggestion(self):
        client = Client()
        client.login(username="suggest_user", password="pw")
        response = client.post(
            reverse("issue-update-suggestion-submit"),
            {"issue_id": "ISSUE-0003", "update_description": "Clarify the test-runner scope."},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        update_suggestion = IssueUpdateSuggestion.objects.get()
        self.assertEqual(update_suggestion.issue_id, "ISSUE-0003")
        self.assertEqual(
            update_suggestion.issue_title,
            "Add efficient end-to-end pipeline test runner for systematic quality checks",
        )
        self.assertEqual(update_suggestion.submitter, self.user)
        self.assertEqual(update_suggestion.status, IssueUpdateSuggestion.STATUS_NEW)

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
        IssueUpdateSuggestion.objects.create(
            issue_id="ISSUE-0003",
            issue_title="Add efficient end-to-end pipeline test runner for systematic quality checks",
            update_description="Clarify the test-runner scope.",
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
        self.assertContains(response, "New issue suggestion 1")
        self.assertContains(response, "Existing issue update suggestions")
        self.assertContains(response, "Existing issue update suggestion 1")
        self.assertContains(
            response,
            "ISSUE-0003: Add efficient end-to-end pipeline test runner for systematic quality checks",
        )
        self.assertContains(response, "Clarify the test-runner scope.")
