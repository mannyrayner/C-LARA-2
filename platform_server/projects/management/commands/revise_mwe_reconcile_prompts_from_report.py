from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from core.ai_api import OpenAIClient
from core.config import OpenAIConfig

from .review_fewshots import _resolve_cli_path
from .revise_mwe_prompt_from_report import DEFAULT_MWE_REVISION_MODEL
from .run_mwe_reconcile_prompt_experiment import load_analysis_templates


class Command(BaseCommand):
    help = "Use AI to revise the three analysis prompts and reconciliation prompt for an MWE reconcile cycle."

    def add_arguments(self, parser):
        parser.add_argument("--current-analysis-template-dir", required=True)
        parser.add_argument("--current-reconcile-template", required=True)
        parser.add_argument("--improvement-report", required=True)
        parser.add_argument("--candidate-guidance", default="")
        parser.add_argument("--output-analysis-template-dir", required=True)
        parser.add_argument("--output-reconcile-template", required=True)
        parser.add_argument("--output-json", default="")
        parser.add_argument("--model", default=DEFAULT_MWE_REVISION_MODEL)
        parser.add_argument("--timeout-s", type=float, default=180.0)
        parser.add_argument("--heartbeat-s", type=float, default=20.0)
        parser.add_argument("--overwrite", action="store_true")

    def handle(self, *args, **options):
        analysis_template_dir = _resolve_cli_path(options["current_analysis_template_dir"], "")
        reconcile_template_path = _resolve_cli_path(options["current_reconcile_template"], "")
        improvement_report_path = _resolve_cli_path(options["improvement_report"], "")
        candidate_guidance_path = _resolve_cli_path(options.get("candidate_guidance") or "", "") if options.get("candidate_guidance") else None
        output_analysis_dir = _resolve_cli_path(options["output_analysis_template_dir"], "")
        output_reconcile_path = _resolve_cli_path(options["output_reconcile_template"], "")
        output_json_path = _resolve_cli_path(options.get("output_json") or "", "") if options.get("output_json") else output_reconcile_path.with_suffix(".json")

        for path, label in (
            (analysis_template_dir, "current analysis template directory"),
            (reconcile_template_path, "current reconciliation template"),
            (improvement_report_path, "improvement report"),
        ):
            if not path.exists():
                raise CommandError(f"{label} not found: {path}")
        if candidate_guidance_path and not candidate_guidance_path.exists():
            raise CommandError(f"candidate guidance not found: {candidate_guidance_path}")
        if not options["overwrite"]:
            existing_outputs = [output_json_path, output_reconcile_path, *output_analysis_dir.glob("*.txt")]
            for path in existing_outputs:
                if path.exists():
                    raise CommandError(f"output already exists: {path}; pass --overwrite")

        analysis_templates = load_analysis_templates(analysis_template_dir)
        reconcile_template = reconcile_template_path.read_text(encoding="utf-8")
        improvement_report = improvement_report_path.read_text(encoding="utf-8")
        candidate_guidance = candidate_guidance_path.read_text(encoding="utf-8") if candidate_guidance_path else ""
        prompt = build_reconcile_revision_prompt(
            analysis_templates=analysis_templates,
            reconcile_template=reconcile_template,
            improvement_report=improvement_report,
            candidate_guidance=candidate_guidance,
        )

        self.stdout.write(f"Requesting revised MWE reconcile prompts with model {options['model']}...")
        client = OpenAIClient(config=OpenAIConfig(timeout_s=options["timeout_s"], heartbeat_s=options["heartbeat_s"]))
        payload = asyncio.run(client.chat_json(prompt, model=str(options["model"]), temperature=None))
        revision = normalize_reconcile_revision_payload(payload, expected_names=[name for name, _template in analysis_templates])

        output_analysis_dir.mkdir(parents=True, exist_ok=True)
        output_reconcile_path.parent.mkdir(parents=True, exist_ok=True)
        output_json_path.parent.mkdir(parents=True, exist_ok=True)
        for name, text in revision["analysis_prompts"].items():
            (output_analysis_dir / name).write_text(text.rstrip() + "\n", encoding="utf-8")
        output_reconcile_path.write_text(revision["reconcile_prompt"].rstrip() + "\n", encoding="utf-8")
        output_json_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "model": options["model"],
                    "current_analysis_template_dir": str(analysis_template_dir),
                    "current_reconcile_template": str(reconcile_template_path),
                    "improvement_report": str(improvement_report_path),
                    "candidate_guidance": str(candidate_guidance_path) if candidate_guidance_path else "",
                    **revision,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        self.stdout.write(f"Revised analysis prompts: {output_analysis_dir}")
        self.stdout.write(f"Revised reconciliation prompt: {output_reconcile_path}")
        self.stdout.write(f"Revision metadata: {output_json_path}")


