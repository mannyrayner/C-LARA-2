from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from core.ai_api import OpenAIClient
from core.config import OpenAIConfig

DEFAULT_MWE_REVISION_MODEL = "gpt-5.5"

from .review_fewshots import _resolve_cli_path


class Command(BaseCommand):
    help = "Use AI to revise an MWE prompt from a scored prompt-improvement report."

    def add_arguments(self, parser):
        parser.add_argument("--current-template", required=True)
        parser.add_argument("--improvement-report", required=True)
        parser.add_argument("--candidate-guidance", default="")
        parser.add_argument("--output-template", required=True)
        parser.add_argument("--output-json", default="")
        parser.add_argument("--model", default=DEFAULT_MWE_REVISION_MODEL)
        parser.add_argument("--timeout-s", type=float, default=180.0)
        parser.add_argument("--heartbeat-s", type=float, default=20.0)
        parser.add_argument("--overwrite", action="store_true")

    def handle(self, *args, **options):
        current_template_path = _resolve_cli_path(options["current_template"], "")
        improvement_report_path = _resolve_cli_path(options["improvement_report"], "")
        candidate_guidance_path = _resolve_cli_path(options.get("candidate_guidance") or "", "") if options.get("candidate_guidance") else None
        output_template_path = _resolve_cli_path(options["output_template"], "")
        output_json_path = _resolve_cli_path(options.get("output_json") or "", "") if options.get("output_json") else output_template_path.with_suffix(".json")

        for path, label in (
            (current_template_path, "current template"),
            (improvement_report_path, "improvement report"),
        ):
            if not path.exists():
                raise CommandError(f"{label} not found: {path}")
        if candidate_guidance_path and not candidate_guidance_path.exists():
            raise CommandError(f"candidate guidance not found: {candidate_guidance_path}")
        if not options["overwrite"]:
            for path in (output_template_path, output_json_path):
                if path.exists():
                    raise CommandError(f"output already exists: {path}; pass --overwrite")

        current_template = current_template_path.read_text(encoding="utf-8")
        improvement_report = improvement_report_path.read_text(encoding="utf-8")
        candidate_guidance = candidate_guidance_path.read_text(encoding="utf-8") if candidate_guidance_path else ""
        prompt = build_revision_prompt(
            current_template=current_template,
            improvement_report=improvement_report,
            candidate_guidance=candidate_guidance,
        )
        self.stdout.write(f"Requesting revised MWE prompt with model {options['model']}...")
        client = OpenAIClient(config=OpenAIConfig(timeout_s=options["timeout_s"], heartbeat_s=options["heartbeat_s"]))
        payload = asyncio.run(client.chat_json(prompt, model=str(options["model"]), temperature=0))
        revision = normalize_revision_payload(payload)

        output_template_path.parent.mkdir(parents=True, exist_ok=True)
        output_json_path.parent.mkdir(parents=True, exist_ok=True)
        output_template_path.write_text(revision["prompt"].rstrip() + "\n", encoding="utf-8")
        output_json_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "model": options["model"],
                    "current_template": str(current_template_path),
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
        self.stdout.write(f"Revised prompt template: {output_template_path}")
        self.stdout.write(f"Revision metadata: {output_json_path}")


def build_revision_prompt(*, current_template: str, improvement_report: str, candidate_guidance: str) -> str:
    return "\n\n".join(
        [
            "You revise C-LARA MWE annotation prompts for prompt-learning experiments.",
            "Return only JSON with keys: prompt, rationale, changes, risks.",
            "The prompt value must be the complete directly usable prompt file content.",
            "Keep the revised prompt simple, general, language-neutral when possible, and suitable for unseen validation/test projects.",
            "Do not memorise project-specific answers, titles, named characters, or exact spans from the report.",
            "Do not add long lists of examples from the development set. If examples are needed, make them short and generic.",
            "Prefer changes that address recurring error patterns: overly long spans, missing fixed expressions, including surrounding function words/pronouns, and compositional phrase overmarking.",
            "Preserve any required response-format instructions from the current prompt unless they clearly conflict with the report.",
            "If the report is insufficient for a safe non-trivial change, still return a complete prompt but keep edits conservative.",
            "## Current prompt template",
            current_template,
            "## Prompt-improvement report",
            improvement_report,
            "## Candidate guidance",
            candidate_guidance or "(none supplied)",
        ]
    )


def normalize_revision_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise CommandError("revision model did not return a JSON object")
    prompt = str(payload.get("prompt") or "").strip()
    if not prompt:
        raise CommandError("revision model did not return a non-empty 'prompt' field")
    changes = payload.get("changes")
    if not isinstance(changes, list):
        changes = [str(changes)] if changes else []
    risks = payload.get("risks")
    if not isinstance(risks, list):
        risks = [str(risks)] if risks else []
    return {
        "prompt": prompt,
        "rationale": str(payload.get("rationale") or ""),
        "changes": [str(item) for item in changes],
        "risks": [str(item) for item in risks],
    }
