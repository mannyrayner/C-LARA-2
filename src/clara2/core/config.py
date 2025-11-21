"""Configuration defaults for OpenAI-backed operations."""
from __future__ import annotations

from dataclasses import dataclass


DEFAULT_HEARTBEAT_S = 5.0
DEFAULT_TIMEOUT_S = 60.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_TEMPERATURE = 0.2


@dataclass
class OpenAIConfig:
    """Runtime configuration for OpenAI calls."""

    model: str = DEFAULT_MODEL
    temperature: float = DEFAULT_TEMPERATURE
    max_retries: int = DEFAULT_MAX_RETRIES
    timeout_s: float = DEFAULT_TIMEOUT_S
    heartbeat_s: float = DEFAULT_HEARTBEAT_S
