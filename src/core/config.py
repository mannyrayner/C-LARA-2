"""Configuration defaults for OpenAI-backed operations."""
from __future__ import annotations

import os

from dataclasses import dataclass


DEFAULT_HEARTBEAT_S = 5.0
DEFAULT_TIMEOUT_S = 60.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_MODEL = "gpt-5"
DEFAULT_TEMPERATURE: float | None = None


@dataclass
class OpenAIConfig:
    """Runtime configuration for OpenAI calls."""

    api_key: str | None = os.getenv("OPENAI_API_KEY")
    model: str = DEFAULT_MODEL
    # Some models (e.g., gpt-5) only support the default temperature. Using
    # ``None`` avoids sending the parameter and lets the model pick the
    # appropriate default.
    temperature: float | None = DEFAULT_TEMPERATURE
    max_retries: int = DEFAULT_MAX_RETRIES
    timeout_s: float = DEFAULT_TIMEOUT_S
    heartbeat_s: float = DEFAULT_HEARTBEAT_S
