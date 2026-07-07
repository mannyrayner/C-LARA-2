import shutil
import tempfile
from pathlib import Path
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from projects.models import Project, ProjectImagePage, ProjectImagePageVariant, ProjectImageStyle
from projects.snapshots import _iter_artifact_paths, list_project_snapshots, restore_project_snapshot, save_project_snapshot


class ProjectSnapshotTests(TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.tmpdir, PIPELINE_OUTPUT_ROOT=Path(self.tmpdir) / "users")
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(lambda: shutil.rmtree(self.tmpdir, ignore_errors=True))
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="snapper", password="pw")
        self.project = Project.objects.create(
            owner=self.user,
            title="Snapshot project",
            source_text="Original text",
            language="en",
            target_language="fr",
        )
        ProjectImageStyle.objects.create(project=self.project, style_brief="Original style")
        page = ProjectImagePage.objects.create(
            project=self.project,
            page_number=1,
            page_text="Original page",
            generation_prompt="Original prompt",
        )
        variant = ProjectImagePageVariant.objects.create(
            page=page,
            variant_index=1,
            image_path="images/pages/page_001/variant_001.png",
        )
        page.preferred_variant = variant
        page.image_path = variant.image_path
        page.save()
        image_path = self.project.artifact_dir() / variant.image_path
        image_path.parent.mkdir(parents=True, exist_ok=True)
        image_path.write_text("original image", encoding="utf-8")
        stage_path = self.project.artifact_dir() / "runs" / "run_demo" / "stages" / "segmentation_phase_1.json"
        stage_path.parent.mkdir(parents=True, exist_ok=True)
        stage_path.write_text('{"segments": ["original"]}', encoding="utf-8")

    def test_programmatic_save_and_restore_restores_db_rows_and_artifacts(self):
        ignored_old_snapshot = self.project.artifact_dir() / "snapshots" / "old" / "manifest.json"
        ignored_old_snapshot.parent.mkdir(parents=True, exist_ok=True)
        ignored_old_snapshot.write_text("old snapshot", encoding="utf-8")
        nested_manual_version = (
            self.project.artifact_dir()
            / "runs"
            / "run_demo"
            / "stages"
            / "manual_versions"
            / "gloss_20260703T023826357632Z.json"
        )
        nested_manual_version.parent.mkdir(parents=True, exist_ok=True)
        nested_manual_version.write_text('{"gloss": "manual"}', encoding="utf-8")
        snapshot = save_project_snapshot(
            self.project,
            name="Before experiment",
            created_by="test",
            contains_gold_standard=True,
            gold_standard_components=["segmentation", "MWE"],
        )
        self.project.source_text = "Changed text"
        self.project.save()
        style = self.project.image_style
        style.style_brief = "Changed style"
        style.save()
        page = self.project.image_pages.get(page_number=1)
        page.generation_prompt = "Changed prompt"
        page.save()
        (self.project.artifact_dir() / "runs" / "run_demo" / "stages" / "segmentation_phase_1.json").write_text(
            '{"segments": ["changed"]}', encoding="utf-8"
        )

        restored = restore_project_snapshot(self.project, snapshot_id=snapshot.snapshot_id)

        self.assertEqual(restored.name, "Before experiment")
        self.project.refresh_from_db()
        self.assertEqual(self.project.source_text, "Original text")
        self.assertEqual(self.project.image_style.style_brief, "Original style")
        page = self.project.image_pages.get(page_number=1)
        self.assertEqual(page.generation_prompt, "Original prompt")
        self.assertEqual(page.preferred_variant.variant_index, 1)
        self.assertEqual(
            (self.project.artifact_dir() / "runs" / "run_demo" / "stages" / "segmentation_phase_1.json").read_text(encoding="utf-8"),
            '{"segments": ["original"]}',
        )
        self.assertEqual(
            (
                snapshot.path
                / "artifacts"
                / "runs"
                / "run_demo"
                / "stages"
                / "manual_versions"
                / "gloss_20260703T023826357632Z.json"
            ).read_text(encoding="utf-8"),
            '{"gloss": "manual"}',
        )
        self.assertFalse((snapshot.path / "artifacts" / "snapshots" / "old" / "manifest.json").exists())
        self.assertEqual(list_project_snapshots(self.project)[0].gold_standard_components, ("segmentation", "MWE"))

    def test_artifact_iterator_prunes_snapshots_directory(self):
        root = self.project.artifact_dir()
        (root / "snapshots" / "current" / "artifacts" / "recursive.txt").parent.mkdir(parents=True, exist_ok=True)
        (root / "snapshots" / "current" / "artifacts" / "recursive.txt").write_text("skip", encoding="utf-8")
        kept_path = root / "runs" / "run_demo" / "stages" / "manual_versions" / "mwe.json"
        kept_path.parent.mkdir(parents=True, exist_ok=True)
        kept_path.write_text("keep", encoding="utf-8")

        rel_paths = {path.relative_to(root).as_posix() for path in _iter_artifact_paths(root)}

        self.assertIn("runs/run_demo/stages/manual_versions/mwe.json", rel_paths)
        self.assertNotIn("snapshots/current/artifacts/recursive.txt", rel_paths)

    def test_platform_save_and_restore_views(self):
        client = Client()
        self.assertTrue(client.login(username="snapper", password="pw"))
        response = client.post(
            reverse("project-snapshot-save", args=[self.project.pk]),
            {
                "name": "UI checkpoint",
                "contains_gold_standard": "on",
                "gold_standard_components": ["gloss annotations", "all image data"],
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        snapshot = list_project_snapshots(self.project)[0]
        self.assertEqual(snapshot.gold_standard_components, ("gloss annotations", "all image data"))
        self.project.source_text = "Changed in UI test"
        self.project.save()

        response = client.post(reverse("project-snapshot-restore", args=[self.project.pk, snapshot.snapshot_id]), follow=True)

        self.assertEqual(response.status_code, 200)
        self.project.refresh_from_db()
        self.assertEqual(self.project.source_text, "Original text")

    def test_management_command_supports_experiment_invocation(self):
        out = StringIO()
        call_command(
            "project_snapshot",
            "save",
            project_id=self.project.pk,
            name="Experiment checkpoint",
            contains_gold_standard=True,
            gold_standard_component=["segmentation"],
            stdout=out,
        )
        self.assertIn("Saved snapshot", out.getvalue())
        snapshot = list_project_snapshots(self.project)[0]

        self.project.source_text = "Changed before command restore"
        self.project.save()
        call_command("project_snapshot", "restore", project_id=self.project.pk, snapshot_id=snapshot.snapshot_id, stdout=StringIO())

        self.project.refresh_from_db()
        self.assertEqual(self.project.source_text, "Original text")
