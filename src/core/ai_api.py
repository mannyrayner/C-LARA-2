"""OpenAI chat wrapper with heartbeat and retries (sync calls + async heartbeat)."""
from __future__ import annotations

import asyncio
import contextlib
import json
import time
import uuid
from importlib import util
from typing import Any, Iterable

from .config import OpenAIConfig
from .telemetry import NullTelemetry, Telemetry

OpenAI = None  # type: ignore[assignment]
APIError = type("APIError", (Exception,), {})
RateLimitError = type("RateLimitError", (Exception,), {})
LengthFinishReasonError = type("LengthFinishReasonError", (Exception,), {})


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
                return json.loads(payload)
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


def _ensure_openai_installed():
    """Check that the OpenAI SDK is installed and importable."""

    if util.find_spec("openai") is None:
        raise ImportError("The openai package is required. Install it via pip install openai")

    try:
        import openai  # type: ignore
    except Exception as exc:  # pragma: no cover - exercised in user envs
        raise ImportError(f"The openai package is required: {exc}") from exc

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
