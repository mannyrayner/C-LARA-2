from __future__ import annotations

import itertools
import json
from collections import Counter
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from .compare_segmentation_judgements import (
    ACCEPT,
    compare_candidate,
    load_latest_judgements,
    normalise_judgement,
    parse_candidates,
)
from .review_fewshots import _resolve_cli_path


class Command(BaseCommand):
    help = "Analyze failure correlation and majority-vote proxy across segmentation judgement tranches."

    def add_arguments(self, parser):
        parser.add_argument("--default-judgements", required=True)
        parser.add_argument("--candidate", action="append", default=[], help="Candidate judgement file as label:path")
        parser.add_argument("--output-dir", required=True)
        parser.add_argument("--split", default="development")
        parser.add_argument("--json", default="sweep_analysis.json")
        parser.add_argument("--markdown", default="sweep_analysis.md")
        parser.add_argument("--patterns-jsonl", default="sweep_patterns.jsonl")

    def handle(self, *args, **options):
        default_path = _resolve_cli_path(options["default_judgements"], "")
        output_dir = _resolve_cli_path(options["output_dir"], "")
        output_dir.mkdir(parents=True, exist_ok=True)
        candidates = parse_candidates(options.get("candidate") or [])
        if len(candidates) < 2:
            raise CommandError("At least two --candidate label:path arguments are required for sweep analysis")

        default_records = load_latest_judgements(default_path)
        candidate_records = [(label, _resolve_cli_path(path, ""), load_latest_judgements(_resolve_cli_path(path, ""))) for label, path in candidates]
        common_ids = common_record_ids(default_records, [records for _, _, records in candidate_records])
        candidate_summaries = [
            compare_candidate(
                label=label,
                default_path=default_path,
                candidate_path=path,
                default_records=default_records,
                candidate_records=records,
            )[0]
            for label, path, records in candidate_records
        ]
        failure_sets = {
            label: {record_id for record_id in common_ids if normalise_judgement(records[record_id].get("judgement")) != ACCEPT}
            for label, _, records in candidate_records
        }
        pairwise = pairwise_failure_overlap(failure_sets)
        patterns = judgement_patterns(default_records, candidate_records, common_ids)
        majority_summary, majority_flagged = majority_vote_summary(default_path, default_records, candidate_records, common_ids)
        payload = {
            "schema_version": 1,
            "split": options["split"],
            "default_judgements": str(default_path),
            "candidate_labels": [label for label, _, _ in candidate_records],
            "records_compared": len(common_ids),
            "candidate_summaries": candidate_summaries,
            "failure_counts": {label: len(records) for label, records in failure_sets.items()},
            "pairwise_failure_overlap": pairwise,
            "pattern_counts": patterns["counts"],
            "records_by_pattern": patterns["records_by_pattern"],
            "majority_vote": majority_summary,
        }
        json_path = output_dir / options["json"]
        markdown_path = output_dir / options["markdown"]
        patterns_path = output_dir / options["patterns_jsonl"]
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        markdown_path.write_text(render_markdown(payload), encoding="utf-8")
        with patterns_path.open("w", encoding="utf-8") as out:
            for item in majority_flagged:
                out.write(json.dumps(item, ensure_ascii=False) + "\n")

        self.stdout.write("Segmentation judgement sweep analysis complete")
        self.stdout.write(f"Candidates: {', '.join(payload['candidate_labels'])}")
        self.stdout.write(f"Records compared: {len(common_ids)}")
        self.stdout.write(f"Analysis JSON: {json_path}")
        self.stdout.write(f"Analysis Markdown: {markdown_path}")
        self.stdout.write(f"Flagged majority examples: {patterns_path}")


def common_record_ids(default_records: dict[str, Any], candidate_records: list[dict[str, Any]]) -> list[str]:
    common = set(default_records)
    for records in candidate_records:
        common &= set(records)
    return sorted(common)


