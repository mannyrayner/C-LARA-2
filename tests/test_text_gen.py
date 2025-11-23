"""Unit tests for the text generation pipeline step."""
from __future__ import annotations

import asyncio
import json
import os
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


class TextGenIntegrationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.prompts_root = Path(__file__).resolve().parents[1] / "prompts"

    def _skip_if_no_key_or_incompatible(self) -> None:
        if not os.getenv("OPENAI_API_KEY"):
            self.skipTest("OPENAI_API_KEY not set; skipping integration test")

        try:
            import openai  # type: ignore
        except ImportError:
            self.skipTest("openai package not installed; skipping integration test")

        version = getattr(openai, "__version__", "0.0.0")
        if not _version_at_least(version, "1.0.0"):
            self.skipTest(
                f"openai version {version} is below 1.0.0; skipping integration test"
            )

        try:
            text_gen.OpenAIClient()
        except ImportError as exc:
            self.skipTest(f"openai async client unavailable: {exc}")

    async def test_generate_text_with_openai_client(self) -> None:
        self._skip_if_no_key_or_incompatible()

        description = {
            "title": "Morning Walk",
            "genre": "short prose",
            "length": "40-80 words",
            "style": "warm and descriptive",
        }

        spec = TextGenSpec(description=description, language="en")
        try:
            result = await text_gen.generate_text(spec)
        except ImportError as exc:
            self.skipTest(f"openai SDK import failure during generate_text: {exc}")

        self.assertIn("surface", result)
        self.assertGreater(len(result["surface"].split()), 5)
        # Capture the generated text in the test log for human inspection.
        print("Generated text (prose):", result["surface"])

    async def test_generate_and_verify_with_openai_client(self) -> None:
        self._skip_if_no_key_or_incompatible()

        description = {
            "title": "Evening Rain",
            "genre": "short poem",
            "length": "20-40 words",
            "style": "gentle and reflective",
        }

        spec = TextGenSpec(description=description, language="en")
        client = text_gen.OpenAIClient()
        try:
            generated = await text_gen.generate_text(spec, client=client)
        except ImportError as exc:
            self.skipTest(f"openai SDK import failure during generate_text: {exc}")

        verify_prompt = "\n".join(
            [
                "Evaluate whether the generated text matches the description.",
                "Reply with JSON: {\"is_valid\": true|false, \"reason\": string, \"word_count\": number}.",
                "Description:",
                json.dumps(description, indent=2),
                "Generated text:",
                generated.get("surface", ""),
            ]
        )

        try:
            verification = await client.chat_json(verify_prompt)
        except ImportError as exc:
            self.skipTest(f"openai SDK import failure during verification call: {exc}")

        self.assertIsInstance(verification, dict)
        self.assertIn("is_valid", verification)
        # Log both the generated text and the verification outcome for manual review if needed.
        print("Generated text (poem):", generated.get("surface", ""))
        print("Verification response:", json.dumps(verification, indent=2))


if __name__ == "__main__":
    unittest.main()


def _version_at_least(current: str, minimum: str) -> bool:
    def to_tuple(v: str) -> tuple[int, ...]:
        parts: list[int] = []
        for part in v.split("."):
            try:
                parts.append(int(part))
            except ValueError:
                parts.append(0)
        return tuple(parts)

    return to_tuple(current) >= to_tuple(minimum)
