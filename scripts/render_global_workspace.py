#!/usr/bin/env python3
"""Validate, render, archive, and safely replace global-workspace state."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "docs/global_workspace/current_state.json"
DEFAULT_OUTPUT = ROOT / "docs/global_workspace/current_state.md"
DEFAULT_ARCHIVE = ROOT / "docs/global_workspace/archive"
INPUT_ARCHIVE_NAME = "inputs"
ID_RE = re.compile(r"^[A-Z]+-[0-9]{4}$")
ARCHIVE_RE = re.compile(r"^rev-(\d{4,})-(\d{4}-\d{2}-\d{2})\.(json|md)$")
CONFIDENCE_VALUES = {"low", "medium", "high"}


class WorkspaceValidationError(ValueError):
    """Raised when current-state data violates the version-1 contract."""


def _require(data: dict[str, Any], keys: set[str], context: str) -> None:
    missing = sorted(keys - data.keys())
    if missing:
        raise WorkspaceValidationError(f"{context} missing fields: {', '.join(missing)}")


def _validate_items(data: dict[str, Any], field: str, required: set[str]) -> set[str]:
    items = data.get(field)
    if not isinstance(items, list):
        raise WorkspaceValidationError(f"{field} must be an array")
    ids: set[str] = set()
    for index, item in enumerate(items):
        context = f"{field}[{index}]"
        if not isinstance(item, dict):
            raise WorkspaceValidationError(f"{context} must be an object")
        _require(item, required, context)
        item_id = item["id"]
        if not isinstance(item_id, str) or not ID_RE.fullmatch(item_id):
            raise WorkspaceValidationError(f"{context}.id is invalid: {item_id!r}")
        if item_id in ids:
            raise WorkspaceValidationError(f"duplicate ID in {field}: {item_id}")
        ids.add(item_id)
    return ids


def _require_references(
    items: list[dict[str, Any]], field: str, allowed: set[str], context: str
) -> None:
    for item in items:
        references = item.get(field)
        if not isinstance(references, list) or not references:
            raise WorkspaceValidationError(f"{item['id']}.{field} must be a non-empty array")
        unknown = sorted(set(references) - allowed)
        if unknown:
            raise WorkspaceValidationError(
                f"{item['id']}.{field} has unknown references: {', '.join(unknown)}"
            )


def validate(data: dict[str, Any]) -> None:
    """Validate the version-1 live-workspace contract and its references."""
    _require(
        data,
        {
            "schema_version",
            "workspace_revision",
            "as_of",
            "assessed_commit_sha",
            "approved_proposal_id",
            "approved_run_id",
            "persistent_goal_ids",
            "current_focus_summary",
            "observations",
            "assessments",
            "reported_valence",
            "uncertainties_and_conflicts",
            "requested_human_decisions",
            "proposed_next_actions",
            "predictions",
            "retired_item_ids",
            "approval",
            "changes_from_previous_revision",
        },
        "workspace",
    )
    if data["schema_version"] != 1:
        raise WorkspaceValidationError("only schema_version 1 is supported")
    if not isinstance(data["workspace_revision"], int) or data["workspace_revision"] < 1:
        raise WorkspaceValidationError("workspace_revision must be a positive integer")
    if not re.fullmatch(r"[0-9a-f]{40}", data["assessed_commit_sha"]):
        raise WorkspaceValidationError("assessed_commit_sha must be a full Git SHA")

    goals = data["persistent_goal_ids"]
    if not isinstance(goals, list) or not goals or any(not re.fullmatch(r"GOAL-\d+", x) for x in goals):
        raise WorkspaceValidationError("persistent_goal_ids must contain GOAL-N identifiers")

    observation_ids = _validate_items(
        data,
        "observations",
        {"id", "summary", "observed_at", "confidence", "evidence"},
    )
    assessment_ids = _validate_items(
        data,
        "assessments",
        {"id", "summary", "goal_ids", "observation_ids", "urgency", "risk", "progress", "confidence"},
    )
    uncertainty_ids = _validate_items(
        data, "uncertainties_and_conflicts", {"id", "summary", "assessment_ids"}
    )
    request_ids = _validate_items(
        data, "requested_human_decisions", {"id", "question", "reason", "assessment_ids"}
    )
    action_ids = _validate_items(
        data, "proposed_next_actions", {"id", "summary", "assessment_ids"}
    )
    prediction_ids = _validate_items(
        data,
        "predictions",
        {"id", "outcome", "horizon", "probability", "confidence", "assessment_ids", "resolution_status"},
    )
    all_ids = observation_ids | assessment_ids | uncertainty_ids | request_ids | action_ids | prediction_ids
    expected_count = sum(
        len(ids)
        for ids in (observation_ids, assessment_ids, uncertainty_ids, request_ids, action_ids, prediction_ids)
    )
    if len(all_ids) != expected_count:
        raise WorkspaceValidationError("item IDs must be globally unique")

    for observation in data["observations"]:
        if observation["confidence"] not in CONFIDENCE_VALUES:
            raise WorkspaceValidationError(f"{observation['id']}.confidence is invalid")
        if not isinstance(observation["evidence"], list) or not observation["evidence"]:
            raise WorkspaceValidationError(f"{observation['id']}.evidence must be non-empty")
        for evidence in observation["evidence"]:
            path = Path(evidence)
            if path.is_absolute() or ".." in path.parts or not (ROOT / path).is_file():
                raise WorkspaceValidationError(f"{observation['id']} has invalid evidence path: {evidence}")
            if evidence.startswith("docs/issues/issues/") and path.suffix != ".json":
                raise WorkspaceValidationError(f"issue evidence must cite canonical JSON: {evidence}")

    _require_references(data["assessments"], "goal_ids", set(goals), "assessments")
    _require_references(data["assessments"], "observation_ids", observation_ids, "assessments")
    for assessment in data["assessments"]:
        if assessment["confidence"] not in CONFIDENCE_VALUES:
            raise WorkspaceValidationError(f"{assessment['id']}.confidence is invalid")
    for field in (
        "uncertainties_and_conflicts",
        "requested_human_decisions",
        "proposed_next_actions",
        "predictions",
    ):
        _require_references(data[field], "assessment_ids", assessment_ids, field)
    for prediction in data["predictions"]:
        probability = prediction["probability"]
        if not isinstance(probability, (int, float)) or not 0 <= probability <= 1:
            raise WorkspaceValidationError(f"{prediction['id']}.probability must be between 0 and 1")
        if prediction["confidence"] not in CONFIDENCE_VALUES:
            raise WorkspaceValidationError(f"{prediction['id']}.confidence is invalid")

    if data["reported_valence"] is not None:
        valence = data["reported_valence"]
        if not isinstance(valence, dict):
            raise WorkspaceValidationError("reported_valence must be null or an object")
        _require(valence, {"text", "assessment_ids"}, "reported_valence")
        unknown = sorted(set(valence["assessment_ids"]) - assessment_ids)
        if unknown:
            raise WorkspaceValidationError(f"reported_valence has unknown assessments: {unknown}")

    retired = data["retired_item_ids"]
    if not isinstance(retired, list) or any(not isinstance(item_id, str) for item_id in retired):
        raise WorkspaceValidationError("retired_item_ids must be an array of strings")
    _require(
        data["approval"],
        {"status", "authorized_by", "authorized_at", "authorization_basis", "comments"},
        "approval",
    )
    _require(
        data["changes_from_previous_revision"],
        {"summary", "added_item_ids", "revised_item_ids", "retained_item_ids", "retired_item_ids"},
        "changes_from_previous_revision",
    )
    change_ids = set(data["changes_from_previous_revision"]["added_item_ids"])
    unknown_changes = sorted(change_ids - all_ids)
    if unknown_changes:
        raise WorkspaceValidationError(f"added_item_ids contains unknown IDs: {unknown_changes}")


def _refs(values: list[str]) -> str:
    return ", ".join(f"`{value}`" for value in values)


def render(data: dict[str, Any]) -> str:
    """Render validated workspace data to stable Markdown."""
    approved_run = (
        f"`{data['approved_run_id']}`"
        if data["approved_run_id"]
        else (
            "None (direct initial baseline)"
            if data["workspace_revision"] == 1
            else "None (no recorded run)"
        )
    )
    lines = [
        "# C-LARA-2 current project state",
        "",
        "> This file is generated from `current_state.json`; do not edit it directly.",
        "",
        f"- **Workspace revision:** {data['workspace_revision']}",
        f"- **As of:** {data['as_of']}",
        f"- **Assessed commit:** `{data['assessed_commit_sha']}`",
        f"- **Approved proposal:** `{data['approved_proposal_id']}`",
        f"- **Approved run:** {approved_run}",
        f"- **Persistent goals:** {_refs(data['persistent_goal_ids'])}",
        "",
        "## Current focus",
        "",
        data["current_focus_summary"],
        "",
        "## Factual observations",
        "",
    ]
    for item in data["observations"]:
        evidence = ", ".join(f"[`{path}`](../{path.removeprefix('docs/')})" for path in item["evidence"])
        lines.extend(
            [
                f"### {item['id']}",
                "",
                item["summary"],
                "",
                f"- **Observed:** {item['observed_at']}",
                f"- **Confidence:** {item['confidence']}",
                f"- **Evidence:** {evidence}",
                "",
            ]
        )

    lines.extend(["## Project-valence assessments", ""])
    for item in data["assessments"]:
        lines.extend(
            [
                f"### {item['id']}",
                "",
                item["summary"],
                "",
                f"- **Goals:** {_refs(item['goal_ids'])}",
                f"- **Grounding observations:** {_refs(item['observation_ids'])}",
                f"- **Urgency / risk / progress:** {item['urgency']} / {item['risk']} / {item['progress']}",
                f"- **Confidence:** {item['confidence']}",
                "",
            ]
        )

    lines.extend(["## Reported valence", ""])
    if data["reported_valence"] is None:
        absence_text = (
            "None. This initial baseline deliberately uses neutral factual and assessment language."
            if data["workspace_revision"] == 1
            else "None. This revision uses neutral factual and assessment language."
        )
        lines.extend([absence_text, ""])
    else:
        lines.extend(
            [
                data["reported_valence"]["text"],
                "",
                f"- **Grounding assessments:** {_refs(data['reported_valence']['assessment_ids'])}",
                "",
            ]
        )

    sections = (
        ("Uncertainties and conflicts", "uncertainties_and_conflicts", "summary"),
        ("Questions for human refinement", "requested_human_decisions", "question"),
        ("Proposed next actions", "proposed_next_actions", "summary"),
    )
    for title, field, text_field in sections:
        lines.extend([f"## {title}", ""])
        for item in data[field]:
            lines.append(f"- **{item['id']}:** {item[text_field]}")
            if field == "requested_human_decisions":
                lines.append(f"  - **Why this matters:** {item['reason']}")
            lines.append(f"  - **Assessments:** {_refs(item['assessment_ids'])}")
        lines.append("")

    lines.extend(["## Open predictions", ""])
    for item in data["predictions"]:
        lines.extend(
            [
                f"- **{item['id']}:** {item['outcome']}",
                f"  - **Horizon:** {item['horizon']}",
                f"  - **Probability / confidence / status:** {item['probability']:.0%} / {item['confidence']} / {item['resolution_status']}",
                f"  - **Assessments:** {_refs(item['assessment_ids'])}",
            ]
        )

    approval = data["approval"]
    changes = data["changes_from_previous_revision"]
    lines.extend(
        [
            "",
            "## Approval and revision",
            "",
            f"- **Status:** {approval['status']}",
            f"- **Authorized by / at:** {approval['authorized_by']} / {approval['authorized_at']}",
            f"- **Basis:** {approval['authorization_basis']}",
            f"- **Comments:** {approval['comments']}",
            f"- **Change summary:** {changes['summary']}",
            f"- **Retired live items:** {_refs(data['retired_item_ids']) if data['retired_item_ids'] else 'None'}",
            "",
        ]
    )
    return "\n".join(lines)


def archive_paths(data: dict[str, Any], archive_dir: Path) -> tuple[Path, Path]:
    """Return the deterministic archive paths for a state revision."""
    revision = data["workspace_revision"]
    date = data["as_of"][:10]
    stem = f"rev-{revision:04d}-{date}"
    return archive_dir / f"{stem}.json", archive_dir / f"{stem}.md"


def _write_new_or_match(path: Path, content: bytes) -> bool:
    """Create an immutable snapshot, or verify an identical existing one."""
    if path.exists():
        if path.is_symlink() or not path.is_file():
            raise WorkspaceValidationError(f"archive target is not a regular file: {path}")
        if path.read_bytes() != content:
            raise WorkspaceValidationError(f"conflicting archive snapshot exists: {path}")
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as stream:
            stream.write(content)
    except FileExistsError:
        if path.read_bytes() != content:
            raise WorkspaceValidationError(f"conflicting archive snapshot exists: {path}")
        return False
    return True


def input_archive_dir(archive_dir: Path, revision: int) -> Path:
    """Return the directory containing exact human inputs for a revision."""
    return archive_dir / INPUT_ARCHIVE_NAME / f"rev-{revision:04d}"


def ensure_inputs_archived(
    archive_dir: Path, revision: int, input_paths: list[Path]
) -> tuple[list[Path], list[Path]]:
    """Create immutable, ordered, byte-exact human-input records."""
    if revision < 2:
        raise WorkspaceValidationError("human-input archives apply to revision 2 and later")
    target_dir = input_archive_dir(archive_dir, revision)
    existing = sorted(target_dir.glob("input-*.md")) if target_dir.exists() else []
    if existing and input_paths:
        if len(existing) != len(input_paths):
            raise WorkspaceValidationError(
                f"revision {revision} already has a different number of archived inputs"
            )
        for existing_path, source_path in zip(existing, input_paths):
            if existing_path.read_bytes() != source_path.read_bytes():
                raise WorkspaceValidationError(
                    f"conflicting human input exists for revision {revision}: {existing_path}"
                )
        return existing, []
    if existing:
        return existing, []
    if not input_paths:
        raise WorkspaceValidationError(
            f"revision {revision} requires at least one archived human-input file"
        )
    created: list[Path] = []
    try:
        for index, source_path in enumerate(input_paths, 1):
            content = source_path.read_bytes()
            target = target_dir / f"input-{index:03d}.md"
            if _write_new_or_match(target, content):
                created.append(target)
    except Exception:
        for path in reversed(created):
            path.unlink(missing_ok=True)
        if target_dir.exists() and not any(target_dir.iterdir()):
            target_dir.rmdir()
        raise
    return [target_dir / f"input-{index:03d}.md" for index in range(1, len(input_paths) + 1)], created


def validate_input_archive(archive_dir: Path, state_revisions: set[int]) -> dict[int, list[Path]]:
    """Validate ordered input records and require them for every post-baseline state."""
    root = archive_dir / INPUT_ARCHIVE_NAME
    if not root.is_dir():
        if state_revisions <= {1}:
            return {}
        raise WorkspaceValidationError(f"human-input archive does not exist: {root}")
    inputs: dict[int, list[Path]] = {}
    for directory in sorted(root.iterdir()):
        if directory.name == "README.md" and directory.is_file() and not directory.is_symlink():
            continue
        match = re.fullmatch(r"rev-(\d{4,})", directory.name)
        if not match or directory.is_symlink() or not directory.is_dir():
            raise WorkspaceValidationError(f"invalid human-input archive entry: {directory}")
        revision = int(match.group(1))
        if revision not in state_revisions:
            raise WorkspaceValidationError(
                f"human inputs refer to an unknown archived revision: {revision}"
            )
        files = sorted(directory.iterdir())
        expected = [f"input-{index:03d}.md" for index in range(1, len(files) + 1)]
        if not files or [path.name for path in files] != expected:
            raise WorkspaceValidationError(
                f"human inputs for revision {revision} must be contiguous input-NNN.md files"
            )
        if any(path.is_symlink() or not path.is_file() for path in files):
            raise WorkspaceValidationError(f"invalid human input file for revision {revision}")
        inputs[revision] = files
    missing = sorted((state_revisions - {1}) - inputs.keys())
    if missing:
        raise WorkspaceValidationError(
            f"archived revisions missing human inputs: {', '.join(map(str, missing))}"
        )
    return inputs


def ensure_archived(
    data: dict[str, Any], json_bytes: bytes, markdown: str, archive_dir: Path
) -> tuple[Path, Path, bool]:
    """Ensure an exact JSON snapshot and deterministic Markdown snapshot exist."""
    json_path, markdown_path = archive_paths(data, archive_dir)
    created_json = _write_new_or_match(json_path, json_bytes)
    try:
        created_markdown = _write_new_or_match(markdown_path, markdown.encode("utf-8"))
    except Exception:
        if created_json:
            json_path.unlink(missing_ok=True)
        raise
    return json_path, markdown_path, created_json or created_markdown


def validate_archive(
    archive_dir: Path, *, require_inputs: bool = True
) -> dict[int, tuple[Path, Path, dict[str, Any]]]:
    """Validate archive naming, pairs, revision identity, and deterministic Markdown."""
    revisions: dict[int, tuple[Path, Path, dict[str, Any]]] = {}
    if not archive_dir.is_dir():
        raise WorkspaceValidationError(f"archive directory does not exist: {archive_dir}")
    files = sorted(
        path
        for path in archive_dir.iterdir()
        if path.name not in {".gitkeep", INPUT_ARCHIVE_NAME}
    )
    grouped: dict[str, dict[str, Path]] = {}
    for path in files:
        match = ARCHIVE_RE.fullmatch(path.name)
        if not match or path.is_symlink() or not path.is_file():
            raise WorkspaceValidationError(f"invalid archive entry: {path}")
        stem = path.name.rsplit(".", 1)[0]
        grouped.setdefault(stem, {})[match.group(3)] = path
    for stem, pair in grouped.items():
        if set(pair) != {"json", "md"}:
            raise WorkspaceValidationError(f"archive snapshot is missing its JSON/Markdown pair: {stem}")
        json_path, markdown_path = pair["json"], pair["md"]
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise WorkspaceValidationError(f"invalid archived JSON {json_path}: {exc}") from exc
        validate(data)
        expected_json, expected_markdown = archive_paths(data, archive_dir)
        if json_path != expected_json or markdown_path != expected_markdown:
            raise WorkspaceValidationError(
                f"archive filename does not match embedded revision/as_of: {json_path.name}"
            )
        revision = data["workspace_revision"]
        if revision in revisions:
            raise WorkspaceValidationError(f"duplicate archived workspace revision: {revision}")
        if markdown_path.read_text(encoding="utf-8") != render(data):
            raise WorkspaceValidationError(f"stale archived Markdown: {markdown_path}")
        revisions[revision] = (json_path, markdown_path, data)
    if require_inputs:
        validate_input_archive(archive_dir, set(revisions))
    return revisions


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, path)
    except Exception:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def apply_update(
    candidate_path: Path,
    live_json_path: Path,
    live_markdown_path: Path,
    archive_dir: Path,
    human_input_paths: list[Path],
) -> tuple[Path, Path]:
    """Archive revision N and atomically install a validated revision N+1 candidate."""
    live_bytes = live_json_path.read_bytes()
    live_data = json.loads(live_bytes)
    validate(live_data)
    live_markdown = render(live_data)
    if live_markdown_path.read_text(encoding="utf-8") != live_markdown:
        raise WorkspaceValidationError("live Markdown is stale; refusing to update")
    validate_archive(archive_dir)

    candidate_bytes = candidate_path.read_bytes()
    candidate_data = json.loads(candidate_bytes)
    validate(candidate_data)
    if candidate_data["workspace_revision"] != live_data["workspace_revision"] + 1:
        raise WorkspaceValidationError(
            "candidate workspace_revision must be exactly one greater than the live revision"
        )
    candidate_markdown = render(candidate_data)
    archived_json, archived_markdown, _ = ensure_archived(
        live_data, live_bytes, live_markdown, archive_dir
    )
    _, created_inputs = ensure_inputs_archived(
        archive_dir, candidate_data["workspace_revision"], human_input_paths
    )
    # Archive first, then replace both live files. Individual writes are atomic; if the
    # second write fails in-process, restore the exact validated live pair from revision N.
    try:
        _atomic_write(live_json_path, candidate_bytes)
        _atomic_write(live_markdown_path, candidate_markdown.encode("utf-8"))
    except Exception:
        _atomic_write(live_json_path, live_bytes)
        _atomic_write(live_markdown_path, live_markdown.encode("utf-8"))
        for path in reversed(created_inputs):
            path.unlink(missing_ok=True)
        raise
    installed = json.loads(live_json_path.read_text(encoding="utf-8"))
    validate(installed)
    if live_markdown_path.read_text(encoding="utf-8") != render(installed):
        raise WorkspaceValidationError("installed live Markdown does not match live JSON")
    # A successfully installed state is immediately a live revision, so preserve it now
    # rather than waiting for the next transition.
    ensure_archived(
        installed,
        live_json_path.read_bytes(),
        live_markdown_path.read_text(encoding="utf-8"),
        archive_dir,
    )
    validate_archive(archive_dir)
    return archived_json, archived_markdown


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--archive-dir", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--check", action="store_true", help="fail if the rendered file is not current")
    parser.add_argument(
        "--archive-current",
        action="store_true",
        help="create or verify the immutable snapshot for the live revision",
    )
    parser.add_argument(
        "--human-input",
        type=Path,
        action="append",
        default=[],
        help="exact user-input file that fed the candidate revision; repeat in message order",
    )
    parser.add_argument(
        "--record-inputs-for",
        type=int,
        metavar="REVISION",
        help="retroactively create or verify human-input records for an archived revision",
    )
    parser.add_argument(
        "--update-from",
        type=Path,
        metavar="CANDIDATE_JSON",
        help="archive the live revision and install a validated next-revision JSON",
    )
    args = parser.parse_args()

    if sum(
        (
            args.check,
            args.archive_current,
            args.update_from is not None,
            args.record_inputs_for is not None,
        )
    ) > 1:
        parser.error(
            "--check, --archive-current, --update-from, and --record-inputs-for are mutually exclusive"
        )
    if args.human_input and args.update_from is None and args.record_inputs_for is None:
        parser.error("--human-input requires --update-from or --record-inputs-for")

    try:
        if args.update_from is not None:
            archived_json, archived_markdown = apply_update(
                args.update_from,
                args.input,
                args.output,
                args.archive_dir,
                args.human_input,
            )
            print(f"archived {archived_json} and {archived_markdown}")
            print(f"installed {args.update_from} as {args.input} and regenerated {args.output}")
            return 0
        if args.record_inputs_for is not None:
            revisions = validate_archive(args.archive_dir, require_inputs=False)
            if args.record_inputs_for not in revisions:
                raise WorkspaceValidationError(
                    f"cannot record inputs for unknown revision {args.record_inputs_for}"
                )
            paths, created = ensure_inputs_archived(
                args.archive_dir, args.record_inputs_for, args.human_input
            )
            action = "created" if created else "verified"
            print(f"{action} {len(paths)} human-input record(s) for revision {args.record_inputs_for}")
            return 0
        data = json.loads(args.input.read_text(encoding="utf-8"))
        validate(data)
        rendered = render(data)
        if args.archive_current:
            json_path, markdown_path, created = ensure_archived(
                data, args.input.read_bytes(), rendered, args.archive_dir
            )
            action = "created" if created else "verified"
            print(f"{action} {json_path} and {markdown_path}")
            return 0
    except (OSError, json.JSONDecodeError, WorkspaceValidationError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.check:
        try:
            current = args.output.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        if current != rendered:
            print(f"error: {args.output} is not the current deterministic rendering", file=sys.stderr)
            return 1
        try:
            revisions = validate_archive(args.archive_dir)
        except (OSError, json.JSONDecodeError, WorkspaceValidationError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        archived = revisions.get(data["workspace_revision"])
        if archived and archived[0].read_bytes() != args.input.read_bytes():
            print("error: archive/live JSON disagreement for current revision", file=sys.stderr)
            return 1
        print(
            f"validated {args.input}, verified {args.output}, and checked "
            f"{len(revisions)} archived revision(s)"
        )
        return 0

    args.output.write_text(rendered, encoding="utf-8")
    print(f"validated {args.input} and rendered {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