def pairwise_failure_overlap(failure_sets: dict[str, set[str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for left, right in itertools.combinations(sorted(failure_sets), 2):
        left_set = failure_sets[left]
        right_set = failure_sets[right]
        intersection = left_set & right_set
        union = left_set | right_set
        rows.append(
            {
                "left": left,
                "right": right,
                "left_failures": len(left_set),
                "right_failures": len(right_set),
                "shared_failures": len(intersection),
                "union_failures": len(union),
                "jaccard": round(len(intersection) / len(union), 4) if union else 1.0,
                "left_failure_shared_rate": round(len(intersection) / len(left_set), 4) if left_set else 1.0,
                "right_failure_shared_rate": round(len(intersection) / len(right_set), 4) if right_set else 1.0,
            }
        )
    return rows


def judgement_patterns(
    default_records: dict[str, dict[str, Any]],
    candidate_records: list[tuple[str, Path, dict[str, dict[str, Any]]]],
    common_ids: list[str],
) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    records_by_pattern: dict[str, list[str]] = {}
    for record_id in common_ids:
        pattern = "".join(
            "A" if normalise_judgement(records[record_id].get("judgement")) == ACCEPT else "R"
            for _, _, records in candidate_records
        )
        counts[pattern] += 1
        records_by_pattern.setdefault(pattern, []).append(record_id)
    return {"counts": dict(sorted(counts.items())), "records_by_pattern": records_by_pattern}


def majority_vote_summary(
    default_path: Path,
    default_records: dict[str, dict[str, Any]],
    candidate_records: list[tuple[str, Path, dict[str, dict[str, Any]]]],
    common_ids: list[str],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    threshold = len(candidate_records) // 2 + 1
    majority_records: dict[str, dict[str, Any]] = {}
    for record_id in common_ids:
        accepts = sum(
            1 for _, _, records in candidate_records if normalise_judgement(records[record_id].get("judgement")) == ACCEPT
        )
        exemplar = candidate_records[0][2][record_id]
        majority_records[record_id] = {
            **exemplar,
            "judgement": ACCEPT if accepts >= threshold else "reject",
            "vote_accept_count": accepts,
            "vote_total": len(candidate_records),
        }
    summary, flagged = compare_candidate(
        label="majority-vote-proxy",
        default_path=default_path,
        candidate_path=Path("<majority-vote-proxy>"),
        default_records=default_records,
        candidate_records=majority_records,
    )
    return summary, flagged


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Segmentation judgement sweep analysis",
        "",
        f"Split: `{payload['split']}`",
        f"Records compared: {payload['records_compared']}",
        f"Candidates: {', '.join(payload['candidate_labels'])}",
        "",
        "## Failure counts",
        "",
        "| Candidate | Failures |",
        "| --- | ---: |",
    ]
    for label, count in payload["failure_counts"].items():
        lines.append(f"| {label} | {count} |")
    lines.extend(["", "## Pairwise failure overlap", "", "| Left | Right | Shared | Union | Jaccard | Left shared | Right shared |", "| --- | --- | ---: | ---: | ---: | ---: | ---: |"])
    for row in payload["pairwise_failure_overlap"]:
        lines.append(
            f"| {row['left']} | {row['right']} | {row['shared_failures']} | {row['union_failures']} | "
            f"{row['jaccard']:.4f} | {row['left_failure_shared_rate']:.4f} | {row['right_failure_shared_rate']:.4f} |"
        )
    lines.extend(["", "## Candidate accept/reject patterns", "", "`A` = accept; `R` = non-accept in candidate label order.", ""])
    for pattern, count in payload["pattern_counts"].items():
        lines.append(f"- `{pattern}`: {count}")
    majority = payload["majority_vote"]
    lines.extend(
        [
            "",
            "## Majority-vote proxy",
            "",
            f"- Candidate accept rate: {majority['candidate_accept_rate']:.1%}",
            f"- Default accept rate: {majority['default_accept_rate']:.1%}",
            f"- Candidate wins: {majority['candidate_win_count']}",
            f"- Candidate losses: {majority['candidate_loss_count']}",
            f"- Net wins: {majority['net_win_count']}",
            "",
            "This is a judgement-level proxy, not yet an implemented token-level ensemble decoder.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"
