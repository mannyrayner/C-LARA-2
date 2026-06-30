from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase

from projects.management.commands.run_chunk_prompt_on_corpus import build_prompt, normalize_parts, normalize_response


class _StubClient:
    def __init__(self, *args, **kwargs):
        pass

    async def chat_json(self, prompt, model=None, temperature=0):
        if "L'amour" in prompt:
            return {"parts": ["L'", "amour"], "notes": "clitic article"}
        return {"parts": ["revient"], "notes": "whole chunk"}


class _InvalidSurfaceClient:
    def __init__(self, *args, **kwargs):
        pass

    async def chat_json(self, prompt, model=None, temperature=0):
        return {
            "parts": ["In", "einer", "kleinen", "Stadt"],
            "notes": "incorrectly segmented sentence context",
        }


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
                max_concurrency=2,
                progress_every=1,
                overwrite=True,
            )

            predictions = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(predictions), 2)
            self.assertEqual(predictions[0]["predicted_parts"], ["L'", "amour"])
            self.assertTrue(predictions[0]["surface_preserved"])
            self.assertEqual(predictions[0]["model"], "test-model")

    def test_build_prompt_emphasizes_chunk_surface_invariant(self):
        prompt = build_prompt(
            prompt_template="Segment compactly",
            prompt_kind="segmentation",
            record={"chunk_surface": "Stadt", "segment_surface": "In einer kleinen Stadt"},
        )

        self.assertIn("use only Record.chunk_surface", prompt)
        self.assertIn("Do not segment Record.segment_surface", prompt)
        self.assertIn("concatenation of JSON parts must exactly equal Record.chunk_surface", prompt)

    def test_normalize_parts_splits_pipe_delimited_item_inside_list(self):
        self.assertEqual(normalize_parts(["cordes|."]), ["cordes", "."])

    def test_normalize_response_repairs_apostrophe_glyph_to_preserve_surface(self):
        prediction = normalize_response(
            record={"record_id": "fr:1", "language": "fr", "chunk_surface": "qu’il"},
            response={"parts": ["qu'|il"]},
            prompt_kind="segmentation",
            model="test-model",
        )

        self.assertEqual(prediction["predicted_parts"], ["qu’", "il"])
        self.assertTrue(prediction["surface_preserved"])

    def test_normalize_response_repairs_quote_and_dash_glyphs_to_preserve_surface(self):
        quote_prediction = normalize_response(
            record={"record_id": "fr:1", "language": "fr", "chunk_surface": "«Bonjour»"},
            response={"parts": ['"|Bonjour|"']},
            prompt_kind="segmentation",
            model="test-model",
        )
        dash_prediction = normalize_response(
            record={"record_id": "fr:2", "language": "fr", "chunk_surface": "au‑dessus"},
            response={"parts": ["au|-|dessus"]},
            prompt_kind="segmentation",
            model="test-model",
        )

        self.assertEqual(quote_prediction["predicted_parts"], ["«", "Bonjour", "»"])
        self.assertTrue(quote_prediction["surface_preserved"])
        self.assertEqual(dash_prediction["predicted_parts"], ["au", "‑", "dessus"])
        self.assertTrue(dash_prediction["surface_preserved"])

    def test_normalize_response_keeps_known_abbreviation_as_one_part(self):
        prediction = normalize_response(
            record={"record_id": "en:1", "language": "en", "chunk_surface": "Mr."},
            response={"parts": ["Mr|."]},
            prompt_kind="segmentation",
            model="test-model",
        )

        self.assertEqual(prediction["predicted_parts"], ["Mr."])
        self.assertTrue(prediction["surface_preserved"])

    @patch("projects.management.commands.run_chunk_prompt_on_corpus.OpenAIClient", _InvalidSurfaceClient)
    def test_command_replaces_non_surface_preserving_segmentation_with_chunk(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "gold.jsonl"
            prompt_path = root / "prompt.md"
            output_path = root / "predictions.jsonl"
            record = {
                "record_id": "de:1",
                "split": "development",
                "language": "de",
                "project_id": 1,
                "project_title": "Fixture",
                "chunk_surface": "Stadt",
                "segment_surface": "In einer kleinen Stadt",
                "gold_parts": ["Stadt"],
            }
            input_path.write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")
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

            prediction = json.loads(output_path.read_text(encoding="utf-8").strip())
            self.assertEqual(prediction["predicted_parts"], ["Stadt"])
            self.assertFalse(prediction["surface_preserved"])
            self.assertTrue(prediction["invalid_response"])
            self.assertEqual(prediction["invalid_response_reason"], "response parts do not concatenate to chunk_surface")
