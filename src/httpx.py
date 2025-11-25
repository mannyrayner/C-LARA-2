"""Lightweight shim for httpx to support offline test environments.

If the real ``httpx`` package is available it will be imported; otherwise minimal
Timeout/TimeoutException shims are provided so the OpenAI wrapper can run under
fakes without network access.
"""
from __future__ import annotations

try:  # pragma: no cover - prefer the real library when present
    from httpx import *  # type: ignore
except Exception:  # pragma: no cover - fallback stub
    class Timeout:  # type: ignore[misc]
        def __init__(self, timeout: float | int) -> None:
            self.timeout = timeout

    class TimeoutException(Exception):
        """Raised when a request times out."""

        pass
