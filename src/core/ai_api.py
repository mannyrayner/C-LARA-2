"""Async OpenAI wrapper with heartbeat + retries for chat completions."""
from __future__ import annotations

import asyncio
import contextlib
import json
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Iterable

from importlib import import_module, util

AsyncOpenAI = None  # type: ignore[assignment]
APIError = type("APIError", (Exception,), {})
RateLimitError = type("RateLimitError", (Exception,), {})
LengthFinishReasonError = type("LengthFinishReasonError", (Exception,), {})
_openai_cache: Any | None = None

from .config import OpenAIConfig
from .telemetry import NullTelemetry, Telemetry


class OpenAIClient:
    """Thin wrapper around OpenAI chat completions with heartbeat + retries."""

    def __init__(self, *, config: OpenAIConfig | None = None, client: Any | None = None) -> None:
        self.config = config or OpenAIConfig()

        if client is not None:
            self._client = client
            return

        _ensure_openai_installed()
        if AsyncOpenAI is None:  # pragma: no cover - missing dependency
            raise ImportError("The openai package is required. Install it via pip install openai")

        client_kwargs: dict[str, Any] = {"timeout": self.config.timeout_s}
        if self.config.api_key:
            client_kwargs["api_key"] = self.config.api_key
        self._client = AsyncOpenAI(**client_kwargs)

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
                request = self._build_request(
                    prompt,
                    model=model,
                    temperature=temperature,
                    tools=tools,
                    response_format=response_format,
                )
                response = await _run_with_heartbeat(request, telemetry, op_id, start, heartbeat_s)
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
            except (LengthFinishReasonError, ImportError) as exc:
                telemetry.event(
                    op_id,
                    "error",
                    "openai async client missing dependencies; reinstall openai",
                    {"error": str(exc), "error_type": exc.__class__.__name__},
                )
                raise
            except Exception as exc:
                # Some environments raise custom error classes (e.g., test fakes)
                # that are not instances of the imported OpenAI exceptions. We
                # detect them by name to keep retry semantics consistent.
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
    ) -> Any:
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

        return self._client.chat.completions.create(**kwargs)

    async def aclose(self) -> None:
        """Close the underlying async client if it exposes an aclose method."""

        close_fn = getattr(self._client, "aclose", None)
        if close_fn is None:
            return
        result = close_fn()
        if asyncio.iscoroutine(result):
            await result


def _ensure_openai_installed():
    """Check that the OpenAI SDK is installed and importable."""

    global AsyncOpenAI, APIError, RateLimitError, LengthFinishReasonError, _openai_cache

    if _openai_cache is not None:
        return _openai_cache

    project_root = Path(__file__).resolve().parents[2]
    local_paths = {str(project_root), str(project_root / "src")}
    original_sys_path = sys.path.copy()

    try:
        sys.path = [p for p in original_sys_path if p not in local_paths] + [p for p in original_sys_path if p in local_paths]

        if util.find_spec("openai") is None:
            raise ImportError("The openai package is required. Install it via pip install openai")

        openai_mod = import_module("openai")
        AsyncOpenAI = getattr(openai_mod, "AsyncOpenAI", None)
        APIError = getattr(openai_mod, "APIError", APIError)
        RateLimitError = getattr(openai_mod, "RateLimitError", RateLimitError)
        try:
            LengthFinishReasonError = import_module("openai._exceptions").LengthFinishReasonError  # type: ignore[attr-defined]
        except Exception:
            class LengthFinishReasonError(Exception):
                pass

        _openai_cache = openai_mod
        return openai_mod
    except Exception as exc:  # pragma: no cover - exercised in user envs
        raise ImportError(f"openai package import failed: {exc}") from exc
    finally:
        sys.path = original_sys_path


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


async def _run_with_heartbeat(coro: Any, telemetry: Telemetry, op_id: str, start: float, heartbeat_s: float) -> Any:
    task = asyncio.create_task(coro)
    try:
        while True:
            try:
                return await asyncio.wait_for(asyncio.shield(task), timeout=heartbeat_s)
            except asyncio.TimeoutError:
                elapsed = time.monotonic() - start
                telemetry.heartbeat(op_id, elapsed)
                continue
    finally:
        if not task.done():
            task.cancel()
        # Always await the task to surface exceptions and avoid event-loop
        # shutdown warnings about pending tasks. Any cancellation or runtime
        # errors are suppressed because the caller has already handled the
        # outcome.
        with contextlib.suppress(Exception):
            await task
