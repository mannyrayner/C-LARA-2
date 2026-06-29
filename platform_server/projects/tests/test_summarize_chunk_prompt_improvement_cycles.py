from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.test import SimpleTestCase


class SummarizeChunkPromptImprovementCyclesTests(SimpleTestCase):
    def test_command_summarizes_cycle_artifacts(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            cycles_dir = root / "fr-segmentation-development"
            cycle_1 = cycles_dir / "cycle_1"
            cycle_2 = cycles_dir / "cycle_2"
            cycle_1.mkdir(parents=True)
            cycle_2.mkdir(parents=True)
            (cycle_1 / "prompt.md").write_text("initial prompt", encoding="utf-8")
            (cycle_1 / "predictions.jsonl").write_text("{}\n", encoding="utf-8")
            (cycle_1 / "prompt_revision.md").write_text("revision", encoding="utf-8")
            (cycle_1 / "prompt_improvement_brief.json").write_text(
                json.dumps(
                    {
                        "summary": {
                            "records_compared": 10,
                            "accuracy": 0.8,
                            "error_count": 2,
                            "success_count": 8,
                            "status_counts": {"correct": 8, "over_split": 2},
                        }
                    }
                ),
                encoding="utf-8",
            )
            (cycle_2 / "prompt.md").write_text("second prompt", encoding="utf-8")
            (cycle_2 / "prompt_improvement_brief.json").write_text(
                json.dumps(
                    {
                        "summary": {
                            "records_compared": 10,
                            "accuracy": 0.9,
                            "error_count": 1,
                            "success_count": 9,
                            "status_counts": {"correct": 9, "under_split": 1},
                        }
                    }
                ),
                encoding="utf-8",
            )
            output_json = root / "cycles_summary.json"
            output_markdown = root / "cycles_summary.md"

            call_command(
                "summarize_chunk_prompt_improvement_cycles",
                cycles_dir=str(cycles_dir),
                output_json=str(output_json),
                output_markdown=str(output_markdown),
                overwrite=True,
            )

            payload = json.loads(output_json.read_text(encoding="utf-8"))
            self.assertEqual(payload["cycle_count"], 2)
            self.assertEqual([cycle["cycle_number"] for cycle in payload["cycles"]], [1, 2])
            self.assertTrue(payload["cycles"][0]["has_prompt_revision"])
            self.assertFalse(payload["cycles"][1]["has_prompt_revision"])
            self.assertEqual(payload["cycles"][1]["accuracy"], 0.9)
            markdown = output_markdown.read_text(encoding="utf-8")
            self.assertIn("| 1 | 10 | 0.8 | 2 |", markdown)
            self.assertIn("| 2 | 10 | 0.9 | 1 |", markdown)
