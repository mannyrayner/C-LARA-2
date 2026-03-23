"""OpenAI chat wrapper with heartbeat and retries (sync calls + async heartbeat)."""
from __future__ import annotations

import asyncio
import base64
import contextlib
import json
import re
import sys
import time
import uuid
from importlib import util
from pathlib import Path
from typing import Any, Iterable

from .config import OpenAIConfig
from .telemetry import NullTelemetry, Telemetry

OpenAI = None  # type: ignore[assignment]
APIError = type("APIError", (Exception,), {})
RateLimitError = type("RateLimitError", (Exception,), {})
LengthFinishReasonError = type("LengthFinishReasonError", (Exception,), {})
_MALFORMED_UNICODE_ESCAPE_RE = re.compile(r"\x00([0-9a-fA-F]{2})")


class OpenAIClient:
    """Thin wrapper around the sync OpenAI client with async heartbeat."""

    def __init__(self, *, config: OpenAIConfig | None = None, client: Any | None = None) -> None:
        self.config = config or OpenAIConfig()

        if client is not None:
            self._client = client
            return

        openai_mod = _ensure_openai_installed()
        global OpenAI, APIError, RateLimitError, LengthFinishReasonError
        OpenAI = getattr(openai_mod, "OpenAI", None)
        if OpenAI is None:  # pragma: no cover - missing dependency
            raise ImportError("The openai package is required. Install it via pip install openai")

        APIError = getattr(openai_mod, "APIError", APIError)
        RateLimitError = getattr(openai_mod, "RateLimitError", RateLimitError)
        try:
            LengthFinishReasonError = getattr(openai_mod, "LengthFinishReasonError")
        except Exception:
            LengthFinishReasonError = type("LengthFinishReasonError", (Exception,), {})

        client_kwargs: dict[str, Any] = {"timeout": self.config.timeout_s}
        if self.config.api_key:
            client_kwargs["api_key"] = self.config.api_key
        self._client = OpenAI(**client_kwargs)

    async def chat_json(
        self,
        prompt: str,
        *,
        model: str | None = None,
        temperature: float | None = None,
        tools: Iterable[dict[str, Any]] | None = None,
        response_format: dict[str, str] | None = None,
        telemetry: Telemetry | None = None,
        op_id: str | None = None,
    ) -> dict[str, Any]:
        """Send a chat completion request and parse the JSON response."""

        telemetry = telemetry or NullTelemetry()
        op_id = op_id or f"op-{uuid.uuid4()}"
        model = model or self.config.model
        temperature = temperature if temperature is not None else self.config.temperature
        heartbeat_s = self.config.heartbeat_s

        attempt = 0
        backoff = 1.0
        while True:
            attempt += 1
            start = time.monotonic()
            telemetry.event(op_id, "info", f"openai.chat attempt {attempt}")
            try:
                kwargs = self._build_request(
                    prompt,
                    model=model,
                    temperature=temperature,
                    tools=tools,
                    response_format=response_format,
                )
                response = await _run_with_heartbeat(self._client, kwargs, telemetry, op_id, start, heartbeat_s)
                payload = _extract_payload(response)
                result = json.loads(payload)
                normalized = _normalize_json_text(result)
                if normalized != result:
                    telemetry.event(op_id, "warn", "normalized malformed unicode escapes in JSON response")
                return normalized
            except json.JSONDecodeError as exc:  # pragma: no cover - edge condition
                telemetry.event(op_id, "error", "invalid JSON response", {"payload": payload})
                raise ValueError("OpenAI returned non-JSON content") from exc
            except (RateLimitError, APIError) as exc:
                if attempt >= self.config.max_retries:
                    telemetry.event(op_id, "error", "openai call failed", {"error": str(exc)})
                    raise
                telemetry.event(op_id, "warn", "openai retry", {"attempt": attempt, "error": str(exc)})
                await asyncio.sleep(backoff)
                backoff *= 2
            except LengthFinishReasonError as exc:
                telemetry.event(
                    op_id,
                    "error",
                    "openai async client missing dependencies; reinstall openai",
                    {"error": str(exc), "error_type": exc.__class__.__name__},
                )
                raise
            except Exception as exc:
                if exc.__class__.__name__ in {"RateLimitError", "APIError"}:
                    if attempt >= self.config.max_retries:
                        telemetry.event(op_id, "error", "openai call failed", {"error": str(exc)})
                        raise
                    telemetry.event(op_id, "warn", "openai retry", {"attempt": attempt, "error": str(exc)})
                    await asyncio.sleep(backoff)
                    backoff *= 2
                    continue
                telemetry.event(op_id, "error", "unexpected failure")
                raise

    def _build_request(
        self,
        prompt: str,
        *,
        model: str,
        temperature: float | None,
        tools: Iterable[dict[str, Any]] | None,
        response_format: dict[str, str] | None,
    ) -> dict[str, Any]:
        messages = [{"role": "user", "content": prompt}]
        response_format = response_format or {"type": "json_object"}
        tools_payload = list(tools) if tools else None

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "tools": tools_payload,
            "response_format": response_format,
        }
        if temperature is not None:
            kwargs["temperature"] = temperature

        return kwargs

    async def aclose(self) -> None:
        """Close the underlying client if it exposes a close/aclose method."""

        close_fn = getattr(self._client, "aclose", None)
        if close_fn is None:
            close_fn = getattr(self._client, "close", None)
        if close_fn is None:
            return
        result = close_fn()
        if asyncio.iscoroutine(result):
            await result

    def generate_image(
        self,
        prompt: str,
        *,
        model: str = "gpt-image-1",
        size: str = "1024x1024",
        quality: str = "medium",
        output_format: str = "png",
    ) -> dict[str, Any]:
        """Generate an image and return decoded bytes plus provider metadata."""

        response = self._client.images.generate(
            model=model,
            prompt=prompt,
            size=size,
            quality=quality,
            output_format=output_format,
            response_format="b64_json",
        )
        data = getattr(response, "data", None) or []
        if not data:
            raise ValueError("Image generation returned no images")
        first = data[0]
        b64_json = getattr(first, "b64_json", None) or (
            first.get("b64_json") if isinstance(first, dict) else None
        )
        if not b64_json:
            raise ValueError("Image generation response did not include base64 image data")
        revised_prompt = getattr(first, "revised_prompt", None) or (
            first.get("revised_prompt") if isinstance(first, dict) else None
        )
        return {
            "bytes": base64.b64decode(b64_json),
            "revised_prompt": revised_prompt or "",
            "model": model,
            "size": size,
            "quality": quality,
            "output_format": output_format,
        }


