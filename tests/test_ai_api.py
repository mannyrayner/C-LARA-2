"""Unit tests for the OpenAI client wrapper."""
from __future__ import annotations

import asyncio
import inspect
import sys
import types
import unittest
from unittest.mock import AsyncMock, patch

try:  # pragma: no cover - exercised in environments without OpenAI installed
    from openai import AsyncOpenAI as _AsyncOpenAI, RateLimitError as _OpenAIRateLimitError
    from openai._exceptions import APIError as _OpenAIAPIError
except ModuleNotFoundError:  # pragma: no cover - fallback for offline test environments
    class TimeoutException(Exception):
        pass


    class Timeout:  # type: ignore[too-few-public-methods]
        def __init__(self, *_: object, **__: object) -> None:
            pass


    sys.modules.setdefault("httpx", types.SimpleNamespace(Timeout=Timeout, TimeoutException=TimeoutException))

    class AsyncOpenAI:  # type: ignore[too-few-public-methods]
        def __init__(self, **_: object) -> None:
            self.chat = None

    class APIError(Exception):
        pass

    class RateLimitError(Exception):
        def __init__(self, message: str, response: object | None = None) -> None:
            super().__init__(message)
            self.response = response

    sys.modules["openai"] = types.SimpleNamespace(AsyncOpenAI=AsyncOpenAI, RateLimitError=RateLimitError)
    sys.modules["openai._exceptions"] = types.SimpleNamespace(APIError=APIError, RateLimitError=RateLimitError)
else:
    AsyncOpenAI = _AsyncOpenAI

    class APIError(Exception):
        pass

    class RateLimitError(Exception):
        def __init__(self, message: str, response: object | None = None) -> None:
            super().__init__(message)
            self.response = response

    sys.modules["openai._exceptions"] = types.SimpleNamespace(APIError=APIError, RateLimitError=RateLimitError)

from core.ai_api import APIRemovedInV1, OpenAIClient
from core.config import OpenAIConfig


class RecordingTelemetry:
    def __init__(self) -> None:
        self.events: list[tuple[str, str, str, dict | None]] = []
        self.heartbeats: list[tuple[str, float, str | None]] = []

    def heartbeat(self, op_id: str, elapsed_s: float, note: str | None = None) -> None:
        self.heartbeats.append((op_id, elapsed_s, note))

    def event(self, op_id: str, level: str, msg: str, data: dict | None = None) -> None:
        self.events.append((op_id, level, msg, data))


class FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class FakeChoice:
    def __init__(self, message: FakeMessage) -> None:
        self.message = message


class FakeResponse:
    def __init__(self, content: str) -> None:
        self.choices = [FakeChoice(FakeMessage(content))]


class FakeChatCompletions:
    def __init__(self, responses: list[object]) -> None:
        self._responses = responses
        self.calls = 0

    async def create(self, **_: object) -> FakeResponse:
        idx = self.calls
        self.calls += 1
        response = self._responses[idx]

        if isinstance(response, Exception):
            raise response
        if inspect.iscoroutine(response):
            return await response
        if inspect.iscoroutinefunction(response):
            return await response()
        if callable(response):
            return response()
        return response  # type: ignore[return-value]


class FakeChat:
    def __init__(self, responses: list[object]) -> None:
        self.completions = FakeChatCompletions(responses)


class FakeClient:
    def __init__(self, responses: list[object]) -> None:
        self.chat = FakeChat(responses)


class OpenAIClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_chat_json_success(self) -> None:
        telemetry = RecordingTelemetry()
        client = OpenAIClient(config=OpenAIConfig(api_key=None), client=FakeClient([FakeResponse('{"ok": true}')]))

        result = await client.chat_json("hello", telemetry=telemetry, op_id="op-1")

        self.assertEqual({"ok": True}, result)
        self.assertEqual(("op-1", "info", "openai.chat attempt 1", None), telemetry.events[0])

    async def test_chat_json_emits_heartbeat(self) -> None:
        telemetry = RecordingTelemetry()

        async def slow_response() -> FakeResponse:
            await asyncio.sleep(0.03)
            return FakeResponse('{"done": true}')

        client = OpenAIClient(
            config=OpenAIConfig(api_key=None, heartbeat_s=0.01),
            client=FakeClient([slow_response]),
        )

        result = await client.chat_json("hi", telemetry=telemetry, op_id="op-2")

        self.assertEqual({"done": True}, result)
        self.assertTrue(any(h[0] == "op-2" for h in telemetry.heartbeats))

    async def test_chat_json_retries_on_rate_limit(self) -> None:
        telemetry = RecordingTelemetry()
        responses = [
            RateLimitError(message="slow down", response=None),
            FakeResponse('{"retried": true}'),
        ]
        client = OpenAIClient(config=OpenAIConfig(api_key=None, heartbeat_s=0.01), client=FakeClient(responses))

        with patch("core.ai_api.asyncio.sleep", new=AsyncMock()) as sleep_mock:
            result = await client.chat_json("go", telemetry=telemetry, op_id="op-3")

        self.assertEqual({"retried": True}, result)
        self.assertTrue(any(evt[1] == "warn" for evt in telemetry.events))
        sleep_mock.assert_awaited()

    async def test_length_finish_error_falls_back_to_legacy(self) -> None:
        telemetry = RecordingTelemetry()

        class LengthFinishReasonError(Exception):
            pass

        class BrokenCompletions:
            def __init__(self) -> None:
                self.calls = 0

            def create(self, **_: object) -> object:
                self.calls += 1
                raise LengthFinishReasonError("boom")

        class BrokenChat:
            def __init__(self) -> None:
                self.completions = BrokenCompletions()

        class BrokenAsyncOpenAI:
            def __init__(self, **_: object) -> None:
                self.chat = BrokenChat()

        class LegacyChatCompletion:
            @staticmethod
            def create(**_: object) -> dict:
                return {"choices": [{"message": {"content": '{"ok": true}'}}]}

        legacy_module = types.SimpleNamespace(ChatCompletion=LegacyChatCompletion, api_key=None)

        with patch("core.ai_api.AsyncOpenAI", BrokenAsyncOpenAI), patch("core.ai_api._openai_module", legacy_module):
            client = OpenAIClient(config=OpenAIConfig(api_key=None))
            result = await client.chat_json("hello", telemetry=telemetry, op_id="op-length")

        self.assertEqual({"ok": True}, result)
        self.assertTrue(
            any((evt[3] or {}).get("error_type") == "LengthFinishReasonError" for evt in telemetry.events)
        )

    async def test_legacy_removed_api_raises_import_error(self) -> None:
        telemetry = RecordingTelemetry()

        class LegacyChatCompletion:
            @staticmethod
            def create(**_: object) -> dict:
                raise APIRemovedInV1(symbol="ChatCompletion")

        legacy_module = types.SimpleNamespace(ChatCompletion=LegacyChatCompletion, api_key=None, __version__="1.2.0")

        with patch("core.ai_api.AsyncOpenAI", None), patch("core.ai_api._openai_module", legacy_module):
            client = OpenAIClient(config=OpenAIConfig(api_key=None))
            with self.assertRaises(ImportError):
                await client.chat_json("hello", telemetry=telemetry, op_id="op-removed")


if __name__ == "__main__":
    unittest.main()
