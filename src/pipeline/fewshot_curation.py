"""Utilities for generating and storing auditable few-shot examples."""
from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.ai_api import OpenAIClient, normalize_json_text


SUPPORTED_OPERATIONS = {"segmentation_phase_2"}


@dataclass(slots=True)
class FewshotCurationSpec:
    """Specification for an incremental few-shot curation batch."""

    operation: str
    language: str
    mechanism: str = "boundary_first"
    target_set: str = "experimental"
    phenomena: tuple[str, ...] = ()
    count: int = 10
    model: str = "gpt-5"
    prompt_version: str = "fewshot-curation-v1"
    request_id: str | None = None
    notes: str = ""
    batch_size: int | None = None
    max_concurrency: int = 4


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%SZ")


def _display_phenomena(phenomena: tuple[str, ...]) -> str:
    return ", ".join(phenomena) if phenomena else "general high-value edge cases"


def build_candidate_generation_prompt(spec: FewshotCurationSpec) -> str:
    """Build a JSON-only prompt for generating candidate few-shot examples."""

    if spec.operation not in SUPPORTED_OPERATIONS:
        raise ValueError(f"Unsupported few-shot curation operation: {spec.operation}")
    if spec.count < 1:
        raise ValueError("count must be at least 1")
    if spec.batch_size is not None and spec.batch_size < 1:
        raise ValueError("batch_size must be at least 1 when set")
    if spec.max_concurrency < 1:
        raise ValueError("max_concurrency must be at least 1")

    return f"""
Generate candidate few-shot examples for C-LARA-2 linguistic annotation.

Operation: {spec.operation}
Language: {spec.language}
Mechanism/strategy: {spec.mechanism}
Target example set: {spec.target_set}
Requested phenomena: {_display_phenomena(spec.phenomena)}
Number of candidates: {spec.count}

For segmentation_phase_2, each candidate must be a JSON-tokenization example:
- input: the original segment string.
- output.surface: exactly the same string as input.
- output.tokens: an ordered array of token objects, each with a non-empty surface.
- Concatenating token surfaces must reproduce input exactly, including spaces and punctuation.
- annotations: an object, usually empty.

Prefer edge cases that are useful for language-learning annotation, including clitics,
compounds, punctuation, named entities, and examples where default token boundaries
should be left alone or repaired.

Return only JSON in this exact shape:
{{
  "candidates": [
    {{
      "input": "...",
      "phenomenon": "short label",
      "rationale": "why this is a useful few-shot example",
      "output": {{
        "surface": "...",
        "tokens": [{{"surface": "..."}}],
        "annotations": {{}}
      }}
    }}
  ]
}}
""".strip()


def validate_segmentation_phase_2_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    """Return deterministic validation results for a segmentation_phase_2 candidate."""

    errors: list[str] = []
    input_text = candidate.get("input")
    if not isinstance(input_text, str) or not input_text:
        errors.append("input must be a non-empty string")
        input_text = "" if input_text is None else str(input_text)

    output = candidate.get("output")
    if not isinstance(output, dict):
        errors.append("output must be an object")
        output = {}

    surface = output.get("surface")
    if not isinstance(surface, str):
        errors.append("output.surface must be a string")
        surface = "" if surface is None else str(surface)
    if surface != input_text:
        errors.append("output.surface must exactly match input")

    tokens = output.get("tokens")
    token_surfaces: list[str] = []
    if not isinstance(tokens, list) or not tokens:
        errors.append("output.tokens must be a non-empty array")
    else:
        for idx, token in enumerate(tokens):
            if not isinstance(token, dict):
                errors.append(f"token {idx} must be an object")
                continue
            token_surface = token.get("surface")
            if not isinstance(token_surface, str):
                errors.append(f"token {idx}.surface must be a string")
                continue
            if token_surface == "":
                errors.append(f"token {idx}.surface must not be empty")
            token_surfaces.append(token_surface)

    concatenated = "".join(token_surfaces)
    if token_surfaces and concatenated != input_text:
        errors.append("concatenated token surfaces must exactly match input")

    annotations = output.get("annotations", {})
    if annotations is not None and not isinstance(annotations, dict):
        errors.append("output.annotations must be an object if present")

    return {
        "schema_pass": not errors,
        "errors": errors,
        "token_count": len(token_surfaces),
        "input_length": len(input_text),
    }


