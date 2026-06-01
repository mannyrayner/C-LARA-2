import tempfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.project_understanding import ProjectUnderstandingAnswer
from projects.models import Community, CommunityMembership


class AdminToolsViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.staff_user = User.objects.create_user(username="staffer", password="pw", is_staff=True)
        self.normal_user = User.objects.create_user(username="normal", password="pw")
        self.target_user = User.objects.create_user(username="target", password="pw")
        self.client = Client()

    def test_non_admin_cannot_access_admin_tools(self):
        self.client.login(username="normal", password="pw")
        resp = self.client.get(reverse("admin-tools"))
        self.assertEqual(resp.status_code, 404)

    def test_admin_tools_links_project_understanding_assistant(self):
        self.client.login(username="staffer", password="pw")
        resp = self.client.get(reverse("admin-tools"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, reverse("admin-project-understanding"))

    def test_non_admin_cannot_access_project_understanding_assistant(self):
        self.client.login(username="normal", password="pw")
        resp = self.client.get(reverse("admin-project-understanding"))
        self.assertEqual(resp.status_code, 404)

    def test_admin_can_open_project_understanding_assistant(self):
        self.client.login(username="staffer", password="pw")
        resp = self.client.get(reverse("admin-project-understanding"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Project-understanding assistant")
        self.assertContains(resp, "Ask Codex")

    @override_settings(
        OPENAI_API_KEY="test-key",
        PROJECT_UNDERSTANDING_REPOSITORY_PATH="/srv/C-LARA-2",
        PROJECT_UNDERSTANDING_CODEX_EXECUTABLE="codex-test",
        PROJECT_UNDERSTANDING_MODEL="gpt-5.3-codex",
        PROJECT_UNDERSTANDING_TIMEOUT_SECONDS=12,
    )
    @patch("projects.views.answer_project_understanding_question_with_codex_exec")
    def test_admin_can_call_project_understanding_assistant(self, mock_answer):
        mock_answer.return_value = ProjectUnderstandingAnswer(
            question="What is C-LARA-2?",
            prompt="Wrapped prompt",
            answer="C-LARA-2 is a repository-grounded platform answer.",
            model="gpt-5.3-codex",
            prompt_version="project-understanding-v1",
            requested_at="2026-06-01T10:00:00Z",
            tokens_used=1234,
            elapsed_seconds=2.5,
            invocation_route="codex-exec",
            repository_path="/srv/C-LARA-2",
            returncode=0,
        )
        self.client.login(username="staffer", password="pw")

        resp = self.client.post(
            reverse("admin-project-understanding"),
            {"question": "What is C-LARA-2?"},
        )

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "C-LARA-2 is a repository-grounded platform answer.")
        self.assertContains(resp, "1234")
        self.assertContains(resp, "2.50")
        mock_answer.assert_called_once_with(
            "What is C-LARA-2?",
            repository_path="/srv/C-LARA-2",
            codex_executable="codex-test",
            model="gpt-5.3-codex",
            timeout_seconds=12.0,
            openai_api_key="test-key",
        )

    def test_admin_can_grant_admin_privileges(self):
        self.client.login(username="staffer", password="pw")
        resp = self.client.post(
            reverse("admin-tools"),
            {"action": "grant_admin", "user": self.target_user.id},
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.target_user.refresh_from_db()
        self.assertTrue(self.target_user.is_staff)

    def test_admin_can_delete_language_audio_cache(self):
        self.client.login(username="staffer", password="pw")
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            cache_dir = root / "audio_repository" / "de"
            cache_dir.mkdir(parents=True, exist_ok=True)
            (cache_dir / "de_test.wav").write_bytes(b"123")

            with override_settings(MEDIA_ROOT=root):
                resp = self.client.post(
                    reverse("admin-tools"),
                    {"action": "delete_audio_cache", "language": "de"},
                    follow=True,
                )
                self.assertEqual(resp.status_code, 200)
                self.assertFalse(cache_dir.exists())

    def test_admin_can_create_community_from_admin_tools(self):
        self.client.login(username="staffer", password="pw")
        resp = self.client.post(
            reverse("admin-tools"),
            {
                "action": "create_community",
                "name": "Drehu language community",
                "language": "dre",
                "description": "First-cut test community",
                "is_active": "on",
            },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Drehu language community")

    def test_admin_tools_community_language_is_dropdown(self):
        self.client.login(username="staffer", password="pw")
        resp = self.client.get(reverse("admin-tools"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "name=\"language\"")
        self.assertContains(resp, "<option value=\"en\" selected>English</option>", html=True)

    def test_admin_can_assign_user_as_community_organiser(self):
        self.client.login(username="staffer", password="pw")
        create = self.client.post(
            reverse("admin-tools"),
            {
                "action": "create_community",
                "name": "Iaai language community",
                "language": "iai",
                "description": "Community for Iaai projects",
                "is_active": "on",
            },
            follow=True,
        )
        self.assertEqual(create.status_code, 200)
        community_id = Community.objects.get(name="Iaai language community").pk

        assign = self.client.post(
            reverse("admin-tools"),
            {
                "action": "assign_community_role",
                "community": community_id,
                "user": self.target_user.id,
                "role": "organiser",
            },
            follow=True,
        )
        self.assertEqual(assign.status_code, 200)
        membership = CommunityMembership.objects.get(user=self.target_user, community_id=community_id)
        self.assertEqual(membership.role, CommunityMembership.ROLE_ORGANISER)

    def test_admin_can_delete_community_from_admin_tools(self):
        self.client.login(username="staffer", password="pw")
        community = Community.objects.create(name="Delete me", language="en")
        resp = self.client.post(
            reverse("admin-tools"),
            {
                "action": "delete_community",
                "community": community.pk,
            },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Community.objects.filter(pk=community.pk).exists())

    @patch("projects.views.call_command")
    def test_admin_tools_can_trigger_discovery_keyword_backfill(self, mock_call_command):
        self.client.login(username="staffer", password="pw")
        resp = self.client.post(
            reverse("admin-tools"),
            {"action": "backfill_project_discovery_keywords", "force_backfill_keywords": "1"},
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        mock_call_command.assert_called_once_with(
            "backfill_project_discovery_keywords",
            admin_username="staffer",
            force=True,
        )


@override_settings(BOOTSTRAP_ADMIN_USERNAMES=["bootstrap"])
class BootstrapAdminRegistrationTests(TestCase):
    def test_bootstrap_user_gets_staff_on_registration(self):
        resp = self.client.post(
            reverse("register"),
            {
                "username": "bootstrap",
                "email": "bootstrap@example.com",
                "password1": "StrongPass123",
                "password2": "StrongPass123",
            },
        )
        self.assertEqual(resp.status_code, 302)
        user = get_user_model().objects.get(username="bootstrap")
        self.assertTrue(user.is_staff)
