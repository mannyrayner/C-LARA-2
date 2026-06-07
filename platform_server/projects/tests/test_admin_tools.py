import tempfile
import uuid
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.project_understanding import ProjectUnderstandingAnswer
from projects import views
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

    def test_top_nav_links_project_understanding_assistant(self):
        self.client.login(username="normal", password="pw")
        resp = self.client.get(reverse("project-list"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, reverse("project-understanding"))

    def test_normal_user_can_access_project_understanding_assistant(self):
        self.client.login(username="normal", password="pw")
        resp = self.client.get(reverse("project-understanding"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Project-understanding assistant")

    def test_staff_can_open_project_understanding_assistant(self):
        self.client.login(username="staffer", password="pw")
        resp = self.client.get(reverse("project-understanding"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Project-understanding assistant")
        self.assertContains(resp, "Ask Codex")

    def test_admin_tools_no_longer_links_project_understanding_assistant(self):
        self.client.login(username="staffer", password="pw")

        resp = self.client.get(reverse("admin-tools"))

        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, reverse("admin-project-understanding"))
        self.assertNotContains(resp, "Project-understanding assistant")

    def test_legacy_admin_project_understanding_url_redirects_to_assistant(self):
        self.client.login(username="normal", password="pw")

        resp = self.client.get(reverse("admin-project-understanding"))

        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp["Location"], reverse("project-understanding"))

    def test_project_understanding_monitor_form_posts_to_new_request_endpoint(self):
        self.client.login(username="staffer", password="pw")
        report_id = uuid.uuid4()

        with tempfile.TemporaryDirectory() as tmpdir, override_settings(MEDIA_ROOT=tmpdir):
            from projects.views import _write_project_understanding_request

            _write_project_understanding_request(
                report_id,
                "What is C-LARA-2?",
                user_id=self.staff_user.id,
                username=self.staff_user.username,
                visibility="private",
            )
            resp = self.client.get(reverse("project-understanding-monitor", args=[report_id]))

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, f'action="{reverse("project-understanding")}"')

    @patch("projects.views.async_task")
    def test_normal_user_can_queue_project_understanding_assistant(self, mock_async_task):
        self.client.login(username="normal", password="pw")

        with tempfile.TemporaryDirectory() as tmpdir, override_settings(MEDIA_ROOT=tmpdir):
            resp = self.client.post(
                reverse("project-understanding"),
                {"question": "What is C-LARA-2?", "visibility": "public"},
            )

        self.assertEqual(resp.status_code, 302)
        self.assertIn("/assistant/project-understanding/", resp["Location"])
        mock_async_task.assert_called_once()
        task_args = mock_async_task.call_args.args
        self.assertEqual("projects.views._run_project_understanding_task", task_args[0])
        self.assertEqual("What is C-LARA-2?", task_args[1])
        self.assertEqual(self.normal_user.id, task_args[2])
        self.assertTrue(TaskUpdate.objects.filter(user=self.normal_user, message="Project-understanding request queued.").exists())

    def test_project_understanding_turn_listing_respects_visibility(self):
        User = get_user_model()
        other_user = User.objects.create_user(username="other_user", password="pw")
        private_report_id = uuid.uuid4()
        public_report_id = uuid.uuid4()
        with tempfile.TemporaryDirectory() as tmpdir, override_settings(MEDIA_ROOT=tmpdir):
            from projects.views import _list_project_understanding_turns, _write_project_understanding_request

            _write_project_understanding_request(
                private_report_id,
                "Private question",
                user_id=self.staff_user.id,
                username=self.staff_user.username,
                visibility="private",
            )
            _write_project_understanding_request(
                public_report_id,
                "Public question",
                user_id=self.staff_user.id,
                username=self.staff_user.username,
                visibility="public",
            )

            visible_to_owner = {turn["question"] for turn in _list_project_understanding_turns(self.staff_user)}
            visible_to_other = {turn["question"] for turn in _list_project_understanding_turns(other_user)}

        self.assertIn("Private question", visible_to_owner)
        self.assertIn("Public question", visible_to_owner)
        self.assertNotIn("Private question", visible_to_other)
        self.assertIn("Public question", visible_to_other)

    def test_project_understanding_answer_markdown_is_rendered_safely(self):
        from projects.views import render_project_understanding_answer_html

        with override_settings(
            PROJECT_UNDERSTANDING_REPOSITORY_PATH="C:/cygwin64/home/github/c-lara-2",
            PROJECT_UNDERSTANDING_GITHUB_BLOB_BASE_URL="https://github.com/mannyrayner/C-LARA-2/blob/main",
        ):
            html = render_project_understanding_answer_html(
                "See [docs](C:/cygwin64/home/github/c-lara-2/docs/roadmap/platform-self-knowledge-assistant.md), "
                "[code](C:/cygwin64/home/github/c-lara-2/src/core/project_understanding.py), "
                "[line](C:/cygwin64/home/github/c-lara-2/README.md:3), "
                "and `Token`.\n"
                "- ignores [unsafe](javascript:alert(1))"
            )

        self.assertIn("https://github.com/mannyrayner/C-LARA-2/blob/main/docs/roadmap/platform-self-knowledge-assistant.md", html)
        self.assertIn("https://github.com/mannyrayner/C-LARA-2/blob/main/src/core/project_understanding.py", html)
        self.assertIn("https://github.com/mannyrayner/C-LARA-2/blob/main/README.md#L3", html)
        with override_settings(
            PROJECT_UNDERSTANDING_REPOSITORY_PATH="/srv/C-LARA-2",
            PROJECT_UNDERSTANDING_GITHUB_BLOB_BASE_URL="https://github.com/mannyrayner/C-LARA-2/blob/main",
        ):
            mismatched_checkout_html = render_project_understanding_answer_html(
                "[lemma](C:\\cygwin64\\home\\github\\c-lara-2\\src\\pipeline\\lemma.py)"
            )
        self.assertIn("https://github.com/mannyrayner/C-LARA-2/blob/main/src/pipeline/lemma.py", mismatched_checkout_html)
        self.assertIn('<code>Token</code>', html)
        self.assertIn("&lt;", render_project_understanding_answer_html("<script>alert(1)</script>"))
        self.assertNotIn('href="javascript:alert(1)"', html)
        self.assertNotIn("file:///", html)

    def test_project_understanding_turns_view_searches_visible_history(self):
        self.client.login(username="staffer", password="pw")
        matching_report_id = uuid.uuid4()
        hidden_report_id = uuid.uuid4()
        with tempfile.TemporaryDirectory() as tmpdir, override_settings(MEDIA_ROOT=tmpdir):
            from projects.views import _write_project_understanding_request

            _write_project_understanding_request(
                matching_report_id,
                "How are annotated tokens represented?",
                user_id=self.staff_user.id,
                username=self.staff_user.username,
                visibility="private",
            )
            _write_project_understanding_request(
                hidden_report_id,
                "How is audio generated?",
                user_id=self.staff_user.id,
                username=self.staff_user.username,
                visibility="private",
            )

            resp = self.client.get(reverse("project-understanding-turns"), {"q": "tokens"})

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Stored project-understanding turns")
        self.assertContains(resp, "How are annotated tokens represented?")
        self.assertNotContains(resp, "How is audio generated?")

    def test_project_understanding_monitor_preserves_current_question(self):
        self.client.login(username="staffer", password="pw")
        report_id = uuid.uuid4()
        with tempfile.TemporaryDirectory() as tmpdir, override_settings(MEDIA_ROOT=tmpdir):
            from projects.views import _write_project_understanding_request

            _write_project_understanding_request(
                report_id,
                "What is the annotation format?",
                user_id=self.staff_user.id,
                username=self.staff_user.username,
                visibility="private",
            )
            resp = self.client.get(reverse("project-understanding-monitor", args=[report_id]))

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
            _write_project_understanding_request(
                report_id,
                "What is C-LARA-2?",
                user_id=self.staff_user.id,
                username=self.staff_user.username,
                visibility="private",
            )
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

            resp = self.client.get(reverse("project-understanding-status", args=[report_id]))

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


    def test_admin_tools_hides_disabled_shutdown_control(self):
        self.client.login(username="staffer", password="pw")

        resp = self.client.get(reverse("admin-tools"))

        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, "shutdown_django_stack")
        self.assertNotContains(resp, "Shutdown Django server and Q worker")

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
