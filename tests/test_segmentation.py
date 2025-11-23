"""Unit tests for the segmentation phase 1 pipeline step."""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import unittest

from core.config import OpenAIConfig
from pipeline import segmentation
from pipeline.segmentation import SegmentationSpec


class FakeAIClient:
    def __init__(self, response: dict) -> None:
        self.response = response
        self.prompts: list[str] = []

    async def chat_json(self, prompt: str, **_: object) -> dict:
        self.prompts.append(prompt)
        await asyncio.sleep(0)
        return self.response


class SegmentationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.prompts_root = Path(__file__).resolve().parents[1] / "prompts"

    def test_loads_fewshots(self) -> None:
        fewshots = segmentation._load_fewshots("en", prompts_root=self.prompts_root)
        self.assertGreaterEqual(len(fewshots), 2)
        self.assertTrue(all("input" in fs and "output" in fs for fs in fewshots))

    def test_build_prompt_includes_text_and_examples(self) -> None:
        template = "Return JSON"
        text = "Hello world.\nAnother line."
        fewshots = [
            {
                "input": "First line.",
                "output": {"surface": "First line.", "pages": []},
            }
        ]

        prompt = segmentation._build_prompt(template, text=text, fewshots=fewshots)

        self.assertIn("Input text:", prompt)
        self.assertIn(text.strip(), prompt)
        self.assertIn("Example 1 input:", prompt)
        self.assertIn(json.dumps(fewshots[0]["output"], indent=2), prompt)

    async def test_segmentation_normalizes_response(self) -> None:
        client = FakeAIClient({
            "pages": [
                {"surface": "Line one.", "segments": [{"surface": "Line one."}]}],
            "annotations": {},
        })
        spec = SegmentationSpec(text="Line one.")

        result = await segmentation.segmentation_phase_1(spec, client=client)

        self.assertEqual("en", result["l2"])
        self.assertEqual("Line one.", result["surface"])
        self.assertEqual(1, len(result["pages"]))
        self.assertTrue(client.prompts)


class SegmentationIntegrationTests(unittest.IsolatedAsyncioTestCase):
    def _skip_if_no_key_or_incompatible(self) -> None:
        if not os.getenv("OPENAI_API_KEY"):
            self.skipTest("OPENAI_API_KEY not set; skipping integration test")

        try:
            import openai  # type: ignore
        except ImportError:
            self.skipTest("openai package not installed; skipping integration test")

        try:
            segmentation.OpenAIClient()
        except ImportError as exc:
            self.skipTest(f"openai async client unavailable: {exc}")

        self.openai = openai
        self.test_model = os.getenv("OPENAI_TEST_MODEL", "gpt-5")

    async def test_segmentation_with_openai_client(self) -> None:
        self._skip_if_no_key_or_incompatible()

        sample_text = "A boy sat by the river. He skipped stones. A fish leapt in the sunlight."
        spec = SegmentationSpec(text=sample_text, language="en")
        client = segmentation.OpenAIClient(config=OpenAIConfig(model=self.test_model))

        try:
            result = await segmentation.segmentation_phase_1(spec, client=client)
        except self.openai.NotFoundError as exc:  # type: ignore[attr-defined]
            self.skipTest(f"model {self.test_model} unavailable: {exc}")

        self.assertIn("pages", result)
        self.assertGreaterEqual(len(result.get("pages", [])), 1)
        # Log the segmentation for manual inspection if needed.
        print("Segmentation output:", json.dumps(result, indent=2))


if __name__ == "__main__":
    unittest.main()
