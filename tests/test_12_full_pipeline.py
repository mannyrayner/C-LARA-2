from __future__ import annotations

import asyncio
import os
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
        # Preserve prior artifacts for easier manual inspection across test runs.
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

    async def test_full_pipeline_with_fake_client_multi_page_mwe(self) -> None:
        """Larger fake flow with two pages and an explicit MWE."""

        multi_text = "The landlord and tenant sign off. Later, they check in again."

        fake_html = self.fake_html_root / "multi"
        fake_audio = self.fake_audio_root / "multi"
        fake_html.mkdir(parents=True, exist_ok=True)
        fake_audio.mkdir(parents=True, exist_ok=True)

        # Phase 1 response: two pages, one segment each.
        seg1_phase1 = {
            "l2": "en",
            "surface": multi_text,
            "pages": [
                {"surface": "The landlord and tenant sign off.", "segments": [{"surface": "The landlord and tenant sign off.", "annotations": {}}], "annotations": {}},
                {"surface": "Later, they check in again.", "segments": [{"surface": "Later, they check in again.", "annotations": {}}], "annotations": {}},
            ],
            "annotations": {},
        }

        # Shared token shapes for downstream steps.
        seg1_tokens = [
            {"surface": "The"},
            {"surface": " "},
            {"surface": "landlord"},
            {"surface": " "},
            {"surface": "and"},
            {"surface": " "},
            {"surface": "tenant"},
            {"surface": " "},
            {"surface": "sign"},
            {"surface": " "},
            {"surface": "off"},
            {"surface": "."},
        ]

        seg2_tokens = [
            {"surface": "Later"},
            {"surface": ","},
            {"surface": " "},
            {"surface": "they"},
            {"surface": " "},
            {"surface": "check"},
            {"surface": " "},
            {"surface": "in"},
            {"surface": " "},
            {"surface": "again"},
            {"surface": "."},
        ]

        # Phase 2 (tokenization) responses, one per segment.
        seg1_phase2 = {"annotations": {}, "tokens": seg1_tokens}
        seg2_phase2 = {"annotations": {}, "tokens": seg2_tokens}

        # Translation per segment.
        seg1_translation = {
            "annotations": {"translation": "Le propriétaire et le locataire signent."},
            "tokens": seg1_tokens,
        }
        seg2_translation = {
            "annotations": {"translation": "Plus tard, ils s'enregistrent à nouveau."},
            "tokens": seg2_tokens,
        }

        # MWE detection: "sign off" is a single MWE.
        seg1_mwe = {
            "annotations": {"mwes": [{"id": "mwe1", "tokens": ["sign", "off"], "label": "phrasal"}]},
            "tokens": [
                {"surface": "The"},
                {"surface": " "},
                {"surface": "landlord"},
                {"surface": " "},
                {"surface": "and"},
                {"surface": " "},
                {"surface": "tenant"},
                {"surface": " "},
                {"surface": "sign", "annotations": {"mwe_id": "mwe1"}},
                {"surface": " ", "annotations": {}},
                {"surface": "off", "annotations": {"mwe_id": "mwe1"}},
                {"surface": "."},
            ],
        }
        seg2_mwe = {"annotations": {"mwes": []}, "tokens": seg2_tokens}

        # Lemma tagging keeps MWE ids intact.
        seg1_lemmas = {
            "annotations": {},
            "tokens": [
                {"surface": "The", "annotations": {"lemma": "the", "pos": "DET"}},
                {"surface": " ", "annotations": {}},
                {"surface": "landlord", "annotations": {"lemma": "landlord", "pos": "NOUN"}},
                {"surface": " "},
                {"surface": "and", "annotations": {"lemma": "and", "pos": "CONJ"}},
                {"surface": " "},
                {"surface": "tenant", "annotations": {"lemma": "tenant", "pos": "NOUN"}},
                {"surface": " "},
                {"surface": "sign", "annotations": {"lemma": "sign", "pos": "VERB", "mwe_id": "mwe1"}},
                {"surface": " "},
                {"surface": "off", "annotations": {"lemma": "off", "pos": "PART", "mwe_id": "mwe1"}},
                {"surface": "."},
            ],
        }
        seg2_lemmas = {
            "annotations": {},
            "tokens": [
                {"surface": "Later", "annotations": {"lemma": "later", "pos": "ADV"}},
                {"surface": ","},
                {"surface": " "},
                {"surface": "they", "annotations": {"lemma": "they", "pos": "PRON"}},
                {"surface": " "},
                {"surface": "check", "annotations": {"lemma": "check", "pos": "VERB"}},
                {"surface": " "},
                {"surface": "in", "annotations": {"lemma": "in", "pos": "PART"}},
                {"surface": " "},
                {"surface": "again", "annotations": {"lemma": "again", "pos": "ADV"}},
                {"surface": "."},
            ],
        }

        # Glossing with shared MWE handling.
        seg1_gloss = {
            "annotations": {},
            "tokens": [
                {"surface": "The", "annotations": {"lemma": "the", "pos": "DET", "gloss": "le/la"}},
                {"surface": " ", "annotations": {}},
                {"surface": "landlord", "annotations": {"lemma": "landlord", "pos": "NOUN", "gloss": "propriétaire"}},
                {"surface": " "},
                {"surface": "and", "annotations": {"lemma": "and", "pos": "CONJ", "gloss": "et"}},
                {"surface": " "},
                {"surface": "tenant", "annotations": {"lemma": "tenant", "pos": "NOUN", "gloss": "locataire"}},
                {"surface": " "},
                {
                    "surface": "sign",
                    "annotations": {
                        "lemma": "sign",
                        "pos": "VERB",
                        "gloss": "signer",
                        "mwe_id": "mwe1",
                    },
                },
                {"surface": " "},
                {
                    "surface": "off",
                    "annotations": {
                        "lemma": "off",
                        "pos": "PART",
                        "gloss": "terminer",
                        "mwe_id": "mwe1",
                    },
                },
                {"surface": "."},
            ],
        }
        seg2_gloss = {
            "annotations": {},
            "tokens": [
                {"surface": "Later", "annotations": {"lemma": "later", "pos": "ADV", "gloss": "plus tard"}},
                {"surface": ","},
                {"surface": " "},
                {"surface": "they", "annotations": {"lemma": "they", "pos": "PRON", "gloss": "ils"}},
                {"surface": " "},
                {"surface": "check", "annotations": {"lemma": "check", "pos": "VERB", "gloss": "vérifier"}},
                {"surface": " "},
                {"surface": "in", "annotations": {"lemma": "in", "pos": "PART", "gloss": "enregistrer"}},
                {"surface": " "},
                {"surface": "again", "annotations": {"lemma": "again", "pos": "ADV", "gloss": "encore"}},
                {"surface": "."},
            ],
        }

        responses = [
            seg1_phase1,
            seg1_phase2,
            seg2_phase2,
            seg1_translation,
            seg2_translation,
            seg1_mwe,
            seg2_mwe,
            seg1_lemmas,
            seg2_lemmas,
            seg1_gloss,
            seg2_gloss,
        ]

        fake_client = FakeAIClient(responses)

        spec = FullPipelineSpec(
            text=multi_text,
            language="en",
            target_language="fr",
            output_dir=fake_html,
            audio_cache_dir=fake_audio,
            telemetry=None,
        )

        result = await run_full_pipeline(spec, client=fake_client)

        run_root = Path(result["html"]["run_root"])
        html_root = Path(result["html"].get("html_root", run_root / "html"))
        html_path = html_root / "page_1.html"
        self.assertTrue(html_path.exists())
        self.assertTrue((html_root / "page_2.html").exists())
        pages = result["text"].get("pages", [])
        self.assertEqual(2, len(pages))
        mwes = pages[0]["segments"][0].get("annotations", {}).get("mwes", [])
        self.assertTrue(mwes)

        log_test_case(
            "pipeline:full:multi",
            purpose="runs multi-page pipeline with MWE using fake AI responses",
            inputs={"text": multi_text},
            output={
                "html_path": str(html_path),
                "pages": len(pages),
                "mwes": mwes,
            },
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
            require_real_tts=True,
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

    async def test_full_pipeline_real_from_segmented(self) -> None:
        """Run from segmented text through HTML with real AI + TTS on two pages and an MWE."""

        self._skip_if_no_key_or_incompatible()

        segmented = {
            "l2": "en",
            "surface": "The landlord and tenant sign off. Later, they check in again.",
            "pages": [
                {
                    "surface": "The landlord and tenant sign off.",
                    "segments": [
                        {
                            "surface": "The landlord and tenant sign off.",
                            "annotations": {},
                        }
                    ],
                    "annotations": {},
                },
                {
                    "surface": "Later, they check in again.",
                    "segments": [
                        {
                            "surface": "Later, they check in again.",
                            "annotations": {},
                        }
                    ],
                    "annotations": {},
                },
            ],
            "annotations": {},
        }

        html_root = self.real_html_root / "segmented_start"
        audio_root = self.real_audio_root / "segmented_start"
        html_root.mkdir(parents=True, exist_ok=True)
        audio_root.mkdir(parents=True, exist_ok=True)

        client = OpenAIClient(config=OpenAIConfig(model=os.getenv("OPENAI_TEST_MODEL", "gpt-5")))
        self.addAsyncCleanup(client.aclose)

        spec = FullPipelineSpec(
            text_obj=segmented,
            language="en",
            target_language="fr",
            output_dir=html_root,
            audio_cache_dir=audio_root,
            telemetry=None,
            start_stage="segmentation_phase_2",
            end_stage="compile_html",
            require_real_tts=True,
        )

        try:
            result = await run_full_pipeline(spec, client=client)
        except ImportError as exc:
            self.skipTest(f"openai SDK import failure during full pipeline: {exc}")
        except self.openai.NotFoundError as exc:  # type: ignore[attr-defined]
            self.skipTest(f"model unavailable: {exc}")

        pages = result["text"].get("pages", [])
        self.assertEqual(2, len(pages))

        html_root_resolved = Path(result["html"].get("html_root", result["html"].get("run_root")))
        html_path = html_root_resolved / "page_1.html"
        self.assertTrue(html_path.exists())

        mwes = [
            mwe
            for page in pages
            for segment in page.get("segments", [])
            for mwe in segment.get("annotations", {}).get("mwes", [])
        ]

        log_test_case(
            "pipeline:full:openai-segmented",
            purpose="runs full pipeline from segmentation→HTML with real OpenAI + TTS",
            inputs={"segmented_text": segmented},
            output={
                "html_path": str(html_path),
                "pages": len(pages),
                "mwes": mwes,
            },
            status="pass",
        )


if __name__ == "__main__":
    unittest.main()
