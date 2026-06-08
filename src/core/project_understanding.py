"""Helpers for restricted C-LARA-2 project-understanding answers."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
import os
import re
import shutil
import subprocess
import time
from typing import Sequence
import uuid

from .ai_api import OpenAIClient
from .config import OpenAIConfig
from .telemetry import NullTelemetry, Telemetry

DEFAULT_PROJECT_UNDERSTANDING_MODEL = "gpt-5.3-codex"
DEFAULT_PROJECT_UNDERSTANDING_REASONING_EFFORT = "medium"
DEFAULT_PROJECT_UNDERSTANDING_MAX_OUTPUT_TOKENS = 3000
PROJECT_UNDERSTANDING_PROMPT_VERSION = "project-understanding-v1"
DEFAULT_CODEX_EXECUTABLE = "codex"
DEFAULT_CODEX_EXEC_TIMEOUT_SECONDS = 300.0

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

_TOKEN_USAGE_RE = re.compile(r"tokens\s+used\s*\r?\n\s*([0-9][0-9,]*)", re.IGNORECASE)
_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_CODEX_SANDBOX_FAILURE_CONTEXTS = (
    "bwrap",
    "bubblewrap",
    "linux sandbox",
    "sandbox uses bubblewrap",
)
_CODEX_SANDBOX_FAILURE_SYMPTOMS = (
    "failed rtm_newaddr",
    "operation not permitted",
    "local file access is currently blocked",
    "command access is currently blocked",
    "command access is failing",
    "could not read sources",
    "could not inspect",
)


def detect_codex_sandbox_access_failure(output: str) -> str:
    """Return a short diagnostic if Codex ran but could not inspect the repo.

    Some Codex CLI sandbox failures are reported inside a successful transcript
    rather than via a non-zero process exit.  Treat those as configuration
    errors so the Assistant does not store a plausible-looking but unevidenced
    answer.
    """

    cleaned = _ANSI_ESCAPE_RE.sub("", output or "").strip()
    lowered = cleaned.lower()
    if not lowered:
        return ""

    has_context = any(marker in lowered for marker in _CODEX_SANDBOX_FAILURE_CONTEXTS)
    has_symptom = any(marker in lowered for marker in _CODEX_SANDBOX_FAILURE_SYMPTOMS)
    if not (has_context and has_symptom):
        return ""

    for line in cleaned.splitlines():
        line_lower = line.lower()
        line_markers = (*_CODEX_SANDBOX_FAILURE_CONTEXTS, *_CODEX_SANDBOX_FAILURE_SYMPTOMS)
        if any(marker in line_lower for marker in line_markers):
            return line.strip()[:500]
    return cleaned[:500]



@dataclass(frozen=True)
class ProjectUnderstandingAnswer:
    """Result returned by a project-understanding request."""

    question: str
    prompt: str
    answer: str
    model: str
    prompt_version: str
    requested_at: str
    tokens_used: int | None = None
    elapsed_seconds: float | None = None
    invocation_route: str = "responses-api"
    repository_path: str | None = None
    command: tuple[str, ...] | None = None
    returncode: int | None = None
    stderr: str = ""
    raw_stdout: str = ""
    estimated_cost_usd: str = ""
    cost_basis: str = ""


class CodexExecError(RuntimeError):
    """Raised when the `codex exec` project-understanding call cannot complete."""


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


def _utc_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_codex_exec_command(
    *,
    repository_path: str | Path,
    codex_executable: str = DEFAULT_CODEX_EXECUTABLE,
    model: str = DEFAULT_PROJECT_UNDERSTANDING_MODEL,
) -> list[str]:
    """Build the safe argument vector for a non-interactive read-only `codex exec` call."""

    repo = str(Path(repository_path))
    if not repo:
        raise ValueError("repository_path must not be empty")
    return [
        codex_executable,
        "exec",
        "--cd",
        repo,
        "--sandbox",
        "read-only",
        "--ephemeral",
        "--model",
        model,
        "-",
    ]


def build_codex_exec_environment(
    *,
    openai_api_key: str | None = None,
    base_environment: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Create a reduced environment suitable for Codex CLI execution.

    Codex may authenticate either from OPENAI_API_KEY or from cached CLI
    credentials under HOME/CODEX_HOME.  Do not require an API key here: on
    AWS/Gunicorn deployments the recommended setup is often to authenticate the
    service account once with `codex login`/`codex login --with-api-key` and
    then point CODEX_HOME at that locked-down credential directory.
    """

    base = os.environ if base_environment is None else base_environment
    api_key = openai_api_key or base.get("OPENAI_API_KEY")

    preserved_names = (
        "PATH",
        "HOME",
        "USERPROFILE",
        "CODEX_HOME",
        "APPDATA",
        "LOCALAPPDATA",
        "PATHEXT",
        "TMPDIR",
        "TEMP",
        "TMP",
        "SYSTEMROOT",
        "SystemRoot",
        "WINDIR",
        "COMSPEC",
    )
    env = {name: value for name in preserved_names if (value := base.get(name))}
    if api_key:
        env["OPENAI_API_KEY"] = api_key
    return env


