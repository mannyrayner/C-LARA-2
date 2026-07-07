from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from .review_fewshots import _resolve_cli_path


class Command(BaseCommand):
    help = "Create a conservative prompt-improvement report from MWE scoring errors."

    def add_arguments(self, parser):
        parser.add_argument("--score-dir", required=True)
        parser.add_argument("--output-dir", required=True)
        parser.add_argument("--max-examples", type=int, default=20)
        parser.add_argument("--overwrite", action="store_true")

    def handle(self, *args, **options):
        score_dir = _resolve_cli_path(options["score_dir"], "")
        output_dir = _resolve_cli_path(options["output_dir"], "")
        if output_dir.exists() and any(output_dir.iterdir()) and not options["overwrite"]:
            raise CommandError(f"output directory already exists and is not empty: {output_dir}; pass --overwrite")
        output_dir.mkdir(parents=True, exist_ok=True)
        summary_path = score_dir / "summary.json"
        per_record_path = score_dir / "per_record_scores.jsonl"
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        errors = [json.loads(line) for line in per_record_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        false_positive = [record for record in errors if record.get("false_positive")][: int(options["max_examples"])]
        false_negative = [record for record in errors if record.get("false_negative")][: int(options["max_examples"])]
        report_path = output_dir / "prompt_improvement.md"
        report_path.write_text(build_report(summary, false_positive=false_positive, false_negative=false_negative), encoding="utf-8")
        candidate_path = output_dir / "candidate_prompt_guidance.txt"
        candidate_path.write_text(CANDIDATE_GUIDANCE, encoding="utf-8")
        self.stdout.write(f"Prompt-improvement report: {report_path}")
        self.stdout.write(f"Conservative candidate guidance: {candidate_path}")


def build_report(summary: dict, *, false_positive: list[dict], false_negative: list[dict]) -> str:
    lines = [
        "# Conservative MWE prompt-improvement proposal",
        "",
        "This report is intentionally general. It is meant to guide a prompt revision without encoding project-specific answers or memorising development examples.",
        "",
        "## Current score",
        "",
        f"- Records: {summary.get('record_count')}",
        f"- Precision: {float(summary.get('precision') or 0):.3f}",
        f"- Recall: {float(summary.get('recall') or 0):.3f}",
        f"- F1: {float(summary.get('f1') or 0):.3f}",
        "",
        "## General revision principles",
        "",
        "- Mark an MWE only when the expression is conventionalized, idiomatic, lexicalized, or functions as a stable multi-token lexical unit.",
        "- Do not mark ordinary compositional adjective+noun, determiner+noun, or verb+object phrases just because they are frequent in the text.",
        "- Prefer high precision: when unsure, leave tokens unmarked rather than inventing an MWE.",
        "- Keep labels broad and language-neutral; avoid rules tied to a single project or named example.",
        "- Preserve the input token sequence exactly and only add MWE IDs to tokens that belong to accepted multi-token expressions.",
        "",
        "## False-positive examples to inspect",
        "",
    ]
    append_examples(lines, false_positive)
    lines.extend(["", "## False-negative examples to inspect", ""])
    append_examples(lines, false_negative)
    return "\n".join(lines) + "\n"


def append_examples(lines: list[str], records: list[dict]) -> None:
    if not records:
        lines.append("No examples in this category.")
        return
    for record in records:
        lines.extend(
            [
                f"### {record.get('record_id')}",
                "",
                record.get("segment_surface") or "",
                "",
                f"- Gold spans: {record.get('gold_spans')}",
                f"- Predicted spans: {record.get('predicted_spans')}",
                "",
            ]
        )


CANDIDATE_GUIDANCE = """Additional conservative MWE guidance:
- Identify only conventionalized, idiomatic, lexicalized, or stable multi-token lexical units.
- Do not mark ordinary compositional phrases merely because their words occur together.
- Prefer precision over recall: if an expression is doubtful, leave it unmarked.
- Keep the original tokens unchanged and assign an MWE ID only to tokens in the accepted expression.
"""
