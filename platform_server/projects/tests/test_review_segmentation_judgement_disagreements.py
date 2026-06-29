from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase


class ReviewSegmentationJudgementDisagreementsTests(SimpleTestCase):
    def test_command_appends_gold_correction_and_review_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            disagreements = root / "disagreements.jsonl"
            gold = root / "gold.jsonl"
            reviewed = root / "reviewed.jsonl"
            disagreements.write_text(
                json.dumps(
                    {
                        "record_id": "r1",
                        "project_id": 1,
                        "project_title": "Title",
                        "split": "development",
                        "input_surface": "conférant à l'ambiance",
                        "segments_display": "conférant| |à| |l|'|ambiance",
                        "gold_judgement": "accept",
                        "evaluator_judgement": "reject",
                        "evaluator_notes": "bad l' split",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            gold.write_text(
                json.dumps({"record_id": "r1", "judgement": "accept"}) + "\n",
                encoding="utf-8",
            )
            responses = iter(["r", "gold was wrong"])
            with patch("builtins.input", side_effect=lambda _prompt="": next(responses)):
                call_command(
                    "review_segmentation_judgement_disagreements",
                    disagreements_jsonl=str(disagreements),
                    gold_judgements=str(gold),
                    reviewed_jsonl=str(reviewed),
                    run_label="review",
                )
            gold_records = [json.loads(line) for line in gold.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(gold_records[-1]["judgement"], "reject")
            self.assertEqual(gold_records[-1]["source"], "ai_evaluator_disagreement_review")
            reviewed_records = [json.loads(line) for line in reviewed.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(reviewed_records[0]["corrected_gold_judgement"], "reject")

    def test_command_back_corrects_numbered_disagreement(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            disagreements = root / "disagreements.jsonl"
            gold = root / "gold.jsonl"
            reviewed = root / "reviewed.jsonl"
            disagreements.write_text(
                "".join(
                    json.dumps(
                        {
                            "record_id": f"r{idx}",
                            "input_surface": f"input {idx}",
                            "segments_display": f"seg {idx}",
                            "gold_judgement": "accept",
                            "evaluator_judgement": "reject",
                        }
                    )
                    + "\n"
                    for idx in (1, 2)
                ),
                encoding="utf-8",
            )
            gold.write_text("", encoding="utf-8")
            responses = iter(["s", "", "b 1", "r", "fix first", "r", "fix second"])
            with patch("builtins.input", side_effect=lambda _prompt="": next(responses)):
                call_command(
                    "review_segmentation_judgement_disagreements",
                    disagreements_jsonl=str(disagreements),
                    gold_judgements=str(gold),
                    reviewed_jsonl=str(reviewed),
                )
            gold_records = [json.loads(line) for line in gold.read_text(encoding="utf-8").splitlines()]
            self.assertEqual([record["record_id"] for record in gold_records], ["r1", "r2"])

    def test_command_accepting_current_gold_writes_review_log_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            disagreements = root / "disagreements.jsonl"
            gold = root / "gold.jsonl"
            reviewed = root / "reviewed.jsonl"
            disagreements.write_text(
                json.dumps(
                    {
                        "record_id": "r1",
                        "input_surface": "avoir",
                        "segments_display": "avoir",
                        "gold_judgement": "accept",
                        "evaluator_judgement": "reject",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            gold.write_text(json.dumps({"record_id": "r1", "judgement": "accept"}) + "\n", encoding="utf-8")
            responses = iter(["a", "gold is correct"])
            with patch("builtins.input", side_effect=lambda _prompt="": next(responses)):
                call_command(
                    "review_segmentation_judgement_disagreements",
                    disagreements_jsonl=str(disagreements),
                    gold_judgements=str(gold),
                    reviewed_jsonl=str(reviewed),
                )
            self.assertEqual(len(gold.read_text(encoding="utf-8").splitlines()), 1)
            reviewed_record = json.loads(reviewed.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(reviewed_record["corrected_gold_judgement"], "accept")