def _ensure_openai_installed():
    """Check that the OpenAI SDK is installed and importable."""

    if util.find_spec("openai") is None:
        raise ImportError("The openai package is required. Install it via pip install openai")

    # Remove project-local paths while importing openai so stdlib/site-packages
    # dependencies (e.g., httpx) are not shadowed by files in this repo.
    project_root = Path(__file__).resolve().parents[2]
    original_sys_path = sys.path.copy()
    filtered_path: list[str] = []
    for entry in original_sys_path:
        try:
            if Path(entry).resolve().is_relative_to(project_root):
                continue
        except Exception:
            # If the path cannot be resolved, keep it as-is.
            pass
        filtered_path.append(entry)

    try:
        sys.path = filtered_path
        import openai  # type: ignore
    except Exception as exc:  # pragma: no cover - exercised in user envs
        raise ImportError(f"The openai package is required: {exc}") from exc
    finally:
        sys.path = original_sys_path

    return openai


def _extract_payload(response: Any) -> str:
    """Extract the content payload from OpenAI responses or fakes."""

    if hasattr(response, "choices"):
        choice = response.choices[0]
        message = getattr(choice, "message", None)
        if message is not None and hasattr(message, "content"):
            return message.content or "{}"
    if isinstance(response, dict):
        choices = response.get("choices", [])
        if choices:
            message = choices[0].get("message", {})
            return message.get("content", "{}") or "{}"
    return "{}"


def _normalize_json_text(value: Any) -> Any:
    """Recursively repair malformed escaped-Unicode sequences in JSON values.

    Some model responses contain strings such as ``"C\\u0000e9line"``. After
    ``json.loads`` this becomes ``"C\\x00e9line"``, which then renders badly in
    HTML. We repair those sequences here so downstream pipeline stages operate on
    normal Unicode strings.
    """

    if isinstance(value, str):
        return _normalize_malformed_unicode_escapes(value)
    if isinstance(value, list):
        return [_normalize_json_text(item) for item in value]
    if isinstance(value, dict):
        return {key: _normalize_json_text(item) for key, item in value.items()}
    return value


def _normalize_malformed_unicode_escapes(text: str) -> str:
    def _replace(match: re.Match[str]) -> str:
        codepoint_text = match.group(1)
        try:
            codepoint = int(codepoint_text, 16)
        except ValueError:
            return match.group(0)
        if codepoint < 0 or codepoint > 0x10FFFF:
            return match.group(0)
        return chr(codepoint)

    normalized = _MALFORMED_UNICODE_ESCAPE_RE.sub(_replace, text)
    if "\x00" in normalized:
        normalized = normalized.replace("\x00", "")
    return normalized


async def _run_with_heartbeat(
    client: Any,
    kwargs: dict[str, Any],
    telemetry: Telemetry,
    op_id: str,
    start: float,
    heartbeat_s: float,
) -> Any:
    """Execute a blocking OpenAI call in an executor with heartbeats."""

    loop = asyncio.get_running_loop()

    def _call() -> Any:
        return client.chat.completions.create(**kwargs)

    future = loop.run_in_executor(None, _call)
    try:
        while True:
            try:
                return await asyncio.wait_for(asyncio.shield(future), timeout=heartbeat_s)
            except asyncio.TimeoutError:
                elapsed = time.monotonic() - start
                telemetry.heartbeat(op_id, elapsed)
                continue
    finally:
        if not future.done():
            future.cancel()
            with contextlib.suppress(Exception):
                await future
