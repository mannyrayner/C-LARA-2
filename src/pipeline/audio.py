"""Audio annotation using a simple TTS engine with caching.

This module adds audio annotations to segments and lexical tokens. It uses a
pluggable TTS engine (defaulting to a small built-in sine-wave synthesizer so
tests run offline) and caches outputs so repeat surfaces reuse the same file.
"""
from __future__ import annotations

import asyncio
import hashlib
import math
import struct
import wave
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from core.ai_api import _ensure_openai_installed
from core.config import OpenAIConfig
from core.telemetry import NullTelemetry, Telemetry


class TTSEngine(Protocol):
    """Protocol for TTS engines that can synthesize audio to a file path."""

    def synthesize_to_path(
        self, text: str, output_path: Path, *, voice: str | None = None, language: str | None = None
    ) -> None:
        ...


class SimpleTTSEngine:
    """Deterministic, offline-friendly TTS stub.

    Generates a short sine wave whose pitch and duration depend on the text so
    repeated requests are stable. This keeps tests hermetic while exercising the
    caching and annotation wiring.
    """

    def __init__(self, sample_rate: int = 22050) -> None:
        self.sample_rate = sample_rate

    def synthesize_to_path(
        self, text: str, output_path: Path, *, voice: str | None = None, language: str | None = None
    ) -> None:
        duration = min(1.5, max(0.25, len(text) * 0.02))
        frequency = 440 + (hash(text) % 220)
        nframes = int(self.sample_rate * duration)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(output_path), "w") as wav:
            wav.setparams((1, 2, self.sample_rate, nframes, "NONE", "not compressed"))
            frames = bytearray()
            for i in range(nframes):
                value = int(32767 * math.sin(2 * math.pi * frequency * (i / self.sample_rate)))
                frames.extend(struct.pack("<h", value))
            wav.writeframes(frames)


