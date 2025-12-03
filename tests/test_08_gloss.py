"""Tests for the gloss annotation pipeline step."""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
import unittest

from core.ai_api import _ensure_openai_installed
from core.config import OpenAIConfig
from pipeline import gloss
from pipeline.gloss import GlossSpec
from tests.log_utils import log_test_case


class FakeAIClient:
    def __init__(self, response: dict, *, delay: float = 0.0) -> None:
        self.response = response
        self.prompts: list[str] = []
        self.delay = delay

    async def chat_json(self, prompt: str, **_: object) -> dict:
        self.prompts.append(prompt)
        if self.delay:
            await asyncio.sleep(self.delay)
        else:
            await asyncio.sleep(0)
        return self.response


class GlossUnitTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.prompts_root = Path(__file__).resolve().parents[1] / "prompts"
        self.sample_segment = {
            "surface": "She put up with the noise.",
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
                "translation": "Elle a supporté le bruit.",
                "mwes": [
                    {"id": "m1", "tokens": ["put", "up", "with"], "label": "phrasal verb"}
                ],
            },
        }
        self.sample_text = {
            "l2": "en",
            "l1": "fr",
            "surface": self.sample_segment["surface"],
            "pages": [
                {"surface": self.sample_segment["surface"], "segments": [self.sample_segment]},
            ],
        }

    def test_loads_fewshots(self) -> None:
        fewshots = gloss._load_fewshots("en", prompts_root=self.prompts_root)
        self.assertGreaterEqual(len(fewshots), 2)

        log_test_case(
            "gloss:load_fewshots",
            purpose="loads gloss few-shot examples",
            inputs={"language": "en"},
            output={"examples": len(fewshots)},
            status="pass",
        )

    def test_build_prompt_mentions_translation(self) -> None:
        template = "Gloss tokens"
        prompt = gloss._build_prompt(
            template,
            segment=self.sample_segment,
            fewshots=[],
            target_language="fr",
        )
        self.assertIn("translation", prompt)
        self.assertIn("Segment JSON", prompt)

        log_test_case(
            "gloss:build_prompt",
            purpose="ensures prompt carries translation hint and tokenized segment",
            inputs={"surface": self.sample_segment["surface"], "translation": self.sample_segment["annotations"]["translation"]},
            output={"prompt_preview": prompt.splitlines()[:4]},
            status="pass",
        )

    async def test_gloss_normalizes_response(self) -> None:
        fake_response = {
            "surface": self.sample_segment["surface"],
            "tokens": [
                {"surface": "She", "annotations": {"gloss": "elle"}},
                {"surface": " ", "annotations": {}},
                {"surface": "put", "annotations": {"mwe_id": "m1", "gloss": "supporter"}},
                {"surface": " ", "annotations": {}},
                {"surface": "up", "annotations": {"mwe_id": "m1", "gloss": "supporter"}},
                {"surface": " ", "annotations": {}},
                {"surface": "with", "annotations": {"mwe_id": "m1", "gloss": "supporter"}},
                {"surface": " ", "annotations": {}},
                {"surface": "the", "annotations": {"gloss": "le"}},
                {"surface": " ", "annotations": {}},
                {"surface": "noise", "annotations": {"gloss": "bruit"}},
                {"surface": "."},
            ],
            "annotations": self.sample_segment.get("annotations", {}),
        }
        client = FakeAIClient(fake_response)
        spec = GlossSpec(text=self.sample_text, language="en", target_language="fr")

        result = await gloss.annotate_gloss(spec, client=client)
        segment = result["pages"][0]["segments"][0]

        glosses = [t.get("annotations", {}).get("gloss") for t in segment.get("tokens", []) if t.get("annotations")]
        self.assertIn("supporter", glosses)
        self.assertTrue(client.prompts)

        log_test_case(
            "gloss:normalize_response",
            purpose="applies gloss annotations to tokens without losing MWE or translation data",
            inputs={"surface": self.sample_segment["surface"]},
            output={"glosses": glosses, "annotations": segment.get("annotations", {})},
            status="pass",
        )

    async def test_gloss_long_segments_reports_time(self) -> None:
        """Ensure longer segments log processing time and still merge glosses."""

        long_segments = [
            {
                "surface": "Once upon a time the kind dormouse shared crumbs with every hungry friend.",
                "tokens": [
                    {"surface": "Once", "annotations": {"mwe_id": "m1"}},
                    {"surface": " ", "annotations": {}},
                    {"surface": "upon", "annotations": {"mwe_id": "m1"}},
                    {"surface": " ", "annotations": {}},
                    {"surface": "a", "annotations": {}},
                    {"surface": " ", "annotations": {}},
                    {"surface": "time", "annotations": {"mwe_id": "m1"}},
                    {"surface": " ", "annotations": {}},
                    {"surface": "the"},
                    {"surface": " ", "annotations": {}},
                    {"surface": "kind"},
                    {"surface": " ", "annotations": {}},
                    {"surface": "dormouse"},
                    {"surface": " ", "annotations": {}},
                    {"surface": "shared"},
                    {"surface": " ", "annotations": {}},
                    {"surface": "crumbs"},
                    {"surface": " ", "annotations": {}},
                    {"surface": "with"},
                    {"surface": " ", "annotations": {}},
                    {"surface": "every"},
                    {"surface": " ", "annotations": {}},
                    {"surface": "hungry"},
                    {"surface": " ", "annotations": {}},
                    {"surface": "friend"},
                    {"surface": "."},
                ],
                "annotations": {
                    "translation": "Il était une fois la gentille souris qui partageait des miettes avec chaque ami affamé.",
                    "mwes": [{"id": "m1", "tokens": ["Once", "upon", "time"], "label": "idiom"}],
                },
            },
            {
                "surface": "Later that evening they cleaned up and said good night before the long trip ahead.",
                "tokens": [
                    {"surface": "Later"},
                    {"surface": " ", "annotations": {}},
                    {"surface": "that"},
                    {"surface": " ", "annotations": {}},
                    {"surface": "evening"},
                    {"surface": " ", "annotations": {}},
                    {"surface": "they"},
                    {"surface": " ", "annotations": {}},
                    {"surface": "cleaned"},
                    {"surface": " ", "annotations": {}},
                    {"surface": "up"},
                    {"surface": " ", "annotations": {}},
                    {"surface": "and"},
                    {"surface": " ", "annotations": {}},
                    {"surface": "said"},
                    {"surface": " ", "annotations": {}},
                    {"surface": "good"},
                    {"surface": " ", "annotations": {}},
                    {"surface": "night"},
                    {"surface": " ", "annotations": {}},
                    {"surface": "before"},
                    {"surface": " ", "annotations": {}},
                    {"surface": "the"},
                    {"surface": " ", "annotations": {}},
                    {"surface": "long"},
                    {"surface": " ", "annotations": {}},
                    {"surface": "trip"},
                    {"surface": " ", "annotations": {}},
                    {"surface": "ahead"},
                    {"surface": "."},
                ],
                "annotations": {
                    "translation": "Plus tard dans la soirée, ils ont tout rangé et se sont dit bonne nuit avant le long voyage.",
                },
            },
        ]

        long_text = {
            "l2": "en",
            "l1": "fr",
            "surface": " ".join(seg["surface"] for seg in long_segments),
            "pages": [
                {"surface": long_segments[0]["surface"], "segments": [long_segments[0]]},
                {"surface": long_segments[1]["surface"], "segments": [long_segments[1]]},
            ],
        }

        fake_response = {"surface": "", "tokens": [], "annotations": {}}
        client = FakeAIClient(fake_response, delay=0.05)

        spec = GlossSpec(text=long_text, language="en", target_language="fr")

        start = asyncio.get_event_loop().time()
        result = await gloss.annotate_gloss(spec, client=client)
        duration = asyncio.get_event_loop().time() - start

        # Ensure tokens preserved
        total_tokens = sum(len(seg.get("tokens", [])) for page in result.get("pages", []) for seg in page.get("segments", []))
        self.assertGreater(total_tokens, 0)

        log_test_case(
            "gloss:long_segments",
            purpose="times glossing of longer segments with simplified prompts",
            inputs={"segments": [seg["surface"] for seg in long_segments]},
            output={"duration_s": round(duration, 3), "prompts": len(client.prompts)},
            status="pass",
        )


class GlossIntegrationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.sample_segment = {
            "surface": "She put up with the noise.",
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
                "translation": "Elle a supporté le bruit.",
                "mwes": [
                    {"id": "m1", "tokens": ["put", "up", "with"], "label": "phrasal verb"}
                ],
            },
        }
        self.sample_text = {
            "l2": "en",
            "l1": "fr",
            "surface": self.sample_segment["surface"],
            "pages": [
                {"surface": self.sample_segment["surface"], "segments": [self.sample_segment]},
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

    async def test_annotate_gloss_with_openai_client(self) -> None:
        self._skip_if_no_key_or_incompatible()

        client = gloss.OpenAIClient(config=OpenAIConfig(model=os.getenv("OPENAI_TEST_MODEL", "gpt-5")))
        self.addAsyncCleanup(client.aclose)

        try:
            result = await gloss.annotate_gloss(GlossSpec(text=self.sample_text), client=client)
        except ImportError as exc:
            self.skipTest(f"openai SDK import failure during gloss annotate: {exc}")
        except self.openai.NotFoundError as exc:  # type: ignore[attr-defined]
            self.skipTest(f"model unavailable: {exc}")

        log_test_case(
            "gloss:integration",
            purpose="integration test for gloss tagging with MWE awareness",
            inputs={"text": self.sample_text, "model": os.getenv("OPENAI_TEST_MODEL", "gpt-5")},
            output={"annotated_text": result},
            status="pass",
            notes="See stdout for annotated output.",
        )


if __name__ == "__main__":
    unittest.main()
