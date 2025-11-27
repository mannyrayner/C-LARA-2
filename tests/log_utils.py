"""Helpers for emitting readable test logs to stdout/log files."""
from __future__ import annotations

import json
from typing import Any


def log_test_case(
    name: str,
    *,
    purpose: str,
    inputs: Any | None = None,
    output: Any | None = None,
    status: str = "info",
    notes: str | None = None,
) -> None:
    """Emit a structured line describing the test scenario.

    The output is intentionally single-line JSON for easy grepping in both
    stdout and the saved test log.
    """

    payload: dict[str, Any] = {"test": name, "purpose": purpose, "status": status}
    if inputs is not None:
        payload["inputs"] = inputs
    if output is not None:
        payload["output"] = output
    if notes:
        payload["notes"] = notes

    try:
        print(f"[TEST] {json.dumps(payload, ensure_ascii=False)}")
    except UnicodeEncodeError:
        # Some consoles (e.g., Windows code pages) cannot encode certain
        # characters. Fall back to an ASCII-safe rendering so tests still log
        # successfully.
        print(f"[TEST] {json.dumps(payload, ensure_ascii=True)}")
