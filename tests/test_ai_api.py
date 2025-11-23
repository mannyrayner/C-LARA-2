"""Unit tests for the OpenAI client wrapper."""
from __future__ import annotations

import asyncio
import json
import os
import types
import unittest
from unittest.mock import AsyncMock, patch

from core.ai_api import OpenAIClient, _ensure_openai_installed
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
        if asyncio.iscoroutine(response):
            return await response
        if asyncio.iscoroutinefunction(response):
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

        print("chat_json_success stubbed response:", result)
        self.assertEqual({"ok": True}, result)
        self.assertTrue(any(evt[2].startswith("openai.chat attempt") for evt in telemetry.events))

    async def test_chat_json_emits_heartbeat(self) -> None:
        telemetry = RecordingTelemetry()

        async def slow_response() -> FakeResponse:
            await asyncio.sleep(0.05)
            return FakeResponse('{"done": true}')

        client = OpenAIClient(
            config=OpenAIConfig(api_key=None, heartbeat_s=0.01), client=FakeClient([slow_response])
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

        print("chat_json_retries_on_rate_limit stubbed response:", result)

        self.assertEqual({"retried": True}, result)
        self.assertTrue(any(evt[1] == "warn" for evt in telemetry.events))
        sleep_mock.assert_awaited()

    async def test_chat_json_raises_on_length_finish_error(self) -> None:
        telemetry = RecordingTelemetry()

        class FakeLengthFinishError(Exception):
            pass

        async def fail() -> FakeResponse:
            raise FakeLengthFinishError("length")

        client = OpenAIClient(config=OpenAIConfig(api_key=None), client=FakeClient([fail]))

        with self.assertRaises(Exception):
            await client.chat_json("hi", telemetry=telemetry, op_id="op-4")

    def test_ensure_openai_installed_raises_when_missing(self) -> None:
        with patch("importlib.util.find_spec", return_value=None):
            with self.assertRaises(ImportError):
                _ensure_openai_installed()


class OpenAIClientIntegrationTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not os.getenv("OPENAI_API_KEY"):
            raise unittest.SkipTest("OPENAI_API_KEY not set; skipping OpenAI integration tests")
        try:
            import openai  # type: ignore
        except ImportError:
            raise unittest.SkipTest("openai package not installed")

        cls.openai = openai
        cls.test_model = os.getenv("OPENAI_TEST_MODEL", "gpt-5")

    async def test_chat_json_with_real_client(self) -> None:
        telemetry = RecordingTelemetry()
        client = OpenAIClient(config=OpenAIConfig(model=self.test_model))
        prompt = "Return a JSON object {\\\"ok\\\": true}."

        try:
            result = await client.chat_json(prompt, telemetry=telemetry, op_id="integration-1")
        except self.openai.NotFoundError as exc:  # type: ignore[attr-defined]
            self.skipTest(f"model {self.test_model} unavailable: {exc}")

        print("chat_json_real_client response:", result)
        self.assertIsInstance(result, dict)
        self.assertTrue(result)


class RateLimitError(Exception):
    def __init__(self, message: str, response: object | None = None) -> None:
        super().__init__(message)
        self.response = response


if __name__ == "__main__":
    unittest.main()
