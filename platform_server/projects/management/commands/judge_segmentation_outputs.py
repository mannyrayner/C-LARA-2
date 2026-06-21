from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TextIO

from django.core.management.base import BaseCommand, CommandError

from .review_fewshots import _resolve_cli_path

ACCEPT_ALIASES = {"a", "accept", "y", "yes", "correct", "c"}
REJECT_ALIASES = {"r", "reject", "n", "no", "wrong", "w"}
SKIP_ALIASES = {"s", "skip", ""}
QUIT_ALIASES = {"q", "quit", "exit"}
HELP_ALIASES = {"?", "h", "help"}


class Command(BaseCommand):
    help = "Interactively judge segmentation_phase_2 output records with append-only resume and cache files."

    def add_arguments(self, parser):
        parser.add_argument("--outputs-jsonl", required=True)
        parser.add_argument("--judgements-jsonl", required=True)
        parser.add_argument("--cache-json", required=True)
        parser.add_argument("--run-label", default="")
        parser.add_argument("--limit", type=int, default=0, help="Maximum new prompts to show; 0 means no limit.")
        parser.add_argument(
            "--include-cached",
            action="store_true",
            help="Append reused cached judgements for this run instead of silently skipping cached segmentations.",
        )

    def handle(self, *args, **options):
        outputs_path = _resolve_cli_path(options["outputs_jsonl"], "")
        judgements_path = _resolve_cli_path(options["judgements_jsonl"], "")
        cache_path = _resolve_cli_path(options["cache_json"], "")
        limit = int(options.get("limit") or 0)
        run_label = str(options.get("run_label") or "")
        include_cached = bool(options.get("include_cached"))

        payloads = load_output_records(outputs_path)
        if not payloads:
            raise CommandError(f"No output records found in {outputs_path}")
        records = [judgement_record_from_output(payload, run_label=run_label) for payload in payloads]
        cache = load_cache(cache_path)
        judged_record_ids = load_judged_record_ids(judgements_path)
        initially_judged_record_ids = set(judged_record_ids)
        judgements_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.parent.mkdir(parents=True, exist_ok=True)

        prompted = 0
        appended = 0
        reused = 0
        current_index = 0
        with judgements_path.open("a", encoding="utf-8") as out:
            while True:
                next_index = next_unjudged_index(records, judged_record_ids, start=current_index)
                if next_index is None:
                    action, target = prompt_after_completion()
                    if action == "quit":
                        break
                    if action == "back":
                        correction_appended = self.rejudge_record(
                            records,
                            target,
                            out=out,
                            cache=cache,
                            cache_path=cache_path,
                            total=len(records),
                        )
                        appended += int(correction_appended)
                    continue

                current_index = next_index
                record = records[current_index]
                cached = cache.get(record["cache_key"])
                if cached:
                    reused += 1
                    judged_record_ids.add(record["record_id"])
                    if include_cached:
                        write_judgement(out, record, cached["judgement"], cached.get("notes", ""), reused=True)
                        out.flush()
                        appended += 1
                    current_index += 1
                    continue

                if limit and prompted >= limit:
                    break
                prompted += 1
                action, decision, notes, target = prompt_for_judgement(
                    record, position=current_index + 1, total=len(records)
                )
                if action == "quit":
                    break
                if action == "back":
                    correction_appended = self.rejudge_record(
                        records,
                        target,
                        out=out,
                        cache=cache,
                        cache_path=cache_path,
                        total=len(records),
                    )
                    appended += int(correction_appended)
                    continue
                write_judgement(out, record, decision, notes, reused=False)
                out.flush()
                update_cache(cache, record, decision, notes)
                write_cache(cache_path, cache)
                judged_record_ids.add(record["record_id"])
                appended += 1
                current_index += 1

        if appended and not cache_path.exists():
            write_cache(cache_path, cache)
        skipped_existing = len(initially_judged_record_ids.intersection({r["record_id"] for r in records}))
        self.stdout.write("Segmentation judgement pass complete")
        self.stdout.write(f"Outputs: {outputs_path}")
        self.stdout.write(f"Judgements: {judgements_path}")
        self.stdout.write(f"Cache: {cache_path}")
        self.stdout.write(
            f"Records: {len(records)}; prompted: {prompted}; appended: {appended}; "
            f"reused_cached: {reused}; skipped_existing: {skipped_existing}"
        )

    def rejudge_record(
        self,
        records: list[dict[str, Any]],
        target: str,
        *,
        out: TextIO,
        cache: dict[str, dict[str, Any]],
        cache_path: Path,
        total: int,
    ) -> bool:
        resolved = resolve_back_target(records, target)
        if resolved is None:
            self.stdout.write(f"No item found for {target!r}; continuing.")
            return False
        position, record = resolved
        action, decision, notes, nested_target = prompt_for_judgement(
            record, position=position, total=total, correction=True
        )
        if action == "quit":
            return False
        if action == "back":
            return self.rejudge_record(records, nested_target, out=out, cache=cache, cache_path=cache_path, total=total)
        write_judgement(out, record, decision, notes, reused=False, correction=True)
        out.flush()
        update_cache(cache, record, decision, notes)
        write_cache(cache_path, cache)
        return True


