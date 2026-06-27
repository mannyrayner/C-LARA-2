from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from core.ai_api import OpenAIClient
from core.config import DEFAULT_MODEL, OpenAIConfig

PROMPT_KINDS = ("segmentation", "rating")


class Command(BaseCommand):
    help = "Prepare a compact, anti-overfitting prompt-improvement brief from chunk dev performance."

    def add_arguments(self, parser):
        parser.add_argument("--gold-jsonl", required=True)
        parser.add_argument("--predictions-jsonl", required=True)
        parser.add_argument("--language", required=True)
        parser.add_argument("--prompt-kind", choices=PROMPT_KINDS, default="segmentation")
        parser.add_argument("--current-prompt", default="")
        parser.add_argument("--output-dir", required=True)
        parser.add_argument("--max-error-examples", type=int, default=20)
        parser.add_argument("--max-success-examples", type=int, default=8)
        parser.add_argument("--json", dest="json_name", default="prompt_improvement_brief.json")
        parser.add_argument("--markdown", dest="markdown_name", default="prompt_improvement_brief.md")
        parser.add_argument("--generate-revised-prompt", action="store_true")
        parser.add_argument("--revision-model", default=DEFAULT_MODEL)
        parser.add_argument("--timeout-s", type=float, default=120.0)
        parser.add_argument("--heartbeat-s", type=float, default=20.0)
        parser.add_argument("--overwrite", action="store_true")

    def handle(self, *args, **options):
        gold_path = Path(options["gold_jsonl"]).resolve()
        predictions_path = Path(options["predictions_jsonl"]).resolve()
        output_dir = Path(options["output_dir"]).resolve()
        if not gold_path.exists():
            raise CommandError(f"gold JSONL not found: {gold_path}")
        if not predictions_path.exists():
            raise CommandError(f"predictions JSONL not found: {predictions_path}")
        max_errors = int(options["max_error_examples"] or 0)
        max_successes = int(options["max_success_examples"] or 0)
        if max_errors < 0 or max_successes < 0:
            raise CommandError("example limits must be non-negative")

        output_dir.mkdir(parents=True, exist_ok=True)
        json_path = resolve_output(output_dir, str(options["json_name"] or ""))
        markdown_path = resolve_output(output_dir, str(options["markdown_name"] or ""))
        if not options["overwrite"]:
            for path in (json_path, markdown_path):
                if path.exists():
                    raise CommandError(f"output already exists: {path}; pass --overwrite")

        gold_records = latest_by_record_id(read_jsonl(gold_path))
        prediction_records = latest_by_record_id(read_jsonl(predictions_path))
        if not gold_records:
            raise CommandError(f"gold JSONL contains no records: {gold_path}")
        if not prediction_records:
            raise CommandError(f"predictions JSONL contains no records: {predictions_path}")

        comparisons = compare_records(gold_records, prediction_records)
        brief = build_brief(
            language=str(options["language"]),
            prompt_kind=str(options["prompt_kind"]),
            gold_path=gold_path,
            predictions_path=predictions_path,
            current_prompt_path=Path(options["current_prompt"]).resolve() if options["current_prompt"] else None,
            comparisons=comparisons,
            max_error_examples=max_errors,
            max_success_examples=max_successes,
        )
        json_path.write_text(json.dumps(brief, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        markdown_path.write_text(render_markdown(brief), encoding="utf-8")
        if options["generate_revised_prompt"]:
            client = OpenAIClient(config=OpenAIConfig(timeout_s=options["timeout_s"], heartbeat_s=options["heartbeat_s"]))
            revision = generate_revised_prompt(
                brief=brief,
                brief_markdown=markdown_path.read_text(encoding="utf-8"),
                client=client,
                model=str(options["revision_model"]),
            )
            prompt_revision_path = write_revision_files(output_dir, revision)
            brief["prompt_revision_path"] = str(prompt_revision_path)
            brief["revised_prompt_path"] = str(prompt_revision_path)
            brief["prompt_revision_json"] = str(output_dir / "prompt_revision.json")
            json_path.write_text(json.dumps(brief, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.stdout.write("Prepared chunk prompt-improvement brief")
        self.stdout.write(f"Records compared: {brief['summary']['records_compared']}")
        self.stdout.write(f"Errors: {brief['summary']['error_count']}")
        self.stdout.write(f"JSON: {json_path}")
        self.stdout.write(f"Markdown: {markdown_path}")
        if options["generate_revised_prompt"]:
            self.stdout.write(f"Prompt revision: {output_dir / 'prompt_revision.md'}")


def compare_records(gold_records: dict[str, dict[str, Any]], prediction_records: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    comparisons: list[dict[str, Any]] = []
    for record_id, gold in sorted(gold_records.items()):
        prediction = prediction_records.get(record_id)
        if prediction is None:
            comparisons.append({"record_id": record_id, "status": "missing_prediction", "gold": gold})
            continue
        gold_parts = normalize_parts(gold.get("gold_parts") or gold.get("parts") or gold.get("expected_parts"))
        predicted_parts = normalize_prediction_parts(prediction)
        status = (
            "invalid_surface"
            if prediction.get("invalid_response") or prediction.get("surface_preserved") is False
            else "correct" if gold_parts == predicted_parts else classify_error(gold_parts, predicted_parts)
        )
        comparisons.append(
            {
                "record_id": record_id,
                "status": status,
                "language": gold.get("language") or prediction.get("language") or "",
                "chunk_surface": gold.get("chunk_surface") or prediction.get("chunk_surface") or "",
                "segment_surface": gold.get("segment_surface") or prediction.get("segment_surface") or "",
                "gold_parts": gold_parts,
                "predicted_parts": predicted_parts,
                "gold_display": "|".join(gold_parts),
                "predicted_display": "|".join(predicted_parts),
                "project_id": gold.get("project_id") or prediction.get("project_id"),
                "project_title": gold.get("project_title") or prediction.get("project_title") or "",
            }
        )
    return comparisons


def normalize_prediction_parts(record: dict[str, Any]) -> list[str]:
    for key in ("predicted_parts", "candidate_parts", "parts", "gold_parts"):
        if key in record:
            return normalize_parts(record.get(key))
    for key in ("predicted_segments_display", "candidate_segments_display", "segments_display", "gold_segments_display"):
        value = record.get(key)
        if isinstance(value, str) and value:
            return [part for part in value.split("|") if part != ""]
    surface = str(record.get("chunk_surface") or "")
    return [surface] if surface else []


def normalize_parts(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(part) for part in value]
    if isinstance(value, str) and value:
        return [part for part in value.split("|") if part != ""]
    return []


def classify_error(gold_parts: list[str], predicted_parts: list[str]) -> str:
    if len(predicted_parts) < len(gold_parts):
        return "under_split"
    if len(predicted_parts) > len(gold_parts):
        return "over_split"
    return "boundary_mismatch"


def build_brief(
    *,
    language: str,
    prompt_kind: str,
    gold_path: Path,
    predictions_path: Path,
    current_prompt_path: Path | None,
    comparisons: list[dict[str, Any]],
    max_error_examples: int,
    max_success_examples: int,
) -> dict[str, Any]:
    status_counts = Counter(item["status"] for item in comparisons)
    errors = [item for item in comparisons if item["status"] != "correct"]
    successes = [item for item in comparisons if item["status"] == "correct"]
    current_prompt = ""
    if current_prompt_path and current_prompt_path.exists():
        current_prompt = current_prompt_path.read_text(encoding="utf-8")
    return {
        "schema_version": 1,
        "language": language,
        "prompt_kind": prompt_kind,
        "gold_jsonl": str(gold_path),
        "predictions_jsonl": str(predictions_path),
        "current_prompt_path": str(current_prompt_path) if current_prompt_path else "",
        "current_prompt": current_prompt,
        "summary": {
            "records_compared": len(comparisons),
            "error_count": len(errors),
            "success_count": len(successes),
            "accuracy": round(len(successes) / len(comparisons), 4) if comparisons else 0.0,
            "status_counts": dict(status_counts),
        },
        "anti_overfitting_requirements": anti_overfitting_requirements(prompt_kind),
        "selected_error_examples": errors[:max_error_examples],
        "selected_success_examples": successes[:max_success_examples],
        "improvement_instruction": improvement_instruction(prompt_kind),
    }


def anti_overfitting_requirements(prompt_kind: str) -> list[str]:
    base = [
        "Keep the revised prompt short and principle-based; do not encode a catalogue of development-set examples.",
        "Use the smallest number of examples that illustrates distinct general rules.",
        "Avoid mentioning rare project-specific strings unless they instantiate a very common pattern.",
        "Prefer reusable language-specific constraints over memorised chunks.",
        "Make no claims based on validation or test data; use only development-set evidence for revisions.",
    ]
    if prompt_kind == "rating":
        base.append("For rating, judge whether the proposed decomposition is correct; do not silently produce a better decomposition unless asked for notes.")
    else:
        base.append("For segmentation, output only the decomposition of the supplied whitespace-delimited chunk; never join across whitespace.")
    return base


def improvement_instruction(prompt_kind: str) -> str:
    if prompt_kind == "rating":
        return (
            "Revise the chunk-segmentation rating prompt so it identifies the observed error patterns while remaining compact. "
            "Return a prompt, a short rationale, and at most a handful of general examples."
        )
    return (
        "Revise the chunk-segmentation prompt so it fixes the observed error patterns while remaining compact. "
        "Return a prompt, a short rationale, and at most a handful of general examples."
    )


def render_markdown(brief: dict[str, Any]) -> str:
    summary = brief["summary"]
    lines = [
        f"# Chunk {brief['prompt_kind']} prompt-improvement brief ({brief['language']})",
        "",
        "## Inputs",
        "",
        f"- Gold JSONL: `{brief['gold_jsonl']}`",
        f"- Predictions JSONL: `{brief['predictions_jsonl']}`",
        f"- Current prompt: `{brief['current_prompt_path'] or '(not supplied)'}`",
        "",
        "## Summary",
        "",
        f"- Records compared: {summary['records_compared']}",
        f"- Accuracy: {summary['accuracy']}",
        f"- Errors: {summary['error_count']}",
        f"- Status counts: `{summary['status_counts']}`",
        "",
        "## Anti-overfitting requirements",
        "",
    ]
    lines.extend(f"- {item}" for item in brief["anti_overfitting_requirements"])
    lines.extend(["", "## Improvement instruction", "", brief["improvement_instruction"], "", "## Error examples", ""])
    lines.extend(render_examples(brief["selected_error_examples"]))
    lines.extend(["", "## Correct examples", ""])
    lines.extend(render_examples(brief["selected_success_examples"]))
    return "\n".join(lines) + "\n"


def generate_revised_prompt(
    *, brief: dict[str, Any], brief_markdown: str, client: OpenAIClient, model: str
) -> dict[str, Any]:
    import asyncio

    prompt = "\n\n".join(
        [
            "You revise compact C-LARA chunk prompts.",
            "Use the brief below to produce a revised prompt, but avoid overfitting.",
            "Return only JSON with keys: prompt, rationale, examples.",
            "The prompt must be directly usable as a prompt file; do not wrap it in Markdown fences.",
            f"Prompt kind: {brief['prompt_kind']}",
            f"Language: {brief['language']}",
            brief_markdown,
        ]
    )
    response = asyncio.run(client.chat_json(prompt, model=model, temperature=0))
    payload = response if isinstance(response, dict) else {}
    revised_prompt = str(payload.get("prompt") or "").strip()
    if not revised_prompt:
        raise CommandError("revision model did not return a non-empty 'prompt' field")
    examples = payload.get("examples")
    if not isinstance(examples, list):
        examples = []
    return {
        "schema_version": 1,
        "model": model,
        "language": brief["language"],
        "prompt_kind": brief["prompt_kind"],
        "prompt": revised_prompt,
        "rationale": str(payload.get("rationale") or ""),
        "examples": examples,
    }


def write_revision_files(output_dir: Path, revision: dict[str, Any]) -> Path:
    prompt_revision_path = output_dir / "prompt_revision.md"
    prompt_revision_text = str(revision["prompt"]).rstrip() + "\n"
    prompt_revision_path.write_text(prompt_revision_text, encoding="utf-8")
    # Compatibility alias for artifacts produced before cycle-specific prompt revisions.
    (output_dir / "revised_prompt.md").write_text(prompt_revision_text, encoding="utf-8")
    (output_dir / "prompt_revision.json").write_text(
        json.dumps(revision, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return prompt_revision_path


def render_examples(examples: list[dict[str, Any]]) -> list[str]:
    if not examples:
        return ["- (none selected)"]
    lines: list[str] = []
    for item in examples:
        lines.append(
            f"- `{item['record_id']}` ({item['status']}): chunk `{item['chunk_surface']}`; "
            f"gold `{item['gold_display']}`; predicted `{item['predicted_display']}`"
        )
    return lines


def latest_by_record_id(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for record in records:
        record_id = str(record.get("record_id") or "")
        if record_id:
            latest[record_id] = record
    return latest


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            records.append(payload)
    return records


def resolve_output(output_dir: Path, value: str) -> Path:
    if not value:
        raise CommandError("output filename must not be empty")
    path = Path(value)
    if not path.is_absolute():
        path = output_dir / path
    return path.resolve()
