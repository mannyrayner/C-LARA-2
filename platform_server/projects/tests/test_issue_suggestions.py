from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from projects.models import IssueSuggestion


class IssueSuggestionTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="suggest_user", password="pw")
        self.admin = user_model.objects.create_user(username="suggest_admin", password="pw", is_staff=True)

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
