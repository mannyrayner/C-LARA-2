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

            with patch("builtins.input", side_effect=["p", "l", "clear phrasal verb"]):
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

    def test_review_can_preserve_primary_and_add_complete_acceptable_alternative(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            gold_path = root / "gold.jsonl"
            outputs_path = root / "outputs.jsonl"
            review_path = root / "review.jsonl"
            gold_path.write_text(
                json.dumps({"record_id": "en:1", "segment_surface": "International Space Station", "gold_mwes": []}) + "\n",
                encoding="utf-8",
            )
            outputs_path.write_text(
                json.dumps({
                    "record_id": "en:1",
                    "segment_surface": "International Space Station",
                    "predicted_mwes": spans_to_mwes([["International", "Space", "Station"]]),
                }) + "\n",
                encoding="utf-8",
            )

            with patch("builtins.input", side_effect=["b", "n", "name and compositional readings both help learners"]):
                call_command(
                    "review_mwe_prompt_divergences",
                    gold_jsonl=str(gold_path), outputs_jsonl=str(outputs_path), review_jsonl=str(review_path),
                )

            latest = json.loads(gold_path.read_text(encoding="utf-8").splitlines()[-1])
            self.assertEqual(latest["gold_mwes"], [])
            alternative = latest["acceptable_mwe_analyses"][0]
            self.assertEqual(alternative["mwes"], spans_to_mwes([["international", "space", "station"]]))
            self.assertEqual(alternative["category"], "proper_name")
            summary = json.loads((root / "review_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["both_acceptable"], 1)
            self.assertEqual(summary["primary_gold_changed"], 0)

    def test_ambiguity_aware_scorer_accepts_alternative_without_changing_strict_score(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            gold_path = root / "gold.jsonl"
            outputs_path = root / "outputs.jsonl"
            score_dir = root / "score"
            alternative = spans_to_mwes([["International", "Space", "Station"]])
            gold_path.write_text(json.dumps({
                "record_id": "en:1", "gold_mwes": [],
                "acceptable_mwe_analyses": [{"analysis_id": "alternative_1", "mwes": alternative}],
            }) + "\n", encoding="utf-8")
            outputs_path.write_text(json.dumps({
                "record_id": "en:1", "project_id": 1, "gold_mwes": [], "predicted_mwes": alternative,
            }) + "\n", encoding="utf-8")

            call_command(
                "score_mwe_prompt_outputs", outputs_jsonl=str(outputs_path), gold_jsonl=str(gold_path),
                output_dir=str(score_dir), overwrite=True,
            )

            summary = json.loads((score_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["f1"], 0.0)
            self.assertEqual(summary["ambiguity_aware"]["f1"], 1.0)
            self.assertEqual(summary["predictions_accepted_via_alternative"], 1)

    def test_ambiguity_aware_scorer_does_not_union_distinct_analyses(self):
        from projects.management.commands.score_mwe_prompt_outputs import score_record

        record = {
            "record_id": "en:1",
            "gold_mwes": spans_to_mwes([["in", "orbit"]]),
            "acceptable_mwe_analyses": [{
                "analysis_id": "alternative_1", "mwes": spans_to_mwes([["space", "station"]]),
            }],
            "predicted_mwes": spans_to_mwes([["in", "orbit"], ["space", "station"]]),
        }
        scored = score_record(record)
        self.assertFalse(scored["ambiguity_aware_exact_match"])
        self.assertEqual(scored["ambiguity_aware_false_positive"], 1)
