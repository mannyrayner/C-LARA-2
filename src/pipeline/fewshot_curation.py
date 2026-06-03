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


@dataclass(slots=True)
class FewshotReviewSpec:
    """Specification for AI review of generated few-shot candidates."""

    operation: str
    language: str
    mechanism: str = "boundary_first"
    target_set: str = "experimental"
    request_id: str | None = None
    model: str = "gpt-5"
    template_model: str | None = None
    template_versions: int = 3
    max_concurrency: int = 4
    prompt_version: str = "fewshot-review-v3"
    refresh_template: bool = False


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


def _display_review_focus(target_set: str) -> str:
    cleaned = " ".join(part for part in re.split(r"[_-]+", target_set or "") if part)
    return cleaned or "the requested boundary phenomena"


def _language_specific_unit_guidance(language: str, focus: str) -> str:
    language_key = language.lower()
    if language_key in {"fr", "french", "français", "francais"}:
        return """
French-specific guidance to include in the generated reviewer template:
- Do NOT say that clitics or elided forms should always be kept together with the following or preceding word.
- Productive learner-relevant clitic/elision pieces should often be separated as their own meaningful units, for example C¦'est, l'¦avait, j'¦ai, qu'¦il when this helps expose the smaller meaningful pieces.
- Lexicalized apostrophe words should normally stay together, for example aujourd'hui, quelqu'un, presqu'île, prud'homme.
- Contractions such as au, aux, du, des are conventional written words and should not be mechanically split into à/le or de/le unless a specific annotation policy says otherwise.
- Hyphenated compounds and imperatives with pronouns require judgement: some should remain one written word-like unit, while transparent learner-relevant combinations may deserve internal boundaries.
- Spaces and punctuation may be represented as separate boundary units by the system; this is acceptable and should not distract from judging word-like units unless the boundary choice is linguistically misleading.
""".strip()
    return f"""
Language-specific guidance to include in the generated reviewer template:
- Explain which clitics, contractions, compounds, affixes, punctuation conventions, abbreviations, names, numbers, and technical strings in {language} should be separate meaningful units and which should remain intact.
- Do not state a simplistic rule that all clitics must stay attached or all visible subparts must be split. Give nuanced guidance for {language}.
- Spaces and punctuation may be represented as separate boundary units by the system; this is acceptable unless the boundary choice is linguistically misleading.
Requested focus: {focus}.
""".strip()


def build_review_template_draft_prompt(spec: FewshotReviewSpec, draft_index: int) -> str:
    """Build a prompt asking the AI to draft a language-specific review template."""

    if spec.operation not in SUPPORTED_OPERATIONS:
        raise ValueError(f"Unsupported few-shot review operation: {spec.operation}")
    if spec.template_versions < 1:
        raise ValueError("template_versions must be at least 1")
    if spec.max_concurrency < 1:
        raise ValueError("max_concurrency must be at least 1")

    focus = _display_review_focus(spec.target_set)
    return f"""
Create draft {draft_index} of a language-specific hostile-review prompt template for word/unit boundary examples.

Language: {spec.language}
Requested focus: {focus}

The template will be used after deterministic validation has already checked that removing boundary
markers recreates exactly the original string. Do not make preservation the main issue. The reviewer
only decides whether the boundary markers are linguistically and pedagogically appropriate. The material
between two boundary markers is one proposed word-like or meaningful unit. A boundary marker can be
inserted, deleted, or moved, but the original non-marker characters are assumed to be fixed.

Avoid project-internal terminology. In the template you produce, do not use terms like C-LARA-2,
segmentation_phase_2, boundary_first, JSON-tokenization, or token. Prefer ordinary phrasing such as
"word", "word-like unit", "meaningful unit", "boundary marker", and "marked string".

Ask the reviewer to find the strongest reason the example should not be used as a few-shot example.
For the requested language, include concrete guidance about what should and should not count as a
word-like or meaningful unit. Include clitics, contractions/elisions, apostrophes, compounds, punctuation,
whitespace, named entities, abbreviations, numbers, technical strings, and cases where a default boundary
should be left unchanged.

{_language_specific_unit_guidance(spec.language, focus)}

The final prompt template must include a {{candidate_json}} placeholder. The candidate JSON supplied to
the template will include at least:
- input: original string;
- boundary_marked: the same string with boundary marker ¦ inserted between proposed units;
- boundary_marker: ¦.

Return only JSON in this shape:
{{
  "template_text": "Prompt text with a {{candidate_json}} placeholder and instructions to return JSON",
  "language_specific_risks": ["risk 1", "risk 2"],
  "checklist": ["check 1", "check 2"],
  "severity_definitions": {{
    "fatal": "...",
    "serious": "...",
    "minor": "...",
    "none": "..."
  }}
}}
""".strip()


