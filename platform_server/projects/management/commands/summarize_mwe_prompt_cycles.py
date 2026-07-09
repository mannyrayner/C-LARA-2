from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from .review_fewshots import _resolve_cli_path


class Command(BaseCommand):
    help = "Collect MWE prompt-cycle performance and prompt-size summaries in one report."

    def add_arguments(self, parser):
        parser.add_argument("--cycle-base-dir", required=True)
        parser.add_argument("--output-json", required=True)
        parser.add_argument("--output-markdown", required=True)
        parser.add_argument("--max-cycles", type=int, default=0)
        parser.add_argument("--overwrite", action="store_true")

    def handle(self, *args, **options):
        base_dir = _resolve_cli_path(options["cycle_base_dir"], "")
        output_json = _resolve_cli_path(options["output_json"], "")
        output_markdown = _resolve_cli_path(options["output_markdown"], "")
        if not base_dir.exists():
            raise CommandError(f"cycle base directory not found: {base_dir}")
        if not options["overwrite"]:
            for path in (output_json, output_markdown):
                if path.exists():
                    raise CommandError(f"output already exists: {path}; pass --overwrite")
        cycles = collect_cycle_summaries(base_dir, max_cycles=int(options["max_cycles"] or 0))
        if not cycles:
            raise CommandError(f"no cycle score summaries found under: {base_dir}")
        payload = {
            "schema_version": 1,
            "cycle_base_dir": str(base_dir),
            "cycle_count": len(cycles),
            "best_cycle": best_cycle(cycles),
            "cycles": cycles,
        }
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_markdown.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        output_markdown.write_text(render_markdown(payload), encoding="utf-8")
        self.stdout.write(f"MWE cycle summary: {output_markdown}")
        self.stdout.write(f"MWE cycle summary JSON: {output_json}")


def collect_cycle_summaries(base_dir: Path, *, max_cycles: int = 0) -> list[dict[str, Any]]:
    cycles: list[dict[str, Any]] = []
    for cycle_dir in sorted(base_dir.glob("cycle_*"), key=cycle_sort_key):
        if max_cycles and len(cycles) >= max_cycles:
            break
        summary_path = cycle_dir / "score" / "summary.json"
        if not summary_path.exists():
            continue
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        prompt_path = cycle_dir / "template.txt"
        revision_path = cycle_dir / "improvement" / "template_revision.txt"
        improvement_path = cycle_dir / "improvement" / "prompt_improvement.md"
        cycles.append(
            {
                "cycle": cycle_sort_key(cycle_dir),
                "cycle_dir": str(cycle_dir),
                "records": int(summary.get("record_count") or 0),
                "precision": float(summary.get("precision") or 0),
                "recall": float(summary.get("recall") or 0),
                "f1": float(summary.get("f1") or 0),
                "exact_match_rate": float(summary.get("exact_match_rate") or 0),
                "true_positive": int(summary.get("true_positive") or 0),
                "false_positive": int(summary.get("false_positive") or 0),
                "false_negative": int(summary.get("false_negative") or 0),
                "prompt_chars": text_length(prompt_path),
                "prompt_lines": line_count(prompt_path),
                "revision_chars": text_length(revision_path),
                "summary_json": str(summary_path),
                "summary_markdown": str(cycle_dir / "score" / "summary.md"),
                "improvement_report": str(improvement_path),
                "template": str(prompt_path),
                "template_revision": str(revision_path),
            }
        )
    return cycles


def cycle_sort_key(path: Path) -> int:
    try:
        return int(path.name.split("_", 1)[1])
    except (IndexError, ValueError):
        return 0


def text_length(path: Path) -> int:
    if not path.exists():
        return 0
    return len(path.read_text(encoding="utf-8"))


def line_count(path: Path) -> int:
    if not path.exists():
        return 0
    return len(path.read_text(encoding="utf-8").splitlines())


def best_cycle(cycles: list[dict[str, Any]]) -> dict[str, Any]:
    return max(cycles, key=lambda item: (item["f1"], item["recall"], item["precision"]))


def render_markdown(payload: dict[str, Any]) -> str:
    cycles = payload["cycles"]
    best = payload["best_cycle"]
    lines = [
        "# MWE prompt-cycle comparison",
        "",
        f"- Cycle base directory: `{payload['cycle_base_dir']}`",
        f"- Cycles summarized: {payload['cycle_count']}",
        f"- Best F1 cycle: cycle {best['cycle']} (F1={best['f1']:.3f}, precision={best['precision']:.3f}, recall={best['recall']:.3f})",
        "",
        "## Score trend",
        "",
        "| Cycle | Records | Precision | Recall | F1 | Exact | TP | FP | FN | Prompt chars | Prompt lines | Revision chars |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in cycles:
        marker = " **best**" if item["cycle"] == best["cycle"] else ""
        lines.append(
            f"| {item['cycle']}{marker} | {item['records']} | {item['precision']:.3f} | {item['recall']:.3f} | "
            f"{item['f1']:.3f} | {item['exact_match_rate']:.3f} | {item['true_positive']} | {item['false_positive']} | "
            f"{item['false_negative']} | {item['prompt_chars']} | {item['prompt_lines']} | {item['revision_chars']} |"
        )
    lines.extend(
        [
            "",
            "## Notes for review",
            "",
            "- If F1 stalls or declines while prompt size grows, inspect whether later prompts have become too long or overly specific.",
            "- Compare precision/recall changes: falling recall suggests missed MWE classes; falling precision suggests over-broad marking.",
            "- Use this report with each cycle's `prompt_improvement.md` before deciding whether to accept, shorten, or revise the next prompt.",
            "",
            "## Artifact paths",
            "",
        ]
    )
    for item in cycles:
        lines.extend(
            [
                f"### Cycle {item['cycle']}",
                "",
                f"- Summary: `{item['summary_markdown']}`",
                f"- Improvement report: `{item['improvement_report']}`",
                f"- Template: `{item['template']}`",
                f"- Next-cycle revision draft: `{item['template_revision']}`",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"
