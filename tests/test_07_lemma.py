"""Tests for the lemma annotation pipeline step."""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
import unittest

from core.ai_api import _ensure_openai_installed
from core.config import OpenAIConfig
from pipeline import lemma
from pipeline.lemma import LemmaSpec
from tests.log_utils import log_test_case


class FakeAIClient:
    def __init__(self, response: dict) -> None:
        self.response = response
        self.prompts: list[str] = []

    async def chat_json(self, prompt: str, **_: object) -> dict:
        self.prompts.append(prompt)
        await asyncio.sleep(0)
        return self.response


class LemmaUnitTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.prompts_root = Path(__file__).resolve().parents[1] / "prompts"
        self.sample_segment = {
            "surface": "She put up with the noise.",
            "tokens": [
                {"surface": "She"},
                {"surface": " "},
                {"surface": "put", "annotations": {"mwe_id": "m1"}},
                {"surface": " "},
                {"surface": "up", "annotations": {"mwe_id": "m1"}},
                {"surface": " "},
                {"surface": "with", "annotations": {"mwe_id": "m1"}},
                {"surface": " "},
                {"surface": "the"},
                {"surface": " "},
                {"surface": "noise"},
                {"surface": "."},
            ],
            "annotations": {
                "mwes": [
                    {"id": "m1", "tokens": ["put", "up", "with"], "label": "phrasal verb"}
                ]
            },
        }
        self.sample_text = {
            "l2": "en",
            "surface": self.sample_segment["surface"],
            "pages": [
                {"surface": self.sample_segment["surface"], "segments": [self.sample_segment]},
            ],
        }

    def test_loads_fewshots(self) -> None:
        fewshots = lemma._load_fewshots("en", prompts_root=self.prompts_root)
        self.assertGreaterEqual(len(fewshots), 2)

        log_test_case(
            "lemma:load_fewshots",
            purpose="loads lemma few-shot examples",
            inputs={"language": "en"},
            output={"examples": len(fewshots)},
            status="pass",
        )

    def test_build_prompt_includes_tokens(self) -> None:
        template = "Lemmatize tokens"
        prompt = lemma._build_prompt(template, segment=self.sample_segment, fewshots=[])
        self.assertIn("Segment JSON", prompt)
        self.assertIn("lemma", prompt.lower())

        log_test_case(
            "lemma:build_prompt",
            purpose="ensures prompt carries tokenized segment JSON and lemma guidance",
            inputs={"surface": self.sample_segment["surface"]},
            output={"prompt_preview": prompt.splitlines()[:4]},
            status="pass",
        )

    async def test_lemmatize_normalizes_response(self) -> None:
        fake_response = {
            "surface": self.sample_segment["surface"],
            "tokens": [
                {"surface": "She", "annotations": {"lemma": "she", "pos": "PRON"}},
                {"surface": " ", "annotations": {}},
                {"surface": "put", "annotations": {"mwe_id": "m1", "lemma": "put up with", "pos": "VERB"}},
                {"surface": " ", "annotations": {}},
                {"surface": "up", "annotations": {"mwe_id": "m1", "lemma": "put up with", "pos": "VERB"}},
                {"surface": " ", "annotations": {}},
                {"surface": "with", "annotations": {"mwe_id": "m1", "lemma": "put up with", "pos": "VERB"}},
                {"surface": " "},
                {"surface": "the", "annotations": {"lemma": "the", "pos": "DET"}},
                {"surface": " "},
                {"surface": "noise", "annotations": {"lemma": "noise", "pos": "NOUN"}},
                {"surface": "."},
            ],
            "annotations": self.sample_segment.get("annotations", {}),
        }
        client = FakeAIClient(fake_response)
        spec = LemmaSpec(text=self.sample_text, language="en")

        result = await lemma.annotate_lemmas(spec, client=client)
        segment = result["pages"][0]["segments"][0]

        lemmas = [t.get("annotations", {}).get("lemma") for t in segment.get("tokens", []) if t.get("annotations")]
        self.assertIn("put up with", lemmas)
        self.assertTrue(client.prompts)

        log_test_case(
            "lemma:normalize_response",
            purpose="applies lemma/POS annotations to tokens without losing MWE data",
            inputs={"surface": self.sample_segment["surface"]},
            output={"lemmas": lemmas},
            status="pass",
        )


class LemmaIntegrationTests(unittest.IsolatedAsyncioTestCase):
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
                                {"surface": "put", "annotations": {"mwe_id": "m1"}},
                                {"surface": " "},
                                {"surface": "up", "annotations": {"mwe_id": "m1"}},
                                {"surface": " "},
                                {"surface": "with", "annotations": {"mwe_id": "m1"}},
                                {"surface": " "},
                                {"surface": "the"},
                                {"surface": " "},
                                {"surface": "noise"},
                                {"surface": "."},
                            ],
                            "annotations": {
                                "mwes": [
                                    {"id": "m1", "tokens": ["put", "up", "with"], "label": "phrasal verb"}
                                ]
                            },
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

    async def test_annotate_lemmas_with_openai_client(self) -> None:
        self._skip_if_no_key_or_incompatible()

        client = lemma.OpenAIClient(config=OpenAIConfig(model=os.getenv("OPENAI_TEST_MODEL", "gpt-5")))
        self.addAsyncCleanup(client.aclose)

        try:
            result = await lemma.annotate_lemmas(LemmaSpec(text=self.sample_text), client=client)
        except ImportError as exc:
            self.skipTest(f"openai SDK import failure during lemma annotate: {exc}")
        except self.openai.NotFoundError as exc:  # type: ignore[attr-defined]
            self.skipTest(f"model unavailable: {exc}")

        log_test_case(
            "lemma:integration",
            purpose="integration test for lemma tagging",
            inputs={"text": self.sample_text, "model": os.getenv("OPENAI_TEST_MODEL", "gpt-5")},
            output={"annotated_text": result},
            status="pass",
            notes="See stdout for annotated output.",
        )


if __name__ == "__main__":
    unittest.main()
