"""Unit tests for the segmentation pipeline steps."""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import unittest

from core.ai_api import _ensure_openai_installed
from core.config import OpenAIConfig
from pipeline import segmentation
from pipeline.segmentation import (
    SegmentationPhase2Spec,
    SegmentationPipelineSpec,
    SegmentationSpec,
    segmentation as run_segmentation,
    segmentation_phase_2,
)
from tests.log_utils import log_test_case


class FakeAIClient:
    def __init__(self, response: dict) -> None:
        self.response = response
        self.prompts: list[str] = []

    async def chat_json(self, prompt: str, **_: object) -> dict:
        self.prompts.append(prompt)
        await asyncio.sleep(0)
        return self.response


class FakePerCallAIClient(FakeAIClient):
    def __init__(self, responses: list[dict]) -> None:
        super().__init__({})
        self._responses = responses
        self._idx = 0

    async def chat_json(self, prompt: str, **_: object) -> dict:  # type: ignore[override]
        self.prompts.append(prompt)
        await asyncio.sleep(0)
        resp = self._responses[self._idx]
        self._idx += 1
        return resp


class SegmentationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.prompts_root = Path(__file__).resolve().parents[1] / "prompts"

    def test_loads_fewshots(self) -> None:
        fewshots = segmentation._load_fewshots("en", prompts_root=self.prompts_root)  # type: ignore[attr-defined]
        self.assertGreaterEqual(len(fewshots), 2)
        self.assertTrue(all("input" in fs and "output" in fs for fs in fewshots))

        log_test_case(
            "segmentation:load_fewshots",
            purpose="loads phase 1 few-shot examples",
            inputs={"language": "en"},
            output={"examples": len(fewshots)},
            status="pass",
        )

    def test_build_prompt_includes_text_and_examples(self) -> None:
        template = "Return JSON"
        text = "Hello world.\nAnother line."
        fewshots = [
            {
                "input": "First line.",
                "output": {"surface": "First line.", "pages": []},
            }
        ]

        prompt = segmentation._build_prompt(template, text=text, fewshots=fewshots)  # type: ignore[attr-defined]

        self.assertIn("Input text:", prompt)
        self.assertIn(text.strip(), prompt)
        self.assertIn("Example 1 input:", prompt)
        self.assertIn(json.dumps(fewshots[0]["output"], indent=2), prompt)

        log_test_case(
            "segmentation:build_prompt",
            purpose="assembles phase 1 segmentation prompt with examples",
            inputs={"text": text},
            output={"prompt_preview": prompt.splitlines()[:4]},
            status="pass",
        )

    async def test_segmentation_normalizes_response(self) -> None:
        client = FakeAIClient(
            {
                "pages": [
                    {"surface": "Line one.", "segments": [{"surface": "Line one."}]}
                ],
                "annotations": {},
            }
        )
        spec = SegmentationSpec(text="Line one.")

        result = await segmentation.segmentation_phase_1(spec, client=client)

        self.assertEqual("en", result["l2"])
        self.assertEqual("Line one.", result["surface"])
        self.assertEqual(1, len(result["pages"]))
        self.assertTrue(client.prompts)

        log_test_case(
            "segmentation:normalize_phase1",
            purpose="ensures phase 1 output normalizes text metadata",
            inputs={"text": "Line one."},
            output={"pages": result["pages"]},
            status="pass",
        )

    async def test_segmentation_phase_2_adds_tokens(self) -> None:
        text = {
            "l2": "en",
            "surface": "Line one.",
            "pages": [
                {"surface": "Line one.", "segments": [{"surface": "Line one."}]}
            ],
            "annotations": {},
        }
        client = FakeAIClient(
            {
                "surface": "Line one.",
                "tokens": [
                    {"surface": "Line"},
                    {"surface": " "},
                    {"surface": "one"},
                    {"surface": "."},
                ],
                "annotations": {},
            }
        )
        spec = SegmentationPhase2Spec(text=text, language="en")

        result = await segmentation_phase_2(spec, client=client)

        segment = result["pages"][0]["segments"][0]
        self.assertIn("tokens", segment)
        self.assertEqual(4, len(segment["tokens"]))

        log_test_case(
            "segmentation:phase2_tokens",
            purpose="adds tokens to segments during phase 2",
            inputs={"surface": text["surface"]},
            output={"tokens": [t["surface"] for t in segment["tokens"]]},
            status="pass",
        )

    async def test_segmentation_phase_2_uses_jieba_for_chinese(self) -> None:
        text = {
            "l2": "zh",
            "surface": "我喜欢苹果。",
            "pages": [
                {
                    "surface": "我喜欢苹果。",
                    "segments": [
                        {
                            "surface": "我喜欢苹果。",
                        }
                    ],
                }
            ],
            "annotations": {},
        }

        spec = SegmentationPhase2Spec(text=text, language="zh")

        try:
            result = await segmentation_phase_2(spec)
        except ImportError as exc:
            self.skipTest(str(exc))

        tokens = result["pages"][0]["segments"][0]["tokens"]
        surfaces = [t["surface"] for t in tokens]
        self.assertIn("我", surfaces)
        self.assertTrue(any("苹果" in tok for tok in surfaces))

        log_test_case(
            "segmentation:phase2_jieba",
            purpose="uses jieba tokenization for Mandarin segments",
            inputs={"surface": text["surface"], "language": "zh"},
            output={"tokens": surfaces},
            status="pass",
        )

    async def test_segmentation_full_pipeline(self) -> None:
        phase1_response = {
            "l2": "en",
            "surface": "A B.",
            "pages": [
                {
                    "surface": "A B.",
                    "segments": [
                        {"surface": "A "},
                        {"surface": "B."},
                    ],
                }
            ],
            "annotations": {},
        }
        phase2_responses = [
            {
                "surface": "A ",
                "tokens": [{"surface": "A"}, {"surface": " "}],
                "annotations": {},
            },
            {
                "surface": "B.",
                "tokens": [{"surface": "B"}, {"surface": "."}],
                "annotations": {},
            },
        ]

        client = FakePerCallAIClient([phase1_response, *phase2_responses])
        spec = SegmentationPipelineSpec(text="A B.")

        result = await run_segmentation(spec, client=client)

        segments = result["pages"][0]["segments"]
        self.assertEqual(2, len(segments))
        self.assertEqual("A", segments[0]["tokens"][0]["surface"])

        log_test_case(
            "segmentation:full_pipeline",
            purpose="runs phase 1 then per-segment phase 2 tokenization",
            inputs={"text": "A B."},
            output={"segment_count": len(segments)},
            status="pass",
        )


