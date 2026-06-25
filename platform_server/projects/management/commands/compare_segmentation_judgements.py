from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from .review_fewshots import _resolve_cli_path

ACCEPT = "accept"
REJECT = "reject"
SKIP = "skip"


class Command(BaseCommand):
    help = "Compare default and candidate segmentation judgement JSONL files."

    def add_arguments(self, parser):
        parser.add_argument("--default-judgements", required=True)
        parser.add_argument(
            "--candidate",
            action="append",
            default=[],
            help="Candidate judgement file as label:path. May be repeated.",
        )
        parser.add_argument("--output-dir", required=True)
        parser.add_argument("--split", default="development")
        parser.add_argument("--json", default="comparison_summary.json")
        parser.add_argument("--markdown", default="comparison_summary.md")
        parser.add_argument("--flagged-jsonl", default="flagged_examples.jsonl")

    def handle(self, *args, **options):
        default_path = _resolve_cli_path(options["default_judgements"], "")
        output_dir = _resolve_cli_path(options["output_dir"], "")
        output_dir.mkdir(parents=True, exist_ok=True)
        candidates = parse_candidates(options.get("candidate") or [])
        if not candidates:
            raise CommandError("At least one --candidate label:path argument is required")

        default_records = load_latest_judgements(default_path)
        summaries: list[dict[str, Any]] = []
        flagged: list[dict[str, Any]] = []
        for label, raw_path in candidates:
            candidate_path = _resolve_cli_path(raw_path, "")
            candidate_records = load_latest_judgements(candidate_path)
            summary, candidate_flagged = compare_candidate(
                label=label,
                default_path=default_path,
                candidate_path=candidate_path,
                default_records=default_records,
                candidate_records=candidate_records,
            )
            summaries.append(summary)
            flagged.extend(candidate_flagged)

        payload = {
            "schema_version": 1,
            "split": options["split"],
            "default_judgements": str(default_path),
            "candidate_count": len(summaries),
            "candidates": summaries,
        }
        json_path = output_dir / options["json"]
        markdown_path = output_dir / options["markdown"]
        flagged_path = output_dir / options["flagged_jsonl"]
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        markdown_path.write_text(render_markdown(payload), encoding="utf-8")
        with flagged_path.open("w", encoding="utf-8") as out:
            for item in flagged:
                out.write(json.dumps(item, ensure_ascii=False) + "\n")

        self.stdout.write("Segmentation judgement comparison complete")
        self.stdout.write(f"Default: {default_path}")
        self.stdout.write(f"Candidates: {len(summaries)}")
        self.stdout.write(f"Summary JSON: {json_path}")
        self.stdout.write(f"Summary Markdown: {markdown_path}")
        self.stdout.write(f"Flagged examples: {flagged_path}")


def parse_candidates(values: list[str]) -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []
    for value in values:
        label, sep, path = value.partition(":")
        if not sep or not label or not path:
            raise CommandError(f"Candidate must be label:path, got {value!r}")
        candidates.append((label, path))
    return candidates


def load_latest_judgements(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        raise CommandError(f"Judgement file not found: {path}")
    latest: dict[str, dict[str, Any]] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        record_id = str(payload.get("record_id") or "")
        if not record_id:
            raise CommandError(f"Judgement without record_id in {path}:{line_number}")
        latest[record_id] = payload
    return latest


def compare_candidate(
    *,
    label: str,
    default_path: Path,
    candidate_path: Path,
    default_records: dict[str, dict[str, Any]],
    candidate_records: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    common_ids = sorted(set(default_records).intersection(candidate_records))
    default_only = sorted(set(default_records).difference(candidate_records))
    candidate_only = sorted(set(candidate_records).difference(default_records))
    categories: Counter[str] = Counter()
    default_judgements: Counter[str] = Counter()
    candidate_judgements: Counter[str] = Counter()
    flagged: list[dict[str, Any]] = []
    for record_id in common_ids:
        default = default_records[record_id]
        candidate = candidate_records[record_id]
        default_j = normalise_judgement(default.get("judgement"))
        candidate_j = normalise_judgement(candidate.get("judgement"))
        default_judgements[default_j] += 1
        candidate_judgements[candidate_j] += 1
        category = comparison_category(default_j, candidate_j)
        categories[category] += 1
        if category in {"candidate_win", "candidate_loss", "disagreement"}:
            flagged.append(flagged_payload(label, category, default, candidate))

    records_compared = len(common_ids)
    summary = {
        "label": label,
        "default_path": str(default_path),
        "candidate_path": str(candidate_path),
        "records_compared": records_compared,
        "missing_from_candidate": len(default_only),
        "missing_from_default": len(candidate_only),
        "default_judgements": dict(sorted(default_judgements.items())),
        "candidate_judgements": dict(sorted(candidate_judgements.items())),
        "categories": dict(sorted(categories.items())),
        "candidate_accept_delta": candidate_judgements[ACCEPT] - default_judgements[ACCEPT],
        "candidate_win_count": categories["candidate_win"],
        "candidate_loss_count": categories["candidate_loss"],
        "net_win_count": categories["candidate_win"] - categories["candidate_loss"],
        "candidate_accept_rate": safe_rate(candidate_judgements[ACCEPT], records_compared),
        "default_accept_rate": safe_rate(default_judgements[ACCEPT], records_compared),
    }
    return summary, flagged


def normalise_judgement(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if raw in {ACCEPT, REJECT, SKIP}:
        return raw
    return "other"


def comparison_category(default_j: str, candidate_j: str) -> str:
    if default_j == candidate_j:
        return f"tie_{default_j}"
    if default_j != ACCEPT and candidate_j == ACCEPT:
        return "candidate_win"
    if default_j == ACCEPT and candidate_j != ACCEPT:
        return "candidate_loss"
    return "disagreement"


def flagged_payload(label: str, category: str, default: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_label": label,
        "category": category,
        "record_id": default.get("record_id") or candidate.get("record_id"),
        "project_id": default.get("project_id") or candidate.get("project_id"),
        "project_title": default.get("project_title") or candidate.get("project_title"),
        "split": default.get("split") or candidate.get("split"),
        "input_surface": default.get("input_surface") or candidate.get("input_surface"),
        "default_judgement": default.get("judgement"),
        "candidate_judgement": candidate.get("judgement"),
        "default_segments": default.get("segments_display"),
        "candidate_segments": candidate.get("segments_display"),
        "default_notes": default.get("notes", ""),
        "candidate_notes": candidate.get("notes", ""),
    }


def safe_rate(count: int, total: int) -> float:
    if not total:
        return 0.0
    return round(count / total, 4)


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Segmentation judgement comparison",
        "",
        f"Split: `{payload['split']}`",
        f"Default judgements: `{payload['default_judgements']}`",
        "",
        "| Candidate | Records | Default accept | Candidate accept | Accept Δ | Wins | Losses | Net wins | Missing cand | Missing default |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for candidate in payload["candidates"]:
        lines.append(
            "| {label} | {records_compared} | {default_accept_rate:.1%} | {candidate_accept_rate:.1%} | "
            "{candidate_accept_delta} | {candidate_win_count} | {candidate_loss_count} | {net_win_count} | "
            "{missing_from_candidate} | {missing_from_default} |".format(**candidate)
        )
    lines.extend(["", "## Category counts", ""])
    for candidate in payload["candidates"]:
        lines.append(f"### {candidate['label']}")
        for key, value in candidate["categories"].items():
            lines.append(f"- `{key}`: {value}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