def _expand_path_with_environment(path_text: str, environment: Mapping[str, str]) -> str:
    """Expand ~ and simple $VARS using the supplied environment mapping."""

    expanded = os.path.expanduser(path_text)
    for name, value in environment.items():
        expanded = expanded.replace(f"${name}", value).replace(f"${{{name}}}", value)
    return expanded


def _path_exists_safely(path: Path) -> bool:
    """Return whether a path exists without leaking permission errors from probes."""

    try:
        return path.exists()
    except OSError:
        return False


def resolve_codex_executable(
    codex_executable: str = DEFAULT_CODEX_EXECUTABLE,
    *,
    environment: Mapping[str, str] | None = None,
) -> str:
    """Resolve the Codex executable, including common Windows npm locations."""

    executable = (codex_executable or "").strip()
    if not executable:
        raise ValueError("codex_executable must not be empty")

    env = os.environ if environment is None else environment
    expanded = _expand_path_with_environment(executable, env)
    if "/" in expanded or "\\" in expanded:
        candidate = Path(expanded)
        if _path_exists_safely(candidate):
            return str(candidate)
        return expanded

    resolved = shutil.which(expanded, path=env.get("PATH"))
    if resolved:
        return resolved

    candidate_dirs: list[Path] = []
    for npm_root_name in ("APPDATA", "LOCALAPPDATA"):
        npm_root = env.get(npm_root_name)
        if npm_root:
            candidate_dirs.append(Path(npm_root) / "npm")

    for home_name in ("CODEX_HOME", "HOME", "USERPROFILE"):
        home = env.get(home_name)
        if home:
            home_path = Path(_expand_path_with_environment(home, env))
            candidate_dirs.extend(
                [
                    home_path / ".local" / "bin",
                    home_path / ".npm-global" / "bin",
                    home_path / "node_modules" / ".bin",
                ]
            )

    candidate_dirs.extend(
        [
            Path("/usr/local/bin"),
            Path("/usr/bin"),
            Path("/opt/homebrew/bin"),
        ]
    )
    candidate_names = (expanded, f"{expanded}.cmd", f"{expanded}.exe", f"{expanded}.bat")
    for directory in candidate_dirs:
        for candidate_name in candidate_names:
            candidate = directory / candidate_name
            if _path_exists_safely(candidate):
                return str(candidate)

    return expanded


def extract_codex_tokens_used(output: str) -> int | None:
    """Extract the final `tokens used` count from a plain-text Codex transcript."""

    matches = _TOKEN_USAGE_RE.findall(output or "")
    if not matches:
        return None
    return int(matches[-1].replace(",", ""))


def extract_codex_formatted_answer(output: str) -> str:
    """Extract the final user-facing answer from a plain-text Codex transcript."""

    clean_output = _ANSI_ESCAPE_RE.sub("", output or "")
    clean_output = _TOKEN_USAGE_RE.sub("", clean_output).rstrip()
    codex_blocks = re.split(r"(?m)^codex\s*$", clean_output)
    if len(codex_blocks) > 1:
        candidate = codex_blocks[-1].strip()
    else:
        candidate = clean_output.strip()
    return candidate


