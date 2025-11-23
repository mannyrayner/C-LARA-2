"""Async OpenAI wrapper with heartbeat + retries (legacy-friendly)."""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Any, Iterable

import httpx

try:  # Prefer the new SDK when present and healthy.
    from openai import AsyncOpenAI  # type: ignore
except Exception:  # pragma: no cover - exercised when only legacy SDK is present
    AsyncOpenAI = None

try:  # Legacy + new SDK compatibility for error types.
    from openai import APIError, RateLimitError
except Exception:  # pragma: no cover - fallback for old SDKs
    try:
        from openai.error import APIError, RateLimitError  # type: ignore
    except Exception:  # pragma: no cover - offline environments
        class APIError(Exception):
            pass

        class RateLimitError(Exception):
            def __init__(self, message: str, response: object | None = None) -> None:
                super().__init__(message)
                self.response = response

try:  # pragma: no cover - optional legacy import
    import openai as _openai_module  # type: ignore
except Exception:  # pragma: no cover - offline environments
    _openai_module = None

try:  # pragma: no cover - optional legacy removal marker
    from openai.lib._old_api import APIRemovedInV1  # type: ignore
except Exception:  # pragma: no cover - fallback when module is absent
    class APIRemovedInV1(Exception):
        """Defined for environments without openai>=1.x installed."""


from .config import OpenAIConfig
from .telemetry import NullTelemetry, Telemetry


class OpenAIClient:
    """Thin wrapper around OpenAI chat completions with heartbeat + retries.

    The client prefers ``AsyncOpenAI`` when available, but automatically falls
    back to the legacy ``openai.ChatCompletion`` interface on platforms with an
    older SDK to avoid import errors like ``LengthFinishReasonError``.
    """

    def __init__(self, *, config: OpenAIConfig | None = None, client: Any | None = None) -> None:
        self.config = config or OpenAIConfig()
        self._legacy_module = _openai_module
        self._legacy_available = _legacy_api_supported(self._legacy_module) if self._legacy_module else False
        self._mode = "async"
        async_supported = _async_api_supported()

        if client is not None:  # Used by unit tests to inject fakes.
            self._client = client
            self._mode = "custom"
            return

        if AsyncOpenAI is not None and async_supported:
            timeout = httpx.Timeout(self.config.timeout_s)
            client_kwargs: dict[str, Any] = {"timeout": timeout}
            if self.config.api_key:
                client_kwargs["api_key"] = self.config.api_key
            self._client = AsyncOpenAI(**client_kwargs)
            self._mode = "async"
        elif AsyncOpenAI is not None and not async_supported:
            telemetry = NullTelemetry()
            telemetry.event("openai", "warn", "async OpenAI client missing dependencies; try reinstalling openai")
            if self._legacy_available:
                if self.config.api_key:
                    self._legacy_module.api_key = self.config.api_key
                self._mode = "legacy"
            else:
                raise ImportError(
                    "AsyncOpenAI is present but required dependencies failed to import; "
                    "try reinstalling openai or install a legacy-compatible version"
                )
        elif self._legacy_available:
            if self.config.api_key:
                self._legacy_module.api_key = self.config.api_key
            self._mode = "legacy"
        else:  # pragma: no cover - offline environments
            raise ImportError("OpenAI SDK is not installed or legacy API is unavailable")

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
            except (RateLimitError, APIError, httpx.TimeoutException) as exc:
                if attempt >= self.config.max_retries:
                    telemetry.event(op_id, "error", "openai call failed", {"error": str(exc)})
                    raise
                telemetry.event(op_id, "warn", "openai retry", {"attempt": attempt, "error": str(exc)})
                await asyncio.sleep(backoff)
                backoff *= 2
            except ImportError as exc:
                can_use_legacy = (
                    self._legacy_module is not None
                    and self._mode == "async"
                    and _legacy_api_supported(self._legacy_module)
                )
                if can_use_legacy:
                    telemetry.event(
                        op_id,
                        "warn",
                        "falling back to legacy OpenAI client",
                        {"error": str(exc), "error_type": exc.__class__.__name__},
                    )
                    self._mode = "legacy"
                    continue

                telemetry.event(
                    op_id,
                    "error",
                    "openai import failure",
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

                if exc.__class__.__name__ == "LengthFinishReasonError" or "LengthFinishReasonError" in str(exc):
                    if self._legacy_available and self._mode == "async":
                        telemetry.event(
                            op_id,
                            "warn",
                            "falling back to legacy OpenAI client after LengthFinishReasonError",
                            {"error": str(exc), "error_type": exc.__class__.__name__},
                        )
                        self._mode = "legacy"
                        continue
                    telemetry.event(
                        op_id,
                        "error",
                        "LengthFinishReasonError with no legacy fallback available",
                        {"error": str(exc), "error_type": exc.__class__.__name__},
                    )
                    raise ImportError("OpenAI async client failed and legacy API is unavailable") from exc
                telemetry.event(op_id, "error", "unexpected failure")
                raise

    def _build_request(
        self,
        prompt: str,
        *,
        model: str,
        temperature: float,
        tools: Iterable[dict[str, Any]] | None,
        response_format: dict[str, str] | None,
    ) -> Any:
        messages = [{"role": "user", "content": prompt}]
        response_format = response_format or {"type": "json_object"}
        tools_payload = list(tools) if tools else None

        if self._mode == "async" or self._mode == "custom":
            # New SDK (or injected fake) path.
            return self._client.chat.completions.create(
                model=model,
                temperature=temperature,
                messages=messages,
                tools=tools_payload,
                response_format=response_format,
            )

        if self._legacy_module is None or not self._legacy_available:  # pragma: no cover - defensive guard
            raise ImportError("OpenAI SDK is not installed or legacy API is unavailable")

        # Legacy synchronous SDK path; run in a thread to preserve async API.
        def _call() -> Any:
            try:
                return self._legacy_module.ChatCompletion.create(  # type: ignore[attr-defined]
                    model=model,
                    temperature=temperature,
                    messages=messages,
                    tools=tools_payload,
                    response_format=response_format,
                )
            except APIRemovedInV1 as exc:  # pragma: no cover - depends on host SDK
                raise ImportError("Legacy ChatCompletion API removed in openai>=1.0.0") from exc

        return asyncio.to_thread(_call)


def _extract_payload(response: Any) -> str:
    """Extract the content payload from both new and legacy responses."""

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


def _parse_version(version: str) -> tuple[int, ...]:
    parts: list[int] = []
    for part in version.split("."):
        try:
            parts.append(int(part))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def _legacy_api_supported(legacy_module: Any) -> bool:
    """Return True if the legacy ChatCompletion API is likely usable."""

    version = getattr(legacy_module, "__version__", "0.0.0")
    # The ChatCompletion surface was removed in >=1.0.0; avoid falling back
    # in those environments to prevent APIRemovedInV1 errors.
    return _parse_version(version) < _parse_version("1.0.0")


def _async_api_supported() -> bool:
    """Return True if the async OpenAI SDK appears import-healthy.

    We proactively import the common dependencies that have been missing on some
    host installs (e.g., ``LengthFinishReasonError``) so we can fail fast rather
    than crashing mid-request. If the probe fails, callers can decide to skip or
    fall back to the legacy client when available.
    """

    if AsyncOpenAI is None:
        return False

    try:  # pragma: no cover - exercised only on hosts with broken installs
        from openai._exceptions import LengthFinishReasonError  # type: ignore
        _ = LengthFinishReasonError
    except Exception:
        return False

    return True


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
