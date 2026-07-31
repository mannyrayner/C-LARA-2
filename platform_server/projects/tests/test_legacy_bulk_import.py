from __future__ import annotations

import io
import json
import tempfile
import zipfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings

from projects.models import LegacyProjectImport, Project


class LegacyBundleLibraryBulkImportTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="legacy_owner", password="pw")
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.root = Path(self.tempdir.name) / "library"
        self.output_root = Path(self.tempdir.name) / "project_artifacts"
        self.root.mkdir()

    def _add_bundle(self, project_id: int, *, title: str | None = None, valid: bool = True) -> None:
        bundle_dir = self.root / str(project_id)
        bundle_dir.mkdir()
        metadata = {
            "id": project_id,
            "title": title or f"Legacy {project_id}",
            "l2": "german",
            "l1": "english",
            "owner_username": f"legacy_user_{project_id}",
            "sha256": f"{project_id:064x}",
        }
        (bundle_dir / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
        zip_path = bundle_dir / "source.zip"
        if not valid:
            zip_path.write_text("not a zip", encoding="utf-8")
            return
        annotated = {
            "l2_language": "german",
            "l1_language": "english",
            "pages": [
                {
                    "segments": [
                        {
                            "content_elements": [
                                {"type": "Word", "content": "Hallo", "annotations": {"gloss": "hello"}}
                            ],
                            "annotations": {"translated": "Hello", "mwes": [], "page_number": 1},
                        }
                    ],
                    "annotations": {},
                }
            ],
        }
        with zipfile.ZipFile(zip_path, "w") as archive:
            archive.writestr("LegacyJSON/annotated_text.json", json.dumps(annotated))

    def _build_metadata(self) -> None:
        call_command("build_legacy_bundle_metadata", str(self.root), verbosity=0)

    def _run(self, *extra: str) -> str:
        output = io.StringIO()
        with override_settings(PIPELINE_OUTPUT_ROOT=self.output_root):
            call_command(
                "import_legacy_bundle_library",
                "--root",
                str(self.root),
                "--owner",
                self.user.username,
                "--library-version",
                "v3",
                *extra,
                stdout=output,
            )
        return output.getvalue()

    def test_dry_run_reports_candidates_without_writing(self):
        self._add_bundle(10)
        self._add_bundle(2)
        self._build_metadata()
        report = Path(self.tempdir.name) / "dry-run.jsonl"

        output = self._run("--dry-run", "--report", str(report))

        self.assertIn("2 would_import", output)
        self.assertIn("10 would_import", output)
        self.assertEqual(Project.objects.count(), 0)
        self.assertEqual(LegacyProjectImport.objects.count(), 0)
        rows = [json.loads(line) for line in report.read_text(encoding="utf-8").splitlines()]
        self.assertEqual([row["legacy_project_id"] for row in rows], ["2", "10"])

    def test_import_is_idempotent_and_records_provenance(self):
        self._add_bundle(1, title="First legacy")
        self._add_bundle(2, title="Second legacy")
        self._build_metadata()

        first_output = self._run()
        second_output = self._run()

        self.assertIn("imported=2", first_output)
        self.assertIn("skipped_existing=2", second_output)
        self.assertEqual(Project.objects.count(), 2)
        self.assertEqual(LegacyProjectImport.objects.count(), 2)
        record = LegacyProjectImport.objects.get(legacy_project_id="1")
        self.assertEqual(record.status, LegacyProjectImport.STATUS_IMPORTED)
        self.assertEqual(record.project.title, "First legacy")
        self.assertEqual(record.original_owner_username, "legacy_user_1")
        self.assertEqual(record.library_version, "v3")
        self.assertEqual(record.attempt_count, 1)
        source_path = (
            self.output_root
            / str(self.user.id)
            / "projects"
            / f"project_{record.project_id}"
            / "source"
            / "source_text.txt"
        )
        self.assertTrue(source_path.exists())

    def test_rerun_repairs_placeholder_title_from_library_metadata(self):
        self._add_bundle(5, title="Metadata title")
        self._build_metadata()
        self._run()
        record = LegacyProjectImport.objects.get(legacy_project_id="5")
        record.project.title = "Imported legacy C-LARA project (9)"
        record.project.save(update_fields=["title", "updated_at"])

        output = self._run()

        self.assertIn("refreshed_title=1", output)
        record.project.refresh_from_db()
        self.assertEqual(record.project.title, "Metadata title")

    def test_failed_bundle_requires_retry_flag(self):
        self._add_bundle(3, valid=False)
        self._build_metadata()

        failed_output = self._run()
        skipped_output = self._run()
        (self.root / "3" / "source.zip").unlink()
        # Recreate the same bundle with valid ZIP contents, retaining metadata.
        metadata = json.loads((self.root / "3" / "metadata.json").read_text(encoding="utf-8"))
        annotated = {
            "l2_language": "german",
            "l1_language": "english",
            "pages": [{"segments": [], "annotations": {"title": metadata["title"]}}],
        }
        with zipfile.ZipFile(self.root / "3" / "source.zip", "w") as archive:
            archive.writestr("LegacyJSON/annotated_text.json", json.dumps(annotated))
        retried_output = self._run("--retry-failed")

        self.assertIn("failed=1", failed_output)
        self.assertIn("skipped_failed=1", skipped_output)
        self.assertIn("imported=1", retried_output)
        record = LegacyProjectImport.objects.get(legacy_project_id="3")
        self.assertEqual(record.status, LegacyProjectImport.STATUS_IMPORTED)
        self.assertEqual(record.attempt_count, 2)

    def test_reconciles_existing_manual_import_from_summary(self):
        self._add_bundle(4)
        self._build_metadata()
        self._run()
        project = Project.objects.get()
        LegacyProjectImport.objects.all().delete()

        output = self._run()

        self.assertIn("reconciled=1", output)
        self.assertEqual(Project.objects.count(), 1)
        record = LegacyProjectImport.objects.get(legacy_project_id="4")
        self.assertEqual(record.project, project)
        self.assertEqual(record.attempt_count, 0)
