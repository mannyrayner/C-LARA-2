from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from core.ai_api import OpenAIClient
from core.config import DEFAULT_MODEL, OpenAIConfig

PROMPT_KINDS = ("segmentation", "rating")


class Command(BaseCommand):
    help = "Run a chunk segmentation/rating prompt over chunk JSONL records and write prediction JSONL."

    def add_arguments(self, parser):
        parser.add_argument("--input-jsonl", required=True)
        parser.add_argument("--prompt-file", required=True)
        parser.add_argument("--output-jsonl", required=True)
        parser.add_argument("--prompt-kind", choices=PROMPT_KINDS, default="segmentation")
        parser.add_argument("--model", default=DEFAULT_MODEL)
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument("--max-concurrency", type=int, default=4)
        parser.add_argument("--progress-every", type=int, default=25)
        parser.add_argument("--timeout-s", type=float, default=120.0)
        parser.add_argument("--heartbeat-s", type=float, default=20.0)
        parser.add_argument("--overwrite", action="store_true")

    def handle(self, *args, **options):
        input_path = Path(options["input_jsonl"]).resolve()
        prompt_path = Path(options["prompt_file"]).resolve()
        output_path = Path(options["output_jsonl"]).resolve()
        if not input_path.exists():
            raise CommandError(f"input JSONL not found: {input_path}")
        if not prompt_path.exists():
            raise CommandError(f"prompt file not found: {prompt_path}")
        if output_path.exists() and not options["overwrite"]:
            raise CommandError(f"output JSONL already exists: {output_path}; pass --overwrite")
        records = read_jsonl(input_path)
        limit = int(options["limit"] or 0)
        if limit > 0:
            records = records[:limit]
        if not records:
            raise CommandError(f"input JSONL contains no records to process: {input_path}")
        max_concurrency = max(1, int(options["max_concurrency"] or 1))
        progress_every = max(0, int(options["progress_every"] or 0))
        prompt_template = prompt_path.read_text(encoding="utf-8")
        client = OpenAIClient(config=OpenAIConfig(timeout_s=options["timeout_s"], heartbeat_s=options["heartbeat_s"]))
        predictions = asyncio.run(
            run_records(
                records=records,
                prompt_template=prompt_template,
                prompt_kind=str(options["prompt_kind"]),
                model=str(options["model"]),
                client=client,
                max_concurrency=max_concurrency,
                progress_every=progress_every,
                progress_callback=lambda completed, total: self.stdout.write(
                    f"[run_chunk_prompt_on_corpus] completed {completed}/{total}"
                ),
            )
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        write_jsonl(output_path, predictions)
        self.stdout.write("Ran chunk prompt over corpus records")
        self.stdout.write(f"Records: {len(predictions)}")
        self.stdout.write(f"Output: {output_path}")


async def run_records(
    *,
    records: list[dict[str, Any]],
    prompt_template: str,
    prompt_kind: str,
    model: str,
    client: OpenAIClient,
    max_concurrency: int = 4,
    progress_every: int = 25,
    progress_callback=None,
) -> list[dict[str, Any]]:
    semaphore = asyncio.Semaphore(max(1, max_concurrency))
    predictions: list[dict[str, Any] | None] = [None] * len(records)

    async def run_one(idx: int, record: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        prompt = build_prompt(prompt_template=prompt_template, prompt_kind=prompt_kind, record=record)
        async with semaphore:
            response = await client.chat_json(prompt, model=model, temperature=0)
        return idx, normalize_response(record=record, response=response, prompt_kind=prompt_kind, model=model)

    completed = 0
    tasks = [asyncio.create_task(run_one(idx, record)) for idx, record in enumerate(records)]
    for task in asyncio.as_completed(tasks):
        idx, prediction = await task
        predictions[idx] = prediction
        completed += 1
        if progress_callback and progress_every and (completed % progress_every == 0 or completed == len(records)):
            progress_callback(completed, len(records))
    return [prediction for prediction in predictions if prediction is not None]


def build_prompt(*, prompt_template: str, prompt_kind: str, record: dict[str, Any]) -> str:
    schema_hint = (
        '{"parts": ["..."], "notes": "..."}'
        if prompt_kind == "segmentation"
        else '{"judgement": "accept|reject", "notes": "..."}'
    )
    return "\n\n".join(
        [
            prompt_template.strip(),
            "Return only JSON matching this schema:",
            schema_hint,
            "Record:",
            json.dumps(record, ensure_ascii=False, indent=2),
        ]
    )


def normalize_response(*, record: dict[str, Any], response: Any, prompt_kind: str, model: str) -> dict[str, Any]:
    payload = response if isinstance(response, dict) else {}
    base = {
        "record_id": str(record.get("record_id") or ""),
        "language": str(record.get("language") or ""),
        "project_id": record.get("project_id"),
        "project_title": str(record.get("project_title") or ""),
        "split": str(record.get("split") or ""),
        "prompt_kind": prompt_kind,
        "model": model,
        "chunk_surface": str(record.get("chunk_surface") or ""),
        "segment_surface": str(record.get("segment_surface") or ""),
        "raw_response": payload,
    }
    if prompt_kind == "rating":
        judgement = str(payload.get("judgement") or "").strip().lower()
        if judgement not in {"accept", "reject"}:
            judgement = "reject"
        return {
            **base,
            "candidate_parts": normalize_parts(record.get("candidate_parts") or record.get("predicted_parts") or record.get("gold_parts")),
            "evaluator_judgement": judgement,
            "notes": str(payload.get("notes") or ""),
        }
    parts = normalize_parts(payload.get("parts") or payload.get("predicted_parts"))
    return {
        **base,
        "predicted_parts": parts,
        "predicted_segments_display": "|".join(parts),
        "notes": str(payload.get("notes") or ""),
        "surface_preserved": "".join(parts) == str(record.get("chunk_surface") or ""),
    }


def normalize_parts(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str) and value:
        return [part for part in value.split("|") if part != ""]
    return []


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            records.append(payload)
    return records


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as out:
        for record in records:
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