class OpenAITTSEngine:
    """OpenAI-backed TTS engine using the synchronous SDK."""

    def __init__(self, *, config: OpenAIConfig | None = None, client: Any | None = None, model: str | None = None):
        self.config = config or OpenAIConfig()
        self.model = model or os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts")

        if client is not None:
            self._client = client
            return

        openai_mod = _ensure_openai_installed()
        OpenAI = getattr(openai_mod, "OpenAI", None)
        if OpenAI is None:  # pragma: no cover - missing dependency
            raise ImportError("The openai package is required. Install it via pip install openai")

        kwargs: dict[str, Any] = {"timeout": self.config.timeout_s}
        if self.config.api_key:
            kwargs["api_key"] = self.config.api_key
        self._client = OpenAI(**kwargs)

    def synthesize_to_path(
        self, text: str, output_path: Path, *, voice: str | None = None, language: str | None = None
    ) -> None:
        response = self._client.audio.speech.create(
            model=self.model,
            voice=voice or "alloy",
            input=text,
            response_format="wav",
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        stream_to_file = getattr(response, "stream_to_file", None)
        if callable(stream_to_file):
            stream_to_file(str(output_path))
        else:  # pragma: no cover - fallback for alternate SDK behaviors
            with open(output_path, "wb") as f:
                f.write(getattr(response, "read", lambda: b"")())

    async def aclose(self) -> None:
        close_fn = getattr(self._client, "aclose", None) or getattr(self._client, "close", None)
        if close_fn:
            result = close_fn()
            if asyncio.iscoroutine(result):
                await result


@dataclass(slots=True)
class AudioSpec:
    """Specification for audio annotation."""

    text: dict[str, Any]
    language: str = "en"
    cache_dir: Path | None = None
    voice: str | None = None
    telemetry: Telemetry | None = None
    op_id: str | None = None


async def annotate_audio(
    spec: AudioSpec, *, tts_engine: TTSEngine | None = None
) -> dict[str, Any]:
    """Attach audio paths to segments and lexical tokens.

    Token audio is only generated for lexical tokens (letters/numbers/CJK). All
    segments receive an audio file. Outputs are cached on disk under ``cache_dir``.
    """

    telemetry = spec.telemetry or NullTelemetry()
    cache_dir = spec.cache_dir or Path("audio_cache")
    cache_dir.mkdir(parents=True, exist_ok=True)

    engine: TTSEngine
    if tts_engine is not None:
        engine = tts_engine
    else:
        if os.getenv("OPENAI_API_KEY") and os.getenv("OPENAI_TTS_MODEL"):
            try:
                engine = OpenAITTSEngine()
            except Exception as exc:  # pragma: no cover - exercised in user envs
                telemetry.event("audio", "warn", f"openai TTS unavailable, falling back: {exc}")
                engine = SimpleTTSEngine()
        else:
            engine = SimpleTTSEngine()
    op_id = spec.op_id or "audio"
    concat_cache: dict[str, Path] = {}

    cache: dict[str, Path] = {}

    async def ensure_audio(text: str, level: str) -> Path | None:
        normalized = text.strip()
        if not normalized:
            return None

        key = f"{level}:{spec.language}:{spec.voice or 'default'}:{normalized.lower()}"
        if key in cache:
            return cache[key]

        filename = hashlib.sha1(key.encode("utf-8")).hexdigest() + ".wav"
        output_path = cache_dir / filename

        if not output_path.exists():
            telemetry.event(op_id, "info", f"synthesizing audio for {level}")
            await asyncio.to_thread(
                engine.synthesize_to_path,
                normalized,
                output_path,
                voice=spec.voice,
                language=spec.language,
            )

        cache[key] = output_path
        return output_path

    new_pages: list[dict[str, Any]] = []
    for page in spec.text.get("pages", []):
        new_segments: list[dict[str, Any]] = []
        segment_audio_paths: list[Path] = []
        for segment in page.get("segments", []):
            tokens_out: list[dict[str, Any]] = []
            for token in segment.get("tokens", []):
                surface = token.get("surface", "")
                annotations = dict(token.get("annotations", {}))

                if _is_word_token(surface):
                    token_key = annotations.get("lemma") or surface
                    audio_path = await ensure_audio(token_key, "token")
                    if audio_path:
                        annotations["audio"] = str(audio_path)

                if annotations:
                    tokens_out.append({**token, "annotations": annotations})
                else:
                    tokens_out.append(dict(token))

            seg_annotations = dict(segment.get("annotations", {}))
            seg_audio = await ensure_audio(segment.get("surface", ""), "segment")
            if seg_audio:
                seg_annotations["audio"] = str(seg_audio)
                segment_audio_paths.append(seg_audio)

            new_segments.append(
                {
                    "surface": segment.get("surface", ""),
                    "tokens": tokens_out if tokens_out else segment.get("tokens", []),
                    "annotations": seg_annotations,
                }
            )

        page_annotations = dict(page.get("annotations", {}))
        if segment_audio_paths:
            page_key = ":".join(str(p) for p in segment_audio_paths)
            hash_key = f"page:{page_key}"
            if hash_key not in concat_cache:
                out_path = cache_dir / (hashlib.sha1(hash_key.encode("utf-8")).hexdigest() + ".wav")
                if not out_path.exists():
                    telemetry.event(op_id, "info", "concatenating page audio")
                    await asyncio.to_thread(_concat_wave_files, segment_audio_paths, out_path)
                concat_cache[hash_key] = out_path
            page_annotations["audio"] = str(concat_cache[hash_key])

        new_pages.append(
            {
                "surface": page.get("surface", ""),
                "segments": new_segments,
                "annotations": page_annotations,
            }
        )
    result = {
        "l2": spec.text.get("l2", spec.language),
        "l1": spec.text.get("l1"),
        "title": spec.text.get("title"),
        "surface": spec.text.get("surface", ""),
        "pages": new_pages,
        "annotations": spec.text.get("annotations", {}),
    }

    close_fn = getattr(engine, "aclose", None) or getattr(engine, "close", None)
    if close_fn:
        result_close = close_fn()
        if asyncio.iscoroutine(result_close):
            await result_close

    return result


def _is_word_token(surface: str) -> bool:
    """Return True for lexical tokens (letters/numbers/CJK), False for whitespace/punctuation."""

    if not surface or surface.isspace():
        return False

    for ch in surface:
        if ch.isalnum() or _is_cjk(ch):
            return True
    return False


def _is_cjk(ch: str) -> bool:
    code = ord(ch)
    return 0x4E00 <= code <= 0x9FFF


def _concat_wave_files(inputs: list[Path], output: Path) -> None:
    """Concatenate multiple WAV files into ``output``."""

    if not inputs:
        return None

    output.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output), "wb") as out:
        with wave.open(str(inputs[0]), "rb") as first:
            out.setparams(first.getparams())
            out.writeframes(first.readframes(first.getnframes()))

        for path in inputs[1:]:
            with wave.open(str(path), "rb") as wav_file:
                out.writeframes(wav_file.readframes(wav_file.getnframes()))
