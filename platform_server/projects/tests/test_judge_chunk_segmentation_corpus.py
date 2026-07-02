from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase

from projects.management.commands.judge_chunk_segmentation_corpus import parse_gold_parts, validate_gold_parts


class JudgeChunkSegmentationCorpusTests(SimpleTestCase):
    def test_parse_and_validate_gold_parts_require_surface_preservation(self):
        record = {"chunk_surface": "L'amour"}

        parts = parse_gold_parts("L'|amour")

        self.assertEqual(parts, ["L'", "amour"])
        self.assertEqual(validate_gold_parts(record, parts), "")
        self.assertIn("concatenate", validate_gold_parts(record, ["L'", "ami"]))

    def test_command_accepts_and_corrects_records_append_only(self):
        with TemporaryDirectory() as tmp:
            input_path = Path(tmp) / "input.jsonl"
            output_path = Path(tmp) / "gold.jsonl"
            records = [
                {
                    "record_id": "fr:project_1:p1:s1:c1",
                    "split": "development",
                    "language": "fr",
                    "project_id": 1,
                    "project_title": "Fixture",
                    "page_index": 1,
                    "segment_index": 1,
                    "chunk_index": 1,
                    "segment_surface": "L'amour revient",
                    "chunk_surface": "L'amour",
                    "gold_parts": ["L'amour"],
                    "gold_segments_display": "L'amour",
                },
                {
                    "record_id": "fr:project_1:p1:s1:c2",
                    "split": "development",
                    "language": "fr",
                    "project_id": 1,
                    "project_title": "Fixture",
                    "page_index": 1,
                    "segment_index": 1,
                    "chunk_index": 2,
                    "segment_surface": "L'amour revient",
                    "chunk_surface": "revient",
                    "gold_parts": ["revient"],
                    "gold_segments_display": "revient",
                },
            ]
            input_path.write_text("".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records), encoding="utf-8")
            responses = iter(["c L'|amour", "corrected", "a", ""])

            with patch("builtins.input", side_effect=lambda _prompt="": next(responses)):
                call_command(
                    "judge_chunk_segmentation_corpus",
                    input_jsonl=str(input_path),
                    output_jsonl=str(output_path),
                )

            judged = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(judged), 2)
            self.assertEqual(judged[0]["human_judgement"], "corrected")
            self.assertEqual(judged[0]["gold_parts"], ["L'", "amour"])
            self.assertEqual(judged[0]["human_notes"], "corrected")
            self.assertEqual(judged[1]["human_judgement"], "accepted")
            self.assertEqual(judged[1]["gold_parts"], ["revient"])
