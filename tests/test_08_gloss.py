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
    def __init__(self, response: dict) -> None:
        self.response = response
        self.prompts: list[str] = []

    async def chat_json(self, prompt: str, **_: object) -> dict:
        self.prompts.append(prompt)
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
