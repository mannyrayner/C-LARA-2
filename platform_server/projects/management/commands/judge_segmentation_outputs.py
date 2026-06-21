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

        records = load_output_records(outputs_path)
        if not records:
            raise CommandError(f"No output records found in {outputs_path}")
        cache = load_cache(cache_path)
        judged_record_ids = load_judged_record_ids(judgements_path)
        judgements_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.parent.mkdir(parents=True, exist_ok=True)

        prompted = 0
        appended = 0
        reused = 0
        skipped_existing = 0
        with judgements_path.open("a", encoding="utf-8") as out:
            for position, payload in enumerate(records, start=1):
                record = judgement_record_from_output(payload, run_label=run_label)
                if record["record_id"] in judged_record_ids:
                    skipped_existing += 1
                    continue
                cached = cache.get(record["cache_key"])
                if cached:
                    reused += 1
                    if include_cached:
                        write_judgement(out, record, cached["judgement"], cached.get("notes", ""), reused=True)
                        out.flush()
                        judged_record_ids.add(record["record_id"])
                        appended += 1
                    continue
                if limit and prompted >= limit:
                    break
                prompted += 1
                decision, notes = prompt_for_judgement(record, position=position, total=len(records))
                if decision == "quit":
                    break
                write_judgement(out, record, decision, notes, reused=False)
                out.flush()
                cache[record["cache_key"]] = {
                    "judgement": decision,
                    "notes": notes,
                    "input_surface": record["input_surface"],
                    "segments_display": record["segments_display"],
                    "updated_at": utc_now(),
                }
                write_cache(cache_path, cache)
                judged_record_ids.add(record["record_id"])
                appended += 1

        if appended and not cache_path.exists():
            write_cache(cache_path, cache)
        self.stdout.write("Segmentation judgement pass complete")
        self.stdout.write(f"Outputs: {outputs_path}")
        self.stdout.write(f"Judgements: {judgements_path}")
        self.stdout.write(f"Cache: {cache_path}")
        self.stdout.write(
            f"Records: {len(records)}; prompted: {prompted}; appended: {appended}; "
            f"reused_cached: {reused}; skipped_existing: {skipped_existing}"
        )


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


def prompt_for_judgement(record: dict[str, Any], *, position: int, total: int) -> tuple[str, str]:
    print(f"\nRecord {position}/{total}: {record['record_id']}")
    print(f"Input surface: {json.dumps(record['input_surface'], ensure_ascii=False)}")
    print(f"Segments: {json.dumps(record['segments_display'], ensure_ascii=False)}")
    while True:
        raw = input("Judgement [a=accept, r=reject, s=skip, q=quit, ?=help]: ").strip().lower()
        if raw in HELP_ALIASES:
            print("accept = segmentation is good enough; reject = boundary error; skip = no judgement; quit = stop")
            continue
        if raw in QUIT_ALIASES:
            return "quit", ""
        if raw in ACCEPT_ALIASES:
            return "accept", prompt_notes()
        if raw in REJECT_ALIASES:
            return "reject", prompt_notes()
        if raw in SKIP_ALIASES:
            return "skip", prompt_notes()
        print("Please enter a, r, s, q, or ?.")


def prompt_notes() -> str:
    return input("Notes (optional): ").strip()


def write_judgement(out: TextIO, record: dict[str, Any], judgement: str, notes: str, *, reused: bool) -> None:
    payload = dict(record)
    payload.update(
        {
            "judgement": judgement,
            "notes": notes,
            "reused_cached_judgement": reused,
            "judged_at": utc_now(),
        }
    )
    out.write(json.dumps(payload, ensure_ascii=False) + "\n")


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
