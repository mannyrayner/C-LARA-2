from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.test import SimpleTestCase

from projects.management.commands.evaluate_segmentation_outputs_with_ai import (
    build_evaluator_prompt,
    evaluator_cache_key,
    normalise_ai_payload,
    select_evaluator_examples,
)
from projects.management.commands.augment_segmentation_evaluator_examples import disagreement_examples


class EvaluateSegmentationOutputsWithAITests(SimpleTestCase):
    def test_select_evaluator_examples_named_counts(self):
        examples = [{"example_id": f"EXAMPLE-{idx:04d}"} for idx in range(1, 31)]
        self.assertEqual(len(select_evaluator_examples(examples, "small")), 8)
        self.assertEqual(len(select_evaluator_examples(examples, "medium")), 24)
        self.assertEqual(len(select_evaluator_examples(examples, "all")), 30)
        self.assertEqual(len(select_evaluator_examples(examples, "3")), 3)

    def test_prompt_includes_examples_and_candidate_segments(self):
        prompt = build_evaluator_prompt(
            {"input_surface": "Il m'appelle.", "segments_display": "Il| |m'|appelle|."},
            [{"example_id": "EXAMPLE-0001", "input": "Je t'aime.", "boundary_marked": "Je¦ ¦t'¦aime¦."}],
        )
        self.assertIn("Je t'aime.", prompt)
        self.assertIn("Il| |m'|appelle|.", prompt)
        self.assertIn('"judgement"', prompt)
        self.assertIn("Accept an unsplit ordinary word", prompt)
        self.assertIn("a|voir", prompt)

    def test_prompt_includes_reject_evaluator_examples(self):
        prompt = build_evaluator_prompt(
            {"input_surface": "elle a l'histoire", "segments_display": "elle| |a| |l'histoire"},
            [
                {
                    "example_id": "DISAGREEMENT-0001",
                    "input": "elle a l'histoire",
                    "candidate_segments": "elle| |a| |l'histoire",
                    "expected_decision": "reject",
                    "rationale": "Gold rejects this false accept.",
                }
            ],
        )
        self.assertIn('"expected_judgement": "reject"', prompt)
        self.assertIn("expected judgement", prompt)

    def test_normalise_ai_payload_rejects_unknown_decision(self):
        payload = normalise_ai_payload({"judgement": "maybe", "rationale": "unclear"})
        self.assertEqual(payload["judgement"], "reject")
        self.assertEqual(payload["severity"], "major")

    def test_disagreement_examples_extracts_false_accepts_as_reject_exemplars(self):
        examples = disagreement_examples(
            [
                {
                    "record_id": "r1",
                    "input_surface": "elle a l'histoire",
                    "segments_display": "elle| |a| |l'histoire",
                    "gold_judgement": "reject",
                    "evaluator_judgement": "accept",
                    "evaluator_notes": "looks okay",
                },
                {
                    "record_id": "r2",
                    "input_surface": "avoir",
                    "segments_display": "avoir",
                    "gold_judgement": "accept",
                    "evaluator_judgement": "reject",
                },
            ],
            include_gold="reject",
            max_examples=0,
            existing_keys=set(),
        )
        self.assertEqual(len(examples), 1)
        self.assertEqual(examples[0]["expected_decision"], "reject")
        self.assertEqual(examples[0]["candidate_segments"], "elle| |a| |l'histoire")

    def test_augment_command_writes_combined_examples_and_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = root / "base.jsonl"
            disagreements = root / "disagreements.jsonl"
            output = root / "augmented.jsonl"
            manifest = root / "manifest.json"
            base.write_text(
                json.dumps({"example_id": "EXAMPLE-0001", "input": "avoir", "boundary_marked": "avoir", "expected_decision": "accept"})
                + "\n",
                encoding="utf-8",
            )
            disagreements.write_text(
                json.dumps(
                    {
                        "record_id": "r1",
                        "input_surface": "elle a l'histoire",
                        "segments_display": "elle| |a| |l'histoire",
                        "gold_judgement": "reject",
                        "evaluator_judgement": "accept",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            call_command(
                "augment_segmentation_evaluator_examples",
                base_examples_jsonl=str(base),
                disagreements_jsonl=str(disagreements),
                output_jsonl=str(output),
                manifest_json=str(manifest),
                overwrite=True,
            )
            records = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(records), 2)
            self.assertEqual(records[-1]["expected_decision"], "reject")
            manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(manifest_payload["added_count"], 1)

    def test_evaluator_cache_key_depends_on_examples_and_prompt_version(self):
        record = {"input_surface": "x", "segments_display": "x"}
        left = evaluator_cache_key(record, examples=[{"example_id": "a"}], model="m", variant_label="small")
        right = evaluator_cache_key(record, examples=[{"example_id": "b"}], model="m", variant_label="small")
        self.assertNotEqual(left, right)
        self.assertEqual(len(left), hashlib.sha256().digest_size * 2)


class ScoreSegmentationEvaluatorJudgementsTests(SimpleTestCase):
    def test_score_command_writes_majority_vote_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            gold = root / "gold.jsonl"
            small = root / "small.jsonl"
            medium = root / "medium.jsonl"
            large = root / "large.jsonl"
            for path, judgements in [
                (gold, ["accept", "reject"]),
                (small, ["accept", "accept"]),
                (medium, ["accept", "reject"]),
                (large, ["accept", "reject"]),
            ]:
                path.write_text(
                    "".join(
                        json.dumps(
                            {
                                "record_id": f"r{idx}",
                                "judgement": judgement,
                                "input_surface": f"input {idx}",
                                "segments_display": f"seg {idx}",
                            }
                        )
                        + "\n"
                        for idx, judgement in enumerate(judgements, start=1)
                    ),
                    encoding="utf-8",
                )
            out_dir = root / "score"
            call_command(
                "score_segmentation_evaluator_judgements",
                gold_judgements=str(gold),
                evaluator=[f"small:{small}", f"medium:{medium}", f"large:{large}"],
                output_dir=str(out_dir),
                split="development",
            )
            payload = json.loads((out_dir / "evaluator_accuracy.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["evaluators"][0]["false_accept_count"], 1)
            self.assertEqual(payload["majority_vote"]["accuracy"], 1.0)
