"""Unit tests for telemetry helpers."""
from __future__ import annotations

import io
import sys
import unittest

from core.telemetry import NullTelemetry, StdoutTelemetry
from tests.log_utils import log_test_case


class TelemetryTests(unittest.TestCase):
    def test_null_telemetry_is_noop(self) -> None:
        telemetry = NullTelemetry()

        self.assertIsNone(telemetry.heartbeat("op", 1.0))
        self.assertIsNone(telemetry.event("op", "info", "msg"))

        log_test_case(
            "telemetry:null_noop",
            purpose="NullTelemetry drops all events and heartbeats",
            inputs={"op_id": "op"},
            output={
                "events": getattr(telemetry, "events", []),
                "heartbeats": getattr(telemetry, "heartbeats", []),
            },
            status="pass",
        )

    def test_stdout_telemetry_prints_messages(self) -> None:
        telemetry = StdoutTelemetry()
        buffer = io.StringIO()

        original_stdout = sys.stdout
        sys.stdout = buffer
        try:
            telemetry.heartbeat("abc", 1.2, "note")
            telemetry.event("abc", "warn", "something", {"k": 1})
        finally:
            sys.stdout = original_stdout

        output = buffer.getvalue().splitlines()
        self.assertIn("[heartbeat] abc +1.2s (note)", output)
        self.assertIn("[warn] abc something data={'k': 1}", output)

        log_test_case(
            "telemetry:stdout_output",
            purpose="StdoutTelemetry prints human-readable heartbeat and event lines",
            inputs={"op_id": "abc"},
            output=output,
            status="pass",
        )


if __name__ == "__main__":
    unittest.main()
