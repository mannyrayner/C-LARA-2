from __future__ import annotations

import io
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command, CommandError
from django.test import TestCase, override_settings

from pipeline.stage_artifacts import write_stage_artifact
from projects.models import LegacyProjectImport, Project, ProjectImagePage, ProjectImagePageVariant


class _TitleProposalClient:
    def __init__(self, *args, **kwargs):
        pass

    async def chat_json(self, prompt, model=None):
        assert "Rocket Raccoon" in prompt
        return {
            "title": "Rocket Raccoon Rides the Subway",
            "confidence": "high",
            "rationale": "The raccoon's subway trip is the central event.",
        }


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

    def test_compile_accepts_legacy_compile_html_payload_and_does_not_require_images(self):
        record = self._record("14", with_stage=False)
        payload = {
            "pages": [
                {
                    "segments": [
                        {
                            "surface": "Text without an image",
                            "tokens": [{"surface": "Text", "annotations": {"lemma": "text"}}],
                            "annotations": {},
                        }
                    ],
                    "annotations": {},
                }
            ]
        }
        write_stage_artifact(
            record.project.artifact_dir() / "runs" / "run_imported", "compile_html", payload
        )

        output = self._call("compile_legacy_projects", "--only-id", "14")

        self.assertIn("compiled=1", output)
        record.project.refresh_from_db()
        compiled = record.project.artifact_dir() / record.project.compiled_path
        self.assertTrue(compiled.is_file())
        stage_path = compiled.parent.parent / "stages" / "compile_html.json"
        stage = json.loads(stage_path.read_text(encoding="utf-8"))
        self.assertEqual(stage["legacy_batch_render"]["input_stage"], "compile_html")

    def test_compile_includes_preferred_project_page_images(self):
        record = self._record("16")
        image_path = "images/pages/page_001/preferred.png"
        image_file = record.project.artifact_dir() / image_path
        image_file.parent.mkdir(parents=True, exist_ok=True)
        image_file.write_bytes(b"png")
        page = ProjectImagePage.objects.create(
            project=record.project,
            page_number=1,
            image_path="images/pages/page_001/fallback.png",
        )
        preferred = ProjectImagePageVariant.objects.create(
            page=page,
            variant_index=1,
            image_path=image_path,
        )
        page.preferred_variant = preferred
        page.save(update_fields=["preferred_variant", "updated_at"])

        output = self._call("compile_legacy_projects", "--only-id", "16")

        self.assertIn("compiled=1", output)
        record.project.refresh_from_db()
        compiled = record.project.artifact_dir() / record.project.compiled_path
        html = compiled.read_text(encoding="utf-8")
        expected_path = os.path.relpath(image_file, compiled.parent).replace("\\", "/")
        self.assertIn(f'src="{expected_path}"', html)
        self.assertIn("generated-page-image-bottom", html)

    def test_missing_input_output_and_report_explain_searched_location(self):
        record = self._record("15", with_stage=False)
        report = Path(self.tempdir.name) / "missing.jsonl"

        output = self._call(
            "compile_legacy_projects", "--only-id", "15", "--report", str(report)
        )

        expected_runs_root = record.project.artifact_dir().resolve() / "runs"
        self.assertIn("skipped_missing_input: runs directory does not exist", output)
        self.assertIn(str(expected_runs_root), output)
        row = json.loads(report.read_text(encoding="utf-8"))
        self.assertEqual(row["status"], "skipped_missing_input")
        self.assertIn(str(expected_runs_root), row["diagnostics"][0])

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

    def test_title_inventory_reports_placeholders_duplicates_and_collisions_without_mutating(self):
        placeholder = self._record("20")
        placeholder.project.title = "Imported legacy C-LARA project (20)"
        placeholder.project.save(update_fields=["title", "updated_at"])
        placeholder.source_title = "Recovered title"
        placeholder.save(update_fields=["source_title", "updated_at"])
        collision = Project.objects.create(
            owner=self.user,
            title="Recovered title",
            language="de",
            target_language="en",
        )
        english = self._record("21")
        english.project.title = "Shared Story"
        english.project.save(update_fields=["title", "updated_at"])
        french = self._record("22")
        french.project.title = "Shared story"
        french.project.target_language = "fr"
        french.project.save(update_fields=["title", "target_language", "updated_at"])
        report_path = Path(self.tempdir.name) / "title-inventory.json"

        output = self._call("inventory_legacy_project_titles", "--report", str(report_path))

        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertIn("placeholders=1", output)
        self.assertEqual(report["summary"]["project_count"], 3)
        self.assertEqual(report["summary"]["placeholder_title_count"], 1)
        placeholder_row = next(row for row in report["projects"] if row["legacy_project_id"] == "20")
        self.assertTrue(placeholder_row["credible_source_title"])
        self.assertEqual(placeholder_row["source_title_collision_project_ids"], [collision.id])
        self.assertEqual(report["duplicate_groups"][0]["classification"], "safe_language_disambiguation")
        self.assertEqual(report["duplicate_groups"][0]["gloss_languages"], ["en", "fr"])
        placeholder.project.refresh_from_db()
        self.assertEqual(placeholder.project.title, "Imported legacy C-LARA project (20)")

    @patch("projects.management.commands.propose_legacy_project_titles.OpenAIClient", _TitleProposalClient)
    def test_title_proposal_and_reviewed_application_workflow(self):
        record = self._record("23", with_stage=False)
        record.project.title = "Imported legacy C-LARA project (23)"
        record.project.source_text = "Rocket Raccoon surprised commuters by riding the Toronto subway."
        record.project.save(update_fields=["title", "source_text", "updated_at"])
        record.source_title = "ALTA EN/SW news story"
        record.save(update_fields=["source_title", "updated_at"])
        inventory_path = Path(self.tempdir.name) / "inventory.json"
        proposals_path = Path(self.tempdir.name) / "proposals.json"
        dry_run_path = Path(self.tempdir.name) / "dry-run.json"
        applied_path = Path(self.tempdir.name) / "applied.json"
        self._call("inventory_legacy_project_titles", "--only-id", "23", "--report", str(inventory_path))

        proposal_output = self._call(
            "propose_legacy_project_titles",
            "--inventory",
            str(inventory_path),
            "--report",
            str(proposals_path),
        )
        proposals = json.loads(proposals_path.read_text(encoding="utf-8"))
        self.assertIn("Wrote 1 title proposal", proposal_output)
        self.assertEqual(proposals["proposals"][0]["proposed_title"], "Rocket Raccoon Rides the Subway")
        record.project.refresh_from_db()
        self.assertEqual(record.project.title, "Imported legacy C-LARA project (23)")

        self._call(
            "apply_legacy_project_titles",
            "--proposals",
            str(proposals_path),
            "--report",
            str(dry_run_path),
        )
        record.project.refresh_from_db()
        self.assertEqual(record.project.title, "Imported legacy C-LARA project (23)")
        self.assertEqual(json.loads(dry_run_path.read_text(encoding="utf-8"))["outcomes"][0]["status"], "would_apply")

        self._call(
            "apply_legacy_project_titles",
            "--proposals",
            str(proposals_path),
            "--report",
            str(applied_path),
            "--apply",
        )
        record.project.refresh_from_db()
        self.assertEqual(record.project.title, "Rocket Raccoon Rides the Subway")

    @patch("projects.management.commands.regenerate_legacy_audio.annotate_audio")
    def test_regenerate_audio_writes_fresh_stage_and_recompiles(self, mock_annotate_audio):
        record = self._record("24")
        audio_file = Path(self.tempdir.name) / "fresh-audio.wav"
        audio_file.write_bytes(b"fresh audio")

        async def fake_annotate(spec):
            payload = json.loads(json.dumps(spec.text))
            segment = payload["pages"][0]["segments"][0]
            segment["annotations"]["audio"] = {"path": str(audio_file)}
            segment["tokens"][0]["annotations"]["audio"] = {"path": str(audio_file)}
            return payload

        mock_annotate_audio.side_effect = fake_annotate
        report_path = Path(self.tempdir.name) / "audio-report.jsonl"

        output = self._call(
            "regenerate_legacy_audio",
            "--project-id",
            str(record.project_id),
            "--report",
            str(report_path),
        )

        self.assertIn("regenerated=1", output)
        audio_spec = mock_annotate_audio.call_args.args[0]
        self.assertTrue(audio_spec.require_real_tts)
        self.assertIn("audio_repository/de", str(audio_spec.cache_dir).replace("\\", "/"))
        row = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(row["status"], "regenerated")
        record.project.refresh_from_db()
        compiled = record.project.artifact_dir() / record.project.compiled_path
        self.assertIn("data-audio=", compiled.read_text(encoding="utf-8"))
        audio_stage = record.project.artifact_dir() / "runs" / row["audio_run"] / "stages" / "audio.json"
        self.assertTrue(audio_stage.is_file())

    def test_regenerate_audio_rejects_non_imported_clara2_project_id(self):
        native = Project.objects.create(
            owner=self.user,
            title="Native project",
            language="de",
            target_language="en",
        )

        with self.assertRaisesMessage(
            CommandError,
            f"C-LARA-2 project IDs are not successful clara_adelaide imports: {native.id}",
        ):
            self._call("regenerate_legacy_audio", "--project-id", str(native.id), "--dry-run")