def validate_candidate(operation: str, candidate: dict[str, Any]) -> dict[str, Any]:
    """Validate a candidate for the requested operation."""

    if operation == "segmentation_phase_2":
        return validate_segmentation_phase_2_candidate(candidate)
    raise ValueError(f"Unsupported few-shot curation operation: {operation}")


async def _generate_candidate_shard(
    spec: FewshotCurationSpec,
    *,
    client: OpenAIClient,
    shard_index: int,
    shard_count: int,
    trace: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Generate one shard of candidate examples."""

    shard_spec = replace(spec, count=shard_count)
    prompt = build_candidate_generation_prompt(shard_spec)
    if trace:
        trace(f"starting generation shard {shard_index} (target {shard_count} candidates)")
    payload = normalize_json_text(await client.chat_json(prompt, model=spec.model))
    if not isinstance(payload, dict):
        raise ValueError(f"few-shot candidate generation shard {shard_index} response must be a JSON object")
    candidates = payload.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError(f"few-shot candidate generation shard {shard_index} response must contain a candidates array")
    if trace:
        trace(f"completed generation shard {shard_index}: received {len(candidates)} candidates")
    return {"shard_index": shard_index, "target_count": shard_count, "prompt": prompt, "candidates": candidates}


def _candidate_shard_counts(spec: FewshotCurationSpec) -> list[int]:
    batch_size = spec.batch_size or spec.count
    counts: list[int] = []
    remaining = spec.count
    while remaining > 0:
        shard_count = min(batch_size, remaining)
        counts.append(shard_count)
        remaining -= shard_count
    return counts


async def generate_candidate_batch(
    spec: FewshotCurationSpec,
    *,
    client: OpenAIClient | None = None,
    trace: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Generate and deterministically validate a batch of candidate examples."""

    if spec.operation not in SUPPORTED_OPERATIONS:
        raise ValueError(f"Unsupported few-shot curation operation: {spec.operation}")
    if spec.count < 1:
        raise ValueError("count must be at least 1")
    if spec.batch_size is not None and spec.batch_size < 1:
        raise ValueError("batch_size must be at least 1 when set")
    if spec.max_concurrency < 1:
        raise ValueError("max_concurrency must be at least 1")

    ai_client = client or OpenAIClient()
    request_id = spec.request_id or _utc_timestamp()
    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    shard_counts = _candidate_shard_counts(spec)
    if trace:
        trace(
            "generating "
            f"{spec.count} candidate examples as {len(shard_counts)} shard(s) "
            f"with max_concurrency={spec.max_concurrency}"
        )

    semaphore = asyncio.Semaphore(spec.max_concurrency)

    async def run_shard(idx: int, shard_count: int) -> dict[str, Any]:
        async with semaphore:
            return await _generate_candidate_shard(
                spec,
                client=ai_client,
                shard_index=idx,
                shard_count=shard_count,
                trace=trace,
            )

    shards = await asyncio.gather(*(run_shard(idx, count) for idx, count in enumerate(shard_counts, start=1)))

    records: list[dict[str, Any]] = []
    next_example_idx = 1
    for shard in shards:
        for raw_candidate in shard["candidates"]:
            candidate = raw_candidate if isinstance(raw_candidate, dict) else {"raw": raw_candidate}
            validation = validate_candidate(spec.operation, candidate)
            status = "schema_validated" if validation["schema_pass"] else "validation_failed"
            records.append(
                {
                    "schema_version": 1,
                    "example_id": f"EXAMPLE-{next_example_idx:04d}",
                    "request_id": request_id,
                    "status": status,
                    "operation": spec.operation,
                    "language": spec.language,
                    "mechanism": spec.mechanism,
                    "target_set": spec.target_set,
                    "phenomena": list(spec.phenomena),
                    "generated_at": generated_at,
                    "generator_model": spec.model,
                    "generator_prompt_version": spec.prompt_version,
                    "shard_index": shard["shard_index"],
                    "candidate": candidate,
                    "validation": validation,
                }
            )
            next_example_idx += 1

    if trace:
        valid_count = sum(1 for record in records if record["validation"]["schema_pass"])
        trace(f"validated {len(records)} candidates; schema-valid={valid_count}; failed={len(records) - valid_count}")

    prompts = [shard["prompt"] for shard in shards]
    return {
        "request": {
            "schema_version": 1,
            "request_id": request_id,
            "operation": spec.operation,
            "language": spec.language,
            "mechanism": spec.mechanism,
            "target_set": spec.target_set,
            "phenomena": list(spec.phenomena),
            "count": spec.count,
            "batch_size": spec.batch_size,
            "max_concurrency": spec.max_concurrency,
            "model": spec.model,
            "prompt_version": spec.prompt_version,
            "requested_at": generated_at,
            "notes": spec.notes,
        },
        "prompt": prompts[0] if prompts else "",
        "prompts": [
            {
                "shard_index": shard["shard_index"],
                "target_count": shard["target_count"],
                "prompt": shard["prompt"],
            }
            for shard in shards
        ],
        "records": records,
    }


def curation_root(repo_root: Path, spec: FewshotCurationSpec) -> Path:
    """Return the storage root for a curation request."""

    return (
        repo_root
        / "docs"
        / "few_shot_curation"
        / spec.operation
        / spec.language
        / spec.mechanism
        / spec.target_set
    )


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _next_prompt_example_index(prompt_dir: Path) -> int:
    highest = 0
    for path in prompt_dir.glob("example*.json"):
        match = re.fullmatch(r"example(\d+)\.json", path.name)
        if match:
            highest = max(highest, int(match.group(1)))
    return highest + 1


def store_candidate_batch(
    batch: dict[str, Any],
    *,
    repo_root: Path,
    accept_valid: bool = False,
    write_prompt_variant: bool = False,
) -> dict[str, Any]:
    """Store generated candidate records and optionally derive prompt few-shot files."""

    request = batch["request"]
    spec = FewshotCurationSpec(
        operation=request["operation"],
        language=request["language"],
        mechanism=request.get("mechanism") or "default",
        target_set=request.get("target_set") or "experimental",
        phenomena=tuple(request.get("phenomena") or ()),
        count=int(request.get("count") or 0),
        model=request.get("model") or "",
        prompt_version=request.get("prompt_version") or "",
        request_id=request["request_id"],
        notes=request.get("notes") or "",
        batch_size=request.get("batch_size"),
        max_concurrency=int(request.get("max_concurrency") or 1),
    )
    root = curation_root(repo_root, spec)
    _write_json(root / "requests" / f"{spec.request_id}.json", request)
    _write_json(
        root / "requests" / f"{spec.request_id}.prompt.json",
        {"prompt": batch.get("prompt") or "", "prompts": batch.get("prompts") or []},
    )

    accepted_records: list[dict[str, Any]] = []
    prompt_files: list[str] = []
    request_id = str(spec.request_id)
    for record in batch["records"]:
        record_filename = f"{request_id}-{record['example_id']}.json"
        _write_json(root / "candidates" / record_filename, record)
        if accept_valid and record.get("validation", {}).get("schema_pass"):
            accepted = {**record, "status": "accepted_experimental"}
            accepted_records.append(accepted)
            _write_json(root / "accepted" / record_filename, accepted)

    if write_prompt_variant:
        prompt_dir = repo_root / "prompts" / spec.operation / "variants" / spec.target_set / "fewshots"
        prompt_dir.mkdir(parents=True, exist_ok=True)
        next_idx = _next_prompt_example_index(prompt_dir)
        for offset, record in enumerate(accepted_records):
            candidate = record.get("candidate") or {}
            prompt_payload = {"input": candidate.get("input"), "output": candidate.get("output")}
            out_path = prompt_dir / f"example{next_idx + offset}.json"
            _write_json(out_path, prompt_payload)
            prompt_files.append(str(out_path.relative_to(repo_root)))

    manifest = {
        "schema_version": 1,
        "request_id": spec.request_id,
        "operation": spec.operation,
        "language": spec.language,
        "mechanism": spec.mechanism,
        "target_set": spec.target_set,
        "candidate_count": len(batch["records"]),
        "batch_size": spec.batch_size,
        "max_concurrency": spec.max_concurrency,
        "accepted_count": len(accepted_records),
        "prompt_files": prompt_files,
        "records": [
            {
                "example_id": record["example_id"],
                "status": "accepted_experimental"
                if any(acc["example_id"] == record["example_id"] for acc in accepted_records)
                else record["status"],
                "schema_pass": record.get("validation", {}).get("schema_pass"),
                "phenomenon": (record.get("candidate") or {}).get("phenomenon"),
            }
            for record in batch["records"]
        ],
    }
    _write_json(root / "manifest.json", manifest)
    return {"root": str(root), "manifest": manifest}
