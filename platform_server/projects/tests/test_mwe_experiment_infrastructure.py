from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from pipeline.stage_artifacts import write_stage_artifact
from projects.management.commands.refresh_mwe_experiment_projects import refresh_projects, resolve_project_ids
from projects.models import Project


class MWEExperimentInfrastructureTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="mannyrayner", password="pw")
        self.projects: list[Project] = []

    def tearDown(self):
        for project in self.projects:
            shutil.rmtree(project.artifact_dir(), ignore_errors=True)

    def _project_with_mwe(self, *, title: str, language: str, idx: int) -> Project:
        project = Project.objects.create(
            owner=self.user,
            title=title,
            language=language,
            target_language="en" if language != "en" else "fr",
            source_text=f"source {idx}",
        )
        self.projects.append(project)
        write_stage_artifact(
            project.artifact_dir() / "runs" / "run_mwe_seed",
            "mwe",
            {
                "pages": [
                    {
                        "segments": [
                            {
                                "surface": f"take off {idx}",
                                "tokens": [
                                    {"surface": "take", "annotations": {"mwe_id": "m1"}},
                                    {"surface": " "},
                                    {"surface": "off", "annotations": {"mwe_id": "m1"}},
                                ],
                                "annotations": {"mwes": [{"id": "m1", "tokens": ["take", "off"], "label": "verb_particle"}]},
                            }
                        ]
                    }
                ]
            },
        )
        return project

    def test_extract_mwe_corpus_writes_project_and_segment_splits(self):
        for language in ("en", "fr", "de"):
            for idx in range(6):
                self._project_with_mwe(title=f"{language} fixture {idx}", language=language, idx=idx)

        with TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "mwe_splits"
            call_command(
                "extract_mwe_corpus",
                username="mannyrayner",
                languages="en,fr,de",
                output_dir=str(output_dir),
                seed="test-mwe-seed",
                development_project_fraction=0.5,
                validation_project_fraction=0.25,
                max_development_segments=100,
                max_validation_segments=100,
                max_test_segments=100,
                overwrite=True,
            )

            manifest = json.loads((output_dir / "multilingual_split_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["languages"], ["en", "fr", "de"])
            for language in ("en", "fr", "de"):
                language_manifest = manifest["languages_detail"][language]
                self.assertEqual(language_manifest["project_count"], 6)
                self.assertTrue(language_manifest["project_level_separation"])
                dev_projects = [
                    json.loads(line)
                    for line in (output_dir / language / "development_projects.jsonl").read_text(encoding="utf-8").splitlines()
                    if line.strip()
                ]
                dev_segments = [
                    json.loads(line)
                    for line in (output_dir / language / "development_segments.jsonl").read_text(encoding="utf-8").splitlines()
                    if line.strip()
                ]
                self.assertTrue(dev_projects)
                self.assertTrue(dev_segments)
                self.assertEqual(dev_segments[0]["language"], language)
                self.assertIn("gold_mwes", dev_segments[0])
                review_text = (output_dir / language / "segments_with_mwes.md").read_text(encoding="utf-8")
                self.assertIn("Total MWEs:", review_text)
                self.assertIn("take | off", review_text)
                self.assertGreater(language_manifest["mwe_count"], 0)

    def test_extract_mwe_corpus_can_split_before_mwe_artifacts_exist(self):
        for idx in range(4):
            project = Project.objects.create(
                owner=self.user,
                title=f"unprocessed {idx}",
                language="en",
                target_language="fr",
                source_text=f"source text {idx}",
            )
            self.projects.append(project)

        with TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "pre_refresh_splits"
            call_command(
                "extract_mwe_corpus",
                username="mannyrayner",
                languages="en",
                output_dir=str(output_dir),
                seed="pre-refresh",
                overwrite=True,
            )

            manifest = json.loads((output_dir / "multilingual_split_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["languages_detail"]["en"]["project_count"], 4)
            dev_projects = [
                json.loads(line)
                for line in (output_dir / "en" / "development_projects.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            dev_segments = (output_dir / "en" / "development_segments.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertTrue(dev_projects)
            self.assertEqual(dev_segments, [])
            review_text = (output_dir / "en" / "segments_with_mwes.md").read_text(encoding="utf-8")
            self.assertIn("Total MWEs: 0", review_text)


    def test_explicit_project_ids_ignore_split_manifest(self):
        first = self._project_with_mwe(title="English one", language="en", idx=1)
        second = self._project_with_mwe(title="German one", language="de", idx=2)
        manifest = {"splits": {"development": {"project_ids": [second.id]}}}
        with TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "split_manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            ids = resolve_project_ids(
                project_ids_text=str(first.id),
                split_manifest_text=str(manifest_path),
                splits=["development"],
            )

        self.assertEqual(ids, [first.id])

    def test_refresh_projects_starts_from_latest_segmentation_phase_1_artifact(self):
        project = Project.objects.create(
            owner=self.user,
            title="English source",
            language="en",
            target_language="fr",
            source_text="This raw text should not be resegmented.",
        )
        self.projects.append(project)
        seg1_payload = {
            "l2": "en",
            "surface": "Page one",
            "pages": [
                {
                    "surface": "Page one",
                    "segments": [{"surface": "Page one", "annotations": {}}],
                    "annotations": {},
                }
            ],
            "annotations": {},
        }
        write_stage_artifact(project.artifact_dir() / "runs" / "run_imported", "segmentation_phase_1", seg1_payload)

        with patch("projects.management.commands.refresh_mwe_experiment_projects.run_full_pipeline", AsyncMock(return_value=seg1_payload)) as runner:
            asyncio.run(
                refresh_projects(
                    [project],
                    run_label_prefix="refresh",
                    start_stage="segmentation_phase_2",
                    end_stage="gloss",
                    stage_parameters={"segmentation_phase_2": {"mechanism": "chunk_decomposition"}},
                )
            )

        spec = runner.await_args.args[0]
        self.assertIsNone(spec.text)
        self.assertEqual(spec.text_obj, seg1_payload)
        self.assertEqual(spec.start_stage, "segmentation_phase_2")
        self.assertEqual(spec.end_stage, "gloss")
        self.assertEqual(spec.stage_parameters["segmentation_phase_2"]["mechanism"], "chunk_decomposition")

    def test_refresh_command_dry_run_uses_split_manifest_project_ids(self):
        first = self._project_with_mwe(title="English one", language="en", idx=1)
        second = self._project_with_mwe(title="English two", language="en", idx=2)
        manifest = {
            "languages_detail": {
                "en": {
                    "splits": {
                        "development": {"project_ids": [first.id]},
                        "validation": {"project_ids": [second.id]},
                        "test": {"project_ids": []},
                    }
                }
            }
        }
        with TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "split_manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            self.assertEqual(resolve_project_ids(project_ids_text="", split_manifest_text=str(manifest_path), splits=["development"]), [first.id])
            with patch("projects.management.commands.refresh_mwe_experiment_projects.run_full_pipeline", AsyncMock()) as runner:
                call_command(
                    "refresh_mwe_experiment_projects",
                    split_manifest=str(manifest_path),
                    splits="development",
                    run_label_prefix="dry",
                    dry_run=True,
                )
            runner.assert_not_called()
