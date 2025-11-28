from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path

from core.ai_api import OpenAIClient
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
        self.tmpdir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.tmpdir.name)
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

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    async def test_full_pipeline_with_fake_client(self) -> None:
        spec = FullPipelineSpec(
            text=self.sample_text,
            language="en",
            target_language="fr",
            output_dir=self.temp_path / "html",
            audio_cache_dir=self.temp_path / "audio",
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


if __name__ == "__main__":
    unittest.main()
