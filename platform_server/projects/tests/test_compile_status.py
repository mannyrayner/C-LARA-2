import os
import uuid
from pathlib import Path
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import Client, TestCase
from django.urls import reverse

from projects import views
from projects.models import Project, TaskUpdate


class CompileStatusViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="tester", password="pw")
        self.project = Project.objects.create(
            owner=self.user,
            title="Test Project",
            source_text="Hello",
            language="en",
            target_language="fr",
        )
        self.client = Client()
        self.client.login(username="tester", password="pw")
        self.report_id = uuid.uuid4()

    def test_status_returns_updates_and_marks_read(self):
        TaskUpdate.objects.create(
            report_id=self.report_id,
            user=self.user,
            task_type="compile_project",
            message="stage1",
            status="running",
        )
        url = reverse(
            "project-compile-status", args=[self.project.pk, self.report_id]
        )
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["messages"], ["stage1"])
        self.assertEqual(data["status"], "running")
        self.assertTrue(
            TaskUpdate.objects.filter(report_id=self.report_id, read=True).exists()
        )

    def test_status_reports_completion_without_new_updates(self):
        TaskUpdate.objects.create(
            report_id=self.report_id,
            user=self.user,
            task_type="compile_project",
            message="done",
            status="finished",
            read=True,
        )
        url = reverse(
            "project-compile-status", args=[self.project.pk, self.report_id]
        )
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "finished")

    def test_status_adds_error_message_for_project_page(self):
        TaskUpdate.objects.create(
            report_id=self.report_id,
            user=self.user,
            task_type="compile_project",
            message="Compile failed: timeout",
            status="error",
        )
        url = reverse(
            "project-compile-status", args=[self.project.pk, self.report_id]
        )

        resp = self.client.get(url)
        self.assertEqual(resp.json()["status"], "error")

        msgs = list(get_messages(resp.wsgi_request))
        self.assertEqual(len(msgs), 1)
        self.assertIn("timeout", msgs[0].message)

    def test_make_task_callback_handles_missing_task_type(self):
        post_update, rep_id = views._make_task_callback(None, self.user.id)
        post_update("hello", status="running")

        update = TaskUpdate.objects.get(report_id=rep_id)
        self.assertEqual(update.message, "hello")
        self.assertEqual(update.task_type, "compile_project")
        self.assertEqual(update.status, "running")

    @patch("projects.views.async_task")
    def test_partial_recompile_reuses_prior_run_artifacts(self, mock_async_task):
        base = self.project.artifact_dir()
        run_old = base / "runs" / "run_older"
        run_newer = base / "runs" / "run_newer"
        for run_dir in (run_old, run_newer):
            (run_dir / "stages").mkdir(parents=True, exist_ok=True)
        # Older run has upstream stage output; newer run only has downstream data.
        (run_old / "stages" / "lemma.json").write_text("{\"lemma\": true}", encoding="utf-8")
        (run_newer / "stages" / "compile_html.json").write_text("{}", encoding="utf-8")
        os.utime(run_old, (1, 1))
        os.utime(run_newer, (2, 2))

        existing_runs = set(Path(base / "runs").glob("run_*"))

        url = reverse("project-compile", args=[self.project.pk])
        resp = self.client.post(url, {"start_stage": "gloss"})
        self.assertEqual(resp.status_code, 302)

        runs_after = set(Path(base / "runs").glob("run_*"))
        new_runs = runs_after - existing_runs
        self.assertEqual(len(new_runs), 1)
        new_run = new_runs.pop()

        copied_stage = new_run / "stages" / "lemma.json"
        self.assertTrue(copied_stage.exists())
        self.assertEqual(copied_stage.read_text(encoding="utf-8"), "{\"lemma\": true}")

        # Ensure we scheduled the compile task using the new run directory.
        self.assertTrue(mock_async_task.called)
        args, kwargs = mock_async_task.call_args
        self.assertIn(str(new_run), args)

    @patch("projects.views.async_task")
    def test_compile_passes_selected_model(self, mock_async_task):
        url = reverse("project-compile", args=[self.project.pk])
        resp = self.client.post(url, {"start_stage": "segmentation_phase_1", "ai_model": "gpt-5"})
        self.assertEqual(resp.status_code, 302)

        self.project.refresh_from_db()
        self.assertEqual(self.project.ai_model, "gpt-5")

        args, kwargs = mock_async_task.call_args
        self.assertIn("gpt-5", args)
