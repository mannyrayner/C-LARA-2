from __future__ import annotations

import io
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings

from pipeline.stage_artifacts import write_stage_artifact
from projects.models import LegacyProjectImport, Project


class LegacyCompilePublishCommandTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="legacy_owner", password="pw")
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.output_root = Path(self.tempdir.name) / "artifacts"
        self.settings = override_settings(PIPELINE_OUTPUT_ROOT=self.output_root)
        self.settings.enable()
        self.addCleanup(self.settings.disable)

    def _record(self, legacy_id: str, *, with_stage: bool = True) -> LegacyProjectImport:
        project = Project.objects.create(
            owner=self.user,
            title=f"Legacy {legacy_id}",
            language="de",
            target_language="en",
        )
        record = LegacyProjectImport.objects.create(
            source_system="clara_adelaide",
            legacy_project_id=legacy_id,
            imported_by=self.user,
            project=project,
            status=LegacyProjectImport.STATUS_IMPORTED,
        )
        if with_stage:
            payload = {
                "pages": [
                    {
                        "segments": [
                            {
                                "surface": "Hallo",
                                "tokens": [
                                    {
                                        "surface": "Hallo",
                                        "annotations": {"lemma": "hallo", "gloss": "hello"},
                                    }
                                ],
                                "annotations": {"translation": "Hello"},
                            }
                        ],
                        "annotations": {},
                    }
                ]
            }
            write_stage_artifact(project.artifact_dir() / "runs" / "run_imported", "audio", payload)
        return record

    def _call(self, command: str, *args: str) -> str:
        output = io.StringIO()
        call_command(command, *args, stdout=output)
        return output.getvalue()

    def test_compile_runs_only_renderer_and_records_output(self):
        record = self._record("7")

        with patch("projects.legacy_batch.compile_html", wraps=__import__(
            "pipeline.compile_html", fromlist=["compile_html"]
        ).compile_html) as renderer:
            output = self._call("compile_legacy_projects", "--only-id", "7")

        self.assertIn("compiled=1", output)
        renderer.assert_called_once()
        record.project.refresh_from_db()
        compiled = record.project.artifact_dir() / record.project.compiled_path
        self.assertTrue(compiled.is_file())
        self.assertIn("run_legacy_render_", record.project.compiled_path)
        stage_path = compiled.parent.parent / "stages" / "compile_html.json"
        stage = json.loads(stage_path.read_text(encoding="utf-8"))
        self.assertEqual(stage["legacy_batch_render"]["input_stage"], "audio")

    def test_compile_skips_missing_input_and_existing_html(self):
        missing = self._record("8", with_stage=False)
        existing = self._record("9")
        compiled = existing.project.artifact_dir() / "runs" / "old" / "html" / "page_1.html"
        compiled.parent.mkdir(parents=True)
        compiled.write_text("ok", encoding="utf-8")
        existing.project.compiled_path = compiled.relative_to(existing.project.artifact_dir()).as_posix()
        existing.project.save(update_fields=["compiled_path", "updated_at"])

        output = self._call("compile_legacy_projects")

        self.assertIn("skipped_missing_input=1", output)
        self.assertIn("skipped_compiled=1", output)
        missing.project.refresh_from_db()
        self.assertEqual(missing.project.compiled_path, "")

    def test_dry_run_does_not_compile_or_publish(self):
        record = self._record("10")
        compile_output = self._call("compile_legacy_projects", "--dry-run")
        record.project.refresh_from_db()

        self.assertIn("would_compile=1", compile_output)
        self.assertEqual(record.project.compiled_path, "")

    @patch("projects.management.commands.publish_legacy_projects.update_project_discovery_metadata")
    def test_publish_requires_valid_html_and_is_idempotent(self, update_metadata):
        valid = self._record("11")
        missing = self._record("12")
        html = valid.project.artifact_dir() / "runs" / "rendered" / "html" / "page_1.html"
        html.parent.mkdir(parents=True)
        html.write_text("ok", encoding="utf-8")
        valid.project.compiled_path = html.relative_to(valid.project.artifact_dir()).as_posix()
        valid.project.save(update_fields=["compiled_path", "updated_at"])

        first = self._call("publish_legacy_projects")
        second = self._call("publish_legacy_projects")

        self.assertIn("published=1", first)
        self.assertIn("skipped_missing_html=1", first)
        self.assertIn("skipped_published=1", second)
        valid.project.refresh_from_db()
        missing.project.refresh_from_db()
        self.assertTrue(valid.project.is_published)
        self.assertIsNotNone(valid.project.published_at)
        self.assertFalse(missing.project.is_published)
        update_metadata.assert_called_once_with(valid.project, force=False)

    def test_publish_rejects_compiled_path_outside_project_root(self):
        record = self._record("13")
        outside = Path(self.tempdir.name) / "outside.html"
        outside.write_text("not safe", encoding="utf-8")
        record.project.compiled_path = str(outside)
        record.project.save(update_fields=["compiled_path", "updated_at"])

        output = self._call("publish_legacy_projects")

        self.assertIn("skipped_missing_html=1", output)
        record.project.refresh_from_db()
        self.assertFalse(record.project.is_published)
