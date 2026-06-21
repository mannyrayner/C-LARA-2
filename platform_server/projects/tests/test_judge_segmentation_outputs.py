from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase

from projects.management.commands.judge_segmentation_outputs import (
    judgement_record_from_output,
    segmentation_cache_key,
)


class JudgeSegmentationOutputsTests(SimpleTestCase):
    def test_judgement_record_formats_segments_and_cache_key(self):
        payload = output_payload()

        record = judgement_record_from_output(payload, run_label="fixture-run")

        self.assertEqual(record["record_id"], "r1")
        self.assertEqual(record["input_surface"], "\nDans un futur proche,")
        self.assertEqual(record["segments_display"], "Dans| |un| |futur| |proche|,")
        self.assertEqual(
            record["cache_key"],
            segmentation_cache_key("\nDans un futur proche,", ["Dans", " ", "un", " ", "futur", " ", "proche", ","]),
        )

    def test_command_appends_judgement_and_cache_then_reuses_cached_segmentation(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            outputs_path = tmp_path / "outputs.jsonl"
            outputs_path.write_text(json.dumps(output_payload()) + "\n", encoding="utf-8")
            judgements_path = tmp_path / "judgements.jsonl"
            cache_path = tmp_path / "cache.json"

            with patch("builtins.input", side_effect=["a", "good"]):
                call_command(
                    "judge_segmentation_outputs",
                    outputs_jsonl=str(outputs_path),
                    judgements_jsonl=str(judgements_path),
                    cache_json=str(cache_path),
                    run_label="fixture-run",
                )

            judgements = [json.loads(line) for line in judgements_path.read_text(encoding="utf-8").splitlines()]
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
            self.assertEqual(judgements[0]["judgement"], "accept")
            self.assertFalse(judgements[0]["reused_cached_judgement"])
            self.assertEqual(len(cache), 1)

            second_judgements = tmp_path / "second.jsonl"
            call_command(
                "judge_segmentation_outputs",
                outputs_jsonl=str(outputs_path),
                judgements_jsonl=str(second_judgements),
                cache_json=str(cache_path),
                run_label="fixture-run-2",
                include_cached=True,
            )

            reused = [json.loads(line) for line in second_judgements.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(reused[0]["judgement"], "accept")
            self.assertTrue(reused[0]["reused_cached_judgement"])


def output_payload():
    return {
        "record_id": "r1",
        "project_id": 8,
        "project_title": "La copine artificielle",
        "split": "development",
        "page_index": 1,
        "segment_index": 1,
        "input_surface": "\nDans un futur proche,",
        "segmentation_phase_2": {
            "pages": [
                {
                    "segments": [
                        {
                            "tokens": [
                                {"surface": "Dans"},
                                {"surface": " "},
                                {"surface": "un"},
                                {"surface": " "},
                                {"surface": "futur"},
                                {"surface": " "},
                                {"surface": "proche"},
                                {"surface": ","},
                            ]
                        }
                    ]
                }
            ]
        },
    }
