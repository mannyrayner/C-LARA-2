import json
import os
import shutil
import time
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
        shutil.rmtree(self.project.artifact_dir(), ignore_errors=True)

    def _latest_run_stage_dir(self) -> Path:
        runs_root = self.project.artifact_dir() / "runs"
        runs = [p for p in runs_root.glob("run_*") if p.is_dir()]
        self.assertTrue(runs)
        latest = max(runs, key=lambda p: p.stat().st_mtime)
        return latest / "stages"

    def test_phase_1_editor_uses_read_only_structure_inputs(self):
        resp = self.client.get(reverse("manual-segmentation-phase-1", args=[self.project.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "name=\"editable_surface\"")
        self.assertContains(resp, "&lt;page&gt;")
        self.assertContains(resp, "||</code> separators")
        self.assertContains(resp, "readonly")

    def test_phase_1_save_writes_versioned_payload_with_hash_metadata(self):
        resp = self.client.post(
            reverse("manual-segmentation-phase-1", args=[self.project.pk]),
            {"editable_surface": "Hello|| world"},
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

    def test_phase_2_save_accepts_browser_crlf_for_multiline_segment(self):
        run_dir = self.project.artifact_dir() / "runs" / "run_seed_multiline" / "stages"
        run_dir.mkdir(parents=True, exist_ok=True)
        seg1_payload = {
            "l2": "non",
            "surface": "Deyr fé,\ndeyja frændr,",
            "pages": [
                {
                    "surface": "Deyr fé,\ndeyja frændr,",
                    "segments": [{"surface": "Deyr fé,\ndeyja frændr,"}],
                    "annotations": {},
                }
            ],
            "annotations": {},
        }
        (run_dir / "segmentation_phase_1.json").write_text(
            json.dumps(seg1_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        resp = self.client.post(
            reverse("manual-segmentation-phase-2", args=[self.project.pk]),
            {
                # Browsers submit textarea line breaks as CRLF.
                "tokenized_text_1_1": "Deyr¦ ¦fé¦,\r\n¦deyja¦ ¦frændr¦,",
            },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Saved manual segmentation phase 2.")

        stage_dir = self._latest_run_stage_dir()
        payload = json.loads((stage_dir / "segmentation_phase_2.json").read_text(encoding="utf-8"))
        tokens = payload["pages"][0]["segments"][0]["tokens"]
        self.assertEqual(
            tokens,
            [
                {"surface": "Deyr"},
                {"surface": " "},
                {"surface": "fé"},
                {"surface": ",\n"},
                {"surface": "deyja"},
                {"surface": " "},
                {"surface": "frændr"},
                {"surface": ","},
            ],
        )

    def test_phase_2_save_reports_precise_text_mismatch_details(self):
        run_dir = self.project.artifact_dir() / "runs" / "run_seed_mismatch" / "stages"
        run_dir.mkdir(parents=True, exist_ok=True)
        seg1_payload = {
            "l2": "en",
            "surface": "Milo was.",
            "pages": [{"surface": "Milo was.", "segments": [{"surface": "Milo was."}], "annotations": {}}],
            "annotations": {},
        }
        (run_dir / "segmentation_phase_1.json").write_text(
            json.dumps(seg1_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        resp = self.client.post(
            reverse("manual-segmentation-phase-2", args=[self.project.pk]),
            {
                "tokenized_text_1_1": "Milo¦ ¦xas.",
            },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "changes text content")
        self.assertContains(resp, "First mismatch at character 6")
        self.assertContains(resp, "edited=&#x27;x&#x27; (U+0078), expected=&#x27;w&#x27; (U+0077)")

    def test_phase_2_save_reconciles_outer_whitespace_only_difference(self):
        run_dir = self.project.artifact_dir() / "runs" / "run_seed_outer_ws" / "stages"
        run_dir.mkdir(parents=True, exist_ok=True)
        seg1_payload = {
            "l2": "en",
            "surface": "\nMilo was.",
            "pages": [{"surface": "\nMilo was.", "segments": [{"surface": "\nMilo was."}], "annotations": {}}],
            "annotations": {},
        }
        (run_dir / "segmentation_phase_1.json").write_text(
            json.dumps(seg1_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        resp = self.client.post(
            reverse("manual-segmentation-phase-2", args=[self.project.pk]),
            {
                # User edits visible content and omits the initial newline.
                "tokenized_text_1_1": "Milo¦ ¦was¦.",
            },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Saved manual segmentation phase 2.")

        stage_dir = self._latest_run_stage_dir()
        payload = json.loads((stage_dir / "segmentation_phase_2.json").read_text(encoding="utf-8"))
        tokens = payload["pages"][0]["segments"][0]["tokens"]
        self.assertEqual(tokens, [{"surface": "\nMilo"}, {"surface": " "}, {"surface": "was"}, {"surface": "."}])

    def test_project_detail_hides_manual_segmentation_links(self):
        resp = self.client.get(reverse("project-detail", args=[self.project.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, reverse("manual-segmentation-phase-1", args=[self.project.pk]))
        self.assertNotContains(resp, reverse("manual-segmentation-phase-2", args=[self.project.pk]))
        self.assertNotContains(resp, reverse("manual-translation", args=[self.project.pk]))

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

    def test_phase_1_editor_canonicalizes_trailing_page_markers(self):
        run_dir = self.project.artifact_dir() / "runs" / "run_trailing_page" / "stages"
        run_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "l2": "en",
            "surface": "Hello world<page>",
            "pages": [{"surface": "Hello world", "segments": [{"surface": "Hello world"}], "annotations": {}}],
            "annotations": {},
        }
        (run_dir / "segmentation_phase_1.json").write_text(json.dumps(payload), encoding="utf-8")
        resp = self.client.get(reverse("manual-segmentation-phase-1", args=[self.project.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, "Hello world&lt;page&gt;")

    def test_phase_1_editor_reconstructs_separators_from_pages_when_surface_has_none(self):
        self.project.source_text = "Hello world"
        self.project.save(update_fields=["source_text", "updated_at"])
        run_dir = self.project.artifact_dir() / "runs" / "run_surface_plain" / "stages"
        run_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "l2": "en",
            # Auto phase-1 output may keep plain text here without marker syntax.
            "surface": "Hello world",
            "pages": [{"surface": "Hello world", "segments": [{"surface": "Hello"}, {"surface": " world"}], "annotations": {}}],
            "annotations": {},
        }
        (run_dir / "segmentation_phase_1.json").write_text(json.dumps(payload), encoding="utf-8")

        resp = self.client.get(reverse("manual-segmentation-phase-1", args=[self.project.pk]), follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, "inconsistent with base text")
        self.assertContains(resp, "Hello|| world")

    def test_phase_1_editor_tolerates_page_boundary_newline_variants(self):
        self.project.source_text = "A.\n\nB."
        self.project.save(update_fields=["source_text", "updated_at"])
        run_dir = self.project.artifact_dir() / "runs" / "run_boundary_ws" / "stages"
        run_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "l2": "en",
            "surface": "<page>\nA.\n<page>\nB.",
            "pages": [
                {"surface": "\nA.\n", "segments": [{"surface": "\nA.\n"}], "annotations": {}},
                {"surface": "\nB.", "segments": [{"surface": "\nB."}], "annotations": {}},
            ],
            "annotations": {},
        }
        (run_dir / "segmentation_phase_1.json").write_text(json.dumps(payload), encoding="utf-8")

        resp = self.client.get(reverse("manual-segmentation-phase-1", args=[self.project.pk]), follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, "inconsistent with base text")
        self.assertContains(resp, "A.")
        self.assertContains(resp, "&lt;page&gt;")

    def test_phase_1_save_salvages_phase_2_for_unchanged_pages_and_invalidates_downstream(self):
        self.project.source_text = "AaaBbb"
        self.project.save(update_fields=["source_text", "updated_at"])
        run_dir = self.project.artifact_dir() / "runs" / "run_seed" / "stages"
        run_dir.mkdir(parents=True, exist_ok=True)
        seg1_payload = {
            "l2": "en",
            "surface": "Aaa<page>Bbb",
            "pages": [
                {"surface": "Aaa", "segments": [{"surface": "Aaa"}], "annotations": {}},
                {"surface": "Bbb", "segments": [{"surface": "Bbb"}], "annotations": {}},
            ],
            "annotations": {},
        }
        seg2_payload = {
            "l2": "en",
            "surface": "Aaa<page>Bbb",
            "pages": [
                {
                    "surface": "Aaa",
                    "segments": [{"surface": "Aaa", "tokens": [{"surface": "A"}, {"surface": "aa"}]}],
                    "annotations": {},
                },
                {
                    "surface": "Bbb",
                    "segments": [{"surface": "Bbb", "tokens": [{"surface": "B"}, {"surface": "bb"}]}],
                    "annotations": {},
                },
            ],
            "annotations": {},
        }
        (run_dir / "segmentation_phase_1.json").write_text(json.dumps(seg1_payload), encoding="utf-8")
        (run_dir / "segmentation_phase_2.json").write_text(json.dumps(seg2_payload), encoding="utf-8")
        (run_dir / "translation.json").write_text("{}", encoding="utf-8")

        resp = self.client.post(
            reverse("manual-segmentation-phase-1", args=[self.project.pk]),
            {"editable_surface": "Aaa<page>Bb||b"},
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)

        latest_stage_dir = self._latest_run_stage_dir()
        salvaged_seg2 = json.loads((latest_stage_dir / "segmentation_phase_2.json").read_text(encoding="utf-8"))
        first_page_tokens = salvaged_seg2["pages"][0]["segments"][0]["tokens"]
        self.assertEqual(first_page_tokens, [{"surface": "A"}, {"surface": "aa"}])
        second_page_tokens = salvaged_seg2["pages"][1]["segments"][0]["tokens"]
        self.assertEqual(second_page_tokens, [{"surface": "Bb"}])
        self.assertFalse((latest_stage_dir / "translation.json").exists())

    def test_annotation_home_uses_latest_stage_files_across_runs(self):
        pipeline_stage_dir = self.project.artifact_dir() / "runs" / "run_pipeline" / "stages"
        manual_stage_dir = self.project.artifact_dir() / "runs" / "run_manual" / "stages"
        pipeline_stage_dir.mkdir(parents=True, exist_ok=True)
        manual_stage_dir.mkdir(parents=True, exist_ok=True)
        (pipeline_stage_dir / "translation.json").write_text("{\"surface\":\"PIPELINE\"}", encoding="utf-8")
        (pipeline_stage_dir / "segmentation_phase_1.json").write_text("{\"surface\":\"old\"}", encoding="utf-8")
        (manual_stage_dir / "segmentation_phase_1.json").write_text("{\"surface\":\"new\"}", encoding="utf-8")
        os.utime(pipeline_stage_dir / "segmentation_phase_1.json", (1000, 1000))
        os.utime(manual_stage_dir / "segmentation_phase_1.json", (2000, 2000))

        resp = self.client.get(reverse("project-annotation-home", args=[self.project.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "run_manual/stages/segmentation_phase_1.json")
        self.assertContains(resp, "run_pipeline/stages/translation.json")

    def test_phase_2_view_uses_latest_seg2_payload_by_file_time(self):
        run_newer_dir = self.project.artifact_dir() / "runs" / "run_newer" / "stages"
        run_manual_dir = self.project.artifact_dir() / "runs" / "run_manual" / "stages"
        run_newer_dir.mkdir(parents=True, exist_ok=True)
        run_manual_dir.mkdir(parents=True, exist_ok=True)
        seg1_payload = {
            "l2": "en",
            "surface": "Hello world",
            "pages": [{"surface": "Hello world", "segments": [{"surface": "Hello world"}], "annotations": {}}],
            "annotations": {},
        }
        seg2_old = {
            "l2": "en",
            "surface": "Hello world",
            "pages": [{"surface": "Hello world", "segments": [{"surface": "Hello world", "tokens": [{"surface": "OLD"}]}]}],
            "annotations": {},
        }
        seg2_new = {
            "l2": "en",
            "surface": "Hello world",
            "pages": [{"surface": "Hello world", "segments": [{"surface": "Hello world", "tokens": [{"surface": "Hello"}, {"surface": " world"}]}]}],
            "annotations": {},
        }
        (run_newer_dir / "segmentation_phase_1.json").write_text(json.dumps(seg1_payload), encoding="utf-8")
        (run_newer_dir / "segmentation_phase_2.json").write_text(json.dumps(seg2_old), encoding="utf-8")
        (run_manual_dir / "segmentation_phase_2.json").write_text(json.dumps(seg2_new), encoding="utf-8")
        # Make manual seg2 the newest stage file while keeping run_newer directory mtime newer.
        old_ts = 1000
        new_ts = 2000
        os.utime(run_newer_dir / "segmentation_phase_2.json", (old_ts, old_ts))
        os.utime(run_manual_dir / "segmentation_phase_2.json", (new_ts, new_ts))
        os.utime(run_newer_dir.parent, (new_ts + 500, new_ts + 500))

        resp = self.client.get(reverse("manual-segmentation-phase-2", args=[self.project.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Hello¦ world")

    def test_phase_2_view_auto_reconciles_inconsistent_payload(self):
        run_dir = self.project.artifact_dir() / "runs" / "run_inconsistent" / "stages"
        run_dir.mkdir(parents=True, exist_ok=True)
        seg1_payload = {
            "l2": "en",
            "surface": "A||B<page>C",
            "pages": [
                {"surface": "A||B", "segments": [{"surface": "A"}, {"surface": "B"}], "annotations": {}},
                {"surface": "C", "segments": [{"surface": "C"}], "annotations": {}},
            ],
            "annotations": {},
        }
        seg2_payload = {
            "l2": "en",
            "surface": "A<page>B||C",
            "pages": [
                {"surface": "A", "segments": [{"surface": "A", "tokens": [{"surface": "A"}]}]},
                {
                    "surface": "B||C",
                    "segments": [
                        {"surface": "B", "tokens": [{"surface": "B"}, {"surface": "x"}]},
                        {"surface": "C", "tokens": [{"surface": "C"}]},
                    ],
                },
            ],
            "annotations": {},
        }
        (run_dir / "segmentation_phase_1.json").write_text(json.dumps(seg1_payload), encoding="utf-8")
        (run_dir / "segmentation_phase_2.json").write_text(json.dumps(seg2_payload), encoding="utf-8")

        resp = self.client.get(reverse("manual-segmentation-phase-2", args=[self.project.pk]), follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "auto-reconciled")
        self.assertContains(resp, "name=\"tokenized_text_1_2\"")
        self.assertContains(resp, ">B</textarea>")

    def test_annotation_home_shows_manual_stage_status(self):
        stage_dir = self.project.artifact_dir() / "runs" / "run_manual" / "stages"
        manual_dir = stage_dir / "manual_versions"
        stage_dir.mkdir(parents=True, exist_ok=True)
        manual_dir.mkdir(parents=True, exist_ok=True)
        (stage_dir / "segmentation_phase_1.json").write_text("{}", encoding="utf-8")
        (manual_dir / "segmentation_phase_1_20260101T000000000000Z.json").write_text("{}", encoding="utf-8")
        ts = 2000
        os.utime(stage_dir / "segmentation_phase_1.json", (ts, ts))
        os.utime(manual_dir / "segmentation_phase_1_20260101T000000000000Z.json", (ts, ts))

        resp = self.client.get(reverse("project-annotation-home", args=[self.project.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, reverse("manual-top-level", args=[self.project.pk]))
        manual = self.client.get(reverse("manual-top-level", args=[self.project.pk]))
        self.assertEqual(manual.status_code, 200)
        self.assertContains(manual, "manual edit")

    def test_phase_2_view_expands_single_token_segments_for_editability(self):
        run_dir = self.project.artifact_dir() / "runs" / "run_single_token" / "stages"
        run_dir.mkdir(parents=True, exist_ok=True)
        seg1_payload = {
            "l2": "en",
            "surface": "One day.",
            "pages": [{"surface": "One day.", "segments": [{"surface": "One day."}], "annotations": {}}],
            "annotations": {},
        }
        seg2_payload = {
            "l2": "en",
            "surface": "One day.",
            "pages": [{"surface": "One day.", "segments": [{"surface": "One day.", "tokens": [{"surface": "One day."}]}]}],
            "annotations": {},
        }
        (run_dir / "segmentation_phase_1.json").write_text(json.dumps(seg1_payload), encoding="utf-8")
        (run_dir / "segmentation_phase_2.json").write_text(json.dumps(seg2_payload), encoding="utf-8")

        resp = self.client.get(reverse("manual-segmentation-phase-2", args=[self.project.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "One¦ ¦day¦.")

    def test_manual_translation_save_and_link_visibility(self):
        run_dir = self.project.artifact_dir() / "runs" / "run_translation" / "stages"
        run_dir.mkdir(parents=True, exist_ok=True)
        seg2_payload = {
            "l2": "en",
            "surface": "Hello world",
            "pages": [{"surface": "Hello world", "segments": [{"surface": "Hello world"}], "annotations": {}}],
            "annotations": {},
        }
        (run_dir / "segmentation_phase_2.json").write_text(json.dumps(seg2_payload), encoding="utf-8")

        ann = self.client.get(reverse("project-annotation-home", args=[self.project.pk]))
        self.assertContains(ann, reverse("manual-top-level", args=[self.project.pk]))
        manual = self.client.get(reverse("manual-top-level", args=[self.project.pk]))
        self.assertContains(manual, reverse("manual-translation", args=[self.project.pk]))

        resp = self.client.post(
            reverse("manual-translation", args=[self.project.pk]),
            {"translation_text_1_1": "Bonjour le monde"},
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        stage_dir = self._latest_run_stage_dir()
        saved = json.loads((stage_dir / "translation.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["pages"][0]["segments"][0]["annotations"]["translation"], "Bonjour le monde")

    def test_manual_mwe_save_and_link_visibility(self):
        run_dir = self.project.artifact_dir() / "runs" / "run_mwe" / "stages"
        run_dir.mkdir(parents=True, exist_ok=True)
        seg2_payload = {
            "l2": "en",
            "surface": "New York!",
            "pages": [
                {
                    "surface": "New York!",
                    "segments": [
                        {
                            "surface": "New York!",
                            "tokens": [{"surface": "New"}, {"surface": " "}, {"surface": "York"}, {"surface": "!"}],
                            "annotations": {},
                        }
                    ],
                    "annotations": {},
                }
            ],
            "annotations": {},
        }
        (run_dir / "segmentation_phase_2.json").write_text(json.dumps(seg2_payload), encoding="utf-8")

        ann = self.client.get(reverse("project-annotation-home", args=[self.project.pk]))
        self.assertContains(ann, reverse("manual-top-level", args=[self.project.pk]))
        manual = self.client.get(reverse("manual-top-level", args=[self.project.pk]))
        self.assertContains(manual, reverse("manual-mwe", args=[self.project.pk]))

        resp = self.client.post(
            reverse("manual-mwe", args=[self.project.pk]),
            {"mwe_id_1_1_1": "city_1", "mwe_id_1_1_3": "city_1"},
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        stage_dir = self._latest_run_stage_dir()
        saved = json.loads((stage_dir / "mwe.json").read_text(encoding="utf-8"))
        tokens = saved["pages"][0]["segments"][0]["tokens"]
        self.assertEqual(tokens[0]["annotations"]["mwe_id"], "p0m1")
        self.assertEqual(tokens[2]["annotations"]["mwe_id"], "p0m1")
        self.assertNotIn("mwe_id", tokens[1].get("annotations", {}))
        mwes = saved["pages"][0]["segments"][0]["annotations"]["mwes"]
        self.assertEqual(len(mwes), 1)

    def test_manual_mwe_view_auto_reconciles_inconsistent_payload(self):
        run_dir = self.project.artifact_dir() / "runs" / "run_mwe_reconcile" / "stages"
        run_dir.mkdir(parents=True, exist_ok=True)
        seg2_payload = {
            "l2": "en",
            "surface": "Alpha beta",
            "pages": [
                {
                    "surface": "Alpha beta",
                    "segments": [
                        {
                            "surface": "Alpha beta",
                            "tokens": [{"surface": "Alpha"}, {"surface": " "}, {"surface": "beta"}],
                            "annotations": {},
                        }
                    ],
                    "annotations": {},
                }
            ],
            "annotations": {},
        }
        mwe_payload = {
            "l2": "en",
            "surface": "Alpha beta",
            "pages": [
                {
                    "surface": "Alpha beta",
                    "segments": [
                        {
                            "surface": "Alpha beta",
                            "tokens": [{"surface": "Alpha beta", "annotations": {"mwe_id": "bad"}}],
                            "annotations": {"mwes": [{"id": "bad", "tokens": ["Alpha beta"], "label": "x"}]},
                        }
                    ],
                    "annotations": {},
                }
            ],
            "annotations": {},
        }
        (run_dir / "segmentation_phase_2.json").write_text(json.dumps(seg2_payload), encoding="utf-8")
        (run_dir / "mwe.json").write_text(json.dumps(mwe_payload), encoding="utf-8")

        resp = self.client.get(reverse("manual-mwe", args=[self.project.pk]), follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "auto-reconciled")

    def test_manual_lemma_save_and_link_visibility(self):
        run_dir = self.project.artifact_dir() / "runs" / "run_lemma" / "stages"
        run_dir.mkdir(parents=True, exist_ok=True)
        mwe_payload = {
            "l2": "en",
            "surface": "Milo was here",
            "pages": [
                {
                    "surface": "Milo was here",
                    "segments": [
                        {
                            "surface": "Milo was here",
                            "tokens": [
                                {"surface": "Milo"},
                                {"surface": " "},
                                {"surface": "was"},
                                {"surface": " "},
                                {"surface": "here"},
                            ],
                            "annotations": {},
                        }
                    ],
                    "annotations": {},
                }
            ],
            "annotations": {},
        }
        (run_dir / "segmentation_phase_2.json").write_text(json.dumps(mwe_payload), encoding="utf-8")
        (run_dir / "mwe.json").write_text(json.dumps(mwe_payload), encoding="utf-8")

        ann = self.client.get(reverse("project-annotation-home", args=[self.project.pk]))
        self.assertContains(ann, reverse("manual-top-level", args=[self.project.pk]))
        manual = self.client.get(reverse("manual-top-level", args=[self.project.pk]))
        self.assertContains(manual, reverse("manual-lemma", args=[self.project.pk]))

        resp = self.client.post(
            reverse("manual-lemma", args=[self.project.pk]),
            {
                "lemma_1_1_1": "Milo",
                "pos_1_1_1": "PROPN",
                "lemma_1_1_3": "be",
                "pos_1_1_3": "VERB",
            },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        stage_dir = self._latest_run_stage_dir()
        saved = json.loads((stage_dir / "lemma.json").read_text(encoding="utf-8"))
        tokens = saved["pages"][0]["segments"][0]["tokens"]
        self.assertEqual(tokens[0]["annotations"]["lemma"], "Milo")
        self.assertEqual(tokens[0]["annotations"]["pos"], "PROPN")
        self.assertEqual(tokens[2]["annotations"]["lemma"], "be")
        self.assertEqual(tokens[2]["annotations"]["pos"], "VERB")
        self.assertNotIn("lemma", tokens[1].get("annotations", {}))

    def test_manual_lemma_view_auto_reconciles_inconsistent_payload(self):
        run_dir = self.project.artifact_dir() / "runs" / "run_lemma_reconcile" / "stages"
        run_dir.mkdir(parents=True, exist_ok=True)
        mwe_payload = {
            "l2": "en",
            "surface": "Alpha beta",
            "pages": [
                {
                    "surface": "Alpha beta",
                    "segments": [
                        {
                            "surface": "Alpha beta",
                            "tokens": [{"surface": "Alpha"}, {"surface": " "}, {"surface": "beta"}],
                            "annotations": {},
                        }
                    ],
                    "annotations": {},
                }
            ],
            "annotations": {},
        }
        lemma_payload = {
            "l2": "en",
            "surface": "Alpha beta",
            "pages": [
                {
                    "surface": "Alpha beta",
                    "segments": [
                        {
                            "surface": "Alpha beta",
                            "tokens": [{"surface": "Alpha beta", "annotations": {"lemma": "x", "pos": "NOUN"}}],
                            "annotations": {},
                        }
                    ],
                    "annotations": {},
                }
            ],
            "annotations": {},
        }
        (run_dir / "mwe.json").write_text(json.dumps(mwe_payload), encoding="utf-8")
        (run_dir / "lemma.json").write_text(json.dumps(lemma_payload), encoding="utf-8")

        resp = self.client.get(reverse("manual-lemma", args=[self.project.pk]), follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "auto-reconciled")

    def test_manual_gloss_save_and_link_visibility(self):
        run_dir = self.project.artifact_dir() / "runs" / "run_gloss" / "stages"
        run_dir.mkdir(parents=True, exist_ok=True)
        lemma_payload = {
            "l2": "en",
            "surface": "Milo was here",
            "pages": [
                {
                    "surface": "Milo was here",
                    "segments": [
                        {
                            "surface": "Milo was here",
                            "tokens": [
                                {"surface": "Milo", "annotations": {"lemma": "Milo", "pos": "PROPN"}},
                                {"surface": " "},
                                {"surface": "was", "annotations": {"lemma": "be", "pos": "VERB"}},
                            ],
                            "annotations": {},
                        }
                    ],
                    "annotations": {},
                }
            ],
            "annotations": {},
        }
        (run_dir / "segmentation_phase_2.json").write_text(json.dumps(lemma_payload), encoding="utf-8")
        (run_dir / "mwe.json").write_text(json.dumps(lemma_payload), encoding="utf-8")
        (run_dir / "lemma.json").write_text(json.dumps(lemma_payload), encoding="utf-8")

        ann = self.client.get(reverse("project-annotation-home", args=[self.project.pk]))
        self.assertContains(ann, reverse("manual-top-level", args=[self.project.pk]))
        manual = self.client.get(reverse("manual-top-level", args=[self.project.pk]))
        self.assertContains(manual, reverse("manual-gloss", args=[self.project.pk]))

        resp = self.client.post(
            reverse("manual-gloss", args=[self.project.pk]),
            {"gloss_1_1_1": "Milo", "gloss_1_1_3": "was"},
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        stage_dir = self._latest_run_stage_dir()
        saved = json.loads((stage_dir / "gloss.json").read_text(encoding="utf-8"))
        tokens = saved["pages"][0]["segments"][0]["tokens"]
        self.assertEqual(tokens[0]["annotations"]["gloss"], "Milo")
        self.assertEqual(tokens[2]["annotations"]["gloss"], "was")
        self.assertNotIn("gloss", tokens[1].get("annotations", {}))

    def test_manual_gloss_view_auto_reconciles_inconsistent_payload(self):
        run_dir = self.project.artifact_dir() / "runs" / "run_gloss_reconcile" / "stages"
        run_dir.mkdir(parents=True, exist_ok=True)
        lemma_payload = {
            "l2": "en",
            "surface": "Alpha beta",
            "pages": [
                {
                    "surface": "Alpha beta",
                    "segments": [
                        {
                            "surface": "Alpha beta",
                            "tokens": [{"surface": "Alpha"}, {"surface": " "}, {"surface": "beta"}],
                            "annotations": {},
                        }
                    ],
                    "annotations": {},
                }
            ],
            "annotations": {},
        }
        gloss_payload = {
            "l2": "en",
            "surface": "Alpha beta",
            "pages": [
                {
                    "surface": "Alpha beta",
                    "segments": [
                        {
                            "surface": "Alpha beta",
                            "tokens": [{"surface": "Alpha beta", "annotations": {"gloss": "bad"}}],
                            "annotations": {},
                        }
                    ],
                    "annotations": {},
                }
            ],
            "annotations": {},
        }
        (run_dir / "lemma.json").write_text(json.dumps(lemma_payload), encoding="utf-8")
        (run_dir / "gloss.json").write_text(json.dumps(gloss_payload), encoding="utf-8")

        resp = self.client.get(reverse("manual-gloss", args=[self.project.pk]), follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "auto-reconciled")

    def test_manual_pinyin_save_and_link_visibility(self):
        run_dir = self.project.artifact_dir() / "runs" / "run_pinyin" / "stages"
        run_dir.mkdir(parents=True, exist_ok=True)
        gloss_payload = {
            "l2": "zh",
            "surface": "你好 世界",
            "pages": [
                {
                    "surface": "你好 世界",
                    "segments": [
                        {
                            "surface": "你好 世界",
                            "tokens": [
                                {"surface": "你好", "annotations": {"gloss": "hello"}},
                                {"surface": " "},
                                {"surface": "世界", "annotations": {"gloss": "world"}},
                            ],
                            "annotations": {},
                        }
                    ],
                    "annotations": {},
                }
            ],
            "annotations": {},
        }
        (run_dir / "segmentation_phase_2.json").write_text(json.dumps(gloss_payload), encoding="utf-8")
        (run_dir / "mwe.json").write_text(json.dumps(gloss_payload), encoding="utf-8")
        (run_dir / "lemma.json").write_text(json.dumps(gloss_payload), encoding="utf-8")
        (run_dir / "gloss.json").write_text(json.dumps(gloss_payload), encoding="utf-8")

        ann = self.client.get(reverse("project-annotation-home", args=[self.project.pk]))
        self.assertContains(ann, reverse("manual-top-level", args=[self.project.pk]))
        manual = self.client.get(reverse("manual-top-level", args=[self.project.pk]))
        self.assertContains(manual, reverse("manual-pinyin", args=[self.project.pk]))

        resp = self.client.post(
            reverse("manual-pinyin", args=[self.project.pk]),
            {"pinyin_1_1_1": "ni3 hao3", "pinyin_1_1_3": "shi4 jie4"},
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        stage_dir = self._latest_run_stage_dir()
        saved = json.loads((stage_dir / "pinyin.json").read_text(encoding="utf-8"))
        tokens = saved["pages"][0]["segments"][0]["tokens"]
        self.assertEqual(tokens[0]["annotations"]["pinyin"], "ni3 hao3")
        self.assertEqual(tokens[2]["annotations"]["pinyin"], "shi4 jie4")
        self.assertNotIn("pinyin", tokens[1].get("annotations", {}))

    def test_manual_pinyin_view_auto_reconciles_inconsistent_payload(self):
        run_dir = self.project.artifact_dir() / "runs" / "run_pinyin_reconcile" / "stages"
        run_dir.mkdir(parents=True, exist_ok=True)
        gloss_payload = {
            "l2": "zh",
            "surface": "你好 世界",
            "pages": [
                {
                    "surface": "你好 世界",
                    "segments": [
                        {
                            "surface": "你好 世界",
                            "tokens": [{"surface": "你好"}, {"surface": " "}, {"surface": "世界"}],
                            "annotations": {},
                        }
                    ],
                    "annotations": {},
                }
            ],
            "annotations": {},
        }
        pinyin_payload = {
            "l2": "zh",
            "surface": "你好 世界",
            "pages": [
                {
                    "surface": "你好 世界",
                    "segments": [
                        {
                            "surface": "你好 世界",
                            "tokens": [{"surface": "你好 世界", "annotations": {"pinyin": "bad"}}],
                            "annotations": {},
                        }
                    ],
                    "annotations": {},
                }
            ],
            "annotations": {},
        }
        (run_dir / "gloss.json").write_text(json.dumps(gloss_payload), encoding="utf-8")
        (run_dir / "pinyin.json").write_text(json.dumps(pinyin_payload), encoding="utf-8")

        resp = self.client.get(reverse("manual-pinyin", args=[self.project.pk]), follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "auto-reconciled")

    def test_page_oriented_manual_annotation_view_renders(self):
        run_dir = self.project.artifact_dir() / "runs" / "run_page_oriented" / "stages"
        run_dir.mkdir(parents=True, exist_ok=True)
        seg1_payload = {
            "l2": "en",
            "surface": "Hello world",
            "pages": [{"surface": "Hello world", "segments": [{"surface": "Hello world"}], "annotations": {}}],
            "annotations": {},
        }
        seg2_payload = {
            "l2": "en",
            "surface": "Hello world",
            "pages": [
                {
                    "surface": "Hello world",
                    "segments": [
                        {
                            "surface": "Hello world",
                            "tokens": [{"surface": "Hello"}, {"surface": " "}, {"surface": "world"}],
                            "annotations": {},
                        }
                    ],
                    "annotations": {},
                }
            ],
            "annotations": {},
        }
        (run_dir / "segmentation_phase_1.json").write_text(json.dumps(seg1_payload), encoding="utf-8")
        (run_dir / "segmentation_phase_2.json").write_text(json.dumps(seg2_payload), encoding="utf-8")
        resp = self.client.get(reverse("manual-page-annotation", args=[self.project.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Page-oriented manual annotation")
        self.assertContains(resp, "Translation")
        self.assertContains(resp, "Romanization")

    def test_page_oriented_manual_annotation_link_location(self):
        ann = self.client.get(reverse("project-annotation-home", args=[self.project.pk]))
        self.assertContains(ann, reverse("manual-page-annotation", args=[self.project.pk]))
        manual = self.client.get(reverse("manual-top-level", args=[self.project.pk]))
        self.assertNotContains(manual, reverse("manual-page-annotation", args=[self.project.pk]))

    def test_manual_top_level_does_not_show_page_oriented_link_even_when_seg2_exists(self):
        run_dir = self.project.artifact_dir() / "runs" / "run_seg2_exists" / "stages"
        run_dir.mkdir(parents=True, exist_ok=True)
        seg1_payload = {
            "l2": "en",
            "surface": "Hello world",
            "pages": [{"surface": "Hello world", "segments": [{"surface": "Hello world"}], "annotations": {}}],
            "annotations": {},
        }
        seg2_payload = {
            "l2": "en",
            "surface": "Hello world",
            "pages": [
                {
                    "surface": "Hello world",
                    "segments": [
                        {
                            "surface": "Hello world",
                            "tokens": [{"surface": "Hello"}, {"surface": " "}, {"surface": "world"}],
                            "annotations": {},
                        }
                    ],
                    "annotations": {},
                }
            ],
            "annotations": {},
        }
        (run_dir / "segmentation_phase_1.json").write_text(json.dumps(seg1_payload), encoding="utf-8")
        (run_dir / "segmentation_phase_2.json").write_text(json.dumps(seg2_payload), encoding="utf-8")
        manual = self.client.get(reverse("manual-top-level", args=[self.project.pk]))
        self.assertEqual(manual.status_code, 200)
        self.assertNotContains(manual, reverse("manual-page-annotation", args=[self.project.pk]))

    def test_page_oriented_mode_handles_phase1_when_missing(self):
        resp = self.client.get(reverse("manual-page-annotation", args=[self.project.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Step 1: Add")
        self.assertContains(resp, "name=\"editable_surface\"")
        save = self.client.post(
            reverse("manual-page-annotation", args=[self.project.pk]),
            {"editable_surface": "Hello<page> world"},
            follow=True,
        )
        self.assertEqual(save.status_code, 200)
        stage_dir = self._latest_run_stage_dir()
        seg1 = json.loads((stage_dir / "segmentation_phase_1.json").read_text(encoding="utf-8"))
        self.assertEqual(seg1["surface"], "Hello<page> world")

    def test_page_oriented_mode_handles_phase2_when_missing(self):
        run_dir = self.project.artifact_dir() / "runs" / "run_only_seg1" / "stages"
        run_dir.mkdir(parents=True, exist_ok=True)
        seg1_payload = {
            "l2": "en",
            "surface": "Hello world",
            "pages": [{"surface": "Hello world", "segments": [{"surface": "Hello world"}], "annotations": {}}],
            "annotations": {},
        }
        (run_dir / "segmentation_phase_1.json").write_text(json.dumps(seg1_payload), encoding="utf-8")
        resp = self.client.get(reverse("manual-page-annotation", args=[self.project.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Step 2: Edit content-element boundaries")
        self.assertContains(resp, "tokenized_text_1_1")
        save = self.client.post(
            reverse("manual-page-annotation", args=[self.project.pk]),
            {"tokenized_text_1_1": "Hello¦ ¦world"},
            follow=True,
        )
        self.assertEqual(save.status_code, 200)
        stage_dir = self._latest_run_stage_dir()
        seg2 = json.loads((stage_dir / "segmentation_phase_2.json").read_text(encoding="utf-8"))
        tokens = seg2["pages"][0]["segments"][0]["tokens"]
        self.assertEqual(tokens, [{"surface": "Hello"}, {"surface": " "}, {"surface": "world"}])

    def test_page_oriented_phase2_default_boundaries_split_punctuation(self):
        run_dir = self.project.artifact_dir() / "runs" / "run_only_seg1_punct" / "stages"
        run_dir.mkdir(parents=True, exist_ok=True)
        seg1_payload = {
            "l2": "en",
            "surface": "Hello, world!",
            "pages": [{"surface": "Hello, world!", "segments": [{"surface": "Hello, world!"}], "annotations": {}}],
            "annotations": {},
        }
        (run_dir / "segmentation_phase_1.json").write_text(json.dumps(seg1_payload), encoding="utf-8")
        resp = self.client.get(reverse("manual-page-annotation", args=[self.project.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Hello¦,¦ ¦world¦!")

    def test_page_oriented_phase2_accepts_plain_pipe_delimiters(self):
        run_dir = self.project.artifact_dir() / "runs" / "run_only_seg1_pipe" / "stages"
        run_dir.mkdir(parents=True, exist_ok=True)
        seg1_payload = {
            "l2": "en",
            "surface": "Hello world",
            "pages": [{"surface": "Hello world", "segments": [{"surface": "Hello world"}], "annotations": {}}],
            "annotations": {},
        }
        (run_dir / "segmentation_phase_1.json").write_text(json.dumps(seg1_payload), encoding="utf-8")
        save = self.client.post(
            reverse("manual-page-annotation", args=[self.project.pk]),
            {"tokenized_text_1_1": "Hello| |world"},
            follow=True,
        )
        self.assertEqual(save.status_code, 200)
        stage_dir = self._latest_run_stage_dir()
        seg2 = json.loads((stage_dir / "segmentation_phase_2.json").read_text(encoding="utf-8"))
        tokens = seg2["pages"][0]["segments"][0]["tokens"]
        self.assertEqual(tokens, [{"surface": "Hello"}, {"surface": " "}, {"surface": "world"}])

    def test_page_oriented_phase2_save_targets_seg1_run(self):
        seg1_run_dir = self.project.artifact_dir() / "runs" / "run_seg1_target" / "stages"
        seg1_run_dir.mkdir(parents=True, exist_ok=True)
        newer_unrelated_run = self.project.artifact_dir() / "runs" / "run_newer_unrelated" / "stages"
        newer_unrelated_run.mkdir(parents=True, exist_ok=True)
        seg1_payload = {
            "l2": "en",
            "surface": "Hello world",
            "pages": [{"surface": "Hello world", "segments": [{"surface": "Hello world"}], "annotations": {}}],
            "annotations": {},
        }
        (seg1_run_dir / "segmentation_phase_1.json").write_text(json.dumps(seg1_payload), encoding="utf-8")
        # Make this run newer so _resolve_run_dir would pick it if the save were not anchored to the seg1 run.
        (newer_unrelated_run / "translation.json").write_text(json.dumps({"surface": ""}), encoding="utf-8")
        now = time.time()
        os.utime(seg1_run_dir.parent, (now - 10, now - 10))
        os.utime(newer_unrelated_run.parent, (now, now))

        save = self.client.post(
            reverse("manual-page-annotation", args=[self.project.pk]),
            {"tokenized_text_1_1": "Hello¦ ¦world"},
            follow=True,
        )
        self.assertEqual(save.status_code, 200)
        self.assertTrue((seg1_run_dir / "segmentation_phase_2.json").exists())
        self.assertFalse((newer_unrelated_run / "segmentation_phase_2.json").exists())

    def test_page_oriented_annotation_hides_whitespace_tokens(self):
        run_dir = self.project.artifact_dir() / "runs" / "run_page_oriented_hide_ws" / "stages"
        run_dir.mkdir(parents=True, exist_ok=True)
        seg1_payload = {
            "l2": "en",
            "surface": "Hello world",
            "pages": [{"surface": "Hello world", "segments": [{"surface": "Hello world"}], "annotations": {}}],
            "annotations": {},
        }
        seg2_payload = {
            "l2": "en",
            "surface": "Hello world",
            "pages": [
                {
                    "surface": "Hello world",
                    "segments": [
                        {
                            "surface": "Hello world",
                            "tokens": [{"surface": "Hello"}, {"surface": " "}, {"surface": "world"}],
                            "annotations": {},
                        }
                    ],
                    "annotations": {},
                }
            ],
            "annotations": {},
        }
        (run_dir / "segmentation_phase_1.json").write_text(json.dumps(seg1_payload), encoding="utf-8")
        (run_dir / "segmentation_phase_2.json").write_text(json.dumps(seg2_payload), encoding="utf-8")
        resp = self.client.get(reverse("manual-page-annotation", args=[self.project.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "name=\"mwe_id_0_0_0\"")
        self.assertContains(resp, "name=\"mwe_id_0_0_2\"")
        self.assertNotContains(resp, "name=\"mwe_id_0_0_1\"")

    def test_page_oriented_manual_annotation_save_writes_stage_payloads(self):
        run_dir = self.project.artifact_dir() / "runs" / "run_page_oriented_save" / "stages"
        run_dir.mkdir(parents=True, exist_ok=True)
        seg1_payload = {
            "l2": "en",
            "surface": "Hello world",
            "pages": [{"surface": "Hello world", "segments": [{"surface": "Hello world"}], "annotations": {}}],
            "annotations": {},
        }
        seg2_payload = {
            "l2": "en",
            "surface": "Hello world",
            "pages": [
                {
                    "surface": "Hello world",
                    "segments": [
                        {
                            "surface": "Hello world",
                            "tokens": [{"surface": "Hello"}, {"surface": " "}, {"surface": "world"}],
                            "annotations": {},
                        }
                    ],
                    "annotations": {},
                }
            ],
            "annotations": {},
        }
        (run_dir / "segmentation_phase_1.json").write_text(json.dumps(seg1_payload), encoding="utf-8")
        (run_dir / "segmentation_phase_2.json").write_text(json.dumps(seg2_payload), encoding="utf-8")
        resp = self.client.post(
            reverse("manual-page-annotation", args=[self.project.pk]),
            {
                "translation_text_0_0": "Bonjour le monde",
                "mwe_id_0_0_0": "m1",
                "mwe_id_0_0_1": "",
                "mwe_id_0_0_2": "m1",
                "lemma_0_0_0": "hello",
                "pos_0_0_0": "INTJ",
                "gloss_0_0_0": "salut",
                "pinyin_0_0_0": "ni hao",
            },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        stage_dir = self._latest_run_stage_dir()
        translation = json.loads((stage_dir / "translation.json").read_text(encoding="utf-8"))
        self.assertEqual(
            translation["pages"][0]["segments"][0]["annotations"].get("translation"),
            "Bonjour le monde",
        )
        lemma = json.loads((stage_dir / "lemma.json").read_text(encoding="utf-8"))
        self.assertEqual(lemma["pages"][0]["segments"][0]["tokens"][0]["annotations"].get("lemma"), "hello")
        self.assertEqual(lemma["pages"][0]["segments"][0]["tokens"][0]["annotations"].get("pos"), "INTJ")
