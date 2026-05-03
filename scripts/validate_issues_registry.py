#!/usr/bin/env python3
"""Validate docs/issues registry baseline files."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ISSUES_ROOT = ROOT / "docs" / "issues"
ISSUES_DIR = ISSUES_ROOT / "issues"
ARCHIVE_DIR = ISSUES_ROOT / "index-archive"
INDEX_FILE = ISSUES_ROOT / "index.json"

VALID_STATES = {"reported", "active", "closed"}
VALID_PRIORITIES = {"P0", "P1", "P2", "P3"}
ARCHIVE_RE = re.compile(r"^index-\d{8}-\d{6}Z\.json$")


def fail(msg: str) -> None:
    print(f"ERROR: {msg}")
    raise SystemExit(1)


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        fail(f"Could not parse JSON {path}: {e}")


def validate_issue(path: Path, all_issue_ids: set[str]) -> None:
    data = load_json(path)
    required = {
        "schema_version",
        "issue_id",
        "title",
        "state",
        "priority",
        "created_at",
        "updated_at",
        "origin",
        "notes",
        "deadline",
        "dependencies",
    }
    missing = sorted(required - set(data.keys()))
    if missing:
        fail(f"{path} missing fields: {missing}")

    issue_id = data["issue_id"]
    if issue_id != path.stem:
        fail(f"{path} issue_id '{issue_id}' does not match filename '{path.stem}'")

    if data["state"] not in VALID_STATES:
        fail(f"{path} invalid state: {data['state']}")

    if data["priority"] not in VALID_PRIORITIES:
        fail(f"{path} invalid priority: {data['priority']}")

    deps = data["dependencies"]
    if not isinstance(deps, list):
        fail(f"{path} dependencies must be a list")
    for dep in deps:
        if dep not in all_issue_ids:
            fail(f"{path} dependency references unknown issue: {dep}")


def validate_index(path: Path, all_issue_ids: set[str]) -> None:
    data = load_json(path)
    for field in ["schema_version", "updated_at", "description", "focus_issue_ids"]:
        if field not in data:
            fail(f"{path} missing field: {field}")
    if not isinstance(data["focus_issue_ids"], list):
        fail(f"{path} focus_issue_ids must be a list")
    for issue_id in data["focus_issue_ids"]:
        if issue_id not in all_issue_ids:
            fail(f"{path} references unknown issue in focus_issue_ids: {issue_id}")


def main() -> int:
    if not ISSUES_ROOT.exists():
        fail(f"Missing directory: {ISSUES_ROOT}")

    issue_files = sorted(ISSUES_DIR.glob("ISSUE-*.json"))
    if not issue_files:
        fail("No issue JSON files found in docs/issues/issues")

    all_issue_ids = {p.stem for p in issue_files}
    for issue_file in issue_files:
        validate_issue(issue_file, all_issue_ids)

    validate_index(INDEX_FILE, all_issue_ids)

    for archive_file in sorted(ARCHIVE_DIR.glob("*.json")):
        if not ARCHIVE_RE.match(archive_file.name):
            fail(f"Archive filename does not match convention: {archive_file.name}")
        validate_index(archive_file, all_issue_ids)

    print("Issues registry validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
