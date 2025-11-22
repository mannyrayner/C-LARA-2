"""Unit tests for the text generation pipeline step."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
import unittest

from pipeline import text_gen
from pipeline.text_gen import TextGenSpec


class FakeAIClient:
    def __init__(self, response: dict) -> None:
        self.response = response
        self.prompts: list[str] = []

    async def chat_json(self, prompt: str, **_: object) -> dict:
        self.prompts.append(prompt)
        await asyncio.sleep(0)
        return self.response


class TextGenTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.prompts_root = Path(__file__).resolve().parents[1] / "prompts"

    def test_loads_fewshots(self) -> None:
        fewshots = text_gen._load_fewshots("en", prompts_root=self.prompts_root)
        self.assertGreaterEqual(len(fewshots), 2)
        self.assertTrue(all("description" in fs and "output" in fs for fs in fewshots))

    def test_build_prompt_includes_description_and_examples(self) -> None:
        template = "Return JSON"
        description = {"title": "Test", "genre": "short prose"}
        fewshots = [
            {
                "description": {"title": "Example"},
                "output": {"surface": "Once"},
            }
        ]

        prompt = text_gen._build_prompt(template, description=description, fewshots=fewshots)

        self.assertIn(json.dumps(description, indent=2), prompt)
        self.assertIn("Example 1 description:", prompt)
        self.assertIn("Example output:", prompt)

    async def test_generate_text_normalizes_response(self) -> None:
        description = {"title": "Rain", "l1": "fr"}
        client = FakeAIClient({"surface": "It rains.", "annotations": {}})
        spec = TextGenSpec(description=description, language="en", telemetry=None)

        result = await text_gen.generate_text(spec, client=client)

        self.assertEqual("en", result["l2"])
        self.assertEqual("fr", result["l1"])
        self.assertEqual("Rain", result["title"])
        self.assertEqual("It rains.", result["surface"])
        self.assertEqual([], result["pages"])
        self.assertEqual({}, result["annotations"])
        self.assertTrue(client.prompts)


if __name__ == "__main__":
    unittest.main()