def next_unjudged_index(records: list[dict[str, Any]], judged_record_ids: set[str], *, start: int) -> int | None:
    for index in range(start, len(records)):
        if records[index]["record_id"] not in judged_record_ids:
            return index
    for index in range(0, min(start, len(records))):
        if records[index]["record_id"] not in judged_record_ids:
            return index
    return None


def resolve_back_target(records: list[dict[str, Any]], target: str) -> tuple[int, dict[str, Any]] | None:
    normalized = target.strip()
    if not normalized:
        return None
    if normalized.isdigit():
        position = int(normalized)
        if 1 <= position <= len(records):
            return position, records[position - 1]
    for position, record in enumerate(records, start=1):
        if record["record_id"] == normalized:
            return position, record
    return None


def update_cache(cache: dict[str, dict[str, Any]], record: dict[str, Any], judgement: str, notes: str) -> None:
    cache[record["cache_key"]] = {
        "judgement": judgement,
        "notes": notes,
        "input_surface": record["input_surface"],
        "segments_display": record["segments_display"],
        "updated_at": utc_now(),
    }


def load_output_records(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def load_cache(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise CommandError(f"Cache must be a JSON object: {path}")
    return payload


def write_cache(path: Path, cache: dict[str, dict[str, Any]]) -> None:
    path.write_text(json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_judged_record_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    judged: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if payload.get("record_id"):
            judged.add(str(payload["record_id"]))
    return judged


def judgement_record_from_output(payload: dict[str, Any], *, run_label: str) -> dict[str, Any]:
    segmentation = payload.get("segmentation_phase_2") or {}
    token_surfaces = extract_token_surfaces(segmentation)
    input_surface = str(payload.get("input_surface") or segmentation.get("surface") or "")
    segments_display = "|".join(token_surfaces)
    cache_key = segmentation_cache_key(input_surface, token_surfaces)
    return {
        "schema_version": 1,
        "run_label": run_label,
        "record_id": str(payload.get("record_id") or ""),
        "project_id": payload.get("project_id"),
        "project_title": payload.get("project_title") or "",
        "split": payload.get("split") or "",
        "page_index": payload.get("page_index"),
        "segment_index": payload.get("segment_index"),
        "input_surface": input_surface,
        "token_surfaces": token_surfaces,
        "segments_display": segments_display,
        "cache_key": cache_key,
    }


def extract_token_surfaces(segmentation: dict[str, Any]) -> list[str]:
    pages = segmentation.get("pages") if isinstance(segmentation, dict) else []
    if not pages:
        return []
    segments = pages[0].get("segments") or []
    if not segments:
        return []
    tokens = segments[0].get("tokens") or []
    return [str(token.get("surface") or "") for token in tokens if isinstance(token, dict)]


def segmentation_cache_key(input_surface: str, token_surfaces: list[str]) -> str:
    payload = {"input_surface": input_surface, "token_surfaces": token_surfaces}
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def prompt_for_judgement(
    record: dict[str, Any], *, position: int, total: int, correction: bool = False
) -> tuple[str, str, str, str]:
    prefix = "Correction" if correction else "Record"
    print(f"\n{prefix} {position}/{total}: {record['record_id']}")
    print(f"Input surface: {json.dumps(record['input_surface'], ensure_ascii=False)}")
    print(f"Segments: {json.dumps(record['segments_display'], ensure_ascii=False)}")
    while True:
        raw = input("Judgement [a=accept, r=reject, s=skip, b <id>=back, q=quit, ?=help]: ").strip()
        lowered = raw.lower()
        back_target = parse_back_command(raw)
        if back_target is not None:
            return "back", "", "", back_target
        if lowered in HELP_ALIASES:
            print(
                "accept = segmentation is good enough; reject = boundary error; skip = no judgement; "
                "b <id> = rejudge item number or record id; quit = stop"
            )
            continue
        if lowered in QUIT_ALIASES:
            return "quit", "", "", ""
        if lowered in ACCEPT_ALIASES:
            return "judgement", "accept", prompt_notes(), ""
        if lowered in REJECT_ALIASES:
            return "judgement", "reject", prompt_notes(), ""
        if lowered in SKIP_ALIASES:
            return "judgement", "skip", prompt_notes(), ""
        print("Please enter a, r, s, b <id>, q, or ?.")


def prompt_after_completion() -> tuple[str, str]:
    while True:
        raw = input("All items are judged. Enter b <id> to correct an item, or q to quit: ").strip()
        lowered = raw.lower()
        back_target = parse_back_command(raw)
        if back_target is not None:
            return "back", back_target
        if lowered in QUIT_ALIASES:
            return "quit", ""
        print("Please enter b <id> or q.")


def parse_back_command(raw: str) -> str | None:
    stripped = raw.strip()
    parts = stripped.split(maxsplit=1)
    if not parts or parts[0].lower() != "b":
        return None
    if len(parts) != 2 or not parts[1].strip():
        return ""
    return parts[1].strip()


def prompt_notes() -> str:
    return input("Notes (optional): ").strip()


def write_judgement(
    out: TextIO, record: dict[str, Any], judgement: str, notes: str, *, reused: bool, correction: bool = False
) -> None:
    payload = dict(record)
    payload.update(
        {
            "judgement": judgement,
            "notes": notes,
            "reused_cached_judgement": reused,
            "is_correction": correction,
            "judged_at": utc_now(),
        }
    )
    out.write(json.dumps(payload, ensure_ascii=False) + "\n")


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