class SegmentationIntegrationTests(unittest.IsolatedAsyncioTestCase):
    def _skip_if_no_key_or_incompatible(self) -> None:
        if not os.getenv("OPENAI_API_KEY"):
            self.skipTest("OPENAI_API_KEY not set; skipping integration test")

        try:
            self.openai = _ensure_openai_installed()  # type: ignore[assignment]
        except ImportError as exc:
            self.skipTest(str(exc))

        try:
            segmentation.OpenAIClient()
        except ImportError as exc:
            self.skipTest(f"openai async client unavailable: {exc}")

        self.test_model = os.getenv("OPENAI_TEST_MODEL", "gpt-5")

    async def test_segmentation_with_openai_client(self) -> None:
        self._skip_if_no_key_or_incompatible()

        sample_text = "A boy sat by the river. He skipped stones. A fish leapt in the sunlight."
        spec = SegmentationSpec(text=sample_text, language="en")
        client = segmentation.OpenAIClient(config=OpenAIConfig(model=self.test_model))
        self.addAsyncCleanup(client.aclose)

        try:
            result = await segmentation.segmentation_phase_1(spec, client=client)
        except self.openai.NotFoundError as exc:  # type: ignore[attr-defined]
            self.skipTest(f"model {self.test_model} unavailable: {exc}")

        self.assertIn("pages", result)
        self.assertGreaterEqual(len(result.get("pages", [])), 1)
        log_test_case(
            "segmentation:integration_phase1",
            purpose="integration test for phase 1 segmentation",
            inputs={"text": sample_text, "model": self.test_model},
            output={"pages": len(result.get("pages", []))},
            status="pass",
            notes="Full output available in test log.",
        )

    async def test_segmentation_phase_2_with_openai_client(self) -> None:
        self._skip_if_no_key_or_incompatible()

        sample_text = {
            "l2": "en",
            "surface": "The boy's name was Will.",
            "pages": [
                {
                    "surface": "The boy's name was Will.",
                    "segments": [{"surface": "The boy's name was Will."}],
                }
            ],
            "annotations": {},
        }
        spec = SegmentationPhase2Spec(text=sample_text, language="en")
        client = segmentation.OpenAIClient(config=OpenAIConfig(model=self.test_model))
        self.addAsyncCleanup(client.aclose)

        try:
            result = await segmentation_phase_2(spec, client=client)
        except self.openai.NotFoundError as exc:  # type: ignore[attr-defined]
            self.skipTest(f"model {self.test_model} unavailable: {exc}")

        tokens = result.get("pages", [])[0]["segments"][0].get("tokens", [])
        self.assertGreaterEqual(len(tokens), 3)
        log_test_case(
            "segmentation:integration_phase2",
            purpose="integration test for per-segment tokenization",
            inputs={"text": sample_text["surface"], "model": self.test_model},
            output={"token_count": len(tokens)},
            status="pass",
            notes="Full output available in test log.",
        )


if __name__ == "__main__":
    unittest.main()
