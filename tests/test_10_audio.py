"""Tests for audio annotation and caching."""
from __future__ import annotations

import asyncio
import math
import os
import struct
import tempfile
import unittest
import wave
from pathlib import Path

from core.ai_api import _ensure_openai_installed
from core.config import OpenAIConfig
from pipeline import audio
from tests.log_utils import log_test_case


class FakeTTSEngine:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Path]] = []

    def synthesize_to_path(
        self, text: str, output_path: Path, *, voice: str | None = None, language: str | None = None
    ) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        sample_rate = 22050
        frames = bytearray()
        freq = 440 + (hash(text) % 200)
        for i in range(int(sample_rate * 0.25)):
            value = int(32767 * math.sin(2 * math.pi * freq * (i / sample_rate)))
            frames.extend(struct.pack("<h", value))

        with wave.open(str(output_path), "w") as wav_file:
            wav_file.setparams((1, 2, sample_rate, 0, "NONE", "not compressed"))
            wav_file.writeframes(frames)

        self.calls.append((text, output_path))


class AudioTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.cache_dir = Path(self.tmpdir.name)

        self.sample_text = {
            "l2": "en",
            "surface": "Hello, world!",
            "pages": [
                {
                    "surface": "Hello, world!",
                    "segments": [
                        {
                            "surface": "Hello, world!",
                            "tokens": [
                                {"surface": "Hello", "annotations": {"lemma": "hello"}},
                                {"surface": ","},
                                {"surface": " ", "annotations": {"translation": " "}},
                                {"surface": "world"},
                                {"surface": "!"},
                            ],
                            "annotations": {"translation": "Bonjour, monde!"},
                        }
                    ],
                }
            ],
        }

    def test_generates_audio_for_words_and_segments(self) -> None:
        engine = FakeTTSEngine()
        spec = audio.AudioSpec(text=self.sample_text, cache_dir=self.cache_dir)

        annotated = asyncio.run(audio.annotate_audio(spec, tts_engine=engine))

        tokens = annotated["pages"][0]["segments"][0]["tokens"]
        hello_audio = next(t.get("annotations", {}).get("audio") for t in tokens if t.get("surface") == "Hello")
        world_audio = next(t.get("annotations", {}).get("audio") for t in tokens if t.get("surface") == "world")
        page_audio = annotated["pages"][0]["annotations"].get("audio")

        self.assertTrue(Path(hello_audio["path"]).exists())
        self.assertTrue(Path(world_audio["path"]).exists())
        self.assertTrue(Path(page_audio["path"]).exists())
        self.assertNotIn("audio", tokens[1].get("annotations", {}))
        self.assertNotIn("audio", tokens[2].get("annotations", {}))
        self.assertIn("translation", annotated["pages"][0]["segments"][0]["annotations"])

        # Expect one call per unique word plus one for the segment.
        self.assertEqual(len(engine.calls), 3)

        log_test_case(
            "audio:unit",
            purpose="annotates lexical tokens and segments with cached audio",
            inputs={"segment": self.sample_text["surface"]},
            output={
                "token_audio": [hello_audio, world_audio],
                "segment_audio": annotated["pages"][0]["segments"][0]["annotations"].get("audio"),
                "page_audio": page_audio,
                "tts_calls": len(engine.calls),
            },
            status="pass",
        )

    def test_caches_repeat_tokens(self) -> None:
        engine = FakeTTSEngine()
        repeat_text = {
            "l2": "en",
            "surface": "echo echo",
            "pages": [
                {
                    "surface": "echo echo",
                    "segments": [
                        {
                            "surface": "echo echo",
                            "tokens": [
                                {"surface": "echo"},
                                {"surface": " "},
                                {"surface": "echo"},
                            ],
                        }
                    ],
                }
            ],
        }

        annotated = asyncio.run(
            audio.annotate_audio(audio.AudioSpec(text=repeat_text, cache_dir=self.cache_dir), tts_engine=engine)
        )

        token_audio = [
            t.get("annotations", {}).get("audio")
            for t in annotated["pages"][0]["segments"][0]["tokens"]
            if t["surface"].strip()
        ]

        # Two unique audio files: one for the shared token, one for the segment.
        self.assertEqual(len({ta["path"] for ta in token_audio}), 1)
        self.assertEqual(len(engine.calls), 2)

        log_test_case(
            "audio:cache",
            purpose="reuses cached audio for repeat tokens",
            inputs={"text": repeat_text["surface"]},
            output={"audio_files": token_audio, "tts_calls": len(engine.calls)},
            status="pass",
        )


class AudioIntegrationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.cache_dir = Path(self.tmpdir.name)

        self.sample_text = {
            "l2": "en",
            "surface": "Evening rain taps softly on the roof.",
            "pages": [
                {
                    "surface": "Evening rain taps softly on the roof.",
                    "segments": [
                        {
                            "surface": "Evening rain taps softly on the roof.",
                            "tokens": [
                                {"surface": "Evening", "annotations": {"lemma": "evening"}},
                                {"surface": " "},
                                {"surface": "rain"},
                                {"surface": " "},
                                {"surface": "taps"},
                                {"surface": " "},
                                {"surface": "softly"},
                                {"surface": " "},
                                {"surface": "on"},
                                {"surface": " "},
                                {"surface": "the"},
                                {"surface": " "},
                                {"surface": "roof"},
                                {"surface": "."},
                            ],
                        }
                    ],
                }
            ],
        }

    def _skip_if_no_key_or_incompatible(self) -> None:
        if not os.getenv("OPENAI_API_KEY"):
            self.skipTest("OPENAI_API_KEY not set; skipping TTS integration test")

        try:
            self.openai = _ensure_openai_installed()  # type: ignore[assignment]
        except ImportError as exc:
            self.skipTest(str(exc))

        version = getattr(self.openai, "__version__", "0.0.0")
        if version.startswith("0."):
            self.skipTest(f"openai version {version} is below 1.0.0; skipping integration test")

    async def test_openai_tts_engine(self) -> None:
        self._skip_if_no_key_or_incompatible()

        engine = audio.OpenAITTSEngine(config=OpenAIConfig())
        annotated = await audio.annotate_audio(
            audio.AudioSpec(text=self.sample_text, cache_dir=self.cache_dir, voice="alloy"),
            tts_engine=engine,
        )

        segment = annotated["pages"][0]["segments"][0]
        token_audio = [
            tok.get("annotations", {}).get("audio")
            for tok in segment["tokens"]
            if tok.get("surface", "").strip()
        ]

        self.assertTrue(all(Path(info["path"]).exists() for info in token_audio if info))
        self.assertTrue(Path(segment["annotations"].get("audio")["path"]).exists())

        log_test_case(
            "audio:integration",
            purpose="OpenAI TTS synthesis for tokens and segments",
            inputs=self.sample_text,
            output=segment,
            status="pass",
            notes="Includes audio annotations with engine/voice metadata",
        )


if __name__ == "__main__":
    unittest.main()
