from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase

from projects.management.commands.review_mwe_prompt_divergences import spans_to_mwes


class ReviewMWEPromptDivergencesTests(SimpleTestCase):
    def test_review_can_replace_dubious_gold_with_prediction(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            gold_path = root / "gold.jsonl"
            outputs_path = root / "outputs.jsonl"
            review_path = root / "review.jsonl"
            gold_path.write_text(
                json.dumps({"record_id": "en:1", "segment_surface": "They took off.", "gold_mwes": []}) + "\n",
                encoding="utf-8",
            )
            outputs_path.write_text(
                json.dumps(
                    {
                        "record_id": "en:1",
                        "segment_surface": "They took off.",
                        "predicted_mwes": [{"id": "m1", "tokens": ["took", "off"]}],
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            with patch("builtins.input", side_effect=["p", "clear phrasal verb"]):
                call_command(
                    "review_mwe_prompt_divergences",
                    gold_jsonl=str(gold_path),
                    outputs_jsonl=str(outputs_path),
                    review_jsonl=str(review_path),
                )

            records = [json.loads(line) for line in gold_path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(records[-1]["gold_mwes"], spans_to_mwes([["took", "off"]]))
            self.assertEqual(records[-1]["pre_review_gold_mwes"], [])
            self.assertTrue(review_path.exists())

    def test_scorer_uses_latest_reviewed_gold_override(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            gold_path = root / "gold.jsonl"
            outputs_path = root / "outputs.jsonl"
            score_dir = root / "score"
            gold_path.write_text(
                "\n".join(
                    [
                        json.dumps({"record_id": "en:1", "gold_mwes": []}),
                        json.dumps({"record_id": "en:1", "gold_mwes": spans_to_mwes([["took", "off"]])}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            outputs_path.write_text(
                json.dumps(
                    {
                        "record_id": "en:1",
                        "project_id": 1,
                        "gold_mwes": [],
                        "predicted_mwes": spans_to_mwes([["took", "off"]]),
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            call_command(
                "score_mwe_prompt_outputs",
                outputs_jsonl=str(outputs_path),
                gold_jsonl=str(gold_path),
                output_dir=str(score_dir),
                overwrite=True,
            )

            summary = json.loads((score_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["f1"], 1.0)
            self.assertEqual(summary["exact_match_count"], 1)
