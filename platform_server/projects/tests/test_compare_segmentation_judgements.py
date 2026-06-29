from __future__ import annotations

import json
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.test import SimpleTestCase

from projects.management.commands.compare_segmentation_judgements import compare_candidate, load_latest_judgements


class CompareSegmentationJudgementsTests(SimpleTestCase):
    def test_compare_candidate_counts_wins_losses_and_latest_corrections(self):
        default = {
            "r1": judgement("r1", "accept", "A| |B"),
            "r2": judgement("r2", "reject", "C|D"),
            "r3": judgement("r3", "accept", "E"),
        }
        candidate = {
            "r1": judgement("r1", "accept", "A| |B"),
            "r2": judgement("r2", "accept", "C| |D"),
            "r3": judgement("r3", "reject", "E|F"),
        }

        summary, flagged = compare_candidate(
            label="fewshots-small",
            default_path=Path("default.jsonl"),
            candidate_path=Path("candidate.jsonl"),
            default_records=default,
            candidate_records=candidate,
        )

        self.assertEqual(summary["records_compared"], 3)
        self.assertEqual(summary["candidate_win_count"], 1)
        self.assertEqual(summary["candidate_loss_count"], 1)
        self.assertEqual(summary["net_win_count"], 0)
        self.assertEqual(summary["candidate_accept_delta"], 0)
        self.assertEqual([item["category"] for item in flagged], ["candidate_win", "candidate_loss"])

    def test_command_writes_summary_markdown_and_flagged_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            default_path = tmp_path / "default.jsonl"
            candidate_path = tmp_path / "candidate.jsonl"
            output_dir = tmp_path / "comparison"
            write_jsonl(
                default_path,
                [
                    judgement("r1", "accept", "A"),
                    judgement("r2", "reject", "B"),
                    {**judgement("r2", "accept", "B"), "is_correction": True},
                ],
            )
            write_jsonl(candidate_path, [judgement("r1", "reject", "A|B"), judgement("r2", "accept", "B")])

            latest = load_latest_judgements(default_path)
            self.assertEqual(latest["r2"]["judgement"], "accept")

            call_command(
                "compare_segmentation_judgements",
                default_judgements=str(default_path),
                candidate=[f"fewshots-small:{candidate_path}"],
                output_dir=str(output_dir),
                split="development",
            )

            summary = json.loads((output_dir / "comparison_summary.json").read_text(encoding="utf-8"))
            flagged = [json.loads(line) for line in (output_dir / "flagged_examples.jsonl").read_text(encoding="utf-8").splitlines()]
            markdown = (output_dir / "comparison_summary.md").read_text(encoding="utf-8")
            self.assertEqual(summary["candidates"][0]["candidate_loss_count"], 1)
            self.assertIn("fewshots-small", markdown)
            self.assertEqual(flagged[0]["record_id"], "r1")


def judgement(record_id: str, judgement_value: str, segments: str) -> dict[str, object]:
    return {
        "record_id": record_id,
        "project_id": 1,
        "project_title": "Fixture",
        "split": "development",
        "input_surface": f"input {record_id}",
        "segments_display": segments,
        "judgement": judgement_value,
        "notes": "",
    }


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
