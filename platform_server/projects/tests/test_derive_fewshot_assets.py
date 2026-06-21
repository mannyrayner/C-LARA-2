from __future__ import annotations

import json
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.test import SimpleTestCase

from projects.management.commands.derive_fewshot_assets import accepted_review_items


class DeriveFewshotAssetsTests(SimpleTestCase):
    def test_accepted_review_items_requires_accept_and_human_correct(self):
        items = [
            {"example_id": "EXAMPLE-0001", "decision": "accept", "severity": "none"},
            {"example_id": "EXAMPLE-0002", "decision": "reject", "severity": "fatal"},
            {"example_id": "EXAMPLE-0003", "decision": "accept", "severity": "minor"},
        ]
        audit = {
            "EXAMPLE-0001": {"example_id": "EXAMPLE-0001", "human_judgement": "correct"},
            "EXAMPLE-0003": {"example_id": "EXAMPLE-0003", "human_judgement": "incorrect"},
        }

        accepted = accepted_review_items(items, audit_by_example=audit, require_audit=True)

        self.assertEqual([item["example_id"] for item in accepted], ["EXAMPLE-0001"])

    def test_command_derives_processing_and_evaluator_assets(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            curation_root = repo_root / "generated" / "few_shot_curation"
            root = curation_root / "segmentation_phase_2" / "fr" / "boundary_first" / "clitic_compound_v2"
            candidates_dir = root / "candidates"
            reviews_dir = root / "reviews"
            candidates_dir.mkdir(parents=True)
            reviews_dir.mkdir(parents=True)
            template_dir = repo_root / "prompts" / "segmentation_phase_2" / "strategies" / "boundary_first"
            template_dir.mkdir(parents=True)
            (template_dir / "template.txt").write_text("Boundary template", encoding="utf-8")
            candidate_path = candidates_dir / "20260615-072115Z-EXAMPLE-0001.json"
            candidate_path.write_text(
                json.dumps(
                    {
                        "example_id": "EXAMPLE-0001",
                        "candidate": {
                            "input": "Je l'ai fait.",
                            "phenomenon": "French clitic",
                            "rationale": "Split learner-useful clitic.",
                            "output": {
                                "surface": "Je l'ai fait.",
                                "tokens": [
                                    {"surface": "Je"},
                                    {"surface": " "},
                                    {"surface": "l'"},
                                    {"surface": "ai"},
                                    {"surface": " "},
                                    {"surface": "fait"},
                                    {"surface": "."},
                                ],
                                "annotations": {},
                            },
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            items = {
                "items": [
                    {
                        "example_id": "EXAMPLE-0001",
                        "boundary_marked": "Je¦ ¦l'¦ai¦ ¦fait¦.",
                        "decision": "accept",
                        "severity": "none",
                        "candidate_path": str(candidate_path),
                        "review_path": str(reviews_dir / "20260615-072115Z-EXAMPLE-0001.review.json"),
                    }
                ]
            }
            (reviews_dir / "20260615-072115Z.items.json").write_text(json.dumps(items), encoding="utf-8")
            (reviews_dir / "20260615-072115Z.human_audit.jsonl").write_text(
                json.dumps(
                    {
                        "example_id": "EXAMPLE-0001",
                        "review_decision": "accept",
                        "review_severity": "none",
                        "human_judgement": "correct",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            processing_dir = repo_root / "prompts" / "segmentation_phase_2" / "variants" / "clitic_compound_v2" / "fewshots"
            evaluator_jsonl = repo_root / "generated" / "derived_assets" / "evaluator_examples.jsonl"
            manifest_json = repo_root / "generated" / "derived_assets" / "manifest.json"

            call_command(
                "derive_fewshot_assets",
                operation="segmentation_phase_2",
                language="fr",
                mechanism="boundary_first",
                target_set="clitic_compound_v2",
                request_id="20260615-072115Z",
                repo_root=str(repo_root),
                curation_root=str(curation_root),
                processing_output_dir=str(processing_dir),
                evaluator_output_jsonl=str(evaluator_jsonl),
                manifest_json=str(manifest_json),
                overwrite=True,
            )

            processing_payload = json.loads((processing_dir / "example1.json").read_text(encoding="utf-8"))
            evaluator_payload = json.loads(evaluator_jsonl.read_text(encoding="utf-8").splitlines()[0])
            manifest = json.loads(manifest_json.read_text(encoding="utf-8"))
            self.assertEqual(processing_payload["input"], "Je l'ai fait.")
            self.assertEqual(evaluator_payload["boundary_marked"], "Je¦ ¦l'¦ai¦ ¦fait¦.")
            self.assertEqual(manifest["accepted_count"], 1)
            self.assertTrue((processing_dir.parent / "boundary_first_template.txt").exists())
