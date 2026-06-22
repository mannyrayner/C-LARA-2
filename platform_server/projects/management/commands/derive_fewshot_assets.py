from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from pipeline.fewshot_curation import FewshotCurationSpec, curation_root
from .review_fewshots import _resolve_cli_path


class Command(BaseCommand):
    help = "Derive prompt-facing and evaluator few-shot assets from reviewed curation records."

    def add_arguments(self, parser):
        parser.add_argument("--operation", default="segmentation_phase_2")
        parser.add_argument("--language", required=True)
        parser.add_argument("--mechanism", default="boundary_first")
        parser.add_argument("--target-set", required=True)
        parser.add_argument("--request-id", required=True)
        parser.add_argument("--repo-root", default="")
        parser.add_argument("--curation-root", default="")
        parser.add_argument("--asset-kind", choices=["processing", "evaluator", "both"], default="both")
        parser.add_argument("--processing-output-dir")
        parser.add_argument("--evaluator-output-jsonl")
        parser.add_argument("--manifest-json", required=True)
        parser.add_argument("--max-examples", type=int, default=0)
        parser.add_argument("--allow-unaudited", action="store_true")
        parser.add_argument("--overwrite", action="store_true")

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
        items_path = reviews_dir / f"{spec.request_id}.items.json"
        if not items_path.exists():
            raise CommandError(f"review item summary not found: {items_path}. Run review_fewshots first.")
        items_payload = _read_json(items_path)
        items = items_payload.get("items")
        if not isinstance(items, list):
            raise CommandError(f"review item summary has no items array: {items_path}")
        audit_path = reviews_dir / f"{spec.request_id}.human_audit.jsonl"
        audit_by_example = _load_audit_records(audit_path)
        if not audit_by_example and not options["allow_unaudited"]:
            raise CommandError(
                f"human audit file not found or empty: {audit_path}; pass --allow-unaudited to derive from AI review only"
            )

        accepted = accepted_review_items(
            items,
            audit_by_example=audit_by_example,
            require_audit=not options["allow_unaudited"],
        )
        max_examples = int(options["max_examples"] or 0)
        if max_examples > 0:
            accepted = accepted[:max_examples]
        if not accepted:
            raise CommandError("no accepted review items available for derivation")

        asset_kind = options["asset_kind"]
        write_processing = asset_kind in {"processing", "both"}
        write_evaluator = asset_kind in {"evaluator", "both"}
        if write_processing and not options.get("processing_output_dir"):
            raise CommandError("--processing-output-dir is required when --asset-kind is processing or both")
        if write_evaluator and not options.get("evaluator_output_jsonl"):
            raise CommandError("--evaluator-output-jsonl is required when --asset-kind is evaluator or both")
        processing_dir = _resolve_output_path(options["processing_output_dir"], repo_root) if write_processing else None
        evaluator_jsonl = _resolve_output_path(options["evaluator_output_jsonl"], repo_root) if write_evaluator else None
        manifest_json = _resolve_output_path(options["manifest_json"], repo_root)
        if processing_dir and processing_dir.exists() and not options["overwrite"]:
            raise CommandError(f"processing output directory already exists: {processing_dir}; pass --overwrite")
        if evaluator_jsonl and evaluator_jsonl.exists() and not options["overwrite"]:
            raise CommandError(f"evaluator output already exists: {evaluator_jsonl}; pass --overwrite")
        if manifest_json.exists() and not options["overwrite"]:
            raise CommandError(f"manifest already exists: {manifest_json}; pass --overwrite")

        records = derive_records(accepted, repo_root=repo_root)
        processing_paths: list[Path] = []
        if processing_dir:
            if processing_dir.exists():
                shutil.rmtree(processing_dir)
            processing_dir.mkdir(parents=True, exist_ok=True)
            _ensure_boundary_first_template(processing_dir.parent, repo_root=repo_root, operation=spec.operation)
            processing_paths = write_processing_examples(processing_dir, records)
        if evaluator_jsonl:
            evaluator_jsonl.parent.mkdir(parents=True, exist_ok=True)
            write_evaluator_examples(evaluator_jsonl, records)
        manifest = build_manifest(
            spec=spec,
            root=root,
            items_path=items_path,
            audit_path=audit_path if audit_by_example else None,
            processing_dir=processing_dir,
            evaluator_jsonl=evaluator_jsonl,
            processing_paths=processing_paths,
            records=records,
            require_audit=not options["allow_unaudited"],
        )
        manifest_json.parent.mkdir(parents=True, exist_ok=True)
        manifest_json.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        self.stdout.write("Derived few-shot assets")
        self.stdout.write(f"Accepted examples: {len(records)}")
        if processing_dir:
            self.stdout.write(f"Processing fewshots: {processing_dir}")
        if evaluator_jsonl:
            self.stdout.write(f"Evaluator examples: {evaluator_jsonl}")
        self.stdout.write(f"Manifest: {manifest_json}")


