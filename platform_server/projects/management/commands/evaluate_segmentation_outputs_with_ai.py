from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from core.ai_api import OpenAIClient
from core.config import OpenAIConfig
from pipeline.fewshot_curation import _filesystem_path, _path_exists, _write_text
from .judge_segmentation_outputs import judgement_record_from_output, load_output_records
from .review_fewshots import _resolve_cli_path

ACCEPT = "accept"
REJECT = "reject"
VALID_JUDGEMENTS = {ACCEPT, REJECT}
EVALUATOR_PROMPT_VERSION = "segmentation-boundary-evaluator-v2"


class Command(BaseCommand):
    help = "Evaluate segmentation_phase_2 outputs with an AI judge using derived evaluator exemplars."

    def add_arguments(self, parser):
        parser.add_argument("--outputs-jsonl", required=True)
        parser.add_argument("--evaluator-examples-jsonl", required=True)
        parser.add_argument("--judgements-jsonl", required=True)
        parser.add_argument("--cache-json", required=True)
        parser.add_argument("--run-label", default="")
        parser.add_argument("--variant-label", default="")
        parser.add_argument("--fewshot-count", default="small")
        parser.add_argument("--model", default="gpt-4o")
        parser.add_argument("--max-concurrency", type=int, default=4)
        parser.add_argument("--timeout-s", type=float, default=180.0)
        parser.add_argument("--heartbeat-s", type=float, default=10.0)
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument("--overwrite", action="store_true")

    def handle(self, *args, **options):
        outputs_path = _resolve_cli_path(options["outputs_jsonl"], "")
        examples_path = _resolve_cli_path(options["evaluator_examples_jsonl"], "")
        judgements_path = _resolve_cli_path(options["judgements_jsonl"], "")
        cache_path = _resolve_cli_path(options["cache_json"], "")
        if _path_exists(judgements_path) and not options["overwrite"]:
            raise CommandError(f"AI judgement output already exists: {judgements_path}; pass --overwrite")

        output_payloads = load_output_records(outputs_path)
        if not output_payloads:
            raise CommandError(f"No output records found in {outputs_path}")
        records = [judgement_record_from_output(payload, run_label=options["run_label"]) for payload in output_payloads]
        limit = int(options.get("limit") or 0)
        if limit > 0:
            records = records[:limit]

        examples = select_evaluator_examples(load_evaluator_examples(examples_path), options["fewshot_count"])
        if not examples:
            raise CommandError(f"No evaluator examples selected from {examples_path}")
        variant_label = options["variant_label"] or f"fewshots-{options['fewshot_count']}"
        cache = load_cache(cache_path)
        client = OpenAIClient(config=OpenAIConfig(timeout_s=options["timeout_s"], heartbeat_s=options["heartbeat_s"]))

        def trace(message: str) -> None:
            self.stdout.write(f"[evaluate_segmentation_outputs_with_ai] {message}")
            self.stdout.flush()

        try:
            judgements = asyncio.run(
                evaluate_records(
                    records,
                    examples=examples,
                    client=client,
                    model=options["model"],
                    variant_label=variant_label,
                    cache=cache,
                    max_concurrency=int(options["max_concurrency"] or 1),
                    trace=trace,
                )
            )
        except Exception as exc:  # pragma: no cover - command surfaces API failures through CommandError
            raise CommandError(str(exc)) from exc

        _write_text(judgements_path, "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in judgements))
        _write_text(cache_path, json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        self.stdout.write("AI segmentation evaluation complete")
        self.stdout.write(f"Records: {len(judgements)}")
        self.stdout.write(f"Evaluator examples: {len(examples)}")
        self.stdout.write(f"Judgements: {judgements_path}")
        self.stdout.write(f"Cache: {cache_path}")


async def evaluate_records(
    records: list[dict[str, Any]],
    *,
    examples: list[dict[str, Any]],
    client: OpenAIClient,
    model: str,
    variant_label: str,
    cache: dict[str, dict[str, Any]],
    max_concurrency: int,
    trace: Callable[[str], None] | None = None,
) -> list[dict[str, Any]]:
    semaphore = asyncio.Semaphore(max(1, max_concurrency))

    async def evaluate_one(index: int, record: dict[str, Any]) -> dict[str, Any]:
        cache_key = evaluator_cache_key(record, examples=examples, model=model, variant_label=variant_label)
        cached = cache.get(cache_key)
        if cached:
            return build_ai_judgement_record(record, cached, model=model, variant_label=variant_label, cache_key=cache_key, reused=True)
        prompt = build_evaluator_prompt(record, examples)
        async with semaphore:
            if trace:
                trace(f"evaluating {index}/{len(records)} {record.get('record_id')}")
            payload = await client.chat_json(prompt, model=model, temperature=0)
        normalised = normalise_ai_payload(payload)
        cache[cache_key] = {
            **normalised,
            "input_surface": record.get("input_surface"),
            "segments_display": record.get("segments_display"),
            "example_ids": [example.get("example_id") for example in examples],
            "prompt_version": EVALUATOR_PROMPT_VERSION,
            "updated_at": utc_now(),
        }
        return build_ai_judgement_record(record, normalised, model=model, variant_label=variant_label, cache_key=cache_key, reused=False)

    return await asyncio.gather(*(evaluate_one(index, record) for index, record in enumerate(records, start=1)))


def load_evaluator_examples(path: Path) -> list[dict[str, Any]]:
    if not _path_exists(path):
        raise CommandError(f"Evaluator examples not found: {path}")
    examples: list[dict[str, Any]] = []
    for line_number, line in enumerate(_filesystem_path(path).read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise CommandError(f"Evaluator example must be an object at {path}:{line_number}")
        examples.append(payload)
    return examples


def select_evaluator_examples(examples: list[dict[str, Any]], count: str) -> list[dict[str, Any]]:
    raw = str(count or "").strip().lower()
    if raw == "all":
        return list(examples)
    named_counts = {"small": 8, "medium": 24}
    if raw in named_counts:
        return examples[: named_counts[raw]]
    try:
        numeric = int(raw)
    except ValueError as exc:
        raise CommandError(f"fewshot count must be small, medium, all, or an integer; got {count!r}") from exc
    if numeric < 1:
        raise CommandError("fewshot count must be at least 1")
    return examples[:numeric]


def build_evaluator_prompt(record: dict[str, Any], examples: list[dict[str, Any]]) -> str:
    example_lines = []
    for idx, example in enumerate(examples, start=1):
        example_lines.append(
            {
                "example": idx,
                "input": example.get("input"),
                "correct_boundary_marked": example.get("boundary_marked"),
                "phenomenon": example.get("phenomenon"),
                "rationale": example.get("rationale"),
            }
        )
    payload = {
        "input_surface": record.get("input_surface"),
        "candidate_segments": record.get("segments_display"),
        "boundary_separator": "|",
    }
    built_in_rubric_examples = [
        {
            "input": "avoir",
            "candidate_segments": "avoir",
            "judgement": "accept",
            "reason": "A single ordinary word with no clitic, contraction, punctuation, or compound boundary should stay unsplit.",
        },
        {
            "input": "enfant",
            "candidate_segments": "enfant",
            "judgement": "accept",
            "reason": "Not every word needs an internal boundary; preserving an ordinary word as one segment is correct.",
        },
        {
            "input": "avoir",
            "candidate_segments": "a|voir",
            "judgement": "reject",
            "reason": "This invents an internal split inside an ordinary word.",
        },
        {
            "input": "Il m'appelle.",
            "candidate_segments": "Il| |m'|appelle|.",
            "judgement": "accept",
            "reason": "The clitic/contraction boundary is learner-useful and the surface text is preserved.",
        },
    ]
    return f"""
You are evaluating French segmentation_phase_2 boundary output for C-LARA.

Task: decide whether the candidate segmentation is acceptable for language-learning annotation.
The candidate uses `|` between proposed segment/token surfaces. If there is no `|`, the candidate is proposing one unsplit token.

Critical rubric:
- Ordinary single words such as "avoir", "attraper", "oiseau", "aimer", "enfant", "homme", or "soleil" SHOULD normally remain unsplit. Accept an unsplit ordinary word.
- Do NOT reject a candidate merely because it has no internal split. Missing an internal split is only a problem when there is a real learner-useful boundary such as a clitic/contraction, punctuation boundary, or justified compound boundary.
- Reject invented splits inside ordinary words or names, for example `a|voir`, `saint|eté`, or `algo|rithmique`.
- Accept learner-useful splits around French clitics/contractions when surface text is preserved, for example `m'|appelle` or `d'|une`.
- Reject outputs that drop, duplicate, or reorder surface text.
- Treat spaces and punctuation as visible segment surfaces; they may appear as separate segments.

Built-in calibration examples:
{json.dumps(built_in_rubric_examples, ensure_ascii=False, indent=2)}

Positive evaluator exemplars from the audited evaluator set (known acceptable boundary-marked outputs):
{json.dumps(example_lines, ensure_ascii=False, indent=2)}

Candidate to judge:
{json.dumps(payload, ensure_ascii=False, indent=2)}

Return only JSON in this exact shape:
{{
  "judgement": "accept" | "reject",
  "severity": "none" | "minor" | "major",
  "rationale": "one concise sentence"
}}
""".strip()


def normalise_ai_payload(payload: dict[str, Any]) -> dict[str, Any]:
    judgement = str(payload.get("judgement") or payload.get("decision") or "").strip().lower()
    if judgement not in VALID_JUDGEMENTS:
        judgement = REJECT
    severity = str(payload.get("severity") or "").strip().lower()
    if severity not in {"none", "minor", "major"}:
        severity = "none" if judgement == ACCEPT else "major"
    rationale = str(payload.get("rationale") or payload.get("reason") or "").strip()
    return {"judgement": judgement, "severity": severity, "rationale": rationale}


def build_ai_judgement_record(
    record: dict[str, Any],
    payload: dict[str, Any],
    *,
    model: str,
    variant_label: str,
    cache_key: str,
    reused: bool,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "run_label": record.get("run_label"),
        "record_id": record.get("record_id"),
        "project_id": record.get("project_id"),
        "project_title": record.get("project_title"),
        "split": record.get("split"),
        "page_index": record.get("page_index"),
        "segment_index": record.get("segment_index"),
        "input_surface": record.get("input_surface"),
        "segments_display": record.get("segments_display"),
        "judgement": payload.get("judgement"),
        "severity": payload.get("severity"),
        "notes": payload.get("rationale", ""),
        "evaluator_model": model,
        "evaluator_variant": variant_label,
        "cache_key": cache_key,
        "reused_cached": reused,
        "judged_at": utc_now(),
    }


def evaluator_cache_key(record: dict[str, Any], *, examples: list[dict[str, Any]], model: str, variant_label: str) -> str:
    payload = {
        "model": model,
        "variant_label": variant_label,
        "prompt_version": EVALUATOR_PROMPT_VERSION,
        "example_ids": [example.get("example_id") for example in examples],
        "input_surface": record.get("input_surface"),
        "segments_display": record.get("segments_display"),
    }
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def load_cache(path: Path) -> dict[str, dict[str, Any]]:
    if not _path_exists(path):
        return {}
    payload = json.loads(_filesystem_path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise CommandError(f"Cache must be a JSON object: {path}")
    return payload


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
