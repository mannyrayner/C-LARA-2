from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase


class _StubClient:
    def __init__(self, *args, **kwargs):
        pass

    async def chat_json(self, prompt, model=None, temperature=0):
        if "L'amour" in prompt:
            return {"parts": ["L'", "amour"], "notes": "clitic article"}
        return {"parts": ["revient"], "notes": "whole chunk"}


class RunChunkPromptOnCorpusTests(SimpleTestCase):
    @patch("projects.management.commands.run_chunk_prompt_on_corpus.OpenAIClient", _StubClient)
    def test_command_writes_segmentation_predictions(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "gold.jsonl"
            prompt_path = root / "prompt.md"
            output_path = root / "predictions.jsonl"
            records = [
                {
                    "record_id": "fr:1",
                    "split": "development",
                    "language": "fr",
                    "project_id": 1,
                    "project_title": "Fixture",
                    "chunk_surface": "L'amour",
                    "segment_surface": "L'amour revient",
                    "gold_parts": ["L'", "amour"],
                },
                {
                    "record_id": "fr:2",
                    "split": "development",
                    "language": "fr",
                    "project_id": 1,
                    "project_title": "Fixture",
                    "chunk_surface": "revient",
                    "segment_surface": "L'amour revient",
                    "gold_parts": ["revient"],
                },
            ]
            input_path.write_text("".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records), encoding="utf-8")
            prompt_path.write_text("Segment the chunk", encoding="utf-8")

            call_command(
                "run_chunk_prompt_on_corpus",
                input_jsonl=str(input_path),
                prompt_file=str(prompt_path),
                output_jsonl=str(output_path),
                prompt_kind="segmentation",
                model="test-model",
                overwrite=True,
            )

            predictions = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(predictions), 2)
            self.assertEqual(predictions[0]["predicted_parts"], ["L'", "amour"])
            self.assertTrue(predictions[0]["surface_preserved"])
            self.assertEqual(predictions[0]["model"], "test-model")
