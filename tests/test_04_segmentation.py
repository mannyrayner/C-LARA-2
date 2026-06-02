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

    async def chat_text(self, prompt: str, **_: object) -> str:
        self.prompts.append(prompt)
        await asyncio.sleep(0)
        return json.dumps(self.response)

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

    async def chat_text(self, prompt: str, **_: object) -> str:  # type: ignore[override]
        self.prompts.append(prompt)
        await asyncio.sleep(0)
        resp = self._responses[self._idx]
        self._idx += 1
        if isinstance(resp, str):
            return resp
        return json.dumps(resp)


class SegmentationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.prompts_root = Path(__file__).resolve().parents[1] / "prompts"

    def test_loads_fewshots(self) -> None:
        fewshots = segmentation._load_fewshots("en", prompts_root=self.prompts_root)  # type: ignore[attr-defined]
        self.assertGreaterEqual(len(fewshots), 2)
        self.assertTrue(all("input" in fs and "output" in fs for fs in fewshots))
        zh_fewshots = segmentation._load_fewshots("zh", prompts_root=self.prompts_root)  # type: ignore[attr-defined]
        self.assertGreaterEqual(len(zh_fewshots), 2)

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

        prompt = segmentation._build_prompt(template, text=text, fewshots=fewshots, language="en")  # type: ignore[attr-defined]

        self.assertIn("Input text:", prompt)
        self.assertIn(text.strip(), prompt)
        self.assertIn("Example 1:", prompt)
        self.assertIn("<startoftext>", prompt)
        self.assertIn("First line.", prompt)

        advised_prompt = segmentation._build_prompt(
            template,
            text=text,
            fewshots=fewshots,
            language="en",
            text_type_advice="For prose, prioritise sentence boundaries.",
        )  # type: ignore[attr-defined]
        self.assertIn("Additional segmentation guidance:", advised_prompt)
        self.assertIn("prioritise sentence boundaries", advised_prompt)

        log_test_case(
            "segmentation:build_prompt",
            purpose="assembles phase 1 segmentation prompt with examples",
            inputs={"text": text},
            output={"prompt_preview": prompt.splitlines()[:4]},
            status="pass",
        )

    async def test_segmentation_phase_1_prioritise_sentences_parameter_adds_guidance(self) -> None:
        client = FakeAIClient(
            {
                "surface": "First sentence. Second sentence.",
                "pages": [
                    {
                        "surface": "First sentence. Second sentence.",
                        "segments": [
                            {"surface": "First sentence."},
                            {"surface": " Second sentence."},
                        ],
                    }
                ],
                "annotations": {},
            }
        )

        await segmentation.segmentation_phase_1(
            SegmentationSpec(text="First sentence. Second sentence.", prioritise_sentences=True),
            client=client,
        )

        self.assertTrue(client.prompts)
        self.assertIn("prioritise sentence boundaries", client.prompts[0])
        self.assertIn("complete sentence", client.prompts[0])

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

    async def test_segmentation_phase_1_retries_when_text_is_changed(self) -> None:
        client = FakePerCallAIClient(
            [
                {"surface": "Different text", "pages": [{"surface": "Different text", "segments": [{"surface": "Different text"}]}]},
                {"surface": "Line one.", "pages": [{"surface": "Line one.", "segments": [{"surface": "Line one."}]}]},
            ]
        )
        spec = SegmentationSpec(text="Line one.")
        result = await segmentation.segmentation_phase_1(spec, client=client)
        self.assertEqual("Line one.", result["surface"])
        self.assertEqual(2, len(client.prompts))

    async def test_segmentation_phase_1_fails_after_retries_if_text_changes(self) -> None:
        client = FakePerCallAIClient(
            [
                {"surface": "Different 1", "pages": [{"surface": "Different 1", "segments": [{"surface": "Different 1"}]}]},
                {"surface": "Different 2", "pages": [{"surface": "Different 2", "segments": [{"surface": "Different 2"}]}]},
                {"surface": "Different 3", "pages": [{"surface": "Different 3", "segments": [{"surface": "Different 3"}]}]},
            ]
        )
        spec = SegmentationSpec(text="Line one.")
        with self.assertRaisesRegex(ValueError, r"diff_index=.*base_excerpt=.*annotated_excerpt="):
            await segmentation.segmentation_phase_1(spec, client=client)

    def test_normalize_phase1_ignores_empty_page_chunks(self) -> None:
        raw = "<page>\nपहली पंक्ति।||दूसरी पंक्ति।"
        result = segmentation._normalize_phase1_response(raw, text="पहली पंक्ति। दूसरी पंक्ति।", language="hi")  # type: ignore[attr-defined]
        self.assertEqual(1, len(result["pages"]))
        self.assertEqual(2, len(result["pages"][0]["segments"]))

    def test_normalize_phase1_converts_closing_page_tags(self) -> None:
        raw = "<startoftext>Hello world.</page>Second page.</endoftext>"
        result = segmentation._normalize_phase1_response(raw, text="Hello world.Second page.", language="en")  # type: ignore[attr-defined]
        self.assertIn("<page>", result["surface"])
        self.assertNotIn("</page>", result["surface"])

    def test_phase1_surface_match_tolerates_whitespace_differences(self) -> None:
        base = "A line.\n\nB line."
        annotated = "A line. \n\n\nB line."
        self.assertTrue(segmentation._phase1_surface_matches_text(base, annotated))  # type: ignore[attr-defined]


    async def test_segmentation_phase_2_uses_prompt_and_fewshot_variant(self) -> None:
        text = {
            "l2": "fr",
            "surface": "C'est l'heure.",
            "pages": [
                {
                    "surface": "C'est l'heure.",
                    "segments": [{"surface": "C'est l'heure.", "annotations": {}}],
                    "annotations": {},
                }
            ],
            "annotations": {},
        }
        client = FakeAIClient(
            {
                "surface": "C'est l'heure.",
                "tokens": [
                    {"surface": "C"},
                    {"surface": "'est"},
                    {"surface": " "},
                    {"surface": "l'"},
                    {"surface": "heure"},
                    {"surface": "."},
                ],
                "annotations": {},
            }
        )

        result = await segmentation_phase_2(
            SegmentationPhase2Spec(
                text=text,
                language="fr",
                prompt_variant="clitic_compound",
                fewshot_variant="clitic_compound",
            ),
            client=client,
        )

        prompt = client.prompts[0]
        self.assertIn("careful treatment of clitics", prompt)
        self.assertIn("C'est l'heure.", prompt)
        self.assertIn("Motorfordon är vanliga.", prompt)
        tokens = result["pages"][0]["segments"][0]["tokens"]
        self.assertEqual(["C", "'est", " ", "l'", "heure", "."], [tok["surface"] for tok in tokens])


    async def test_segmentation_phase_2_limits_fewshot_tranche(self) -> None:
        text = {
            "l2": "fr",
            "surface": "C'est l'heure.",
            "pages": [
                {
                    "surface": "C'est l'heure.",
                    "segments": [{"surface": "C'est l'heure.", "annotations": {}}],
                    "annotations": {},
                }
            ],
            "annotations": {},
        }
        client = FakeAIClient(
            {
                "surface": "C'est l'heure.",
                "tokens": [{"surface": "C'est l'heure."}],
                "annotations": {},
            }
        )

        await segmentation_phase_2(
            SegmentationPhase2Spec(
                text=text,
                language="fr",
                prompt_variant="clitic_compound",
                fewshot_variant="clitic_compound",
                fewshot_count=1,
            ),
            client=client,
        )

        prompt = client.prompts[0]
        self.assertIn("C'est l'heure.", prompt)
        self.assertNotIn("Dimela con calma.", prompt)
        self.assertNotIn("Motorfordon är vanliga.", prompt)

    async def test_segmentation_phase_2_boundary_first_combines_with_clitic_compound_variant(self) -> None:
        text = {
            "l2": "fr",
            "surface": "C'est l'heure.",
            "pages": [
                {
                    "surface": "C'est l'heure.",
                    "segments": [{"surface": "C'est l'heure.", "annotations": {}}],
                    "annotations": {},
                }
            ],
            "annotations": {},
        }
        client = FakePerCallAIClient(["C¦'est¦ ¦l'¦heure¦."])

        result = await segmentation_phase_2(
            SegmentationPhase2Spec(
                text=text,
                language="fr",
                mechanism="boundary_first",
                prompt_variant="clitic_compound",
                fewshot_variant="clitic_compound",
                fewshot_count="small",
            ),
            client=client,
        )

        prompt = client.prompts[0]
        self.assertIn("special attention to clitics", prompt)
        self.assertIn("C¦'est¦ ¦l'¦heure¦.", prompt)
        self.assertIn("Di¦me¦la¦ ¦con¦ ¦calma¦.", prompt)
        self.assertNotIn("Motor¦fordon", prompt)
        tokens = result["pages"][0]["segments"][0]["tokens"]
        self.assertEqual(["C", "'est", " ", "l'", "heure", "."], [tok["surface"] for tok in tokens])

    async def test_segmentation_phase_2_rejects_unsafe_variant_name(self) -> None:
        text = {"l2": "en", "surface": "Hello.", "pages": [{"surface": "Hello.", "segments": [{"surface": "Hello."}]}]}
        with self.assertRaisesRegex(ValueError, "Invalid prompt/few-shot variant"):
            await segmentation_phase_2(
                SegmentationPhase2Spec(text=text, language="en", prompt_variant="../bad"),
                client=FakeAIClient({}),
            )

    async def test_segmentation_phase_2_boundary_first_mechanism_adds_tokens(self) -> None:
        text = {
            "l2": "en",
            "surface": "A cat sleeps.",
            "pages": [
                {
                    "surface": "A cat sleeps.",
                    "segments": [{"surface": "A cat sleeps.", "annotations": {}}],
                    "annotations": {},
                }
            ],
            "annotations": {},
        }
        client = FakePerCallAIClient(["A¦ cat¦ sleeps¦."])

        result = await segmentation_phase_2(
            SegmentationPhase2Spec(text=text, language="en", mechanism="boundary_first"),
            client=client,
        )

        tokens = result["pages"][0]["segments"][0]["tokens"]
        self.assertEqual(["A", " cat", " sleeps", "."], [tok["surface"] for tok in tokens])
        self.assertIn("already contains provisional", client.prompts[0])
        self.assertIn("A¦ ¦cat¦ ¦sleeps¦.", client.prompts[0])
        self.assertIn("it¦'s", client.prompts[0])
        self.assertIn("motor¦fordon", client.prompts[0])

    async def test_segmentation_phase_2_boundary_first_fans_out_over_segments(self) -> None:
        text = {
            "l2": "en",
            "surface": "It's fine. Motorfordon är svenska.",
            "pages": [
                {
                    "surface": "It's fine. Motorfordon är svenska.",
                    "segments": [
                        {"surface": "It's fine.", "annotations": {}},
                        {"surface": "Motorfordon är svenska.", "annotations": {}},
                    ],
                    "annotations": {},
                }
            ],
            "annotations": {},
        }
        client = FakePerCallAIClient(["It¦'s¦ fine¦.", "Motor¦fordon¦ är¦ svenska¦."])

        result = await segmentation_phase_2(
            SegmentationPhase2Spec(text=text, language="en", mechanism="boundary_first"),
            client=client,
        )

        segments = result["pages"][0]["segments"]
        self.assertEqual(["It", "'s", " fine", "."], [tok["surface"] for tok in segments[0]["tokens"]])
        self.assertEqual(["Motor", "fordon", " är", " svenska", "."], [tok["surface"] for tok in segments[1]["tokens"]])
        self.assertEqual(2, len(client.prompts))

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

    async def test_segmentation_phase_2_preserves_surface_and_recovers_bad_tokens(self) -> None:
        text = {
            "l2": "hi",
            "surface": "नमस्ते दुनिया",
            "pages": [{"surface": "नमस्ते दुनिया", "segments": [{"surface": "नमस्ते दुनिया"}]}],
            "annotations": {},
        }
        client = FakeAIClient(
            {
                "surface": "Few-shot examples: Hello world",
                "tokens": [{"surface": "Few-shot"}, {"surface": "examples"}],
                "annotations": {},
            }
        )
        result = await segmentation_phase_2(SegmentationPhase2Spec(text=text, language="hi"), client=client)
        segment = result["pages"][0]["segments"][0]
        self.assertEqual("नमस्ते दुनिया", segment["surface"])
        self.assertEqual(["नमस्ते", " ", "दुनिया"], [t["surface"] for t in segment["tokens"]])

    async def test_segmentation_phase_2_accepts_string_tokens_from_model(self) -> None:
        text = {
            "l2": "hi",
            "surface": "नमस्ते दुनिया",
            "pages": [{"surface": "नमस्ते दुनिया", "segments": [{"surface": "नमस्ते दुनिया"}]}],
            "annotations": {},
        }
        client = FakeAIClient({"tokens": ["नमस्ते", " ", "दुनिया"], "annotations": {}})
        result = await segmentation_phase_2(SegmentationPhase2Spec(text=text, language="hi"), client=client)
        segment = result["pages"][0]["segments"][0]
        self.assertEqual("नमस्ते दुनिया", segment["surface"])
        self.assertEqual(["नमस्ते", " ", "दुनिया"], [t["surface"] for t in segment["tokens"]])

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
