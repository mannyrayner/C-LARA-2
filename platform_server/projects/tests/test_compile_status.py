import os
import json
import uuid
from pathlib import Path
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import Client, TestCase
from django.urls import reverse

from projects import views
from projects.models import (
    Profile,
    Project,
    ProjectImageElement,
    ProjectImagePage,
    ProjectImageStyle,
    TaskUpdate,
)


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

    def test_task_telemetry_writes_jsonl_and_surfaces_warning(self):
        telemetry_log = (
            self.project.artifact_dir()
            / "runs"
            / "new_run"
            / "stages"
            / f"telemetry_test_{uuid.uuid4().hex}.jsonl"
        )
        captured: list[tuple[str, str | None]] = []

        def _post_update(message: str, status: str | None = None) -> None:
            captured.append((message, status))

        telemetry = views._TaskTelemetry(log_path=telemetry_log, post_update=_post_update)
        telemetry.event("op-1", "warn", "openai.chat_text response normalized", {"preview": "bad payload"})

        self.assertTrue(telemetry_log.parent.exists())
        self.assertTrue(telemetry_log.exists())
        lines = telemetry_log.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 1)
        record = json.loads(lines[0])
        self.assertEqual(record["type"], "event")
        self.assertEqual(record["op_id"], "op-1")
        self.assertEqual(record["level"], "warn")
        self.assertTrue(captured)
        self.assertIn("openai.chat_text response normalized", captured[0][0])

    def test_task_telemetry_surfaces_api_request_start_messages(self):
        telemetry_log = (
            self.project.artifact_dir()
            / "runs"
            / "new_run"
            / "stages"
            / f"telemetry_test_info_{uuid.uuid4().hex}.jsonl"
        )
        captured: list[tuple[str, str | None]] = []

        def _post_update(message: str, status: str | None = None) -> None:
            captured.append((message, status))

        telemetry = views._TaskTelemetry(log_path=telemetry_log, post_update=_post_update)
        telemetry.event("op-2", "info", "openai.chat_text request start", {"model": "gpt-5"})

        self.assertTrue(captured)
        self.assertIn("openai.chat_text request start", captured[0][0])

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

    @patch("projects.views.async_task")
    def test_compile_passes_end_stage_and_page_image_placement(self, mock_async_task):
        self.project.page_image_placement = "bottom"
        self.project.save(update_fields=["page_image_placement"])
        url = reverse("project-compile", args=[self.project.pk])
        resp = self.client.post(
            url,
            {
                "start_stage": "segmentation_phase_1",
                "end_stage": "segmentation_phase_1",
                "ai_model": "gpt-4o",
            },
        )
        self.assertEqual(resp.status_code, 302)
        args, kwargs = mock_async_task.call_args
        self.assertIn("segmentation_phase_1", args)
        self.assertIn("bottom", args)

    def test_set_page_image_placement_updates_project(self):
        url = reverse("project-image-placement", args=[self.project.pk])
        resp = self.client.post(url, {"page_image_placement": "top"})
        self.assertEqual(resp.status_code, 302)
        self.project.refresh_from_db()
        self.assertEqual(self.project.page_image_placement, "top")

    def test_project_detail_shows_image_stage_ticks(self):
        ProjectImageStyle.objects.create(
            project=self.project,
            style_brief="style",
            sample_image_path="images/style/style_sample_image.png",
            status=ProjectImageStyle.STATUS_GENERATED,
        )
        ProjectImageElement.objects.create(
            project=self.project,
            name="Celine",
            element_type="character",
            image_path="images/elements/celine/reference.png",
        )
        ProjectImagePage.objects.create(
            project=self.project,
            page_number=1,
            page_text="hello",
            image_path="images/pages/page_001/image.png",
        )

        resp = self.client.get(reverse("project-detail", args=[self.project.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Image style ✅")
        self.assertContains(resp, "Image elements ✅")
        self.assertContains(resp, "Page images ✅")

    @patch("projects.views._build_ai_client")
    @patch("projects.views.run_full_pipeline")
    def test_compile_task_warns_when_placement_enabled_but_no_images_for_compile_input(
        self, mock_run_full_pipeline, mock_build_ai_client
    ):
        project = self.project
        project.page_image_placement = "top"
        project.save(update_fields=["page_image_placement"])
        Profile.objects.get_or_create(user=self.user, defaults={"timezone": "UTC"})

        run_root = project.artifact_dir() / "runs" / "run_test"
        run_root.mkdir(parents=True, exist_ok=True)
        page_file = run_root / "page_1.html"
        page_file.write_text(
            '<div class="page" id="main-text-pane"><p>hello</p></div></div><div class="concordance-pane-wrapper">',
            encoding="utf-8",
        )

        async def _fake_pipeline(spec, client):
            return {"html": {"run_root": str(run_root), "index_path": str(page_file)}}

        mock_run_full_pipeline.side_effect = _fake_pipeline
        mock_build_ai_client.return_value = object()

        views._run_compile_task(
            project.id,
            self.user.id,
            str(run_root),
            str(project.artifact_dir()),
            "segmentation_phase_1",
            "UTC",
            project.description,
            "Hello world",
            None,
            str(uuid.uuid4()),
            "compile_project_test",
            "gpt-4o",
            "compile_html",
            "top",
        )

        self.assertTrue(
            TaskUpdate.objects.filter(
                user=self.user,
                message__icontains="no page images were found for compile input",
            ).exists()
        )

    @patch("projects.views._build_ai_client")
    @patch("projects.views.run_full_pipeline")
    def test_compile_task_passes_page_images_into_pipeline_spec(
        self, mock_run_full_pipeline, mock_build_ai_client
    ):
        project = self.project
        project.page_image_placement = "top"
        project.save(update_fields=["page_image_placement"])
        Profile.objects.get_or_create(user=self.user, defaults={"timezone": "UTC"})

        image_dir = project.artifact_dir() / "images" / "pages" / "page_001"
        image_dir.mkdir(parents=True, exist_ok=True)
        (image_dir / "image.png").write_bytes(b"png")
        ProjectImagePage.objects.create(
            project=project,
            page_number=1,
            page_text="hello",
            image_path="images/pages/page_001/image.png",
        )

        run_root = project.artifact_dir() / "runs" / "run_spec"
        run_root.mkdir(parents=True, exist_ok=True)
        page_file = run_root / "page_1.html"
        page_file.write_text('<div id="main-text-pane" class="page"></div>', encoding="utf-8")

        captured = {}

        async def _fake_pipeline(spec, client):
            captured["page_images"] = spec.page_images
            return {"html": {"run_root": str(run_root), "index_path": str(page_file)}}

        mock_run_full_pipeline.side_effect = _fake_pipeline
        mock_build_ai_client.return_value = object()

        views._run_compile_task(
            project.id,
            self.user.id,
            str(run_root),
            str(project.artifact_dir()),
            "segmentation_phase_1",
            "UTC",
            project.description,
            "Hello world",
            None,
            str(uuid.uuid4()),
            "compile_project_test",
            "gpt-4o",
            "compile_html",
            "top",
        )

        self.assertIn(1, captured["page_images"])
        self.assertEqual("top", captured["page_images"][1]["placement"])
        self.assertTrue(captured["page_images"][1]["path"].startswith("../../../images/pages/"))

    @patch("projects.views._build_ai_client")
    @patch("projects.views.run_full_pipeline")
    def test_compile_task_non_html_end_stage_reports_finished_not_error(
        self, mock_run_full_pipeline, mock_build_ai_client
    ):
        project = self.project
        Profile.objects.get_or_create(user=self.user, defaults={"timezone": "UTC"})

        run_root = project.artifact_dir() / "runs" / "run_non_html"
        run_root.mkdir(parents=True, exist_ok=True)

        async def _fake_pipeline(spec, client):
            return {"text": {"pages": []}}

        mock_run_full_pipeline.side_effect = _fake_pipeline
        mock_build_ai_client.return_value = object()

        report_id = str(uuid.uuid4())
        views._run_compile_task(
            project.id,
            self.user.id,
            str(run_root),
            str(project.artifact_dir()),
            "segmentation_phase_1",
            "UTC",
            project.description,
            "Hello world",
            None,
            report_id,
            "compile_project_test",
            "gpt-4o",
            "segmentation_phase_2",
            "none",
        )

        updates = TaskUpdate.objects.filter(report_id=report_id, user=self.user).order_by("timestamp")
        self.assertTrue(updates.filter(status="finished").exists())
        self.assertTrue(
            updates.filter(message__icontains="Pipeline finished successfully at stage: segmentation_phase_2.").exists()
        )
