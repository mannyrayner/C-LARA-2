"""Tests for the MWE annotation pipeline step."""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
import unittest

from core.ai_api import _ensure_openai_installed
from core.config import OpenAIConfig
from pipeline import mwe
from pipeline.mwe import MWESpec
from tests.log_utils import log_test_case


class FakeAIClient:
    def __init__(self, response: dict) -> None:
        self.response = response
        self.prompts: list[str] = []

    async def chat_json(self, prompt: str, **_: object) -> dict:
        self.prompts.append(prompt)
        await asyncio.sleep(0)
        return self.response


class MWEUnitTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.prompts_root = Path(__file__).resolve().parents[1] / "prompts"
        self.sample_segment = {
            "surface": "She put up with the noise.",
            "tokens": [
                {"surface": "She"},
                {"surface": " "},
                {"surface": "put"},
                {"surface": " "},
                {"surface": "up"},
                {"surface": " "},
                {"surface": "with"},
                {"surface": " "},
                {"surface": "the"},
                {"surface": " "},
                {"surface": "noise"},
                {"surface": "."},
            ],
            "annotations": {},
        }
        self.sample_text = {
            "l2": "en",
            "surface": self.sample_segment["surface"],
            "pages": [
                {"surface": self.sample_segment["surface"], "segments": [self.sample_segment]},
            ],
        }

    def test_loads_fewshots(self) -> None:
        fewshots = mwe._load_fewshots("en", prompts_root=self.prompts_root)
        self.assertGreaterEqual(len(fewshots), 2)

        log_test_case(
            "mwe:load_fewshots",
            purpose="loads MWE few-shot examples",
            inputs={"language": "en"},
            output={"examples": len(fewshots)},
            status="pass",
        )

    def test_build_prompt_includes_tokens(self) -> None:
        template = "Detect MWEs"
        prompt = mwe._build_prompt(template, segment=self.sample_segment, fewshots=[])
        self.assertIn("Segment JSON", prompt)
        self.assertIn("mwe", prompt.lower())

        log_test_case(
            "mwe:build_prompt",
            purpose="ensures prompt carries tokenized segment JSON and guidance",
            inputs={"surface": self.sample_segment["surface"]},
            output={"prompt_preview": prompt.splitlines()[:4]},
            status="pass",
        )

    async def test_detect_mwes_normalizes_response(self) -> None:
        fake_response = {
            "surface": self.sample_segment["surface"],
            "tokens": [
                {"surface": "She"},
                {"surface": " ", "annotations": {}},
                {"surface": "put", "annotations": {"mwe_id": "m1"}},
                {"surface": " ", "annotations": {}},
                {"surface": "up", "annotations": {"mwe_id": "m1"}},
                {"surface": " ", "annotations": {}},
                {"surface": "with", "annotations": {"mwe_id": "m1"}},
                {"surface": " ", "annotations": {}},
                {"surface": "the"},
                {"surface": " ", "annotations": {}},
                {"surface": "noise"},
                {"surface": "."},
            ],
            "annotations": {
                "mwes": [
                    {"id": "m1", "tokens": ["put", "up", "with"], "label": "phrasal verb"}
                ]
            },
        }
        client = FakeAIClient(fake_response)
        spec = MWESpec(text=self.sample_text, language="en")

        result = await mwe.annotate_mwes(spec, client=client)
        segment = result["pages"][0]["segments"][0]

        mwe_ids = [t.get("annotations", {}).get("mwe_id") for t in segment.get("tokens", [])]
        self.assertIn("m1", mwe_ids)
        self.assertEqual("phrasal verb", segment.get("annotations", {}).get("mwes", [{}])[0].get("label"))
        self.assertTrue(client.prompts)

        log_test_case(
            "mwe:normalize_response",
            purpose="applies MWE annotations to tokens and segment",
            inputs={"surface": self.sample_segment["surface"]},
            output={"mwe_ids": [m for m in mwe_ids if m], "mwes": segment.get("annotations", {}).get("mwes", [])},
            status="pass",
        )


class MWEIntegrationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.sample_text = {
            "l2": "en",
            "surface": "She put up with the noise.",
            "pages": [
                {
                    "surface": "She put up with the noise.",
                    "segments": [
                        {
                            "surface": "She put up with the noise.",
                            "tokens": [
                                {"surface": "She"},
                                {"surface": " "},
                                {"surface": "put"},
                                {"surface": " "},
                                {"surface": "up"},
                                {"surface": " "},
                                {"surface": "with"},
                                {"surface": " "},
                                {"surface": "the"},
                                {"surface": " "},
                                {"surface": "noise"},
                                {"surface": "."},
                            ],
                            "annotations": {},
                        }
                    ],
                }
            ],
        }

    def _skip_if_no_key_or_incompatible(self) -> None:
        if not os.getenv("OPENAI_API_KEY"):
            self.skipTest("OPENAI_API_KEY not set; skipping integration test")

        try:
            self.openai = _ensure_openai_installed()  # type: ignore[assignment]
        except ImportError as exc:
            self.skipTest(str(exc))

        version = getattr(self.openai, "__version__", "0.0.0")
        if version.startswith("0."):
            self.skipTest(f"openai version {version} is below 1.0.0; skipping integration test")

    async def test_annotate_mwes_with_openai_client(self) -> None:
        self._skip_if_no_key_or_incompatible()

        client = mwe.OpenAIClient(config=OpenAIConfig(model=os.getenv("OPENAI_TEST_MODEL", "gpt-5")))
        self.addAsyncCleanup(client.aclose)

        try:
            result = await mwe.annotate_mwes(MWESpec(text=self.sample_text), client=client)
        except ImportError as exc:
            self.skipTest(f"openai SDK import failure during mwe annotate: {exc}")
        except self.openai.NotFoundError as exc:  # type: ignore[attr-defined]
            self.skipTest(f"model unavailable: {exc}")

        mwes = []
        for page in result.get("pages", []):
            for segment in page.get("segments", []):
                mwes.extend(segment.get("annotations", {}).get("mwes", []))

        log_test_case(
            "mwe:integration",
            purpose="integration test for MWE detection",
            inputs={"text": self.sample_text, "model": os.getenv("OPENAI_TEST_MODEL", "gpt-5")},
            output={"mwes_found": len(mwes), "annotated_text": result},
            status="pass",
            notes="See stdout for detailed annotated output.",
        )


if __name__ == "__main__":
    unittest.main()