def accepted_review_items(
    items: list[dict[str, Any]], *, audit_by_example: dict[str, dict[str, Any]], require_audit: bool
) -> list[dict[str, Any]]:
    accepted: list[dict[str, Any]] = []
    for item in sorted(items, key=lambda payload: str(payload.get("example_id") or "")):
        decision = str(item.get("decision") or "").lower()
        severity = str(item.get("severity") or "").lower()
        if decision != "accept" or severity not in {"none", "minor"}:
            continue
        audit = audit_by_example.get(str(item.get("example_id") or ""))
        if require_audit:
            if not audit or audit.get("human_judgement") != "correct":
                continue
        accepted.append({**item, "human_audit": audit or {}})
    return accepted


def derive_records(items: list[dict[str, Any]], *, repo_root: Path) -> list[dict[str, Any]]:
    records = []
    for item in items:
        candidate_path = _resolve_record_path(str(item.get("candidate_path") or ""), repo_root=repo_root)
        candidate_record = _read_json(candidate_path)
        candidate = candidate_record.get("candidate") if isinstance(candidate_record.get("candidate"), dict) else {}
        output = candidate.get("output") if isinstance(candidate.get("output"), dict) else {}
        tokens = output.get("tokens") if isinstance(output.get("tokens"), list) else []
        token_surfaces = [str(token.get("surface") or "") for token in tokens if isinstance(token, dict)]
        boundary_marked = "¦".join(token_surfaces) if token_surfaces else str(candidate.get("input") or "")
        records.append(
            {
                "example_id": candidate_record.get("example_id") or item.get("example_id"),
                "input": candidate.get("input"),
                "output": output,
                "boundary_marked": boundary_marked,
                "phenomenon": candidate.get("phenomenon"),
                "rationale": candidate.get("rationale"),
                "candidate_path": str(candidate_path),
                "review_path": str(_resolve_record_path(str(item.get("review_path") or ""), repo_root=repo_root)) if item.get("review_path") else "",
                "review_decision": item.get("decision"),
                "review_severity": item.get("severity"),
                "human_audit": item.get("human_audit") or {},
            }
        )
    return records


def write_processing_examples(processing_dir: Path, records: list[dict[str, Any]]) -> list[Path]:
    paths: list[Path] = []
    for idx, record in enumerate(records, start=1):
        payload = {
            "input": record["input"],
            "output": record["output"],
            "phenomenon": record.get("phenomenon"),
            "rationale": record.get("rationale"),
            "provenance": {
                "example_id": record.get("example_id"),
                "candidate_path": record.get("candidate_path"),
                "review_decision": record.get("review_decision"),
                "review_severity": record.get("review_severity"),
            },
        }
        path = processing_dir / f"example{idx}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        paths.append(path)
    return paths


def write_evaluator_examples(path: Path, records: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as out:
        for record in records:
            payload = {
                "example_id": record.get("example_id"),
                "input": record.get("input"),
                "boundary_marked": record.get("boundary_marked"),
                "boundary_marker": "¦",
                "expected_decision": "accept",
                "expected_severity": "none" if record.get("review_severity") == "none" else record.get("review_severity"),
                "phenomenon": record.get("phenomenon"),
                "rationale": record.get("rationale"),
                "provenance": {
                    "candidate_path": record.get("candidate_path"),
                    "review_path": record.get("review_path"),
                    "human_audit": record.get("human_audit"),
                },
            }
            out.write(json.dumps(payload, ensure_ascii=False) + "\n")


def build_manifest(
    *,
    spec: FewshotCurationSpec,
    root: Path,
    items_path: Path,
    audit_path: Path | None,
    processing_dir: Path | None,
    evaluator_jsonl: Path | None,
    processing_paths: list[Path],
    records: list[dict[str, Any]],
    require_audit: bool,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "operation": spec.operation,
        "language": spec.language,
        "mechanism": spec.mechanism,
        "target_set": spec.target_set,
        "request_id": spec.request_id,
        "curation_root": str(root),
        "items_path": str(items_path),
        "audit_path": str(audit_path) if audit_path else "",
        "require_human_audit": require_audit,
        "accepted_count": len(records),
        "processing_output_dir": str(processing_dir) if processing_dir else "",
        "processing_files": [str(path) for path in processing_paths],
        "evaluator_output_jsonl": str(evaluator_jsonl) if evaluator_jsonl else "",
        "records": [
            {
                "example_id": record.get("example_id"),
                "phenomenon": record.get("phenomenon"),
                "candidate_path": record.get("candidate_path"),
                "review_path": record.get("review_path"),
                "review_decision": record.get("review_decision"),
                "review_severity": record.get("review_severity"),
            }
            for record in records
        ],
    }


def _load_audit_records(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    records = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        example_id = str(payload.get("example_id") or "")
        if example_id:
            records[example_id] = payload
    return records


def _ensure_boundary_first_template(variant_dir: Path, *, repo_root: Path, operation: str) -> None:
    target = variant_dir / "boundary_first_template.txt"
    if target.exists():
        return
    candidates = [
        repo_root / "prompts" / operation / "variants" / "clitic_compound" / "boundary_first_template.txt",
        repo_root / "prompts" / operation / "strategies" / "boundary_first" / "template.txt",
    ]
    for candidate in candidates:
        if candidate.exists():
            variant_dir.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(candidate, target)
            return


def _resolve_output_path(value: str, repo_root: Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = repo_root / path
    return path.resolve()


def _resolve_record_path(value: str, *, repo_root: Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = repo_root / path
    return path.resolve()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
