from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError


CYCLE_RE = re.compile(r"^cycle_(\d+)$")


class Command(BaseCommand):
    help = "Package chunk prompt-improvement cycle prompts into a deterministic zipfile."

    def add_arguments(self, parser):
        parser.add_argument("--generated-dir", required=True)
        parser.add_argument("--output-zip", required=True)
        parser.add_argument("--languages", default="fr,de,en")
        parser.add_argument("--prompt-kind", default="segmentation")
        parser.add_argument("--source-split", default="development")
        parser.add_argument("--overwrite", action="store_true")

    def handle(self, *args, **options):
        generated_dir = Path(options["generated_dir"]).resolve()
        output_zip = Path(options["output_zip"]).resolve()
        languages = [item.strip() for item in options["languages"].split(",") if item.strip()]
        prompt_kind = str(options["prompt_kind"] or "segmentation")
        source_split = str(options["source_split"] or "development")
        if not generated_dir.exists():
            raise CommandError(f"generated directory not found: {generated_dir}")
        if not generated_dir.is_dir():
            raise CommandError(f"generated path is not a directory: {generated_dir}")
        if output_zip.exists() and not options["overwrite"]:
            raise CommandError(f"output zip already exists: {output_zip}; pass --overwrite")

        prompts = collect_prompts(
            generated_dir,
            languages=languages,
            prompt_kind=prompt_kind,
            source_split=source_split,
        )
        if not prompts:
            raise CommandError(
                f"no prompt.md files found under {generated_dir / 'prompt_improvement'} "
                f"for languages={languages}, prompt_kind={prompt_kind}, source_split={source_split}"
            )

        output_zip.parent.mkdir(parents=True, exist_ok=True)
        manifest = {
            "schema_version": 1,
            "generated_dir": str(generated_dir),
            "languages": languages,
            "prompt_kind": prompt_kind,
            "source_split": source_split,
            "prompt_count": len(prompts),
            "prompts": prompts,
        }
        with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
            for prompt in prompts:
                archive.write(prompt["source_path"], arcname=prompt["archive_path"])
        self.stdout.write("Packaged chunk prompts")
        self.stdout.write(f"Prompts: {len(prompts)}")
        self.stdout.write(f"Zip: {output_zip}")


def collect_prompts(
    generated_dir: Path, *, languages: list[str], prompt_kind: str, source_split: str
) -> list[dict[str, Any]]:
    root = generated_dir / "prompt_improvement"
    if not root.exists():
        return []
    prompts: list[dict[str, Any]] = []
    for language in languages:
        base_dir = root / f"{language}-{prompt_kind}-{source_split}"
        if not base_dir.is_dir():
            continue
        for cycle_dir in base_dir.iterdir():
            match = CYCLE_RE.match(cycle_dir.name)
            if not cycle_dir.is_dir() or not match:
                continue
            prompt_path = cycle_dir / "prompt.md"
            if not prompt_path.exists():
                continue
            cycle_number = int(match.group(1))
            archive_path = f"prompts/{prompt_kind}/{language}/{source_split}/cycle_{cycle_number}/prompt.md"
            prompts.append(
                {
                    "language": language,
                    "prompt_kind": prompt_kind,
                    "source_split": source_split,
                    "cycle_number": cycle_number,
                    "source_path": str(prompt_path),
                    "archive_path": archive_path,
                }
            )
    return sorted(prompts, key=lambda item: (item["language"], item["cycle_number"]))
