from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.test import SimpleTestCase

from projects.management.commands.prepare_chunk_prompt_improvement import classify_error, compare_records


class PrepareChunkPromptImprovementTests(SimpleTestCase):
    def test_compare_records_classifies_over_and_under_splits(self):
        gold = {
            "one": {"record_id": "one", "chunk_surface": "lamour", "gold_parts": ["l", "amour"]},
            "two": {"record_id": "two", "chunk_surface": "bonjour", "gold_parts": ["bonjour"]},
        }
        predictions = {
            "one": {"record_id": "one", "predicted_parts": ["lamour"]},
            "two": {"record_id": "two", "predicted_segments_display": "bon|jour"},
        }

        comparisons = compare_records(gold, predictions)

        self.assertEqual([item["status"] for item in comparisons], ["under_split", "over_split"])
        self.assertEqual(classify_error(["a"], ["b"]), "boundary_mismatch")

    def test_command_writes_anti_overfitting_brief(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            gold_path = root / "gold.jsonl"
            predictions_path = root / "predictions.jsonl"
            prompt_path = root / "prompt.md"
            output_dir = root / "brief"
            gold_records = [
                {
                    "record_id": "fr:1",
                    "language": "fr",
                    "chunk_surface": "L'amour",
                    "segment_surface": "L'amour revient",
                    "gold_parts": ["L'", "amour"],
                    "project_id": 1,
                    "project_title": "Fixture",
                },
                {
                    "record_id": "fr:2",
                    "language": "fr",
                    "chunk_surface": "revient",
                    "segment_surface": "L'amour revient",
                    "gold_parts": ["revient"],
                    "project_id": 1,
                    "project_title": "Fixture",
                },
            ]
            prediction_records = [
                {"record_id": "fr:1", "chunk_surface": "L'amour", "predicted_parts": ["L'amour"]},
                {"record_id": "fr:2", "chunk_surface": "revient", "predicted_parts": ["revient"]},
            ]
            gold_path.write_text("".join(json.dumps(record, ensure_ascii=False) + "\n" for record in gold_records), encoding="utf-8")
            predictions_path.write_text(
                "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in prediction_records),
                encoding="utf-8",
            )
            prompt_path.write_text("Current compact prompt", encoding="utf-8")

            call_command(
                "prepare_chunk_prompt_improvement",
                gold_jsonl=str(gold_path),
                predictions_jsonl=str(predictions_path),
                language="fr",
                prompt_kind="segmentation",
                current_prompt=str(prompt_path),
                output_dir=str(output_dir),
                overwrite=True,
            )

            brief = json.loads((output_dir / "prompt_improvement_brief.json").read_text(encoding="utf-8"))
            markdown = (output_dir / "prompt_improvement_brief.md").read_text(encoding="utf-8")
            self.assertEqual(brief["summary"]["records_compared"], 2)
            self.assertEqual(brief["summary"]["error_count"], 1)
            self.assertIn("Keep the revised prompt short", brief["anti_overfitting_requirements"][0])
            self.assertIn("under_split", markdown)
