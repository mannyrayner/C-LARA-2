"""Helpers for restricted C-LARA-2 project-understanding answers."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Sequence
import uuid

from .ai_api import OpenAIClient
from .config import OpenAIConfig
from .telemetry import NullTelemetry, Telemetry

DEFAULT_PROJECT_UNDERSTANDING_MODEL = "gpt-5.3-codex"
DEFAULT_PROJECT_UNDERSTANDING_REASONING_EFFORT = "medium"
DEFAULT_PROJECT_UNDERSTANDING_MAX_OUTPUT_TOKENS = 3000
PROJECT_UNDERSTANDING_PROMPT_VERSION = "project-understanding-v1"

DEFAULT_EVIDENCE_PATHS = (
    "docs/roadmap/",
    "docs/issues/",
    "docs/howto/",
    "docs/publications/",
    "tests/",
    "prompts/",
    "src/",
    "platform_server/",
)


@dataclass(frozen=True)
class ProjectUnderstandingAnswer:
    """Result returned by a project-understanding model request."""

    question: str
    prompt: str
    answer: str
    model: str
    prompt_version: str
    requested_at: str


def build_project_understanding_prompt(
    user_request: str,
    *,
    evidence_paths: Sequence[str] = DEFAULT_EVIDENCE_PATHS,
    prompt_version: str = PROJECT_UNDERSTANDING_PROMPT_VERSION,
) -> str:
    """Wrap a user's project question in the restricted ISSUE-0034 prompt."""

    request = (user_request or "").strip()
    if not request:
        raise ValueError("user_request must not be empty")

    evidence_list = "\n".join(f"- `{path}`" for path in evidence_paths)
    return f"""You are answering questions about the C-LARA-2 project.

Prompt version: {prompt_version}

Use the C-LARA-2 repository documentation and codebase as evidence. Prefer these evidence areas when relevant:
{evidence_list}

Answer at the level of a project collaborator who understands the current architecture, goals, implementation status, issue structure, roadmap plans, prompt design, tests, and module relationships.

Rules:
- Distinguish implemented functionality from planned, speculative, or roadmap-only functionality.
- Cite supporting repository file paths whenever possible.
- Identify uncertainty instead of guessing.
- Say explicitly when the available project materials do not support an answer.
- Do not expose secrets, private user/project data, credentials, raw server logs, environment variables, or non-public operational details.
- Do not propose executing code, mutating platform/repository state, or triggering expensive workflows as part of the answer.
- Keep the answer concise but sufficiently detailed for a maintainer.

User question:
{request}
"""


async def answer_project_understanding_question(
    user_request: str,
    *,
    model: str = DEFAULT_PROJECT_UNDERSTANDING_MODEL,
    reasoning_effort: str | None = DEFAULT_PROJECT_UNDERSTANDING_REASONING_EFFORT,
    max_output_tokens: int | None = DEFAULT_PROJECT_UNDERSTANDING_MAX_OUTPUT_TOKENS,
    client: OpenAIClient | None = None,
    config: OpenAIConfig | None = None,
    telemetry: Telemetry | None = None,
    op_id: str | None = None,
) -> ProjectUnderstandingAnswer:
    """Build the ISSUE-0034 prompt, submit it to a Codex-capable model, and return the answer."""

    prompt = build_project_understanding_prompt(user_request)
    telemetry = telemetry or NullTelemetry()
    op_id = op_id or f"project-understanding-{uuid.uuid4()}"
    requested_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    owns_client = client is None
    client = client or OpenAIClient(config=config or OpenAIConfig(model=model))

    try:
        answer = await client.responses_text(
            prompt,
            model=model,
            reasoning_effort=reasoning_effort,
            max_output_tokens=max_output_tokens,
            telemetry=telemetry,
            op_id=op_id,
        )
    finally:
        if owns_client:
            await client.aclose()

    return ProjectUnderstandingAnswer(
        question=user_request.strip(),
        prompt=prompt,
        answer=answer,
        model=model,
        prompt_version=PROJECT_UNDERSTANDING_PROMPT_VERSION,
        requested_at=requested_at,
    )


def render_project_understanding_record(result: ProjectUnderstandingAnswer) -> str:
    """Render a versionable Markdown evidence record for a model answer."""

    return f"""# Project-understanding answer ({result.requested_at})

- Model: `{result.model}`
- Prompt version: `{result.prompt_version}`
- Human assessment: `unreviewed`
- Reviewer notes: _pending_

## Question

{result.question}

## Answer

{result.answer}

## Prompt sent to model

```text
{result.prompt}
```
"""


def write_project_understanding_record(
    result: ProjectUnderstandingAnswer,
    *,
    output_dir: str | Path = "docs/project_understanding",
) -> Path:
    """Write a Markdown evidence record and return its path."""

    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    safe_timestamp = result.requested_at.replace(":", "").replace("-", "").replace("Z", "Z")
    path = directory / f"project-understanding-{safe_timestamp}.md"
    path.write_text(render_project_understanding_record(result), encoding="utf-8")
    return path
