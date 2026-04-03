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
        self.assertIn("\"tokens\"", prompt)
        self.assertNotIn("\"translation\"", prompt)

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
        self.assertTrue(any(str(mid).startswith("p0m") for mid in mwe_ids if mid))
        self.assertEqual("phrasal verb", segment.get("annotations", {}).get("mwes", [{}])[0].get("label"))
        self.assertTrue(client.prompts)

        log_test_case(
            "mwe:normalize_response",
            purpose="applies MWE annotations to tokens and segment",
            inputs={"surface": self.sample_segment["surface"]},
            output={"mwe_ids": [m for m in mwe_ids if m], "mwes": segment.get("annotations", {}).get("mwes", [])},
            status="pass",
        )

    async def test_detect_mwes_filters_single_token_mwes(self) -> None:
        fake_response = {
            "surface": self.sample_segment["surface"],
            "tokens": [
                {"surface": "She"},
                {"surface": " ", "annotations": {}},
                {"surface": "put", "annotations": {"mwe_id": "m1"}},
                {"surface": " ", "annotations": {}},
                {"surface": "up", "annotations": {"mwe_id": "m2"}},
                {"surface": " ", "annotations": {}},
                {"surface": "with", "annotations": {"mwe_id": "m1"}},
                {"surface": "."},
            ],
            "annotations": {
                "mwes": [
                    {"id": "m1", "tokens": ["put", "with"], "label": "phrasal"},
                    {"id": "m2", "tokens": ["up"], "label": "bad-single"},
                ]
            },
        }
        client = FakeAIClient(fake_response)
        spec = MWESpec(text=self.sample_text, language="en")

        result = await mwe.annotate_mwes(spec, client=client)
        segment = result["pages"][0]["segments"][0]
        mwes = segment.get("annotations", {}).get("mwes", [])
        self.assertEqual(1, len(mwes))
        self.assertTrue(str(mwes[0]["id"]).startswith("p0m"))
        token_ids = [t.get("annotations", {}).get("mwe_id") for t in segment.get("tokens", [])]
        self.assertFalse(any(str(mid).endswith("_m2") for mid in token_ids if mid))

    async def test_detect_mwes_ids_are_unique_within_page(self) -> None:
        text = {
            "l2": "de",
            "surface": "x",
            "pages": [
                {
                    "surface": "x",
                    "segments": [
                        {"surface": "auf Deutsch", "tokens": [{"surface": "auf"}, {"surface": " "}, {"surface": "Deutsch"}], "annotations": {}},
                        {"surface": "aber auch", "tokens": [{"surface": "aber"}, {"surface": " "}, {"surface": "auch"}], "annotations": {}},
                    ],
                }
            ],
        }
        responses = [
            {
                "surface": "auf Deutsch",
                "tokens": [
                    {"surface": "auf", "annotations": {"mwe_id": "m1"}},
                    {"surface": " ", "annotations": {}},
                    {"surface": "Deutsch", "annotations": {"mwe_id": "m1"}},
                ],
                "annotations": {"mwes": [{"id": "m1", "tokens": ["auf", "Deutsch"], "label": "pp"}]},
            },
            {
                "surface": "aber auch",
                "tokens": [
                    {"surface": "aber", "annotations": {"mwe_id": "m1"}},
                    {"surface": " ", "annotations": {}},
                    {"surface": "auch", "annotations": {"mwe_id": "m1"}},
                ],
                "annotations": {"mwes": [{"id": "m1", "tokens": ["aber", "auch"], "label": "conj"}]},
            },
        ]
        client = FakePerCallAIClient(responses)
        result = await mwe.annotate_mwes(MWESpec(text=text, language="de"), client=client)
        seg0, seg1 = result["pages"][0]["segments"]
        id0 = seg0["annotations"]["mwes"][0]["id"]
        id1 = seg1["annotations"]["mwes"][0]["id"]
        self.assertNotEqual(id0, id1)

    async def test_detect_mwes_preserves_original_surface(self) -> None:
        fake_response = {
            "surface": "There is a clever panda, his name is Xiaobai.",
            "tokens": [{"surface": "有"}, {"surface": "一只"}],
            "annotations": {},
        }
        original_surface = "有一只聪明的熊猫，他叫小白。"
        sample_text = {
            "l2": "zh",
            "l1": "en",
            "surface": original_surface,
            "pages": [
                {
                    "surface": original_surface,
                    "segments": [
                        {
                            "surface": original_surface,
                            "tokens": [{"surface": "有"}, {"surface": "一只"}],
                            "annotations": {"translation": "There is a clever panda, his name is Xiaobai."},
                        }
                    ],
                }
            ],
        }
        client = FakeAIClient(fake_response)
        result = await mwe.annotate_mwes(MWESpec(text=sample_text, language="zh"), client=client)
        segment = result["pages"][0]["segments"][0]
        self.assertEqual(original_surface, segment["surface"])

    async def test_detect_mwes_restores_token_surfaces_and_mwe_tokens(self) -> None:
        sample_text = {
            "l2": "hi",
            "surface": "अंकल और आंटी",
            "pages": [
                {
                    "surface": "अंकल और आंटी",
                    "segments": [
                        {
                            "surface": "अंकल और आंटी",
                            "tokens": [
                                {"surface": "अंकल"},
                                {"surface": " "},
                                {"surface": "और", "annotations": {"mwe_id": "m1"}},
                                {"surface": " "},
                                {"surface": "आंटी", "annotations": {"mwe_id": "m1"}},
                            ],
                            "annotations": {},
                        }
                    ],
                }
            ],
        }
        fake_response = {
            "tokens": [
                {"surface": "\u0005\u00012"},
                {"surface": " "},
                {"surface": "\u00029\u00028", "annotations": {"mwe_id": "m1"}},
                {"surface": " "},
                {"surface": "\u0003", "annotations": {"mwe_id": "m1"}},
            ],
            "annotations": {"mwes": [{"id": "m1", "tokens": ["\u00029\u00028", "\u0003"], "label": "fixed expression"}]},
        }
        result = await mwe.annotate_mwes(MWESpec(text=sample_text, language="hi"), client=FakeAIClient(fake_response))
        segment = result["pages"][0]["segments"][0]
        self.assertEqual(["अंकल", " ", "और", " ", "आंटी"], [t["surface"] for t in segment["tokens"]])
        self.assertEqual(["और", "आंटी"], segment["annotations"]["mwes"][0]["tokens"])

    async def test_detect_mwes_scopes_ids_by_segment(self) -> None:
        text = {
            "l2": "en",
            "surface": "Turn off the light. She turned off the road.",
            "pages": [
                {
                    "surface": "Turn off the light. She turned off the road.",
                    "segments": [
                        {
                            "surface": "Turn off the light.",
                            "tokens": [{"surface": "Turn", "annotations": {"mwe_id": "m1"}}, {"surface": " "}, {"surface": "off", "annotations": {"mwe_id": "m1"}}],
                            "annotations": {},
                        },
                        {
                            "surface": "She turned off the road.",
                            "tokens": [{"surface": "turned", "annotations": {"mwe_id": "m1"}}, {"surface": " "}, {"surface": "off", "annotations": {"mwe_id": "m1"}}],
                            "annotations": {},
                        },
                    ],
                }
            ],
        }
        fake = {
            "tokens": [{"surface": "Turn", "annotations": {"mwe_id": "m1"}}, {"surface": " "}, {"surface": "off", "annotations": {"mwe_id": "m1"}}],
            "annotations": {"mwes": [{"id": "m1", "tokens": ["Turn", "off"], "label": "phrasal verb"}]},
        }
        client = FakePerCallAIClient([fake, fake])
        result = await mwe.annotate_mwes(MWESpec(text=text, language="en"), client=client)
        seg1 = result["pages"][0]["segments"][0]
        seg2 = result["pages"][0]["segments"][1]
        id1 = seg1["annotations"]["mwes"][0]["id"]
        id2 = seg2["annotations"]["mwes"][0]["id"]
        self.assertNotEqual(id1, id2)


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
