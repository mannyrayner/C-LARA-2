import os
import shutil
import io
import json
import uuid
import zipfile
from pathlib import Path
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from projects import views
from projects.models import (
    Profile,
    Project,
    ProjectImageElement,
    ProjectImagePage,
    ProjectImageStyle,
    ProjectCollaborator,
    ContentComment,
    ContentRating,
    TaskUpdate,
    ExerciseSet,
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
        (run_old / "audio").mkdir(parents=True, exist_ok=True)
        (run_old / "audio" / "stale.wav").write_bytes(b"old")
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
        self.assertFalse((new_run / "audio").exists())

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
    def test_segmentation_phase_1_uses_text_gen_surface_when_source_text_missing(self, mock_async_task):
        self.project.source_text = ""
        self.project.input_mode = Project.INPUT_DESCRIPTION
        self.project.description = "A short German text."
        self.project.save(update_fields=["source_text", "input_mode", "description"])

        base = self.project.artifact_dir()
        run_text_gen = base / "runs" / "run_text_gen"
        (run_text_gen / "stages").mkdir(parents=True, exist_ok=True)
        (run_text_gen / "stages" / "text_gen.json").write_text(
            json.dumps({"surface": "Guten Morgen, Anna."}, ensure_ascii=False),
            encoding="utf-8",
        )

        url = reverse("project-compile", args=[self.project.pk])
        resp = self.client.post(url, {"start_stage": "segmentation_phase_1", "end_stage": "segmentation_phase_1"})
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(mock_async_task.called)
        args, _ = mock_async_task.call_args
        # Positional arg 8 is the raw text argument passed into _run_compile_task.
        self.assertEqual("Guten Morgen, Anna.", args[8])

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

    @patch("projects.views.async_task")
    def test_compile_passes_detailed_api_trace_flag(self, mock_async_task):
        url = reverse("project-compile", args=[self.project.pk])
        resp = self.client.post(
            url,
            {
                "start_stage": "segmentation_phase_1",
                "end_stage": "segmentation_phase_1",
                "detailed_api_trace": "1",
            },
        )
        self.assertEqual(resp.status_code, 302)
        args, _kwargs = mock_async_task.call_args
        self.assertTrue(args[-1])

    @patch("projects.views.async_task")
    def test_compile_from_annotation_preserves_annotation_return_target(self, mock_async_task):
        url = reverse("project-compile", args=[self.project.pk])
        resp = self.client.post(
            url,
            {
                "start_stage": "segmentation_phase_1",
                "end_stage": "segmentation_phase_1",
                "return_to": reverse("project-annotation-home", args=[self.project.pk]),
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/compile/monitor/", resp.url)
        self.assertIn("next=/projects/", resp.url)
        self.assertIn("/annotation/", resp.url)

    @patch("projects.views.async_task")
    def test_compile_html_uses_fresher_translation_stage_when_audio_is_stale(self, mock_async_task):
        base = self.project.artifact_dir()
        run_translation = base / "runs" / "run_translation" / "stages"
        run_audio = base / "runs" / "run_audio" / "stages"
        run_translation.mkdir(parents=True, exist_ok=True)
        run_audio.mkdir(parents=True, exist_ok=True)

        translation_payload = {"surface": "Hello", "pages": [{"segments": [{"surface": "Hello", "annotations": {"translation": "Bonjour"}}]}]}
        audio_payload = {"surface": "Hello", "pages": [{"segments": [{"surface": "Hello", "annotations": {"translation": "Old"}}]}]}
        (run_translation / "translation.json").write_text(json.dumps(translation_payload), encoding="utf-8")
        (run_audio / "audio.json").write_text(json.dumps(audio_payload), encoding="utf-8")
        os.utime(run_translation / "translation.json", (2_000, 2_000))
        os.utime(run_audio / "audio.json", (1_000, 1_000))

        with patch("projects.views.credits_enabled", return_value=False):
            resp = self.client.post(
                reverse("project-compile", args=[self.project.pk]),
                {"start_stage": "compile_html", "end_stage": "compile_html"},
            )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(mock_async_task.called)
        args, _kwargs = mock_async_task.call_args
        self.assertEqual("mwe", args[5])

    @patch("projects.views.async_task")
    def test_compile_html_compose_latest_runs_without_confirmation_checkbox(self, mock_async_task):
        base = self.project.artifact_dir()
        run_translation = base / "runs" / "run_translation" / "stages"
        run_translation.mkdir(parents=True, exist_ok=True)
        translation_payload = {
            "surface": "Hello",
            "pages": [{"segments": [{"surface": "Hello", "annotations": {"translation": "Bonjour"}}]}],
        }
        (run_translation / "translation.json").write_text(json.dumps(translation_payload), encoding="utf-8")

        with patch("projects.views.credits_enabled", return_value=False):
            resp = self.client.post(
                reverse("project-compile", args=[self.project.pk]),
                {
                    "start_stage": "compile_html",
                    "end_stage": "compile_html",
                },
            )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(mock_async_task.called)

    @patch("projects.views.async_task")
    def test_compile_html_compose_latest_uses_merged_payload(self, mock_async_task):
        base = self.project.artifact_dir()
        run_translation = base / "runs" / "run_translation" / "stages"
        run_audio = base / "runs" / "run_audio" / "stages"
        run_translation.mkdir(parents=True, exist_ok=True)
        run_audio.mkdir(parents=True, exist_ok=True)

        translation_payload = {
            "surface": "Hello",
            "pages": [{"segments": [{"surface": "Hello", "annotations": {"translation": "Bonjour"}}]}],
        }
        audio_payload = {
            "surface": "Hello",
            "pages": [
                {
                    "segments": [
                        {
                            "surface": "Hello",
                            "tokens": [{"surface": "Hello", "annotations": {"audio": {"path": "x.wav"}}}],
                            "annotations": {"translation": "Old"},
                        }
                    ]
                }
            ],
        }
        (run_translation / "translation.json").write_text(json.dumps(translation_payload), encoding="utf-8")
        (run_audio / "audio.json").write_text(json.dumps(audio_payload), encoding="utf-8")
        os.utime(run_translation / "translation.json", (2_000, 2_000))
        os.utime(run_audio / "audio.json", (1_000, 1_000))

        with patch("projects.views.credits_enabled", return_value=False):
            resp = self.client.post(
                reverse("project-compile", args=[self.project.pk]),
                {
                    "start_stage": "compile_html",
                    "end_stage": "compile_html",
                },
            )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(mock_async_task.called)
        args, _kwargs = mock_async_task.call_args
        self.assertEqual("compile_html", args[5])
        merged = args[9]
        self.assertEqual("Bonjour", merged["pages"][0]["segments"][0]["annotations"]["translation"])

    def test_annotation_home_default_start_stage_follows_freshest_output(self):
        project = Project.objects.create(
            owner=self.user,
            title="Default start stage project",
            source_text="Hello",
            language="en",
            target_language="fr",
        )
        resp = self.client.get(reverse("project-annotation-home", args=[project.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["default_start_stage"], "text_gen")
        self.assertNotContains(resp, "compose_latest_upstream")
        self.assertNotContains(resp, "confirm_compose_latest")

        run_dir = project.artifact_dir() / "runs" / "run_default_start" / "stages"
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "segmentation_phase_1.json").write_text("{}", encoding="utf-8")
        os.utime(run_dir / "segmentation_phase_1.json", (2_000, 2_000))
        resp2 = self.client.get(reverse("project-annotation-home", args=[project.pk]))
        self.assertEqual(resp2.context["default_start_stage"], "segmentation_phase_2")

        (run_dir / "compile_html.json").write_text("{}", encoding="utf-8")
        os.utime(run_dir / "compile_html.json", (3_000, 3_000))
        resp3 = self.client.get(reverse("project-annotation-home", args=[project.pk]))
        self.assertEqual(resp3.context["default_start_stage"], "compile_html")

    def test_resolve_run_dir_prefers_latest_run_over_compiled_path_run(self):
        base = self.project.artifact_dir()
        older = base / "runs" / "run_old"
        newer = base / "runs" / "run_new"
        for run_dir in (older, newer):
            (run_dir / "stages").mkdir(parents=True, exist_ok=True)

        (older / "stages" / "compile_html.json").write_text("{}", encoding="utf-8")
        (newer / "stages" / "lemma.json").write_text("{}", encoding="utf-8")
        os.utime(older, (1, 1))
        os.utime(newer, (4_000_000_000, 4_000_000_000))

        self.project.compiled_path = "runs/run_old/html/page_1.html"
        self.project.save(update_fields=["compiled_path", "updated_at"])
        selected = views._resolve_run_dir(self.project)
        self.assertEqual(selected, newer.resolve())

    def test_set_page_image_placement_updates_project(self):
        url = reverse("project-image-placement", args=[self.project.pk])
        resp = self.client.post(url, {"page_image_placement": "top"})
        self.assertEqual(resp.status_code, 302)
        self.project.refresh_from_db()
        self.assertEqual(self.project.page_image_placement, "top")

    def test_project_create_form_uses_language_dropdowns_with_clear_labels(self):
        Profile.objects.update_or_create(user=self.user, defaults={"timezone": "UTC", "dialogue_language": "de"})
        resp = self.client.get(reverse("project-create"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Text language")
        self.assertContains(resp, "Glossing language")
        self.assertContains(resp, '<select name="language"', html=False)
        self.assertContains(resp, '<select name="target_language"', html=False)
        self.assertContains(resp, "English")
        self.assertContains(resp, "German")
        self.assertContains(resp, "Persian")
        self.assertContains(resp, "Old Norse")
        self.assertContains(resp, '<option value="de" selected>German</option>', html=False)

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



    def test_download_project_bundle_includes_run_and_images(self):
        run_dir = self.project.artifact_dir() / "runs" / "run_bundle"
        html_dir = run_dir / "html"
        audio_dir = run_dir / "audio"
        html_dir.mkdir(parents=True, exist_ok=True)
        audio_dir.mkdir(parents=True, exist_ok=True)
        (html_dir / "index.html").write_text("<html>ok</html>", encoding="utf-8")
        (audio_dir / "a.wav").write_bytes(b"wav")

        images_dir = self.project.artifact_dir() / "images" / "pages" / "page_001"
        images_dir.mkdir(parents=True, exist_ok=True)
        (images_dir / "image.png").write_bytes(b"png")

        self.project.compiled_path = "runs/run_bundle/html/index.html"
        self.project.save(update_fields=["compiled_path", "updated_at"])

        resp = self.client.get(reverse("project-download-bundle", args=[self.project.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/zip")

        payload = b"".join(resp.streaming_content)
        with zipfile.ZipFile(io.BytesIO(payload), "r") as zf:
            names = set(zf.namelist())

        expected_prefix = "test-project-bundle/"
        self.assertIn(
            expected_prefix + "runs/run_bundle/html/index.html",
            names,
        )
        self.assertIn(
            expected_prefix + "runs/run_bundle/audio/a.wav",
            names,
        )
        self.assertIn(
            expected_prefix + "images/pages/page_001/image.png",
            names,
        )
        self.assertIn(expected_prefix + "README.html", names)



    def test_download_project_bundle_readme_notes_missing_audio_and_images(self):
        shutil.rmtree(self.project.artifact_dir(), ignore_errors=True)
        run_dir = self.project.artifact_dir() / "runs" / "run_bundle_no_media"
        html_dir = run_dir / "html"
        html_dir.mkdir(parents=True, exist_ok=True)
        (html_dir / "page_1.html").write_text("<html>p1</html>", encoding="utf-8")

        self.project.compiled_path = "runs/run_bundle_no_media/html/page_1.html"
        self.project.save(update_fields=["compiled_path", "updated_at"])

        resp = self.client.get(reverse("project-download-bundle", args=[self.project.pk]))
        self.assertEqual(resp.status_code, 200)

        payload = b"".join(resp.streaming_content)
        with zipfile.ZipFile(io.BytesIO(payload), "r") as zf:
            readme = zf.read("test-project-bundle/README.html").decode("utf-8")

        self.assertIn("Created (UTC):", readme)
        self.assertIn("runs/run_bundle_no_media/html/page_1.html", readme)
        self.assertIn("Audio files: none included in this bundle.", readme)
        self.assertIn("Image files: none included in this bundle.", readme)

    def test_download_project_bundle_requires_existing_run(self):
        shutil.rmtree(self.project.artifact_dir(), ignore_errors=True)
        resp = self.client.get(reverse("project-download-bundle", args=[self.project.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse("project-detail", args=[self.project.pk]))

    def test_download_source_bundle_contains_stage_and_image_metadata(self):
        run_dir = self.project.artifact_dir() / "runs" / "run_source"
        stages_dir = run_dir / "stages"
        stages_dir.mkdir(parents=True, exist_ok=True)
        for stage in views.SOURCE_BUNDLE_REQUIRED_STAGES:
            (stages_dir / f"{stage}.json").write_text('{"ok": true}', encoding="utf-8")
        (self.project.artifact_dir() / "source").mkdir(parents=True, exist_ok=True)
        (self.project.artifact_dir() / "source" / "source_text.txt").write_text("Hello", encoding="utf-8")

        ProjectImageStyle.objects.create(
            project=self.project,
            style_brief="flat colors",
            sample_image_path="images/style/sample.png",
        )
        img_path = self.project.artifact_dir() / "images" / "style" / "sample.png"
        img_path.parent.mkdir(parents=True, exist_ok=True)
        img_path.write_bytes(b"png")

        self.project.compiled_path = "runs/run_source/html/page_1.html"
        self.project.save(update_fields=["compiled_path", "updated_at"])

        resp = self.client.get(reverse("project-download-source-bundle", args=[self.project.pk]))
        self.assertEqual(resp.status_code, 200)
        payload = b"".join(resp.streaming_content)
        with zipfile.ZipFile(io.BytesIO(payload), "r") as zf:
            names = set(zf.namelist())
            root = "test-project-source-bundle/"
            self.assertIn(root + "manifest.json", names)
            self.assertIn(root + "project/metadata.json", names)
            self.assertIn(root + "stages/segmentation_phase_1.json", names)
            self.assertIn(root + "images/style.json", names)
            self.assertIn(root + "assets/images/style/sample.png", names)
            metadata = json.loads(zf.read(root + "project/metadata.json").decode("utf-8"))
            self.assertEqual(metadata.get("text_direction"), "ltr")
            self.assertEqual(metadata.get("annotation_direction"), "ltr")


    def test_download_source_bundle_auto_refreshes_missing_current_run_stages(self):
        base = self.project.artifact_dir() / "runs"
        upstream_stages = base / "run_upstream" / "stages"
        upstream_stages.mkdir(parents=True, exist_ok=True)
        for stage in views.SOURCE_BUNDLE_REGEN_UPSTREAM_STAGES:
            upstream_stages.joinpath(f"{stage}.json").write_text('{"pages":[]}', encoding="utf-8")

        latest_stages = base / "run_compile_only" / "stages"
        latest_stages.mkdir(parents=True, exist_ok=True)
        latest_stages.joinpath("compile_html.json").write_text('{"pages":[]}', encoding="utf-8")
        self.project.compiled_path = "runs/run_compile_only/html/page_1.html"
        self.project.save(update_fields=["compiled_path", "updated_at"])

        def fake_run_compile_task(*args, **_kwargs):
            output_dir = Path(args[2])
            stages_dir = output_dir / "stages"
            stages_dir.mkdir(parents=True, exist_ok=True)
            stages_dir.joinpath("audio.json").write_text('{"pages":[]}', encoding="utf-8")
            stages_dir.joinpath("compile_html.json").write_text('{"pages":[]}', encoding="utf-8")

        with patch("projects.views._run_compile_task", side_effect=fake_run_compile_task) as mock_run:
            resp = self.client.get(reverse("project-download-source-bundle", args=[self.project.pk]))

        self.assertEqual(resp.status_code, 200)
        mock_run.assert_called_once()
        self.assertEqual(mock_run.call_args.args[4], "audio")
        self.assertEqual(mock_run.call_args.args[12], "compile_html")
        payload = b"".join(resp.streaming_content)
        with zipfile.ZipFile(io.BytesIO(payload), "r") as zf:
            names = set(zf.namelist())
            root = next(name.split("/")[0] for name in names if name.endswith("manifest.json")) + "/"
            for stage in views.SOURCE_BUNDLE_REQUIRED_STAGES:
                self.assertIn(root + f"stages/{stage}.json", names)

    def test_import_source_bundle_creates_new_project(self):
        bundle = io.BytesIO()
        with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as zf:
            root = "imported-source-bundle"
            zf.writestr(
                f"{root}/project/metadata.json",
                json.dumps(
                    {
                        "title": "Hindi Story",
                        "description": "desc",
                        "source_text": "नमस्ते दुनिया",
                        "input_mode": "source_text",
                        "language": "hi",
                        "target_language": "en",
                        "ai_model": "gpt-4o",
                        "page_image_placement": "top",
                        "segmentation_method": "ai",
                        "romanization_method": "indic_transliteration",
                    }
                ),
            )
            zf.writestr(f"{root}/text/source_text.txt", "नमस्ते दुनिया")
            for stage in views.SOURCE_BUNDLE_REQUIRED_STAGES:
                zf.writestr(f"{root}/stages/{stage}.json", '{"pages":[]}')
        bundle.seek(0)

        upload = SimpleUploadedFile("source_bundle.zip", bundle.getvalue(), content_type="application/zip")
        resp = self.client.post(reverse("project-import-source-bundle"), {"source_bundle": upload})
        self.assertEqual(resp.status_code, 302)

        imported = Project.objects.exclude(pk=self.project.pk).get()
        self.assertEqual("Hindi Story", imported.title)
        self.assertEqual(imported.language, "hi")
        self.assertEqual(imported.target_language, "en")

        stage_files = list((imported.artifact_dir() / "runs").rglob("translation.json"))
        self.assertTrue(stage_files)


    def test_import_legacy_clara_json_bundle_creates_project_with_pinyin_audio_and_images(self):
        bundle = io.BytesIO()
        root = "DepressedPandaJSON"
        annotated_text = {
            "l2_language": "mandarin",
            "l1_language": "english",
            "pages": [
                {
                    "segments": [
                        {
                            "content_elements": [
                                {"type": "Markup", "content": "<h1>", "annotations": {}},
                                {
                                    "type": "Word",
                                    "content": "熊猫",
                                    "annotations": {
                                        "gloss": "panda",
                                        "lemma": "熊猫",
                                        "pos": "NOUN",
                                        "pinyin": "xióng māo",
                                        "tts": {
                                            "engine_id": "google",
                                            "language_id": "cmn-CN",
                                            "voice_id": "default",
                                            "file_path": "audio/default_panda.mp3",
                                        },
                                    },
                                },
                                {"type": "NonWordText", "content": "。", "annotations": {}},
                            ],
                            "annotations": {
                                "translated": "Panda.",
                                "mwes": [],
                                "tts": {
                                    "engine_id": "google",
                                    "language_id": "cmn-CN",
                                    "voice_id": "cmn-CN-Wavenet-C",
                                    "file_path": "audio/segment_panda.mp3",
                                },
                                "page_number": 1,
                                "segment_uid": "seg_panda_1",
                            },
                        },
                        {
                            "content_elements": [
                                {
                                    "type": "Image",
                                    "content": {
                                        "src": "page_1.png",
                                        "thumbnail_src": "page_1_thumbnail.png",
                                        "width": 512,
                                        "height": 512,
                                    },
                                    "annotations": {},
                                }
                            ],
                            "annotations": {"mwes": [], "page_number": 1, "segment_uid": "seg_panda_img"},
                        },
                    ],
                    "annotations": {
                        "title": "熊猫独白",
                        "tts": {
                            "engine_id": "google",
                            "language_id": "cmn-CN",
                            "voice_id": "cmn-CN-Wavenet-C",
                            "file_path": "audio/segment_panda.mp3",
                        },
                    },
                }
            ],
            "annotations": {"voice": "google_cmn-CN"},
        }
        image_metadata = [
            {
                "image_file_path": "page_1.png",
                "thumbnail_file_path": "page_1_thumbnail.png",
                "image_name": "page_1",
                "page": 1,
                "position": "bottom",
                "image_type": "page",
                "user_prompt": "",
                "content_description": "",
            },
            {
                "image_file_path": "style.png",
                "thumbnail_file_path": "style_thumbnail.png",
                "image_name": "style",
                "page": 1,
                "position": "bottom",
                "image_type": "style",
                "advice": "Create a style inspired by traditional Chinese pen and ink art.",
            },
        ]
        with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(f"{root}/annotated_text.json", json.dumps(annotated_text, ensure_ascii=False))
            zf.writestr(
                f"{root}/metadata.json",
                json.dumps({"simple_clara_type": "create_text_and_image", "audio_type_for_words": "tts"}),
            )
            zf.writestr(f"{root}/audio/default_panda.mp3", b"fake mp3 bytes")
            zf.writestr(f"{root}/audio/segment_panda.mp3", b"fake segment mp3 bytes")
            zf.writestr(f"{root}/audio/metadata.json", json.dumps({"words": [], "segments": []}))
            zf.writestr(f"{root}/images/page_1.png", b"fake image bytes")
            zf.writestr(f"{root}/images/page_1_thumbnail.png", b"fake thumbnail bytes")
            zf.writestr(f"{root}/images/style.png", b"fake style bytes")
            zf.writestr(f"{root}/images/metadata.json", json.dumps(image_metadata))
        bundle.seek(0)

        upload = SimpleUploadedFile("legacy_clara.zip", bundle.getvalue(), content_type="application/zip")
        resp = self.client.post(reverse("project-import-source-bundle"), {"source_bundle": upload})
        self.assertEqual(resp.status_code, 302)

        imported = Project.objects.exclude(pk=self.project.pk).get()
        self.assertEqual(imported.title, "熊猫独白")
        self.assertEqual(imported.language, "zh")
        self.assertEqual(imported.target_language, "en")
        self.assertEqual(imported.page_image_placement, "bottom")
        self.assertIn("熊猫。", imported.source_text)

        pinyin_path = next((imported.artifact_dir() / "runs").rglob("pinyin.json"))
        pinyin_payload = json.loads(pinyin_path.read_text(encoding="utf-8"))
        token = pinyin_payload["pages"][0]["segments"][0]["tokens"][0]
        self.assertEqual(token["annotations"]["pinyin"], "xióng māo")
        self.assertEqual(token["annotations"]["gloss"], "panda")
        self.assertEqual(pinyin_payload["pages"][0]["segments"][0]["annotations"]["translation"], "Panda.")
        self.assertTrue(Path(token["annotations"]["audio"]["path"]).exists())

        self.assertTrue((imported.artifact_dir() / "legacy_clara" / "annotated_text.json").exists())
        self.assertTrue((imported.artifact_dir() / "legacy_clara" / "audio" / "default_panda.mp3").exists())
        self.assertTrue((imported.artifact_dir() / "legacy_clara" / "images" / "page_1.png").exists())
        image_page = ProjectImagePage.objects.get(project=imported, page_number=1)
        self.assertEqual(image_page.image_path, "legacy_clara/images/page_1.png")
        style = ProjectImageStyle.objects.get(project=imported)
        self.assertEqual(style.sample_image_path, "legacy_clara/images/style.png")


    def test_import_legacy_clara_json_bundle_accepts_flat_zip_layout(self):
        bundle = io.BytesIO()
        annotated_text = {
            "l2_language": "mandarin",
            "l1_language": "english",
            "pages": [
                {
                    "segments": [
                        {
                            "content_elements": [
                                {
                                    "type": "Word",
                                    "content": "熊猫",
                                    "annotations": {
                                        "gloss": "panda",
                                        "lemma": "熊猫",
                                        "pos": "NOUN",
                                        "pinyin": "xióng māo",
                                        "tts": {
                                            "engine_id": "google",
                                            "language_id": "cmn-CN",
                                            "voice_id": "default",
                                            "file_path": "audio/default_panda.mp3",
                                        },
                                    },
                                }
                            ],
                            "annotations": {"translated": "Panda.", "mwes": [], "page_number": 1},
                        }
                    ],
                    "annotations": {"title": "Flat Panda"},
                }
            ],
        }
        with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("annotated_text.json", json.dumps(annotated_text, ensure_ascii=False))
            zf.writestr("metadata.json", json.dumps({"simple_clara_type": "create_text"}))
            zf.writestr("audio/default_panda.mp3", b"fake mp3 bytes")
        bundle.seek(0)

        upload = SimpleUploadedFile("flat_legacy_clara.zip", bundle.getvalue(), content_type="application/zip")
        resp = self.client.post(reverse("project-import-source-bundle"), {"source_bundle": upload})
        self.assertEqual(resp.status_code, 302)

        imported = Project.objects.exclude(pk=self.project.pk).get()
        self.assertEqual(imported.title, "Flat Panda")
        self.assertEqual(imported.language, "zh")
        self.assertTrue((imported.artifact_dir() / "legacy_clara" / "metadata.json").exists())
        self.assertTrue((imported.artifact_dir() / "legacy_clara" / "audio" / "default_panda.mp3").exists())
        pinyin_path = next((imported.artifact_dir() / "runs").rglob("pinyin.json"))
        pinyin_payload = json.loads(pinyin_path.read_text(encoding="utf-8"))
        self.assertEqual(
            pinyin_payload["pages"][0]["segments"][0]["tokens"][0]["annotations"]["pinyin"],
            "xióng māo",
        )

    def test_import_source_bundle_adds_suffix_when_title_conflicts_for_same_user(self):
        bundle = io.BytesIO()
        with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as zf:
            root = "imported-source-bundle"
            zf.writestr(
                f"{root}/project/metadata.json",
                json.dumps(
                    {
                        "title": "Test Project",
                        "source_text": "hello",
                        "input_mode": "source_text",
                        "language": "en",
                        "target_language": "fr",
                    }
                ),
            )
            for stage in views.SOURCE_BUNDLE_REQUIRED_STAGES:
                zf.writestr(f"{root}/stages/{stage}.json", '{"pages":[]}')
        upload = SimpleUploadedFile("source_bundle.zip", bundle.getvalue(), content_type="application/zip")
        resp = self.client.post(reverse("project-import-source-bundle"), {"source_bundle": upload})
        self.assertEqual(resp.status_code, 302)
        imported = Project.objects.exclude(pk=self.project.pk).get()
        self.assertEqual("Test Project (2)", imported.title)

    def test_import_source_bundle_rejects_missing_required_stages(self):
        bundle = io.BytesIO()
        with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as zf:
            root = "imported-source-bundle"
            zf.writestr(
                f"{root}/project/metadata.json",
                json.dumps(
                    {
                        "title": "Incomplete Story",
                        "source_text": "hello",
                        "input_mode": "source_text",
                        "language": "en",
                        "target_language": "fr",
                    }
                ),
            )
            zf.writestr(f"{root}/stages/compile_html.json", '{"pages":[]}')
        upload = SimpleUploadedFile("source_bundle.zip", bundle.getvalue(), content_type="application/zip")
        resp = self.client.post(reverse("project-import-source-bundle"), {"source_bundle": upload}, follow=True)
        self.assertEqual(resp.status_code, 200)
        messages = [str(message) for message in get_messages(resp.wsgi_request)]
        self.assertTrue(any("Source bundle is missing required stage artifacts" in message for message in messages))
        self.assertFalse(Project.objects.filter(title="Incomplete Story").exists())

    def test_generate_cloze_exercises_creates_set(self):
        run_dir = self.project.artifact_dir() / "runs" / "run_exercise" / "stages"
        run_dir.mkdir(parents=True, exist_ok=True)
        sample = {
            "pages": [
                {
                    "page_number": 1,
                    "segments": [
                        {"tokens": [{"surface": "The "}, {"surface": "cat"}, {"surface": " sleeps"}]},
                        {"tokens": [{"surface": "A "}, {"surface": "dog"}, {"surface": " runs"}]},
                    ],
                }
            ]
        }
        (run_dir / "gloss.json").write_text(json.dumps(sample), encoding="utf-8")
        self.project.compiled_path = "runs/run_exercise/html/page_1.html"
        self.project.save(update_fields=["compiled_path", "updated_at"])

        class _FakeClient:
            async def chat_json(self, *_args, **_kwargs):
                return {"distractors": ["bird", "fish", "mouse"], "rationale": {"bird": "animal"}}

        with patch("projects.views._build_ai_client", return_value=_FakeClient()):
            resp = self.client.post(
                reverse("project-generate-cloze", args=[self.project.pk]),
                {"theme": "vocabulary", "item_count": 2, "ai_model": "gpt-4o"},
            )
        self.assertEqual(resp.status_code, 302)
        ex_set = ExerciseSet.objects.get(project=self.project)
        self.assertEqual(ex_set.exercise_type, ExerciseSet.TYPE_CLOZE)
        self.assertEqual(ex_set.items.count(), 2)

    def test_generate_cloze_form_uses_model_dropdown(self):
        resp = self.client.get(reverse("project-generate-cloze", args=[self.project.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '<select name="ai_model"', html=False)
        self.assertContains(resp, "gpt-4o")

    def test_generate_flashcards_creates_set(self):
        run_dir = self.project.artifact_dir() / "runs" / "run_flashcards" / "stages"
        run_dir.mkdir(parents=True, exist_ok=True)
        sample = {
            "pages": [
                {
                    "page_number": 1,
                    "segments": [
                        {
                            "tokens": [
                                {"surface": "cat", "annotations": {"gloss": "chat"}},
                                {"surface": "sleeps", "annotations": {"gloss": "dort"}},
                            ]
                        }
                    ],
                }
            ]
        }
        (run_dir / "gloss.json").write_text(json.dumps(sample), encoding="utf-8")
        self.project.compiled_path = "runs/run_flashcards/html/page_1.html"
        self.project.save(update_fields=["compiled_path", "updated_at"])

        class _FakeClient:
            async def chat_json(self, *_args, **_kwargs):
                return {"distractors": ["chien", "oiseau", "poisson"], "rationale": {"chien": "animal"}}

        with patch("projects.views._build_ai_client", return_value=_FakeClient()):
            resp = self.client.post(
                reverse("project-generate-flashcards", args=[self.project.pk]),
                {
                    "theme": "vocabulary",
                    "flashcard_mode": "form_to_meaning",
                    "item_count": 1,
                    "ai_model": "gpt-4o",
                },
            )
        self.assertEqual(resp.status_code, 302)
        ex_set = ExerciseSet.objects.get(project=self.project, exercise_type=ExerciseSet.TYPE_FLASHCARD)
        self.assertEqual(ex_set.items.count(), 1)
        item = ex_set.items.first()
        self.assertIsNotNone(item)
        self.assertIn("chat", item.options)
        self.assertNotEqual(item.options[0], item.answer)

    def test_generate_inverse_flashcards_creates_set(self):
        run_dir = self.project.artifact_dir() / "runs" / "run_flashcards_inverse" / "stages"
        run_dir.mkdir(parents=True, exist_ok=True)
        sample = {
            "pages": [
                {
                    "page_number": 1,
                    "segments": [
                        {"tokens": [{"surface": "freund", "annotations": {"gloss": "boyfriend"}}]}
                    ],
                }
            ]
        }
        (run_dir / "gloss.json").write_text(json.dumps(sample), encoding="utf-8")
        self.project.compiled_path = "runs/run_flashcards_inverse/html/page_1.html"
        self.project.save(update_fields=["compiled_path", "updated_at"])

        class _FakeClient:
            async def chat_json(self, *_args, **_kwargs):
                return {"distractors": ["mann", "haus", "kind"], "rationale": {}}

        with patch("projects.views._build_ai_client", return_value=_FakeClient()):
            resp = self.client.post(
                reverse("project-generate-flashcards", args=[self.project.pk]),
                {
                    "theme": "vocabulary",
                    "flashcard_mode": "meaning_to_form",
                    "item_count": 1,
                    "ai_model": "gpt-4o",
                },
            )
        self.assertEqual(resp.status_code, 302)
        ex_set = ExerciseSet.objects.filter(
            project=self.project, exercise_type=ExerciseSet.TYPE_FLASHCARD
        ).order_by("-id").first()
        self.assertIsNotNone(ex_set)
        item = ex_set.items.first()
        self.assertIsNotNone(item)
        self.assertIn("boyfriend", item.prompt.lower())
        self.assertEqual(item.answer, "freund")

    def test_project_exercises_home_shows_flashcard_generation_link(self):
        resp = self.client.get(reverse("project-exercises-home", args=[self.project.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, reverse("project-generate-flashcards", args=[self.project.pk]))

    def test_project_detail_shows_subpage_links(self):
        resp = self.client.get(reverse("project-detail", args=[self.project.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, reverse("project-annotation-home", args=[self.project.pk]))
        self.assertContains(resp, reverse("project-images-home", args=[self.project.pk]))
        self.assertContains(resp, reverse("project-exercises-home", args=[self.project.pk]))

    def test_project_detail_shows_rtl_directions_for_arabic_project(self):
        self.project.language = "ar"
        self.project.target_language = "fa"
        self.project.save(update_fields=["language", "target_language", "updated_at"])
        resp = self.client.get(reverse("project-detail", args=[self.project.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Direction: rtl (text) / rtl (annotation)")

    def test_project_detail_shows_view_via_server_link_when_compiled(self):
        self.project.compiled_path = "runs/run_demo/html/page_1.html"
        self.project.save(update_fields=["compiled_path", "updated_at"])
        resp = self.client.get(reverse("project-detail", args=[self.project.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(
            resp,
            reverse("project-compiled", args=[self.project.pk, "runs/run_demo/html/page_1.html"]),
        )

    def test_annotation_home_lists_telemetry_artifact_link(self):
        telemetry_path = self.project.artifact_dir() / "runs" / "run_demo" / "stages" / "telemetry.jsonl"
        telemetry_path.parent.mkdir(parents=True, exist_ok=True)
        telemetry_path.write_text('{"type":"event"}\n', encoding="utf-8")
        self.project.compiled_path = "runs/run_demo/html/page_1.html"
        self.project.save(update_fields=["compiled_path", "updated_at"])

        resp = self.client.get(reverse("project-annotation-home", args=[self.project.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "runs/run_demo/stages/telemetry.jsonl")

    def test_project_images_home_shows_phase_1_control_only_when_needed(self):
        url = reverse("project-images-home", args=[self.project.pk])
        resp_before = self.client.get(url)
        self.assertEqual(resp_before.status_code, 200)
        self.assertContains(resp_before, "Segment text into pages (phase 1 only)")

        run_dir = self.project.artifact_dir() / "runs" / "run_for_seg1" / "stages"
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "segmentation_phase_1.json").write_text("{}", encoding="utf-8")
        self.project.compiled_path = "runs/run_for_seg1/html/page_1.html"
        self.project.save(update_fields=["compiled_path", "updated_at"])

        resp_after = self.client.get(url)
        self.assertEqual(resp_after.status_code, 200)
        self.assertNotContains(resp_after, "Segment text into pages (phase 1 only)")

    def test_project_images_home_shows_existing_assets_summary(self):
        ProjectImageStyle.objects.create(
            project=self.project,
            sample_image_path="images/style/style_sample_image.png",
        )
        ProjectImageElement.objects.create(
            project=self.project,
            name="cat",
            image_path="images/elements/cat/reference.png",
        )
        ProjectImagePage.objects.create(
            project=self.project,
            page_number=1,
            image_path="images/pages/page_1/image.png",
        )

        resp = self.client.get(reverse("project-images-home", args=[self.project.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "sample image is available")
        self.assertContains(resp, "1 element image(s) available")
        self.assertContains(resp, "cat")
        self.assertContains(resp, "1 page image(s) available")
        self.assertContains(resp, "Page 1")

    def test_project_exercises_home_shows_only_latest_set_per_type(self):
        old_cloze = ExerciseSet.objects.create(
            project=self.project,
            created_by=self.user,
            exercise_type=ExerciseSet.TYPE_CLOZE,
            theme=ExerciseSet.THEME_VOCAB,
            title="Older cloze",
        )
        latest_cloze = ExerciseSet.objects.create(
            project=self.project,
            created_by=self.user,
            exercise_type=ExerciseSet.TYPE_CLOZE,
            theme=ExerciseSet.THEME_VOCAB,
            title="Latest cloze",
        )
        ExerciseSet.objects.create(
            project=self.project,
            created_by=self.user,
            exercise_type=ExerciseSet.TYPE_FLASHCARD,
            theme=ExerciseSet.THEME_VOCAB,
            title="Flashcards",
        )
        self.assertNotEqual(old_cloze.id, latest_cloze.id)

        resp = self.client.get(reverse("project-exercises-home", args=[self.project.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Latest cloze")
        self.assertNotContains(resp, "Older cloze")
        self.assertContains(resp, "Flashcards")

    def test_project_exercises_home_shows_latest_flashcards_per_mode(self):
        ExerciseSet.objects.create(
            project=self.project,
            created_by=self.user,
            exercise_type=ExerciseSet.TYPE_FLASHCARD,
            flashcard_mode=ExerciseSet.FLASHCARD_MODE_FORM_TO_MEANING,
            theme=ExerciseSet.THEME_VOCAB,
            title="F2M set",
        )
        ExerciseSet.objects.create(
            project=self.project,
            created_by=self.user,
            exercise_type=ExerciseSet.TYPE_FLASHCARD,
            flashcard_mode=ExerciseSet.FLASHCARD_MODE_MEANING_TO_FORM,
            theme=ExerciseSet.THEME_VOCAB,
            title="M2F set",
        )

        resp = self.client.get(reverse("project-exercises-home", args=[self.project.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "F2M set")
        self.assertContains(resp, "M2F set")

    def test_published_content_links_to_playable_exercises(self):
        ex_set = ExerciseSet.objects.create(
            project=self.project,
            created_by=self.user,
            exercise_type=ExerciseSet.TYPE_CLOZE,
            theme=ExerciseSet.THEME_VOCAB,
            title="Set 1",
            status=ExerciseSet.STATUS_PUBLISHED,
            is_published=True,
        )
        ex_set.items.create(
            order_index=0,
            page_number=1,
            segment_index=0,
            segment_text="The cat sleeps",
            prompt="The ____ sleeps",
            answer="cat",
            options=["cat", "dog", "fish", "bird"],
            rationale={},
        )
        self.project.is_published = True
        self.project.save(update_fields=["is_published", "updated_at"])

        resp = self.client.get(reverse("content-detail", args=[self.project.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, reverse("exercise-set-play", args=[ex_set.id]))

        play = self.client.post(reverse("exercise-set-play", args=[ex_set.id]), {"choice": "dog"})
        self.assertEqual(play.status_code, 200)
        self.assertContains(play, "Incorrect")


    def test_content_list_filters_published_projects(self):
        self.project.is_published = True
        self.project.published_at = timezone.now()
        self.project.compiled_path = "runs/run_1/html/page_1.html"
        self.project.save(update_fields=["is_published", "published_at", "compiled_path", "updated_at"])

        other = Project.objects.create(
            owner=self.user,
            title="Unpublished",
            source_text="x",
            language="fr",
            target_language="en",
        )

        resp = self.client.get(reverse("content-list"), {"title": "Test", "text_language": "en"})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Test Project")
        self.assertNotContains(resp, "Unpublished")

    def test_content_detail_increments_access_count_and_links_page_one(self):
        self.project.is_published = True
        self.project.published_at = timezone.now()
        self.project.compiled_path = "runs/run_demo/html/page_2.html"
        run_dir = self.project.artifact_dir() / "runs" / "run_demo" / "html"
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "page_1.html").write_text("<html>p1</html>", encoding="utf-8")
        self.project.save(update_fields=["is_published", "published_at", "compiled_path", "updated_at"])

        url = reverse("content-detail", args=[self.project.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

        self.project.refresh_from_db()
        self.assertEqual(self.project.access_count, 1)
        self.assertContains(resp, "Accesses:")
        self.assertContains(resp, reverse("project-compiled", args=[self.project.pk, "runs/run_demo/html/page_1.html"]))


    def test_content_detail_supports_comments_and_ratings(self):
        self.project.is_published = True
        self.project.published_at = timezone.now()
        self.project.save(update_fields=["is_published", "published_at", "updated_at"])

        url = reverse("content-detail", args=[self.project.pk])
        post_comment = self.client.post(url, {"action": "comment", "body": "Great story"})
        self.assertEqual(post_comment.status_code, 302)
        self.assertTrue(ContentComment.objects.filter(project=self.project, body="Great story").exists())

        post_rating = self.client.post(url, {"action": "rate", "value": "up", "comment": "Nice"})
        self.assertEqual(post_rating.status_code, 302)
        rating = ContentRating.objects.get(project=self.project, author=self.user)
        self.assertEqual(rating.value, "up")

        page = self.client.get(url)
        self.assertContains(page, "Great story")
        self.assertContains(page, "👍")

    def test_project_collaborator_viewer_can_open_detail_but_not_publish(self):
        User = get_user_model()
        collaborator = User.objects.create_user(username="viewer", password="pw")
        ProjectCollaborator.objects.create(project=self.project, user=collaborator, role=ProjectCollaborator.ROLE_VIEWER)

        viewer_client = Client()
        viewer_client.login(username="viewer", password="pw")

        resp_detail = viewer_client.get(reverse("project-detail", args=[self.project.pk]))
        self.assertEqual(resp_detail.status_code, 200)

        resp_publish = viewer_client.get(reverse("project-publish", args=[self.project.pk]))
        self.assertEqual(resp_publish.status_code, 404)



    def test_project_detail_shows_collaborator_user_menu_for_owner(self):
        User = get_user_model()
        candidate = User.objects.create_user(username="candidate_user", password="pw")

        resp = self.client.get(reverse("project-detail", args=[self.project.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'name="username"')
        self.assertContains(resp, "candidate_user")
        self.assertNotContains(resp, 'value="tester"')

    def test_project_owner_can_assign_collaborator_role(self):
        User = get_user_model()
        collaborator = User.objects.create_user(username="annotator", password="pw")

        resp = self.client.post(
            reverse("project-collaborators", args=[self.project.pk]),
            {"username": "annotator", "role": "annotator"},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(
            ProjectCollaborator.objects.filter(
                project=self.project,
                user=collaborator,
                role=ProjectCollaborator.ROLE_ANNOTATOR,
            ).exists()
        )
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
            captured["audio_cache_dir"] = spec.audio_cache_dir
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
        self.assertIn("audio_repository/en", str(captured["audio_cache_dir"]).replace("\\", "/"))

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


class CloneProjectTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="cloner", password="pw")
        self.client = Client()
        self.client.login(username="cloner", password="pw")
        self.project = Project.objects.create(
            owner=self.user,
            title="Original",
            description="desc",
            source_text="source",
            language="en",
            target_language="fr",
        )

    def test_clone_project_copies_latest_run_files(self):
        runs_root = self.project.artifact_dir() / "runs"
        run_old = runs_root / "run_old" / "stages"
        run_new = runs_root / "run_new" / "stages"
        run_old.mkdir(parents=True, exist_ok=True)
        run_new.mkdir(parents=True, exist_ok=True)
        (run_old / "segmentation_phase_1.json").write_text("{\"surface\":\"OLD\"}", encoding="utf-8")
        (run_new / "segmentation_phase_1.json").write_text("{\"surface\":\"NEW\"}", encoding="utf-8")
        old_ts = 1000
        new_ts = 2000
        os.utime(run_old / "segmentation_phase_1.json", (old_ts, old_ts))
        os.utime(run_new / "segmentation_phase_1.json", (new_ts, new_ts))

        style = ProjectImageStyle.objects.create(
            project=self.project,
            style_brief="brief",
            sample_image_path="images/style/style_sample_image.png",
        )
        self.assertIsNotNone(style.pk)
        ProjectImageElement.objects.create(
            project=self.project,
            name="Milo",
            image_path="images/elements/milo/reference.png",
        )
        ProjectImagePage.objects.create(
            project=self.project,
            page_number=1,
            image_path="images/pages/page_001/image.png",
        )
        style_path = self.project.artifact_dir() / "images" / "style" / "style_sample_image.png"
        style_path.parent.mkdir(parents=True, exist_ok=True)
        style_path.write_bytes(b"img")

        resp = self.client.post(
            reverse("project-clone", args=[self.project.pk]),
            {"clone_title": "My Snapshot"},
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        clone = Project.objects.exclude(pk=self.project.pk).get()
        self.assertEqual(clone.title, "My Snapshot")

        clone_runs = sorted((clone.artifact_dir() / "runs").glob("run_*"))
        self.assertTrue(clone_runs)
        copied_stage = clone_runs[-1] / "stages" / "segmentation_phase_1.json"
        self.assertTrue(copied_stage.exists())
        self.assertIn("NEW", copied_stage.read_text(encoding="utf-8"))
        self.assertTrue((clone.artifact_dir() / "images" / "style" / "style_sample_image.png").exists())
        self.assertEqual(clone.image_elements.count(), 1)
        self.assertEqual(clone.image_pages.count(), 1)

    def test_clone_project_can_override_glossing_language(self):
        resp = self.client.post(
            reverse("project-clone", args=[self.project.pk]),
            {"clone_title": "Spanish Gloss Clone", "clone_target_language": "es"},
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        clone = Project.objects.exclude(pk=self.project.pk).get()
        self.assertEqual(clone.title, "Spanish Gloss Clone")
        self.assertEqual(clone.target_language, "es")

    def test_project_detail_clone_form_uses_glossing_language_menu(self):
        resp = self.client.get(reverse("project-detail", args=[self.project.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'name="clone_target_language"')
        self.assertContains(resp, "<select")
        self.assertContains(resp, "Spanish")

    def test_clone_project_rejects_unknown_glossing_language(self):
        resp = self.client.post(
            reverse("project-clone", args=[self.project.pk]),
            {"clone_title": "Bad Clone", "clone_target_language": "xx-invalid"},
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Project.objects.filter(title="Bad Clone").exists())