def answer_project_understanding_question_with_codex_exec(
    user_request: str,
    *,
    repository_path: str | Path = ".",
    codex_executable: str = DEFAULT_CODEX_EXECUTABLE,
    model: str = DEFAULT_PROJECT_UNDERSTANDING_MODEL,
    timeout_seconds: float = DEFAULT_CODEX_EXEC_TIMEOUT_SECONDS,
    openai_api_key: str | None = None,
    base_environment: Mapping[str, str] | None = None,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    monotonic: Callable[[], float] = time.perf_counter,
) -> ProjectUnderstandingAnswer:
    """Answer a project-understanding question by safely wrapping `codex exec`.

    The prompt is passed on stdin rather than interpolated into a shell command.
    The returned answer includes the formatted final response, token usage when
    present in the Codex transcript, and elapsed wall-clock time.
    """

    question = (user_request or "").strip()
    if not question:
        raise ValueError("user_request must not be empty")

    prompt = build_project_understanding_prompt(question)
    env = build_codex_exec_environment(
        openai_api_key=openai_api_key,
        base_environment=base_environment,
    )
    resolved_codex_executable = resolve_codex_executable(codex_executable, environment=env)
    command = build_codex_exec_command(
        repository_path=repository_path,
        codex_executable=resolved_codex_executable,
        model=model,
    )
    requested_at = _utc_timestamp()
    started = monotonic()
    try:
        completed = runner(
            command,
            input=prompt,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
            env=env,
        )
    except FileNotFoundError as exc:
        raise CodexExecError(
            "Could not start codex exec because the Codex CLI executable was not found. "
            f"Tried `{resolved_codex_executable}`. Set C_LARA_CODEX_EXECUTABLE to the full path "
            "of codex or codex.cmd, or add the npm global bin directory to PATH for the Django process."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        elapsed = monotonic() - started
        raise CodexExecError(
            f"codex exec timed out after {elapsed:.2f}s (limit {timeout_seconds:.2f}s)"
        ) from exc
    except OSError as exc:
        raise CodexExecError(f"Could not start codex exec: {exc}") from exc
    elapsed = monotonic() - started

    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    combined_output = "\n".join([stdout, stderr])
    sandbox_failure_detail = detect_codex_sandbox_access_failure(combined_output)
    if sandbox_failure_detail:
        raise CodexExecError(
            "codex exec completed, but Codex reported that it could not inspect the repository because "
            "the Linux sandbox/command execution layer failed. Check bubblewrap/user-namespace/systemd "
            "restrictions for the Unix user running the Assistant worker. "
            f"Detail: {sandbox_failure_detail}"
        )
    if completed.returncode != 0:
        detail = (stderr or stdout).strip()
        if len(detail) > 500:
            detail = f"{detail[:500]}..."
        raise CodexExecError(f"codex exec failed with exit status {completed.returncode}: {detail}")

    return ProjectUnderstandingAnswer(
        question=question,
        prompt=prompt,
        answer=extract_codex_formatted_answer(stdout),
        model=model,
        prompt_version=PROJECT_UNDERSTANDING_PROMPT_VERSION,
        requested_at=requested_at,
        tokens_used=extract_codex_tokens_used("\n".join([stdout, stderr])),
        elapsed_seconds=elapsed,
        invocation_route="codex-exec",
        repository_path=str(Path(repository_path)),
        command=tuple(command),
        returncode=completed.returncode,
        stderr=stderr,
        raw_stdout=stdout,
    )


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
    requested_at = _utc_timestamp()
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

    metadata_lines = [
        f"- Model: `{result.model}`",
        f"- Prompt version: `{result.prompt_version}`",
        f"- Invocation route: `{result.invocation_route}`",
    ]
    if result.tokens_used is not None:
        metadata_lines.append(f"- Tokens used: `{result.tokens_used}`")
    if result.elapsed_seconds is not None:
        metadata_lines.append(f"- Elapsed seconds: `{result.elapsed_seconds:.2f}`")
    if result.estimated_cost_usd:
        metadata_lines.append(f"- Estimated cost USD: `{result.estimated_cost_usd}`")
    if result.cost_basis:
        metadata_lines.append(f"- Cost basis: `{result.cost_basis}`")
    if result.repository_path:
        metadata_lines.append(f"- Repository path: `{result.repository_path}`")
    if result.returncode is not None:
        metadata_lines.append(f"- Exit status: `{result.returncode}`")
    metadata_lines.extend([
        "- Human assessment: `unreviewed`",
        "- Reviewer notes: _pending_",
    ])
    metadata = "\n".join(metadata_lines)

    command_block = ""
    if result.command:
        command_block = "\n## Codex command\n\n```text\n" + " ".join(result.command) + "\n```\n"

    return f"""# Project-understanding answer ({result.requested_at})

{metadata}

## Question

{result.question}

## Answer

{result.answer}
{command_block}
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
