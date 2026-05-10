from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Build a global metadata file for a folder of legacy C-LARA bundle directories."

    def add_arguments(self, parser):
        parser.add_argument("bundle_root", help="Folder containing per-project legacy bundle directories.")
        parser.add_argument(
            "--output",
            default="legacy_bundle_metadata.json",
            help="Output JSON path. Relative paths are resolved inside bundle_root.",
        )

    def handle(self, *args, **options):
        root = Path(options["bundle_root"]).expanduser().resolve()
        if not root.exists() or not root.is_dir():
            raise CommandError(f"Bundle root is not a directory: {root}")

        output = Path(options["output"]).expanduser()
        if not output.is_absolute():
            output = root / output
        output = output.resolve()

        bundles: list[dict[str, Any]] = []
        for child in sorted(root.iterdir(), key=lambda p: p.name):
            if not child.is_dir():
                continue
            metadata_path = child / "metadata.json"
            if not metadata_path.exists():
                continue
            try:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            except Exception as exc:  # noqa: BLE001
                self.stderr.write(f"Skipping {child.name}: could not parse metadata.json ({exc})")
                continue
            if not isinstance(metadata, dict):
                self.stderr.write(f"Skipping {child.name}: metadata.json is not an object")
                continue

            zip_candidates = sorted(child.glob("*.zip"), key=lambda p: p.name)
            zip_path = zip_candidates[0] if zip_candidates else None
            entry = {
                **metadata,
                "directory_name": child.name,
                "relative_path": child.relative_to(root).as_posix(),
                "metadata_relative_path": metadata_path.relative_to(root).as_posix(),
                "zip_relative_path": zip_path.relative_to(root).as_posix() if zip_path else "",
                "import_relative_path": (zip_path or child).relative_to(root).as_posix(),
                "has_zip": bool(zip_path),
            }
            bundles.append(entry)

        payload = {
            "schema_version": 1,
            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "root": str(root),
            "bundle_count": len(bundles),
            "bundles": bundles,
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"Wrote {len(bundles)} bundle metadata entries to {output}"))
