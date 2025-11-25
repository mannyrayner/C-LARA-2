"""Async OpenAI wrapper with heartbeat + retries for chat completions."""
from __future__ import annotations

import asyncio
import json
import sys
import time
import uuid
from typing import Any, Iterable

import httpx

TimeoutException = getattr(httpx, "TimeoutException", type("TimeoutException", (Exception,), {}))

try:  # pragma: no cover - exercised indirectly in integration environments
    from openai import APIError, AsyncOpenAI, RateLimitError
    from openai._exceptions import LengthFinishReasonError
except ImportError:  # pragma: no cover - offline test environments
    AsyncOpenAI = None  # type: ignore[misc,assignment]
    APIError = type("APIError", (Exception,), {})
    RateLimitError = type("RateLimitError", (Exception,), {})
    class LengthFinishReasonError(Exception):
        pass

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

        timeout = httpx.Timeout(self.config.timeout_s)
        client_kwargs: dict[str, Any] = {"timeout": timeout}
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
            except (RateLimitError, APIError, TimeoutException) as exc:
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


def _ensure_openai_installed():
    """Import the OpenAI SDK, raising ImportError with context if unavailable.

    Some hosts accidentally shadow dependencies (e.g., a local ``httpx.py`` on
    ``sys.path``). To avoid that, we temporarily move the repository paths to
    the end of ``sys.path`` so site-packages are preferred during the import.
    """

    from importlib import import_module, util
    from pathlib import Path

    if util.find_spec("openai") is None:
        raise ImportError("The openai package is required. Install it via pip install openai")

    repo_root = Path(__file__).resolve().parents[2]

    def _is_repo_path(entry: str) -> bool:
        try:
            return Path(entry or ".").resolve().is_relative_to(repo_root)
        except Exception:
            return False

    original_path = list(sys.path)
    try:
        preferred = [p for p in original_path if not _is_repo_path(p)]
        fallback = [p for p in original_path if _is_repo_path(p)]
        sys.path = preferred + fallback
        return import_module("openai")
    except Exception as exc:  # pragma: no cover - exercised in user envs
        raise ImportError(f"openai package import failed: {exc}") from exc
    finally:
        sys.path = original_path


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
    while not task.done():
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=heartbeat_s)
        except asyncio.TimeoutError:
            elapsed = time.monotonic() - start
            telemetry.heartbeat(op_id, elapsed)
            continue
    return await task
