from __future__ import annotations

import json
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.test import SimpleTestCase

from projects.management.commands.split_french_evaluation_corpus import (
    assign_project_splits,
    build_manifest,
    build_segment_records,
    cap_records,
)


class SplitFrenchEvaluationCorpusTests(SimpleTestCase):
    def test_assign_project_splits_is_deterministic_and_project_separated(self):
        projects = [
            _project(1, "small-a", 2),
            _project(2, "small-b", 4),
            _project(3, "medium-a", 8),
            _project(4, "medium-b", 16),
            _project(5, "large-a", 32),
            _project(6, "large-b", 64),
        ]

        first = assign_project_splits(projects, seed="fixed", dev_project_fraction=0.5)
        second = assign_project_splits(projects, seed="fixed", dev_project_fraction=0.5)

        self.assertEqual(first, second)
        dev_ids = {assignment.project_id for assignment in first if assignment.split == "development"}
        test_ids = {assignment.project_id for assignment in first if assignment.split == "test"}
        self.assertTrue(dev_ids)
        self.assertTrue(test_ids)
        self.assertFalse(dev_ids & test_ids)
        self.assertEqual({assignment.stratum for assignment in first}, {"small", "medium", "large"})

    def test_segment_records_and_caps_use_stage_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            stage_path = tmp_path / "segmentation_phase_2.json"
            stage_path.write_text(
                json.dumps(
                    {
                        "pages": [
                            {
                                "segments": [
                                    {"surface": "Bonjour le monde", "tokens": [{"surface": "Bonjour"}, {"surface": " "}, {"surface": "monde"}]},
                                    {"surface": "Salut !", "tokens": [{"surface": "Salut"}, {"surface": " !"}]},
                                ]
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            projects = [_project(10, "fixture", 2, stage_path)]
            assignments = assign_project_splits(projects, seed="fixed", dev_project_fraction=0.5)

            records_by_split = build_segment_records(assignments, seed="fixed")
            all_records = records_by_split[assignments[0].split]
            capped = cap_records(all_records, 1, seed="fixed", split=assignments[0].split)
            manifest = build_manifest(
                source_summary=tmp_path / "corpus_summary.json",
                assignments=assignments,
                development_records=capped if assignments[0].split == "development" else [],
                test_records=capped if assignments[0].split == "test" else [],
                seed="fixed",
                dev_project_fraction=0.5,
                max_development_segments=1,
                max_test_segments=1,
                development_jsonl=tmp_path / "development.jsonl",
                test_jsonl=tmp_path / "test.jsonl",
            )

            self.assertEqual(len(all_records), 2)
            self.assertEqual(len(capped), 1)
            self.assertEqual(all_records[0].project_id, 10)
            self.assertIn("H1:", manifest["hypotheses"][0])
            self.assertTrue(manifest["summary"]["project_level_separation"])

    def test_management_command_writes_split_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            stage_paths = []
            projects = []
            for project_id in range(1, 5):
                stage_path = tmp_path / f"project_{project_id}" / "stages" / "segmentation_phase_2.json"
                stage_path.parent.mkdir(parents=True)
                stage_path.write_text(
                    json.dumps({"pages": [{"segments": [{"surface": f"Segment {project_id}", "tokens": [{"surface": "Segment"}, {"surface": " "}, {"surface": str(project_id)}]}]}]}),
                    encoding="utf-8",
                )
                stage_paths.append(stage_path)
                projects.append(_project(project_id, f"project {project_id}", project_id * 10, stage_path))
            summary_path = tmp_path / "corpus_summary.json"
            summary_path.write_text(json.dumps({"summary": {"project_count": len(projects)}, "projects": projects}), encoding="utf-8")
            output_dir = tmp_path / "splits"

            call_command(
                "split_french_evaluation_corpus",
                corpus_summary_json=str(summary_path),
                output_dir=str(output_dir),
                seed="fixed",
                max_development_segments=5,
                max_test_segments=5,
            )

            self.assertTrue((output_dir / "development.jsonl").exists())
            self.assertTrue((output_dir / "test.jsonl").exists())
            manifest = json.loads((output_dir / "split_manifest.json").read_text(encoding="utf-8"))
            self.assertTrue(manifest["summary"]["project_level_separation"])
            self.assertIn("human_audit_plan", manifest)


def _project(project_id: int, title: str, segment_count: int, stage_path: Path | None = None) -> dict[str, object]:
    return {
        "project_id": project_id,
        "title": title,
        "has_segmentation_phase_2": True,
        "segment_count": segment_count,
        "latest_segmentation_path": str(stage_path or f"/tmp/project_{project_id}/segmentation_phase_2.json"),
    }
