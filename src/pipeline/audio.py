"""Audio annotation using a simple TTS engine with caching.

This module adds audio annotations to segments and lexical tokens. It uses a
pluggable TTS engine (defaulting to a small built-in sine-wave synthesizer so
tests run offline) and caches outputs so repeat surfaces reuse the same file.
"""
from __future__ import annotations

import asyncio
import hashlib
import shutil
import math
import struct
import wave
import os
import contextlib
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
        output_path.parent.mkdir(parents=True, exist_ok=True)

        streaming_factory = getattr(self._client.audio.speech, "with_streaming_response", None)
        if streaming_factory:
            # Recommended streaming path for SDK >=2.0.0
            with streaming_factory.create(
                model=self.model,
                voice=voice or "alloy",
                input=text,
                response_format="wav",
            ) as response:
                response.stream_to_file(str(output_path))
        else:  # pragma: no cover - fallback for SDKs lacking streaming helpers
            response = self._client.audio.speech.create(
                model=self.model,
                voice=voice or "alloy",
                input=text,
                response_format="wav",
            )
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


class GoogleTTSEngine:
    """Google Cloud-backed TTS engine with credential discovery.

    Prefers ``GOOGLE_APPLICATION_CREDENTIALS`` but can also load credentials
    from ``GOOGLE_CREDENTIALS_JSON`` by writing a temp file. Uses LINEAR16 to
    emit WAV-friendly PCM that downstream code can concatenate.
    """

    def __init__(self, *, voice: str | None = None, language: str | None = None, creds_path: Path | None = None):
        self.voice = voice or "default"
        self.language = language or "en-US"

        try:  # pragma: no cover - exercised in user envs
            from google.cloud import texttospeech
        except Exception as exc:  # pragma: no cover - dependency optional
            raise ImportError("google-cloud-texttospeech is required for Google TTS") from exc

        self._tts_mod = texttospeech
        self._creds_path = creds_path or self._ensure_google_creds()
        if self._creds_path:
            os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", str(self._creds_path))
        self._client = self._tts_mod.TextToSpeechClient()

    @staticmethod
    def _ensure_google_creds() -> Path | None:
        creds_file = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if creds_file and Path(creds_file).exists():
            return Path(creds_file)

        creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
        if creds_json:
            tmp_path = Path("/tmp/google_credentials_from_env.json")
            tmp_path.write_text(creds_json)
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(tmp_path)
            return tmp_path
        return None

    def synthesize_to_path(
        self, text: str, output_path: Path, *, voice: str | None = None, language: str | None = None
    ) -> None:
        tts = self._tts_mod
        voice_params = tts.VoiceSelectionParams(
            language_code=language or self.language,
            name=(voice or self.voice) if (voice or self.voice) != "default" else None,
        )
        audio_config = tts.AudioConfig(
            audio_encoding=tts.AudioEncoding.LINEAR16,
            sample_rate_hertz=24000,
        )

        response = self._client.synthesize_speech(
            input=tts.SynthesisInput(text=text),
            voice=voice_params,
            audio_config=audio_config,
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(output_path), "wb") as wav_file:
            wav_file.setparams((1, 2, audio_config.sample_rate_hertz, 0, "NONE", "not compressed"))
            wav_file.writeframes(response.audio_content)

    async def aclose(self) -> None:  # pragma: no cover - sync client
        close_fn = getattr(self._client, "close", None)
        if close_fn:
            close_fn()


@dataclass(slots=True)
class AudioSpec:
    """Specification for audio annotation."""

    text: dict[str, Any]
    language: str = "en"
    cache_dir: Path | None = None
    voice: str | None = None
    telemetry: Telemetry | None = None
    op_id: str | None = None


def _audio_annotation(path: Path, *, surface: str, spec: AudioSpec, level: str, engine: TTSEngine) -> dict[str, Any]:
    """Return a JSON-friendly audio annotation with metadata for auditing."""

    engine_name = getattr(engine, "name", None) or engine.__class__.__name__
    return {
        "path": str(path),
        "surface": surface,
        "engine": engine_name,
        "voice": spec.voice or "default",
        "language": spec.language,
        "level": level,
    }