def build_review_template_reconciliation_prompt(spec: FewshotReviewSpec, drafts: list[dict[str, Any]]) -> str:
    """Build a prompt asking the AI to reconcile candidate review templates."""

    focus = _display_review_focus(spec.target_set)
    return f"""
Reconcile these draft language-specific word/unit boundary review prompt templates into one best template.

Language: {spec.language}
Requested focus: {focus}

The final template must be a hostile-review prompt: it should ask for the strongest reason the
boundary markers should not be used as a few-shot boundary example, classify severity as fatal,
serious, minor, or none, and return structured JSON. It must include a {{candidate_json}} placeholder.

Important: deterministic validation has already checked that removing boundary markers recreates the
original string. The reviewer should focus on whether the markers are in linguistically appropriate
places: the material between two markers is one proposed word-like or meaningful unit. Do not make
exact preservation the main topic.

Avoid project-internal terminology in the final template. Do not use C-LARA-2, segmentation_phase_2,
boundary_first, JSON-tokenization, or token. Use ordinary terms like "word", "word-like unit",
"meaningful unit", "boundary marker", and "marked string".

{_language_specific_unit_guidance(spec.language, focus)}

Drafts:
{json.dumps(drafts, ensure_ascii=False, indent=2)}

Return only JSON in this shape:
{{
  "template_text": "Final prompt text with a {{candidate_json}} placeholder and JSON-output instructions",
  "language_specific_risks": ["risk 1", "risk 2"],
  "checklist": ["check 1", "check 2"],
  "severity_definitions": {{
    "fatal": "...",
    "serious": "...",
    "minor": "...",
    "none": "..."
  }},
  "reconciliation_rationale": "why this merged template is best"
}}
""".strip()


def _boundary_marked_from_candidate(candidate: dict[str, Any], marker: str = "¦") -> str:
    output = candidate.get("output") if isinstance(candidate.get("output"), dict) else {}
    tokens = output.get("tokens") if isinstance(output, dict) else []
    if not isinstance(tokens, list) or not tokens:
        return str(candidate.get("input") or "")
    surfaces = []
    for token in tokens:
        if isinstance(token, dict) and isinstance(token.get("surface"), str):
            surfaces.append(token["surface"])
    return marker.join(surfaces) if surfaces else str(candidate.get("input") or "")


def _review_candidate_payload(record: dict[str, Any]) -> dict[str, Any]:
    candidate = record.get("candidate") if isinstance(record.get("candidate"), dict) else {}
    marker = "¦"
    return {
        "input": candidate.get("input"),
        "boundary_marked": _boundary_marked_from_candidate(candidate, marker=marker),
        "boundary_marker": marker,
        "phenomenon": candidate.get("phenomenon"),
        "rationale": candidate.get("rationale"),
    }


def _review_spec_from_request(request: dict[str, Any], spec: FewshotReviewSpec) -> FewshotCurationSpec:
    return FewshotCurationSpec(
        operation=request["operation"],
        language=request["language"],
        mechanism=request.get("mechanism") or spec.mechanism,
        target_set=request.get("target_set") or spec.target_set,
        count=int(request.get("count") or 0),
        model=request.get("model") or "",
        prompt_version=request.get("prompt_version") or "",
        request_id=request["request_id"],
    )


