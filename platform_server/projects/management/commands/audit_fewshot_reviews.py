from __future__ import annotations

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from pipeline.fewshot_curation import FewshotCurationSpec, _filesystem_path, _path_exists, _read_json, _write_text, curation_root
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
        if not _path_exists(items_path):
            raise CommandError(f"review item summary not found: {items_path}. Run review_fewshots first.")
        payload = _read_json(items_path)
        items = payload.get("items")
        if not isinstance(items, list):
            raise CommandError(f"review item summary has no items array: {items_path}")
        limit = options["limit"]
        if limit > 0:
            items = items[:limit]

        audit_path = reviews_dir / f"{options['request_id']}.human_audit.jsonl"
        existing_audit_records = [] if options["overwrite"] else _load_existing_audit_records(audit_path)
        completed_existing_records = [record for record in existing_audit_records if _is_completed_audit_record(record)]
        existing_by_example = {str(record.get("example_id") or ""): record for record in completed_existing_records}
        if existing_audit_records and not options["dry_run"]:
            self.stdout.write(
                f"Resuming existing audit with {len(existing_audit_records)} saved judgement(s) "
                f"({len(completed_existing_records)} completed) from {audit_path}"
            )
        items_to_audit = [item for item in items if str(item.get("example_id") or "") not in existing_by_example]
        item_index_by_example = {str(item.get("example_id") or ""): idx for idx, item in enumerate(items, start=1)}

        audit_records: list[dict[str, object]] = list(existing_audit_records)
        completed_this_run: set[str] = set()
        pending_index = 0
        while pending_index < len(items_to_audit):
            item = items_to_audit[pending_index]
            example_id = str(item.get("example_id") or "")
            if example_id in completed_this_run:
                pending_index += 1
                continue
            display_index = item_index_by_example.get(example_id, pending_index + 1)
            if options["dry_run"]:
                _display_audit_item(self, item, display_index=display_index, total=len(items))
                pending_index += 1
                continue
            action = _prompt_for_audit_action(self, item, display_index=display_index, total=len(items))
            if action["kind"] == "quit":
                break
            if action["kind"] == "back":
                back_index = int(action["index"])
                if back_index < 1 or back_index > len(items):
                    self.stdout.write(f"No review item {back_index}; choose 1-{len(items)}.")
                    continue
                corrected_item = items[back_index - 1]
                correction = _prompt_for_audit_action(
                    self,
                    corrected_item,
                    display_index=back_index,
                    total=len(items),
                    heading="Correction",
                )
                if correction["kind"] == "quit":
                    break
                if correction["kind"] != "judgement":
                    self.stdout.write("Nested back commands are ignored while correcting; returning to current item.")
                    continue
                audit_records.append(_audit_record(corrected_item, str(correction["judgement"])))
                if _is_completed_audit_record(audit_records[-1]):
                    completed_this_run.add(str(corrected_item.get("example_id") or ""))
                continue
            audit_records.append(_audit_record(item, str(action["judgement"])))
            if _is_completed_audit_record(audit_records[-1]):
                completed_this_run.add(example_id)
            pending_index += 1

        if options["dry_run"]:
            self.stdout.write(self.style.SUCCESS(f"Displayed {len(items_to_audit)} unaudited review item(s) from {items_path}"))
            return

        _write_text(
            audit_path,
            "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in audit_records),
        )
        self.stdout.write(self.style.SUCCESS(f"Wrote {len(audit_records)} human audit record(s) to {audit_path}"))


def _display_audit_item(
    command: BaseCommand, item: dict[str, object], *, display_index: int, total: int, heading: str = ""
) -> None:
    command.stdout.write("\n" + "=" * 72)
    prefix = f"{heading} " if heading else ""
    command.stdout.write(
        f"{prefix}{display_index}/{total} {item.get('example_id')}  "
        f"decision={item.get('decision')} severity={item.get('severity')}"
    )
    command.stdout.write(f"boundary_marked: {item.get('boundary_marked')}")
    if item.get("strongest_reason"):
        command.stdout.write(f"reason: {item.get('strongest_reason')}")
    if item.get("explanation"):
        command.stdout.write(f"explanation: {item.get('explanation')}")


def _prompt_for_audit_action(
    command: BaseCommand, item: dict[str, object], *, display_index: int, total: int, heading: str = ""
) -> dict[str, object]:
    _display_audit_item(command, item, display_index=display_index, total=total, heading=heading)
    while True:
        answer = (
            input(
                "Judge decision correct? "
                "[a/c]=accept/correct, [r/i]=reject/incorrect, [s]=skip, [b <n>]=back, [q]=quit: "
            )
            .strip()
            .lower()
        )
        if answer in {"q", "quit"}:
            return {"kind": "quit"}
        if answer.startswith("b "):
            try:
                return {"kind": "back", "index": int(answer.split(None, 1)[1])}
            except ValueError:
                command.stdout.write("Use 'b <number>' to go back to a review item, e.g. 'b 3'.")
                continue
        judgement = _normalise_audit_answer(answer)
        if judgement:
            return {"kind": "judgement", "judgement": judgement}
        command.stdout.write("Unrecognised response. Use a/c, r/i, s, b <number>, or q.")


def _normalise_audit_answer(answer: str) -> str:
    if answer in {"a", "accept", "c", "correct", "y", "yes"}:
        return "correct"
    if answer in {"r", "reject", "i", "incorrect", "n", "no"}:
        return "incorrect"
    if answer in {"s", "skip", "skipped"}:
        return "skipped"
    return ""


def _audit_record(item: dict[str, object], judgement: str) -> dict[str, object]:
    return {
        "example_id": item.get("example_id"),
        "review_decision": item.get("decision"),
        "review_severity": item.get("severity"),
        "human_judgement": judgement,
        "boundary_marked": item.get("boundary_marked"),
    }


def _load_existing_audit_records(path: Path) -> list[dict[str, object]]:
    if not _path_exists(path):
        return []
    records: list[dict[str, object]] = []
    for line in _filesystem_path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            records.append(payload)
    return records


def _is_completed_audit_record(record: dict[str, object]) -> bool:
    return str(record.get("human_judgement") or "").lower() in {"correct", "incorrect"}