def _validate_wav(path: Path, *, min_duration_s: float = 0.1) -> None:
    """Raise ValueError if WAV file is missing or unrealistically short."""

    if not path.exists():
        raise ValueError(f"audio file missing: {path}")

    with contextlib.closing(wave.open(str(path), "rb")) as wav_file:
        params = wav_file.getparams()
        if params.nframes <= 0 or params.framerate <= 0:
            raise ValueError(f"invalid audio params for {path}: {params}")

        duration = params.nframes / float(params.framerate)
        if duration < min_duration_s:
            raise ValueError(f"audio too short ({duration:.3f}s) for {path}")


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
        engine = SimpleTTSEngine()

        # Prefer Google TTS when credentials are present and dependency installed.
        if os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or os.getenv("GOOGLE_CREDENTIALS_JSON"):
            try:  # pragma: no cover - exercised in user envs
                engine = GoogleTTSEngine(language=spec.language, voice=spec.voice)
            except Exception as exc:
                telemetry.event("audio", "warn", f"google TTS unavailable, using stub: {exc}")

        # Otherwise, prefer OpenAI when credentials/model provided.
        elif os.getenv("OPENAI_API_KEY") and os.getenv("OPENAI_TTS_MODEL"):
            try:
                engine = OpenAITTSEngine()
            except Exception as exc:  # pragma: no cover - exercised in user envs
                telemetry.event("audio", "warn", f"openai TTS unavailable, using stub: {exc}")
    op_id = spec.op_id or "audio"
    concat_cache: dict[str, Path] = {}

    cache: dict[str, Path] = {}

    async def ensure_audio(text: str, level: str) -> Path | None:
        nonlocal engine
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
            try:
                await asyncio.to_thread(
                    engine.synthesize_to_path,
                    normalized,
                    output_path,
                    voice=spec.voice,
                    language=spec.language,
                )
                await asyncio.to_thread(_validate_wav, output_path)
            except Exception as exc:
                telemetry.event(op_id, "warn", f"primary TTS failed ({exc}); using stub")
                # Fall back to deterministic stub for reliable audio.
                engine = SimpleTTSEngine()
                await asyncio.to_thread(
                    engine.synthesize_to_path,
                    normalized,
                    output_path,
                    voice=spec.voice,
                    language=spec.language,
                )
                await asyncio.to_thread(_validate_wav, output_path)

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
                        annotations["audio"] = _audio_annotation(
                            audio_path, surface=token_key, spec=spec, level="token", engine=engine
                        )

                if annotations:
                    tokens_out.append({**token, "annotations": annotations})
                else:
                    tokens_out.append(dict(token))

            seg_annotations = dict(segment.get("annotations", {}))
            seg_audio = await ensure_audio(segment.get("surface", ""), "segment")
            if seg_audio:
                seg_annotations["audio"] = _audio_annotation(
                    seg_audio,
                    surface=segment.get("surface", ""),
                    spec=spec,
                    level="segment",
                    engine=engine,
                )
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
                    try:
                        await asyncio.to_thread(_concat_wave_files, segment_audio_paths, out_path)
                    except Exception as exc:  # pragma: no cover - depends on TTS backend
                        telemetry.event(op_id, "warn", f"page audio concat failed: {exc}")
                        out_path = None
                if out_path:
                    concat_cache[hash_key] = out_path
            if concat_cache.get(hash_key):
                page_annotations["audio"] = _audio_annotation(
                    concat_cache[hash_key],
                    surface=page.get("surface", ""),
                    spec=spec,
                    level="page",
                    engine=engine,
                )

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

    # Single input: avoid header rewriting to reduce fragility when upstream
    # TTS providers emit uncommon WAV params.
    if len(inputs) == 1:
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(inputs[0], output)
        return None

    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with wave.open(str(output), "wb") as out:
            with wave.open(str(inputs[0]), "rb") as first:
                params = first.getparams()
                # Guard against malformed inputs that report zeroed params or
                # unreasonable channel/sample specs.
                if (
                    params.nchannels <= 0
                    or params.sampwidth not in (1, 2, 3, 4)
                    or params.framerate <= 0
                ):
                    raise ValueError(f"Invalid WAV parameters for {inputs[0]}: {params}")

                out.setparams(params)
                out.writeframes(first.readframes(first.getnframes()))

            for path in inputs[1:]:
                with wave.open(str(path), "rb") as wav_file:
                    out.writeframes(wav_file.readframes(wav_file.getnframes()))
    except (wave.Error, struct.error) as exc:
        raise ValueError(f"Failed to concatenate WAV files: {exc}") from exc
