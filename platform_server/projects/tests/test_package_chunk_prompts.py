from __future__ import annotations

import json
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.test import SimpleTestCase


class PackageChunkPromptsTests(SimpleTestCase):
    def test_packages_prompt_cycles_and_manifest(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "generated"
            self._write_prompt(root, "de", 2, "German prompt")
            self._write_prompt(root, "en", 1, "English prompt")
            self._write_prompt(root, "fr", 3, "French prompt")
            output_zip = root / "prompt_packages" / "segmentation-development-prompts.zip"

            call_command(
                "package_chunk_prompts",
                generated_dir=str(root),
                output_zip=str(output_zip),
                languages="fr,de,en",
                prompt_kind="segmentation",
                source_split="development",
                overwrite=True,
            )

            with zipfile.ZipFile(output_zip) as archive:
                names = set(archive.namelist())
                self.assertIn("manifest.json", names)
                self.assertIn("prompts/segmentation/de/development/cycle_2/prompt.md", names)
                self.assertIn("prompts/segmentation/en/development/cycle_1/prompt.md", names)
                self.assertIn("prompts/segmentation/fr/development/cycle_3/prompt.md", names)
                manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
                self.assertEqual(manifest["prompt_count"], 3)
                self.assertEqual(
                    [item["language"] for item in manifest["prompts"]],
                    ["de", "en", "fr"],
                )

    def _write_prompt(self, root: Path, language: str, cycle: int, text: str) -> None:
        path = root / "prompt_improvement" / f"{language}-segmentation-development" / f"cycle_{cycle}" / "prompt.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")
