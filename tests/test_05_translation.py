"""Tests for the translation pipeline step."""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
import unittest

from core.ai_api import _ensure_openai_installed
from core.config import OpenAIConfig
from pipeline import translation
from pipeline.translation import TranslationSpec
from tests.log_utils import log_test_case


class FakeAIClient:
    def __init__(self, response: dict) -> None:
        self.response = response
        self.prompts: list[str] = []

    async def chat_json(self, prompt: str, **_: object) -> dict:
        self.prompts.append(prompt)
        await asyncio.sleep(0)
        return self.response


class TranslationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.prompts_root = Path(__file__).resolve().parents[1] / "prompts"
        self.sample_text = {
            "l2": "en",
            "surface": "He closed the window before the storm arrived.",
            "pages": [
                {
                    "surface": "He closed the window before the storm arrived.",
                    "segments": [
                        {"surface": "He closed the window before the storm arrived.", "annotations": {}},
                    ],
                }
            ],
        }

    def test_loads_fewshots(self) -> None:
        fewshots = translation._load_fewshots("en", prompts_root=self.prompts_root)
        self.assertGreaterEqual(len(fewshots), 2)
        self.assertTrue(all("annotations" in fs.get("output", {}) for fs in fewshots))

        log_test_case(
            "translation:load_fewshots",
            purpose="loads translation few-shot examples",
            inputs={"language": "en"},
            output={"examples": len(fewshots)},
            status="pass",
        )

    def test_build_prompt_mentions_target_language(self) -> None:
        template = "Translate."
        prompt = translation._build_prompt(
            template,
            segment={"surface": "Hello"},
            fewshots=[],
            target_language="fr",
        )
        self.assertIn("translate into fr", prompt.lower())
        self.assertIn("annotations.translation", prompt)

        log_test_case(
            "translation:build_prompt",
            purpose="ensures target language and annotation guidance appear in prompt",
            inputs={"segment": "Hello", "target_language": "fr"},
            output={"prompt_preview": prompt.splitlines()[:3]},
            status="pass",
        )

    async def test_translate_normalizes_response_and_sets_l1(self) -> None:
        fake_response = {
            "surface": self.sample_text["surface"],
            "annotations": {"translation": "Il a fermé la fenêtre avant l'orage."},
        }
        client = FakeAIClient(fake_response)
        spec = TranslationSpec(text=self.sample_text, language="en", target_language="fr")

        result = await translation.translate(spec, client=client)

        page = result["pages"][0]["segments"][0]
        self.assertEqual("Il a fermé la fenêtre avant l'orage.", page["annotations"]["translation"])
        self.assertEqual("fr", result["l1"])
        self.assertTrue(client.prompts)

        log_test_case(
            "translation:normalize_response",
            purpose="populates translation annotations and sets L1",
            inputs={"surface": self.sample_text["surface"]},
            output={"translation": page["annotations"]["translation"], "l1": result["l1"]},
            status="pass",
        )


class TranslationIntegrationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.prompts_root = Path(__file__).resolve().parents[1] / "prompts"
        self.sample_text = {
            "l2": "en",
            "surface": "A boy sat by the river. He skipped stones.",
            "pages": [
                {
                    "surface": "A boy sat by the river. He skipped stones.",
                    "segments": [
                        {"surface": "A boy sat by the river.", "annotations": {}},
                        {"surface": " He skipped stones.", "annotations": {}},
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

    async def test_translate_with_openai_client(self) -> None:
        self._skip_if_no_key_or_incompatible()

        client = translation.OpenAIClient(config=OpenAIConfig(model=os.getenv("OPENAI_TEST_MODEL", "gpt-5")))
        self.addAsyncCleanup(client.aclose)

        try:
            result = await translation.translate(
                TranslationSpec(
                    text=self.sample_text,
                    language="en",
                    target_language="fr",
                ),
                client=client,
            )
        except ImportError as exc:
            self.skipTest(f"openai SDK import failure during translate: {exc}")
        except self.openai.NotFoundError as exc:  # type: ignore[attr-defined]
            self.skipTest(f"model unavailable: {exc}")

        for page in result.get("pages", []):
            for segment in page.get("segments", []):
                translation_text = segment.get("annotations", {}).get("translation", "")
                self.assertTrue(translation_text)

        log_test_case(
            "translation:integration",
            purpose="integration test for EN→FR segment translation",
            inputs={"text": self.sample_text["surface"], "model": os.getenv("OPENAI_TEST_MODEL", "gpt-5")},
            output={"segments_translated": sum(len(p.get("segments", [])) for p in result.get("pages", []))},
            status="pass",
            notes="Segment translations available in full log output.",
        )


if __name__ == "__main__":
    unittest.main()
