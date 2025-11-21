"""Telemetry interfaces for pipeline operations.

A minimal, pluggable heartbeat/event sink so callers can surface
progress in CLI, tests, or future web UIs.
"""
from __future__ import annotations

import time
from typing import Protocol


class Telemetry(Protocol):
    """A sink for heartbeat and event notifications.

    Implementations can print to stdout, log, or push to a web socket.
    """

    def heartbeat(self, op_id: str, elapsed_s: float, note: str | None = None) -> None:
        """Emit a periodic heartbeat for a long-running operation."""

    def event(self, op_id: str, level: str, msg: str, data: dict | None = None) -> None:
        """Emit a structured event for diagnostics or user feedback."""


class NullTelemetry:
    """A no-op telemetry sink suitable for tests and scripts."""

    def heartbeat(self, op_id: str, elapsed_s: float, note: str | None = None) -> None:  # noqa: D401
        return None

    def event(self, op_id: str, level: str, msg: str, data: dict | None = None) -> None:  # noqa: D401
        return None


class StdoutTelemetry:
    """A simple stdout implementation useful while bootstrapping."""

    def __init__(self) -> None:
        self._start = time.monotonic()

    def heartbeat(self, op_id: str, elapsed_s: float, note: str | None = None) -> None:
        note_suffix = f" ({note})" if note else ""
        print(f"[heartbeat] {op_id} +{elapsed_s:.1f}s{note_suffix}")

    def event(self, op_id: str, level: str, msg: str, data: dict | None = None) -> None:
        data_suffix = f" data={data}" if data else ""
        print(f"[{level}] {op_id} {msg}{data_suffix}")
