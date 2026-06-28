from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.test import SimpleTestCase


class PreviewChunkPromptTests(SimpleTestCase):
    def test_command_writes_full_api_prompt_for_record(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "gold.jsonl"
            prompt_path = root / "prompt.md"
            output_path = root / "preview.txt"
            input_path.write_text(
                json.dumps(
                    {
                        "record_id": "en:1",
                        "chunk_surface": "opened,",
                        "segment_surface": "eyes shall be opened, and",
                        "gold_parts": ["opened", ","],
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            prompt_path.write_text("Segment one chunk.\n\nExamples:\n- `word,` → `word|,`\n", encoding="utf-8")

            call_command(
                "preview_chunk_prompt",
                input_jsonl=str(input_path),
                prompt_file=str(prompt_path),
                output_text=str(output_path),
                prompt_kind="segmentation",
                overwrite=True,
            )

            preview = output_path.read_text(encoding="utf-8")
            self.assertIn("Segment one chunk.", preview)
            self.assertIn("`word,` → `word|,`", preview)
            self.assertIn("Critical invariant: use only Record.chunk_surface", preview)
            self.assertIn('"chunk_surface": "opened,"', preview)
            self.assertIn('"segment_surface": "eyes shall be opened, and"', preview)
