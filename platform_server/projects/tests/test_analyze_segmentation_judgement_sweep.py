from __future__ import annotations

import json
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.test import SimpleTestCase

from projects.management.commands.analyze_segmentation_judgement_sweep import (
    majority_vote_summary,
    pairwise_failure_overlap,
)


class AnalyzeSegmentationJudgementSweepTests(SimpleTestCase):
    def test_pairwise_failure_overlap_and_majority_vote(self):
        failure_sets = {"small": {"r1", "r2"}, "medium": {"r2"}, "all": {"r3"}}
        overlap = pairwise_failure_overlap(failure_sets)
        self.assertEqual(overlap[0]["left"], "all")
        self.assertEqual(overlap[0]["right"], "medium")
        self.assertEqual(overlap[0]["jaccard"], 0.0)

        default = {"r1": judgement("r1", "reject"), "r2": judgement("r2", "accept"), "r3": judgement("r3", "accept")}
        candidates = [
            ("small", Path("small.jsonl"), {"r1": judgement("r1", "accept"), "r2": judgement("r2", "reject"), "r3": judgement("r3", "accept")}),
            ("medium", Path("medium.jsonl"), {"r1": judgement("r1", "accept"), "r2": judgement("r2", "accept"), "r3": judgement("r3", "reject")}),
            ("all", Path("all.jsonl"), {"r1": judgement("r1", "reject"), "r2": judgement("r2", "accept"), "r3": judgement("r3", "accept")}),
        ]
        summary, flagged = majority_vote_summary(Path("default.jsonl"), default, candidates, ["r1", "r2", "r3"])
        self.assertEqual(summary["candidate_win_count"], 1)
        self.assertEqual(summary["candidate_loss_count"], 0)
        self.assertEqual(summary["candidate_judgements"]["accept"], 3)
        self.assertEqual(flagged[0]["record_id"], "r1")

    def test_command_writes_sweep_analysis(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            default_path = tmp_path / "default.jsonl"
            small_path = tmp_path / "small.jsonl"
            medium_path = tmp_path / "medium.jsonl"
            all_path = tmp_path / "all.jsonl"
            output_dir = tmp_path / "analysis"
            write_jsonl(default_path, [judgement("r1", "reject"), judgement("r2", "accept")])
            write_jsonl(small_path, [judgement("r1", "accept"), judgement("r2", "reject")])
            write_jsonl(medium_path, [judgement("r1", "accept"), judgement("r2", "accept")])
            write_jsonl(all_path, [judgement("r1", "reject"), judgement("r2", "accept")])

            call_command(
                "analyze_segmentation_judgement_sweep",
                default_judgements=str(default_path),
                candidate=[f"small:{small_path}", f"medium:{medium_path}", f"all:{all_path}"],
                output_dir=str(output_dir),
                split="development",
            )

            payload = json.loads((output_dir / "sweep_analysis.json").read_text(encoding="utf-8"))
            markdown = (output_dir / "sweep_analysis.md").read_text(encoding="utf-8")
            flagged = [json.loads(line) for line in (output_dir / "sweep_patterns.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual(payload["pattern_counts"], {"AAR": 1, "RAA": 1})
            self.assertIn("Majority-vote proxy", markdown)
            self.assertEqual(flagged[0]["record_id"], "r1")


def judgement(record_id: str, value: str) -> dict[str, object]:
    return {
        "record_id": record_id,
        "project_id": 1,
        "project_title": "Fixture",
        "split": "development",
        "input_surface": f"input {record_id}",
        "segments_display": f"segments {record_id}",
        "judgement": value,
        "notes": "",
    }


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
