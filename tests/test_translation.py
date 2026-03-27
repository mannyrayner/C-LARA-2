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


class FakeAIClient:
    def __init__(self, response: str) -> None:
        self.response = response
        self.prompts: list[str] = []

    async def chat_text(self, prompt: str, **_: object) -> str:
        self.prompts.append(prompt)
        await asyncio.sleep(0)
        return self.response


class RecordingTelemetry:
    def __init__(self) -> None:
        self.events: list[tuple[str, str, str, dict | None]] = []

    def heartbeat(self, op_id: str, elapsed_s: float, note: str | None = None) -> None:
        return None

    def event(self, op_id: str, level: str, msg: str, data: dict | None = None) -> None:
        self.events.append((op_id, level, msg, data))


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
        self.assertTrue(all(isinstance(fs.get("output"), str) for fs in fewshots))
        fallback_fewshots = translation._load_fewshots("xx", prompts_root=self.prompts_root)
        self.assertGreaterEqual(len(fallback_fewshots), 2)

    def test_build_prompt_mentions_target_language(self) -> None:
        template = "Translate the text into {glossing_language}."
        prompt = translation._build_prompt(
            template,
            segment_surface="Hello",
            fewshots=[],
            source_language="en",
            target_language="fr",
        )
        self.assertIn("Translate the text into fr.", prompt)
        self.assertIn("<start>Hello</end>", prompt)
        self.assertIn("Return format: <start>...</end>", prompt)

    def test_build_prompt_mentions_source_and_target_in_examples_preface(self) -> None:
        template = "Translate the text from {text_language} into {glossing_language}."
        prompt = translation._build_prompt(
            template,
            segment_surface="Guten Tag",
            fewshots=[{"input": "<start>Hallo</end>", "output": "<start>Hello</end>"}],
            source_language="de",
            target_language="en",
        )
        self.assertIn("Here are some examples showing de glossed with en.", prompt)
        self.assertIn("<start>Guten Tag</end>", prompt)

    async def test_translate_normalizes_response_and_sets_l1(self) -> None:
        fake_response = "<start>Il a fermé la fenêtre avant l'orage.</end>"
        client = FakeAIClient(fake_response)
        spec = TranslationSpec(text=self.sample_text, language="en", target_language="fr")

        result = await translation.translate(spec, client=client)

        page = result["pages"][0]["segments"][0]
        self.assertEqual("Il a fermé la fenêtre avant l'orage.", page["annotations"]["translation"])
        self.assertEqual("fr", result["l1"])
        self.assertTrue(client.prompts)

    async def test_translate_extracts_json_wrapper_and_unescapes_unicode(self) -> None:
        fake_response = (
            '{"translated_text":"<start>C\\u0000e9line est une \\u0000e9tudiante fran\\u0000e7aise '
            'en \\u0000e9change \\u0000e0 Ad\\u0000e9la\\u0000efd.</end>"}'
        )
        client = FakeAIClient(fake_response)
        spec = TranslationSpec(text=self.sample_text, language="en", target_language="fr")

        result = await translation.translate(spec, client=client)

        page = result["pages"][0]["segments"][0]
        self.assertEqual(
            "Céline est une étudiante française en échange à Adélaïd.",
            page["annotations"]["translation"],
        )

    async def test_translate_emits_raw_response_logging(self) -> None:
        client = FakeAIClient('{"translated_text":"<start>Bonjour</end>"}')
        telemetry = RecordingTelemetry()
        spec = TranslationSpec(
            text=self.sample_text,
            language="en",
            target_language="fr",
            telemetry=telemetry,
            op_id="translation-telemetry-test",
        )

        result = await translation.translate(spec, client=client)

        self.assertEqual("Bonjour", result["pages"][0]["segments"][0]["annotations"]["translation"])
        messages = [evt[2] for evt in telemetry.events]
        self.assertIn("translation segment raw response received", messages)
        self.assertIn("translation segment response normalized", messages)


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
                print("Translation output:", translation_text)


if __name__ == "__main__":
    unittest.main()
