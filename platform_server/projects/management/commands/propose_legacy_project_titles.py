from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from core.ai_api import OpenAIClient
from core.config import DEFAULT_MODEL, OpenAIConfig
from projects.management.commands.inventory_legacy_project_titles import PLACEHOLDER_TITLE_RE
from projects.models import Project


def _clean_title(value: Any) -> str:
    title = " ".join(str(value or "").replace("\n", " ").split()).strip(" \"'")
    return title[:200].rstrip()


def _prompt(row: dict[str, Any]) -> str:
    evidence = {
        "current_placeholder_title": row.get("title"),
        "retained_source_title": row.get("source_title"),
        "text_language": row.get("text_language"),
        "gloss_language": row.get("gloss_language"),
        "discovery_summary": row.get("discovery_summary"),
        "discovery_keywords": row.get("discovery_keywords"),
        "text_preview": row.get("text_preview"),
    }
    return (
        "Propose a concise, informative title for this language-learning text. Use only the supplied evidence. "
        "Prefer the language of the text, retain a well-supported proper name, and do not add a gloss-language suffix. "
        "Do not repeat administrative labels such as ALTA, C-LARA, imported project, language codes, or project IDs "
        "unless they are genuinely part of the text's subject. Return JSON with exactly these fields: "
        '{"title":"...","confidence":"high|medium|low","rationale":"..."}. '
        "The title must be at most 200 characters.\n\nEvidence:\n"
        + json.dumps(evidence, ensure_ascii=False, indent=2)
    )


class Command(BaseCommand):
    help = "Use AI to create a reviewable title-proposal report for placeholder legacy projects; never rename projects."

    def add_arguments(self, parser):
        parser.add_argument("--inventory", required=True, help="JSON produced by inventory_legacy_project_titles.")
        parser.add_argument("--report", required=True, help="Destination JSON proposal report.")
        parser.add_argument("--model", default=DEFAULT_MODEL)
        parser.add_argument("--only-id", action="append", default=[], help="Legacy project ID; repeatable.")
        parser.add_argument("--limit", type=int)
        parser.add_argument("--timeout-s", type=float, default=120.0)
        parser.add_argument("--heartbeat-s", type=float, default=20.0)
        parser.add_argument("--overwrite", action="store_true")

    def handle(self, *args, **options):
        inventory_path = Path(options["inventory"]).expanduser().resolve()
        report_path = Path(options["report"]).expanduser().resolve()
        if not inventory_path.is_file():
            raise CommandError(f"inventory not found: {inventory_path}")
        if report_path.exists() and not options["overwrite"]:
            raise CommandError(f"report already exists: {report_path}; pass --overwrite to replace it")
        if options["limit"] is not None and options["limit"] < 1:
            raise CommandError("--limit must be a positive integer.")
        inventory_bytes = inventory_path.read_bytes()
        try:
            inventory = json.loads(inventory_bytes)
        except json.JSONDecodeError as exc:
            raise CommandError(f"inventory is not valid JSON: {inventory_path}") from exc
        if inventory.get("schema_version") != 1 or not isinstance(inventory.get("projects"), list):
            raise CommandError("unsupported title-inventory schema")

        only_ids = {str(value).strip() for value in options["only_id"] if str(value).strip()}
        candidates = [
            row
            for row in inventory["projects"]
            if isinstance(row, dict)
            and row.get("title_status") == "placeholder"
            and (not only_ids or str(row.get("legacy_project_id")) in only_ids)
        ]
        found_ids = {str(row.get("legacy_project_id")) for row in candidates}
        if only_ids - found_ids:
            raise CommandError("Placeholder legacy IDs not found in inventory: " + ", ".join(sorted(only_ids - found_ids)))
        if options["limit"] is not None:
            candidates = candidates[: options["limit"]]
        if not candidates:
            raise CommandError("inventory contains no matching placeholder-title projects")

        model = str(options["model"])
        client = OpenAIClient(
            config=OpenAIConfig(
                model=model,
                timeout_s=float(options["timeout_s"]),
                heartbeat_s=float(options["heartbeat_s"]),
            )
        )
        proposals = []
        for index, row in enumerate(candidates, 1):
            legacy_id = str(row.get("legacy_project_id"))
            base = {
                "source_system": row.get("source_system"),
                "legacy_project_id": legacy_id,
                "project_id": row.get("project_id"),
                "owner_id": row.get("owner_id"),
                "current_title": row.get("title"),
                "inventory_text_sha256": row.get("text_sha256"),
            }
            current = Project.objects.filter(
                pk=row.get("project_id"),
                owner_id=row.get("owner_id"),
                legacy_import_records__source_system=row.get("source_system"),
                legacy_import_records__legacy_project_id=legacy_id,
            ).first()
            if current is None or current.title != row.get("title") or not PLACEHOLDER_TITLE_RE.fullmatch(current.title):
                proposals.append({**base, "status": "skipped_stale", "error": "live project no longer matches inventory"})
                self.stdout.write(f"[{index}/{len(candidates)}] {legacy_id} skipped_stale")
                continue
            try:
                response = asyncio.run(client.chat_json(_prompt(row), model=model))
                proposed_title = _clean_title(response.get("title"))
                confidence = str(response.get("confidence") or "").strip().lower()
                rationale = " ".join(str(response.get("rationale") or "").split())[:1000]
                if not proposed_title or PLACEHOLDER_TITLE_RE.fullmatch(proposed_title):
                    raise ValueError("model returned an empty or placeholder title")
                if confidence not in {"high", "medium", "low"}:
                    raise ValueError("model returned invalid confidence")
                collision_ids = list(
                    Project.objects.filter(owner_id=row.get("owner_id"), title__iexact=proposed_title)
                    .exclude(pk=row.get("project_id"))
                    .values_list("id", flat=True)
                )
                proposals.append(
                    {
                        **base,
                        "status": "proposed" if not collision_ids else "collision",
                        "proposed_title": proposed_title,
                        "confidence": confidence,
                        "rationale": rationale,
                        "collision_project_ids": collision_ids,
                    }
                )
            except Exception as exc:
                proposals.append({**base, "status": "failed", "error": str(exc)})
            self.stdout.write(f"[{index}/{len(candidates)}] {legacy_id} {proposals[-1]['status']}")

        report = {
            "schema_version": 1,
            "source_system": inventory.get("source_system"),
            "inventory_path": str(inventory_path),
            "inventory_sha256": hashlib.sha256(inventory_bytes).hexdigest(),
            "model": model,
            "summary": {
                "candidate_count": len(candidates),
                "proposed_count": sum(row["status"] == "proposed" for row in proposals),
                "collision_count": sum(row["status"] == "collision" for row in proposals),
                "failed_count": sum(row["status"] == "failed" for row in proposals),
                "skipped_stale_count": sum(row["status"] == "skipped_stale" for row in proposals),
            },
            "proposals": proposals,
        }
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"Wrote {len(proposals)} title proposal(s) to {report_path}"))