def build_reconcile_revision_prompt(
    *,
    analysis_templates: list[tuple[str, str]],
    reconcile_template: str,
    improvement_report: str,
    candidate_guidance: str,
) -> str:
    analysis_sections = []
    for name, template in analysis_templates:
        analysis_sections.extend([f"### {name}", template])
    return "\n\n".join(
        [
            "You revise a four-prompt C-LARA MWE annotation workflow for prompt-learning experiments.",
            "The workflow has three independent analysis prompts followed by one reconciliation/extraction prompt.",
            "Return only JSON with keys: analysis_prompts, reconcile_prompt, rationale, changes, risks.",
            "analysis_prompts must be an object whose keys are exactly the existing analysis template filenames and whose values are complete directly usable prompt files.",
            "reconcile_prompt must be the complete directly usable reconciliation prompt file.",
            "Keep the prompts general and suitable for unseen validation/test projects; do not memorise project-specific answers, titles, named characters, or exact spans from the report.",
            "Preserve useful diversity among the three analysis prompts: for example source-language conservatism, gloss/translation evidence, and boundary precision.",
            "Make explicit that MWE identification supports C-LARA glossing, so translation_context is important evidence when source tokens are translated as a phrase or would be glossed badly word by word.",
            "Keep the reconciliation prompt responsible for resolving disagreements and ensuring final annotations.mwes exactly match the final explanation.",
            "Avoid making prompts unnecessarily long; prefer concise, non-overlapping instructions.",
            "## Current analysis prompts",
            *analysis_sections,
            "## Current reconciliation prompt",
            reconcile_template,
            "## Prompt-improvement report",
            improvement_report,
            "## Candidate guidance",
            candidate_guidance or "(none supplied)",
        ]
    )


def normalize_reconcile_revision_payload(payload: Any, *, expected_names: list[str]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise CommandError("revision model did not return a JSON object")
    analysis_prompts = payload.get("analysis_prompts")
    if not isinstance(analysis_prompts, dict):
        raise CommandError("revision model did not return an 'analysis_prompts' object")
    normalized_analysis: dict[str, str] = {}
    for name in expected_names:
        text = str(analysis_prompts.get(name) or analysis_prompts.get(f"{name}.txt") or "").strip()
        if not text:
            raise CommandError(f"revision model did not return a non-empty analysis prompt for {name}")
        normalized_analysis[f"{name}.txt"] = text
    reconcile_prompt = str(payload.get("reconcile_prompt") or "").strip()
    if not reconcile_prompt:
        raise CommandError("revision model did not return a non-empty 'reconcile_prompt' field")
    changes = payload.get("changes")
    if not isinstance(changes, list):
        changes = [str(changes)] if changes else []
    risks = payload.get("risks")
    if not isinstance(risks, list):
        risks = [str(risks)] if risks else []
    return {
        "analysis_prompts": normalized_analysis,
        "reconcile_prompt": reconcile_prompt,
        "rationale": str(payload.get("rationale") or ""),
        "changes": [str(item) for item in changes],
        "risks": [str(item) for item in risks],
    }
