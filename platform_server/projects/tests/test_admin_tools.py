import tempfile
import uuid
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.project_understanding import ProjectUnderstandingAnswer
from projects.models import Community, CommunityMembership, TaskUpdate


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

    def test_project_understanding_monitor_form_posts_to_new_request_endpoint(self):
        self.client.login(username="staffer", password="pw")
        report_id = uuid.uuid4()

        resp = self.client.get(reverse("admin-project-understanding-monitor", args=[report_id]))

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, f'action="{reverse("admin-project-understanding")}"')

    @patch("projects.views.async_task")
    def test_admin_can_queue_project_understanding_assistant(self, mock_async_task):
        self.client.login(username="staffer", password="pw")

        with tempfile.TemporaryDirectory() as tmpdir, override_settings(MEDIA_ROOT=tmpdir):
            resp = self.client.post(
                reverse("admin-project-understanding"),
                {"question": "What is C-LARA-2?"},
            )

        self.assertEqual(resp.status_code, 302)
        self.assertIn("/admin-tools/project-understanding/", resp["Location"])
        mock_async_task.assert_called_once()
        task_args = mock_async_task.call_args.args
        self.assertEqual("projects.views._run_project_understanding_task", task_args[0])
        self.assertEqual("What is C-LARA-2?", task_args[1])
        self.assertEqual(self.staff_user.id, task_args[2])
        self.assertTrue(TaskUpdate.objects.filter(user=self.staff_user, message="Project-understanding request queued.").exists())

    def test_project_understanding_monitor_preserves_current_question(self):
        self.client.login(username="staffer", password="pw")
        report_id = uuid.uuid4()
        with tempfile.TemporaryDirectory() as tmpdir, override_settings(MEDIA_ROOT=tmpdir):
            from projects.views import _write_project_understanding_request

            _write_project_understanding_request(report_id, "What is the annotation format?")
            resp = self.client.get(reverse("admin-project-understanding-monitor", args=[report_id]))

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "What is the annotation format?")

    def test_project_understanding_status_returns_messages_and_result(self):
        self.client.login(username="staffer", password="pw")
        report_id = uuid.uuid4()
        TaskUpdate.objects.create(
            report_id=report_id,
            user=self.staff_user,
            task_type="admin_project_understanding",
            message="Done",
            status="finished",
        )
        from projects.views import _write_project_understanding_request, _write_project_understanding_result

        with tempfile.TemporaryDirectory() as tmpdir, override_settings(MEDIA_ROOT=tmpdir):
            _write_project_understanding_request(report_id, "What is C-LARA-2?")
            _write_project_understanding_result(
                report_id,
                ProjectUnderstandingAnswer(
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
                ),
            )

            resp = self.client.get(reverse("admin-project-understanding-status", args=[report_id]))

        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertEqual("finished", payload["status"])
        self.assertEqual(["Done"], payload["messages"])
        self.assertEqual("C-LARA-2 is a repository-grounded platform answer.", payload["result"]["answer"])
        self.assertEqual(1234, payload["result"]["tokens_used"])
        self.assertEqual("What is C-LARA-2?", payload["question"])

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
