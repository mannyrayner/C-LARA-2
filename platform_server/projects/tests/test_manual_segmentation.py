import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from projects.models import Project


class ManualSegmentationEditorTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="annotator", password="pw")
        self.project = Project.objects.create(
            owner=self.user,
            title="Segmentation Project",
            source_text="Hello world",
            language="en",
            target_language="fr",
        )
        self.client = Client()
        self.client.login(username="annotator", password="pw")

    def _latest_run_stage_dir(self) -> Path:
        runs_root = self.project.artifact_dir() / "runs"
        runs = [p for p in runs_root.glob("run_*") if p.is_dir()]
        self.assertTrue(runs)
        latest = max(runs, key=lambda p: p.stat().st_mtime)
        return latest / "stages"

    def test_phase_1_editor_uses_read_only_structure_inputs(self):
        resp = self.client.get(reverse("manual-segmentation-phase-1", args=[self.project.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "name=\"segment_breaks\"")
        self.assertContains(resp, "name=\"page_breaks\"")
        self.assertContains(resp, "readonly")

    def test_phase_1_save_writes_versioned_payload_with_hash_metadata(self):
        resp = self.client.post(
            reverse("manual-segmentation-phase-1", args=[self.project.pk]),
            {"segment_breaks": "5", "page_breaks": ""},
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)

        stage_dir = self._latest_run_stage_dir()
        canonical = stage_dir / "segmentation_phase_1.json"
        self.assertTrue(canonical.exists())
        payload = json.loads(canonical.read_text(encoding="utf-8"))
        self.assertEqual(payload["surface"], "Hello|| world")

        version_files = list((stage_dir / "manual_versions").glob("segmentation_phase_1_*.json"))
        self.assertTrue(version_files)
        version_payload = json.loads(version_files[0].read_text(encoding="utf-8"))
        self.assertEqual(version_payload["stage"], "segmentation_phase_1")
        self.assertIn("before_text_hash", version_payload["metadata"])
        self.assertEqual(
            version_payload["metadata"]["before_text_hash"],
            version_payload["metadata"]["after_text_hash"],
        )

    def test_phase_2_save_writes_versioned_payload_with_hash_metadata(self):
        run_dir = self.project.artifact_dir() / "runs" / "run_seed" / "stages"
        run_dir.mkdir(parents=True, exist_ok=True)
        seg1_payload = {
            "l2": "en",
            "surface": "Hello world",
            "pages": [{"surface": "Hello world", "segments": [{"surface": "Hello world"}], "annotations": {}}],
            "annotations": {},
        }
        (run_dir / "segmentation_phase_1.json").write_text(
            json.dumps(seg1_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        resp = self.client.post(
            reverse("manual-segmentation-phase-2", args=[self.project.pk]),
            {"tokenized_text_1_1": "Hello¦ world"},
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)

        stage_dir = self._latest_run_stage_dir()
        canonical = stage_dir / "segmentation_phase_2.json"
        self.assertTrue(canonical.exists())
        payload = json.loads(canonical.read_text(encoding="utf-8"))
        tokens = payload["pages"][0]["segments"][0]["tokens"]
        self.assertEqual(tokens, [{"surface": "Hello"}, {"surface": " world"}])

        version_files = list((stage_dir / "manual_versions").glob("segmentation_phase_2_*.json"))
        self.assertTrue(version_files)
        version_payload = json.loads(version_files[0].read_text(encoding="utf-8"))
        self.assertEqual(version_payload["stage"], "segmentation_phase_2")
        self.assertEqual(
            version_payload["metadata"]["before_text_hash"],
            version_payload["metadata"]["after_text_hash"],
        )

    def test_project_detail_shows_manual_segmentation_link(self):
        resp = self.client.get(reverse("project-detail", args=[self.project.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, reverse("manual-segmentation-phase-1", args=[self.project.pk]))

    def test_phase_1_handles_inconsistent_existing_surface_without_server_error(self):
        run_dir = self.project.artifact_dir() / "runs" / "run_broken" / "stages"
        run_dir.mkdir(parents=True, exist_ok=True)
        broken = {
            "l2": "en",
            "surface": "Different text||here",
            "pages": [{"surface": "Different text||here", "segments": [{"surface": "Different text"}, {"surface": "here"}]}],
            "annotations": {},
        }
        (run_dir / "segmentation_phase_1.json").write_text(json.dumps(broken), encoding="utf-8")

        resp = self.client.get(reverse("manual-segmentation-phase-1", args=[self.project.pk]), follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "inconsistent with base text")