def _review_template_dir(repo_root: Path, spec: FewshotReviewSpec) -> Path:
    curation_spec = FewshotCurationSpec(
        operation=spec.operation,
        language=spec.language,
        mechanism=spec.mechanism,
        target_set=spec.target_set,
        request_id=spec.request_id,
    )
    return curation_root(repo_root, curation_spec) / "review_templates"


def _curation_root_for_review_spec(repo_root: Path, spec: FewshotReviewSpec) -> Path:
    curation_spec = FewshotCurationSpec(
        operation=spec.operation,
        language=spec.language,
        mechanism=spec.mechanism,
        target_set=spec.target_set,
        request_id=spec.request_id,
    )
    return curation_root(repo_root, curation_spec)


def _missing_request_message(request_path: Path) -> str:
    request_dir = request_path.parent
    available = sorted(path.stem for path in request_dir.glob("*.json") if not path.name.endswith(".prompt.json"))
    if available:
        return f"few-shot curation request not found: {request_path}. Available request IDs: {', '.join(available)}"
    return f"few-shot curation request not found: {request_path}. No curation request files are present in {request_dir}"


def _candidate_review_prompt(template: dict[str, Any], record: dict[str, Any]) -> str:
    candidate_json = json.dumps(_review_candidate_payload(record), ensure_ascii=False, indent=2)
    template_text = str(template.get("template_text") or "")
    if "{candidate_json}" in template_text:
        return template_text.replace("{candidate_json}", candidate_json)
    return f"{template_text}\n\nCandidate JSON:\n{candidate_json}"


