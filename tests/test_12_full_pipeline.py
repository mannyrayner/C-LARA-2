from __future__ import annotations

import asyncio
import os
import shutil
import unittest
from pathlib import Path

from core.ai_api import OpenAIClient, _ensure_openai_installed
from core.config import OpenAIConfig
from pipeline.full_pipeline import FullPipelineSpec, run_full_pipeline
from tests.log_utils import log_test_case


class FakeAIClient(OpenAIClient):
    def __init__(self, responses: list[dict[str, object]]):
        # We do not call super() to avoid initializing real clients.
        self.responses = list(responses)

    async def chat_json(self, prompt: str, **_: object) -> dict:
        await asyncio.sleep(0)
        if not self.responses:
            raise RuntimeError("No fake responses left for chat_json")
        response = self.responses.pop(0)
        return response


class FullPipelineTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.artifacts = Path("tests/artifacts/full_pipeline")
        if self.artifacts.exists():
            shutil.rmtree(self.artifacts)
        self.artifacts.mkdir(parents=True, exist_ok=True)

        self.fake_html_root = self.artifacts / "fake_html"
        self.fake_audio_root = self.artifacts / "fake_audio"
        self.real_html_root = self.artifacts / "real_html"
        self.real_audio_root = self.artifacts / "real_audio"
        for path in [self.fake_html_root, self.fake_audio_root, self.real_html_root, self.real_audio_root]:
            path.mkdir(parents=True, exist_ok=True)
        self.sample_text = "A cat sleeps."

        # Responses for: seg1, seg2, translation, mwe, lemma, gloss
        seg1 = {
            "l2": "en",
            "surface": self.sample_text,
            "pages": [
                {
                    "surface": self.sample_text,
                    "segments": [
                        {"surface": self.sample_text, "annotations": {"mwes": []}},
                    ],
                }
            ],
            "annotations": {},
        }
        tokens = [
            {"surface": "A"},
            {"surface": " "},
            {"surface": "cat"},
            {"surface": " "},
            {"surface": "sleeps"},
            {"surface": "."},
        ]
        seg2 = {"annotations": {}, "tokens": tokens}
        translation = {"annotations": {"translation": "Un chat dort."}, "tokens": tokens}
        mwe = {"annotations": {"mwes": []}, "tokens": tokens}
        lemma_tokens = [
            {"surface": "A", "annotations": {"lemma": "a", "pos": "DET"}},
            {"surface": " ", "annotations": {}},
            {"surface": "cat", "annotations": {"lemma": "cat", "pos": "N"}},
            {"surface": " ", "annotations": {}},
            {"surface": "sleeps", "annotations": {"lemma": "sleep", "pos": "V"}},
            {"surface": ".", "annotations": {}},
        ]
        lemma = {"annotations": {}, "tokens": lemma_tokens}
        gloss_tokens = [
            {"surface": "A", "annotations": {"lemma": "a", "pos": "DET", "gloss": "un"}},
            {"surface": " ", "annotations": {}},
            {"surface": "cat", "annotations": {"lemma": "cat", "pos": "N", "gloss": "chat"}},
            {"surface": " ", "annotations": {}},
            {
                "surface": "sleeps",
                "annotations": {"lemma": "sleep", "pos": "V", "gloss": "dort"},
            },
            {"surface": ".", "annotations": {}},
        ]
        gloss = {"annotations": {}, "tokens": gloss_tokens}

        self.fake_client = FakeAIClient([seg1, seg2, translation, mwe, lemma, gloss])

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

    async def test_full_pipeline_with_fake_client(self) -> None:
        spec = FullPipelineSpec(
            text=self.sample_text,
            language="en",
            target_language="fr",
            output_dir=self.fake_html_root,
            audio_cache_dir=self.fake_audio_root,
            telemetry=None,
        )

        result = await run_full_pipeline(spec, client=self.fake_client)
        html_path = Path(result["html"]["html_path"])
        self.assertTrue(html_path.exists())

        # Verify lemmas/glosses survive through the pipeline.
        final_pages = result["text"].get("pages", [])
        tokens = final_pages[0]["segments"][0]["tokens"]
        lemmas = [t.get("annotations", {}).get("lemma") for t in tokens if t.get("surface", "").strip()]
        self.assertIn("cat", lemmas)

        log_test_case(
            "pipeline:full",
            purpose="runs segmentation→audio→HTML end-to-end with fake AI responses",
            inputs={"text": self.sample_text},
            output={"html_path": str(html_path), "lemmas": lemmas},
            status="pass",
        )

    async def test_full_pipeline_with_real_client(self) -> None:
        """Run end-to-end with the real OpenAI client using a short text."""

        self._skip_if_no_key_or_incompatible()

        client = OpenAIClient(config=OpenAIConfig(model=os.getenv("OPENAI_TEST_MODEL", "gpt-5")))
        self.addAsyncCleanup(client.aclose)

        spec = FullPipelineSpec(
            text=self.sample_text,
            language="en",
            target_language="fr",
            output_dir=self.real_html_root,
            audio_cache_dir=self.real_audio_root,
            telemetry=None,
        )

        try:
            result = await run_full_pipeline(spec, client=client)
        except ImportError as exc:
            self.skipTest(f"openai SDK import failure during full pipeline: {exc}")
        except self.openai.NotFoundError as exc:  # type: ignore[attr-defined]
            self.skipTest(f"model unavailable: {exc}")

        html_path = Path(result["html"]["html_path"])
        self.assertTrue(html_path.exists())
        html_content = html_path.read_text(encoding="utf-8")

        log_test_case(
            "pipeline:full:openai",
            purpose="runs full pipeline with real OpenAI client",
            inputs={"text": self.sample_text, "model": os.getenv("OPENAI_TEST_MODEL", "gpt-5")},
            output={
                "html_path": str(html_path),
                "html_content": html_content,
                "lemmas": [
                    t.get("annotations", {}).get("lemma")
                    for p in result["text"].get("pages", [])
                    for s in p.get("segments", [])
                    for t in s.get("tokens", [])
                    if t.get("surface", "").strip()
                ],
            },
            status="pass",
            notes="Full HTML content included for audit.",
        )


if __name__ == "__main__":
    unittest.main()
