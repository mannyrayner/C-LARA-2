from __future__ import annotations

import json
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from pipeline.stage_artifacts import write_stage_artifact
from projects.management.commands.extract_chunk_segmentation_corpus import chunks_from_token_surfaces
from projects.models import Project


class ExtractChunkSegmentationCorpusTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="mannyrayner", password="pw")
        self.projects: list[Project] = []

    def tearDown(self):
        for project in self.projects:
            shutil.rmtree(project.artifact_dir(), ignore_errors=True)

    def _project_with_segmentation(self, *, title: str, language: str, project_index: int) -> Project:
        project = Project.objects.create(
            owner=self.user,
            title=title,
            language=language,
            target_language="en" if language != "en" else "fr",
            source_text="source",
        )
        self.projects.append(project)
        write_stage_artifact(
            project.artifact_dir() / "runs" / "run_imported",
            "segmentation_phase_2",
            {
                "pages": [
                    {
                        "segments": [
                            {
                                "surface": f"L'amour revient {project_index}.",
                                "tokens": [
                                    {"surface": "L'"},
                                    {"surface": "amour"},
                                    {"surface": " revient"},
                                    {"surface": f" {project_index}"},
                                    {"surface": "."},
                                ],
                            }
                        ]
                    }
                ]
            },
        )
        return project

    def test_chunks_from_token_surfaces_preserves_internal_boundaries(self):
        chunks = chunks_from_token_surfaces(["L'", "amour", " revient", " aujourd'hui", "."])

        self.assertEqual(chunks, [["L'", "amour"], ["revient"], ["aujourd'hui", "."]])

    def test_command_extracts_project_separated_language_splits(self):
        for language in ("fr", "de", "en"):
            for idx in range(12):
                self._project_with_segmentation(title=f"{language} fixture {idx}", language=language, project_index=idx)

        with TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "splits"
            call_command(
                "extract_chunk_segmentation_corpus",
                username="mannyrayner",
                languages="fr,de,en",
                output_dir=str(output_dir),
                seed="test-seed",
                development_project_fraction=0.5,
                validation_project_fraction=0.25,
                max_development_chunks=100,
                max_validation_chunks=100,
                max_test_chunks=100,
                overwrite=True,
            )

            manifest = json.loads((output_dir / "multilingual_split_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["languages"], ["fr", "de", "en"])
            for language in ("fr", "de", "en"):
                language_manifest = manifest["languages_detail"][language]
                self.assertEqual(language_manifest["project_count"], 12)
                split_project_sets = [
                    set(language_manifest["splits"][split]["project_ids"])
                    for split in ("development", "validation", "test")
                ]
                self.assertFalse(split_project_sets[0] & split_project_sets[1])
                self.assertFalse(split_project_sets[0] & split_project_sets[2])
                self.assertFalse(split_project_sets[1] & split_project_sets[2])
                self.assertTrue(all(split_project_sets))
                dev_records = [
                    json.loads(line)
                    for line in (output_dir / language / "development.jsonl").read_text(encoding="utf-8").splitlines()
                    if line.strip()
                ]
                self.assertTrue(dev_records)
                self.assertEqual(dev_records[0]["language"], language)
                self.assertIn("chunk_surface", dev_records[0])
                self.assertIn("gold_parts", dev_records[0])
