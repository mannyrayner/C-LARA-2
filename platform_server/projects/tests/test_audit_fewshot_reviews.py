from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase


class AuditFewshotReviewsTests(SimpleTestCase):
    def test_command_writes_empty_audit_when_user_quits(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            curation_root = repo_root / "generated" / "few_shot_curation"
            reviews_dir = (
                curation_root
                / "segmentation_phase_2"
                / "fr"
                / "boundary_first"
                / "clitic_compound_v2_evaluator"
                / "reviews"
            )
            reviews_dir.mkdir(parents=True)
            items_path = reviews_dir / "REQUEST.items.json"
            items_path.write_text(
                json.dumps(
                    {
                        "items": [
                            {
                                "example_id": "EXAMPLE-0001",
                                "decision": "accept",
                                "severity": "none",
                                "boundary_marked": "Il¦ ¦me¦ ¦les¦ ¦donne¦.",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            with patch("builtins.input", return_value="q"):
                call_command(
                    "audit_fewshot_reviews",
                    operation="segmentation_phase_2",
                    language="fr",
                    mechanism="boundary_first",
                    target_set="clitic_compound_v2_evaluator",
                    request_id="REQUEST",
                    repo_root=str(repo_root),
                    curation_root=str(curation_root),
                )

            audit_path = reviews_dir / "REQUEST.human_audit.jsonl"
            self.assertTrue(audit_path.exists())
            self.assertEqual(audit_path.read_text(encoding="utf-8"), "")

    def test_command_resumes_existing_audit_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            curation_root = repo_root / "generated" / "few_shot_curation"
            reviews_dir = (
                curation_root
                / "segmentation_phase_2"
                / "fr"
                / "boundary_first"
                / "clitic_compound_v2_evaluator"
                / "reviews"
            )
            reviews_dir.mkdir(parents=True)
            (reviews_dir / "REQUEST.items.json").write_text(
                json.dumps(
                    {
                        "items": [
                            {"example_id": "EXAMPLE-0001", "decision": "accept", "severity": "none"},
                            {"example_id": "EXAMPLE-0002", "decision": "accept", "severity": "none"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            audit_path = reviews_dir / "REQUEST.human_audit.jsonl"
            audit_path.write_text(
                json.dumps({"example_id": "EXAMPLE-0001", "human_judgement": "correct"}) + "\n",
                encoding="utf-8",
            )

            with patch("builtins.input", return_value="c"):
                call_command(
                    "audit_fewshot_reviews",
                    operation="segmentation_phase_2",
                    language="fr",
                    mechanism="boundary_first",
                    target_set="clitic_compound_v2_evaluator",
                    request_id="REQUEST",
                    repo_root=str(repo_root),
                    curation_root=str(curation_root),
                )

            records = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual([record["example_id"] for record in records], ["EXAMPLE-0001", "EXAMPLE-0002"])
            self.assertEqual(records[1]["human_judgement"], "correct")
