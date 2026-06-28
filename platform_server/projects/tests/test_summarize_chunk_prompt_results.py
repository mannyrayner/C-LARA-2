from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.test import SimpleTestCase


class SummarizeChunkPromptResultsTests(SimpleTestCase):
    def test_summarizes_development_validation_and_test_results(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "generated"
            self._write_brief(
                root / "prompt_improvement" / "en-segmentation-development" / "cycle_1" / "prompt_improvement_brief.json",
                records=100,
                accuracy=0.98,
                errors=2,
            )
            self._write_brief(
                root / "prompt_validation" / "en-segmentation-development-cycle_1-on-validation" / "prompt_improvement_brief.json",
                records=40,
                accuracy=0.975,
                errors=1,
            )
            self._write_brief(
                root / "prompt_validation" / "fr-segmentation-development-cycle_3-on-test" / "prompt_improvement_brief.json",
                records=80,
                accuracy=0.9875,
                errors=1,
            )
            output_json = root / "prompt_results_summary.json"
            output_markdown = root / "prompt_results_summary.md"

            call_command(
                "summarize_chunk_prompt_results",
                generated_dir=str(root),
                output_json=str(output_json),
                output_markdown=str(output_markdown),
                languages="fr,en,de",
                prompt_kind="segmentation",
                overwrite=True,
            )

            payload = json.loads(output_json.read_text(encoding="utf-8"))
            self.assertEqual(payload["result_count"], 3)
            rows = {(row["language"], row["split"], row["source_cycle_number"]): row for row in payload["results"]}
            self.assertEqual(rows[("en", "development", 1)]["result_type"], "development_cycle")
            self.assertEqual(rows[("en", "validation", 1)]["result_type"], "heldout_evaluation")
            self.assertEqual(rows[("fr", "test", 3)]["error_rate"], 0.0125)
            markdown = output_markdown.read_text(encoding="utf-8")
            self.assertIn("| en | validation | 1 | heldout_evaluation | 40 | 0.9750 | 0.0250 | 1 |", markdown)

    def _write_brief(self, path: Path, *, records: int, accuracy: float, errors: int) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "summary": {
                        "records_compared": records,
                        "accuracy": accuracy,
                        "error_count": errors,
                        "success_count": records - errors,
                        "status_counts": {"correct": records - errors, "under_split": errors},
                    }
                }
            ),
            encoding="utf-8",
        )
