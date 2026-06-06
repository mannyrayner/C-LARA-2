from __future__ import annotations

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from pipeline.fewshot_curation import FewshotCurationSpec, curation_root
from .review_fewshots import _resolve_cli_path


class Command(BaseCommand):
    help = "Interactively audit compact few-shot review decisions."

    def add_arguments(self, parser):
        parser.add_argument("--operation", default="segmentation_phase_2")
        parser.add_argument("--language", required=True)
        parser.add_argument("--mechanism", default="boundary_first")
        parser.add_argument("--target-set", required=True)
        parser.add_argument("--request-id", required=True)
        parser.add_argument("--repo-root", default="")
        parser.add_argument(
            "--curation-root",
            default="",
            help="Optional base directory for curation artifacts; defaults to <repo-root>/docs/few_shot_curation",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Maximum number of review items to show; 0 means all",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print items without prompting or writing audit output",
        )
        parser.add_argument("--overwrite", action="store_true", help="Replace an existing audit JSONL file")

    def handle(self, *args, **options):
        repo_root = _resolve_cli_path(options["repo_root"], getattr(settings, "ROOT_DIR", Path.cwd()))
        curation_root_base = _resolve_cli_path(options["curation_root"], "") if options.get("curation_root") else None
        spec = FewshotCurationSpec(
            operation=options["operation"],
            language=options["language"],
            mechanism=options["mechanism"],
            target_set=options["target_set"],
            request_id=options["request_id"],
        )
        root = curation_root(repo_root, spec, curation_root_base=curation_root_base)
        reviews_dir = root / "reviews"
        items_path = reviews_dir / f"{options['request_id']}.items.json"
        if not items_path.exists():
            raise CommandError(f"review item summary not found: {items_path}. Run review_fewshots first.")
        payload = json.loads(items_path.read_text(encoding="utf-8"))
        items = payload.get("items")
        if not isinstance(items, list):
            raise CommandError(f"review item summary has no items array: {items_path}")
        limit = options["limit"]
        if limit > 0:
            items = items[:limit]

        audit_path = reviews_dir / f"{options['request_id']}.human_audit.jsonl"
        if audit_path.exists() and not (options["overwrite"] or options["dry_run"]):
            raise CommandError(f"audit output already exists: {audit_path}; pass --overwrite to replace it")

        audit_records: list[dict[str, object]] = []
        for idx, item in enumerate(items, start=1):
            self.stdout.write("\n" + "=" * 72)
            self.stdout.write(
                f"{idx}/{len(items)} {item.get('example_id')}  "
                f"decision={item.get('decision')} severity={item.get('severity')}"
            )
            self.stdout.write(f"boundary_marked: {item.get('boundary_marked')}")
            if item.get("strongest_reason"):
                self.stdout.write(f"reason: {item.get('strongest_reason')}")
            if item.get("explanation"):
                self.stdout.write(f"explanation: {item.get('explanation')}")
            if options["dry_run"]:
                continue
            answer = input("Judge decision correct? [c]orrect/[i]ncorrect/[s]kip/[q]uit: ").strip().lower()
            if answer == "q":
                break
            if answer not in {"c", "i", "s"}:
                answer = "s"
            audit_records.append(
                {
                    "example_id": item.get("example_id"),
                    "review_decision": item.get("decision"),
                    "review_severity": item.get("severity"),
                    "human_judgement": {"c": "correct", "i": "incorrect", "s": "skipped"}[answer],
                    "boundary_marked": item.get("boundary_marked"),
                }
            )

        if options["dry_run"]:
            self.stdout.write(self.style.SUCCESS(f"Displayed {len(items)} review item(s) from {items_path}"))
            return

        audit_path.parent.mkdir(parents=True, exist_ok=True)
        audit_path.write_text(
            "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in audit_records),
            encoding="utf-8",
        )
        self.stdout.write(self.style.SUCCESS(f"Wrote {len(audit_records)} human audit record(s) to {audit_path}"))
