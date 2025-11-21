"""Async OpenAI wrapper with heartbeat + retries."""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Any, Iterable

import httpx
from openai import AsyncOpenAI
from openai._exceptions import APIError, RateLimitError

from .config import OpenAIConfig
from .telemetry import NullTelemetry, Telemetry


class OpenAIClient:
    """Thin wrapper around :class:`AsyncOpenAI` with heartbeat + retries."""

    def __init__(self, *, config: OpenAIConfig | None = None, client: AsyncOpenAI | None = None) -> None:
        self.config = config or OpenAIConfig()
        if client:
            self._client = client
        else:
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
                request_coro = self._client.chat.completions.create(
                    model=model,
                    temperature=temperature,
                    messages=[{"role": "user", "content": prompt}],
                    tools=list(tools) if tools else None,
                    response_format=response_format or {"type": "json_object"},
                )
                response = await _run_with_heartbeat(request_coro, telemetry, op_id, start, heartbeat_s)
                payload = response.choices[0].message.content or "{}"
                return json.loads(payload)
            except json.JSONDecodeError as exc:  # pragma: no cover - edge condition
                telemetry.event(op_id, "error", "invalid JSON response", {"payload": payload})
                raise ValueError("OpenAI returned non-JSON content") from exc
            except (RateLimitError, APIError, httpx.TimeoutException) as exc:
                if attempt >= self.config.max_retries:
                    telemetry.event(op_id, "error", "openai call failed", {"error": str(exc)})
                    raise
                telemetry.event(op_id, "warn", "openai retry", {"attempt": attempt, "error": str(exc)})
                await asyncio.sleep(backoff)
                backoff *= 2
            except Exception:
                telemetry.event(op_id, "error", "unexpected failure")
                raise


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