async def ensure_review_template(
    spec: FewshotReviewSpec,
    *,
    repo_root: Path,
    client: OpenAIClient | None = None,
    trace: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Load or create a reconciled language-specific candidate-review prompt template."""

    template_dir = _review_template_dir(repo_root, spec)
    final_path = template_dir / "template.json"
    if final_path.exists() and not spec.refresh_template:
        existing_template = json.loads(final_path.read_text(encoding="utf-8"))
        if existing_template.get("prompt_version") == spec.prompt_version:
            if trace:
                trace(f"using existing review template {final_path}")
            return existing_template
        if trace:
            trace(f"refreshing review template because prompt_version changed to {spec.prompt_version}")

    ai_client = client or OpenAIClient()
    model = spec.template_model or spec.model
    template_dir.mkdir(parents=True, exist_ok=True)
    if trace:
        trace(f"creating {spec.template_versions} review-template draft(s) for language={spec.language}")

    async def make_draft(idx: int) -> dict[str, Any]:
        draft_path = template_dir / "drafts" / f"draft{idx}.json"
        if draft_path.exists() and not spec.refresh_template:
            existing_draft = json.loads(draft_path.read_text(encoding="utf-8"))
            if existing_draft.get("prompt_version") == spec.prompt_version:
                if trace:
                    trace(f"using existing review-template draft {idx}")
                return existing_draft
        prompt = build_review_template_draft_prompt(spec, idx)
        if trace:
            trace(f"starting review-template draft {idx}")
        payload = normalize_json_text(await ai_client.chat_json(prompt, model=model))
        if not isinstance(payload, dict):
            raise ValueError(f"review-template draft {idx} response must be a JSON object")
        draft = {**payload, "draft_index": idx, "model": model, "prompt_version": spec.prompt_version, "prompt": prompt}
        _write_json(draft_path, draft)
        if trace:
            trace(f"completed review-template draft {idx}")
        return draft

    drafts = await asyncio.gather(*(make_draft(idx) for idx in range(1, spec.template_versions + 1)))
    if trace:
        trace("reconciling review-template drafts")
    reconciliation_prompt = build_review_template_reconciliation_prompt(spec, drafts)
    final_template = normalize_json_text(await ai_client.chat_json(reconciliation_prompt, model=model))
    if not isinstance(final_template, dict):
        raise ValueError("review-template reconciliation response must be a JSON object")
    if "{candidate_json}" not in str(final_template.get("template_text") or ""):
        raise ValueError("review-template reconciliation must include a {candidate_json} placeholder")
    final_template = {
        **final_template,
        "schema_version": 1,
        "operation": spec.operation,
        "language": spec.language,
        "mechanism": spec.mechanism,
        "target_set": spec.target_set,
        "model": model,
        "prompt_version": spec.prompt_version,
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "draft_count": len(drafts),
    }
    _write_json(template_dir / "reconciliation.prompt.json", {"prompt": reconciliation_prompt})
    _write_json(final_path, final_template)
    if trace:
        trace(f"stored review template {final_path}")
    return final_template


async def review_candidate_batch(
    spec: FewshotReviewSpec,
    *,
    repo_root: Path,
    client: OpenAIClient | None = None,
    trace: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Run AI review over generated candidates using a language-specific template."""

    if spec.request_id is None:
        raise ValueError("request_id is required to review a curation batch")
    if spec.max_concurrency < 1:
        raise ValueError("max_concurrency must be at least 1")
    ai_client = client or OpenAIClient()
    request_root = _curation_root_for_review_spec(repo_root, spec)
    request_path = request_root / "requests" / f"{spec.request_id}.json"
    if not request_path.exists():
        raise FileNotFoundError(_missing_request_message(request_path))
    request = json.loads(request_path.read_text(encoding="utf-8"))
    template = await ensure_review_template(spec, repo_root=repo_root, client=ai_client, trace=trace)
    curation_spec = _review_spec_from_request(request, spec)
    root = curation_root(repo_root, curation_spec)
    candidates_dir = root / "candidates"
    candidate_paths = sorted(candidates_dir.glob(f"{spec.request_id}-EXAMPLE-*.json"))
    if trace:
        trace(f"reviewing {len(candidate_paths)} candidate(s) with max_concurrency={spec.max_concurrency}")

    reviews_dir = root / "reviews"
    semaphore = asyncio.Semaphore(spec.max_concurrency)

    async def review_one(path: Path) -> dict[str, Any]:
        async with semaphore:
            record = json.loads(path.read_text(encoding="utf-8"))
            prompt = _candidate_review_prompt(template, record)
            if trace:
                trace(f"starting review {record['example_id']}")
            payload = normalize_json_text(await ai_client.chat_json(prompt, model=spec.model))
            if not isinstance(payload, dict):
                raise ValueError(f"review response for {record['example_id']} must be a JSON object")
            severity = str(payload.get("severity") or "").lower()
            if severity not in {"fatal", "serious", "minor", "none"}:
                severity = "serious"
                payload = {**payload, "severity_normalization_note": "Invalid or missing severity normalized to serious."}
            review = {
                "schema_version": 1,
                "request_id": spec.request_id,
                "example_id": record["example_id"],
                "operation": spec.operation,
                "language": spec.language,
                "mechanism": spec.mechanism,
                "target_set": spec.target_set,
                "reviewed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "review_model": spec.model,
                "review_prompt_version": spec.prompt_version,
                "template_path": str((_review_template_dir(repo_root, spec) / "template.json").relative_to(repo_root)),
                "severity": severity,
                "review": {**payload, "severity": severity},
            }
            _write_json(reviews_dir / f"{path.stem}.review.json", review)
            if trace:
                trace(f"completed review {record['example_id']}: severity={severity}")
            return review

    reviews = await asyncio.gather(*(review_one(path) for path in candidate_paths))
    severity_counts = {severity: 0 for severity in ["fatal", "serious", "minor", "none"]}
    for review in reviews:
        severity_counts[review["severity"]] += 1
    summary = {
        "schema_version": 1,
        "request_id": spec.request_id,
        "review_count": len(reviews),
        "severity_counts": severity_counts,
        "template_path": str((_review_template_dir(repo_root, spec) / "template.json").relative_to(repo_root)),
    }
    _write_json(root / "reviews" / f"{spec.request_id}.summary.json", summary)
    if trace:
        trace(f"reviewed {len(reviews)} candidates; severity_counts={severity_counts}")
    return {"root": str(root), "summary": summary, "reviews": reviews, "template": template}
