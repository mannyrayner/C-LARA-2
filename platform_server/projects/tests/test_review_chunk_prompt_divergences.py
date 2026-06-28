from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase


class ReviewChunkPromptDivergencesTests(SimpleTestCase):
    def test_command_can_use_prediction_to_correct_gold(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            gold_path = root / "gold.jsonl"
            predictions_path = root / "predictions.jsonl"
            review_path = root / "review.jsonl"
            gold_record = {
                "record_id": "de:1",
                "split": "development",
                "language": "de",
                "project_id": 199,
                "project_title": "Fixture",
                "page_index": 1,
                "segment_index": 1,
                "chunk_index": 1,
                "segment_surface": "„Natürlich.\"",
                "chunk_surface": "„Natürlich.\"",
                "gold_parts": ["„Natürlich", ".\""],
                "gold_segments_display": "„Natürlich|.\"",
            }
            prediction_record = {
                "record_id": "de:1",
                "chunk_surface": "„Natürlich.\"",
                "predicted_parts": ["„", "Natürlich", ".\""],
                "predicted_segments_display": "„|Natürlich|.\"",
                "surface_preserved": True,
            }
            gold_path.write_text(json.dumps(gold_record, ensure_ascii=False) + "\n", encoding="utf-8")
            predictions_path.write_text(json.dumps(prediction_record, ensure_ascii=False) + "\n", encoding="utf-8")

            with patch("builtins.input", side_effect=["p", "punctuation split"]):
                call_command(
                    "review_chunk_prompt_divergences",
                    gold_jsonl=str(gold_path),
                    predictions_jsonl=str(predictions_path),
                    review_jsonl=str(review_path),
                )

            gold_records = [json.loads(line) for line in gold_path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(gold_records), 2)
            self.assertEqual(gold_records[-1]["gold_parts"], ["„", "Natürlich", ".\""])
            self.assertEqual(gold_records[-1]["human_judgement"], "gold_corrected_from_prediction")
            review_records = [json.loads(line) for line in review_path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(review_records[0]["review_decision"], "use_prediction")
            self.assertEqual(review_records[0]["gold_parts_after"], ["„", "Natürlich", ".\""])

    def test_command_can_accept_current_gold_without_appending_gold(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            gold_path = root / "gold.jsonl"
            predictions_path = root / "predictions.jsonl"
            review_path = root / "review.jsonl"
            gold_path.write_text(
                json.dumps({"record_id": "de:1", "chunk_surface": "Beim", "gold_parts": ["Beim"]}) + "\n",
                encoding="utf-8",
            )
            predictions_path.write_text(
                json.dumps({"record_id": "de:1", "chunk_surface": "Beim", "predicted_parts": ["Bei", "m"]}) + "\n",
                encoding="utf-8",
            )

            with patch("builtins.input", side_effect=["a", "keep contraction"]):
                call_command(
                    "review_chunk_prompt_divergences",
                    gold_jsonl=str(gold_path),
                    predictions_jsonl=str(predictions_path),
                    review_jsonl=str(review_path),
                )

            self.assertEqual(len(gold_path.read_text(encoding="utf-8").splitlines()), 1)
            review_record = json.loads(review_path.read_text(encoding="utf-8").strip())
            self.assertEqual(review_record["review_decision"], "accept_gold")
