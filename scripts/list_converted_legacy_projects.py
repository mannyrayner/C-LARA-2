#!/usr/bin/env python3
"""List legacy projects whose first-stage conversion produced source.zip."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", required=True, help="Directory containing converted project subfolders")
    parser.add_argument("--output", required=True, help="TSV file to write")
    return parser.parse_args()


def successful_projects(input_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not input_dir.exists():
        return rows
    for project_dir in sorted(path for path in input_dir.iterdir() if path.is_dir()):
        metadata_path = project_dir / "metadata.json"
        source_zip = project_dir / "source.zip"
        if not metadata_path.exists() or not source_zip.exists():
            continue
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        rows.append(
            {
                "id": metadata.get("id", ""),
                "title": metadata.get("title", ""),
                "l2": metadata.get("l2", ""),
                "l1": metadata.get("l1", ""),
            }
        )
    return sorted(rows, key=_project_sort_key)


def _project_sort_key(row: dict[str, Any]) -> tuple[int, str]:
    try:
        return int(row.get("id") or 0), str(row.get("title") or "")
    except (TypeError, ValueError):
        return 0, str(row.get("title") or "")


def write_tsv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=["id", "title", "l2", "l1"], delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    input_dir = Path(args.input_dir).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()
    rows = successful_projects(input_dir)
    write_tsv(output_path, rows)
    print(f"Wrote {len(rows)} successfully converted projects to {output_path}")


if __name__ == "__main__":
    main()
