"""Helpers for restricted C-LARA-2 project-understanding answers."""
from __future__ import annotations

from collections.abc import Callable, Mapping
import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
import json
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
PROJECT_MANAGER_PROMPT_VERSION = "project-manager-v1"
PROJECT_MANAGER_CLASSIFICATION_MARKER = "PROJECT_MANAGER_CLASSIFICATION"
DEFAULT_CODEX_EXECUTABLE = "codex"
DEFAULT_CODEX_EXEC_TIMEOUT_SECONDS = 300.0
DEFAULT_SANDBOX_FAILURE_REVIEW_MODEL = "gpt-4o"

DEFAULT_EVIDENCE_PATHS = (
    "AGENTS.md",
    "docs/global_workspace/",
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
_REPOSITORY_QUOTE_RE = re.compile(r"^(?:\.?/|/)?(?:[A-Za-z0-9_.-]+/)+[^:\n]+:\d+:")
_CODEX_SANDBOX_FAILURE_CONTEXTS = (
    "bwrap",
    "bubblewrap",
    "linux sandbox",
    "current sandbox",
    "sandbox uses bubblewrap",
)
_CODEX_SANDBOX_FAILURE_SYMPTOMS = (
    "failed rtm_newaddr",
    "operation not permitted",
    "local file access is currently blocked",
    "shell commands are blocked",
    "command access is currently blocked",
    "command access is failing",
    "can't access the repository",
    "can’t access the repository",
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

    # Treat a line as a sandbox failure only when it is reporting the live
    # Codex execution context failing, not merely discussing a known issue.
    # Assistant self-queries can legitimately quote docs/issues text containing
    # phrases like "failed rtm_newaddr"; those should not be converted into
    # worker errors unless the transcript itself says access/commands failed.
    for line in cleaned.splitlines():
        line_lower = line.lower()
        # Codex answers to self-understanding questions often include grep-style
        # citations such as `docs/issues/issues/ISSUE-0034.json:10: ...`. Those
        # are repository evidence lines, not live runtime diagnostics.
        if _REPOSITORY_QUOTE_RE.match(line.strip()):
            continue

        has_context = any(marker in line_lower for marker in _CODEX_SANDBOX_FAILURE_CONTEXTS)
        has_symptom = any(marker in line_lower for marker in _CODEX_SANDBOX_FAILURE_SYMPTOMS)
        if not (has_context and has_symptom):
            continue

        direct_access_failure = any(
            marker in line_lower
            for marker in (
                "i cannot",
                "i can't",
                "i can’t",
                "i am unable",
                "i'm unable",
                "cannot inspect",
                "could not inspect",
                "couldn't inspect",
                "unable to inspect",
                "cannot access",
                "can't access",
                "can’t access",
                "command access is currently blocked",
                "command access is failing",
                "shell commands are blocked",
                "local file access is currently blocked",
                "bwrap:",
                "bubblewrap:",
            )
        )
        low_level_bwrap_failure = "failed rtm_newaddr" in line_lower and (
            "bwrap:" in line_lower or "bubblewrap:" in line_lower or "loopback" in line_lower
        )
        if direct_access_failure or low_level_bwrap_failure:
            return line.strip()[:500]
    return ""



def _truncate_for_review(text: str, *, limit: int = 6000) -> str:
    text = text or ""
    if len(text) <= limit:
        return text
    half = limit // 2
    return f"{text[:half]}\n... [truncated] ...\n{text[-half:]}"


async def _review_codex_sandbox_failure_with_ai_async(
    *,
    question: str,
    stdout: str,
    stderr: str,
    detected_detail: str,
    openai_api_key: str | None,
    model: str = DEFAULT_SANDBOX_FAILURE_REVIEW_MODEL,
) -> tuple[bool, str]:
    prompt = f"""You are checking the result of a Codex CLI repository-inspection run.
Decide whether the transcript is a genuine live sandbox/command-access failure,
or whether it is a plausible answer that merely quotes repository text/source code
mentioning old sandbox failures.

Return JSON only, with fields:
- verdict: one of "error", "answer", or "uncertain"
- reason: one short sentence

Classify as "error" only if the transcript itself says Codex could not inspect
the repository in this run (for example live bwrap/bubblewrap/command-access
failure). Classify as "answer" if the transcript appears to answer the user
and sandbox phrases occur only inside quoted files, issue notes, source code, or
other repository evidence.

User question:
{question}

Heuristic detail that triggered review:
{detected_detail}

Codex stdout:
{_truncate_for_review(stdout)}

Codex stderr:
{_truncate_for_review(stderr)}
"""
    client = OpenAIClient(config=OpenAIConfig(api_key=openai_api_key, model=model, timeout_s=30, max_retries=1))
    try:
        payload = await client.chat_json(prompt, model=model, temperature=None)
    finally:
        await client.aclose()
    verdict = str(payload.get("verdict", "uncertain")).strip().lower()
    reason = str(payload.get("reason", "")).strip()[:500]
    return verdict == "error", f"reviewer verdict={verdict}; reason={reason or '(none)'}"


def review_codex_sandbox_failure_with_ai(
    *,
    question: str,
    stdout: str,
    stderr: str,
    detected_detail: str,
    openai_api_key: str | None,
    model: str = DEFAULT_SANDBOX_FAILURE_REVIEW_MODEL,
) -> tuple[bool, str]:
    return asyncio.run(
        _review_codex_sandbox_failure_with_ai_async(
            question=question,
            stdout=stdout,
            stderr=stderr,
            detected_detail=detected_detail,
            openai_api_key=openai_api_key,
            model=model,
        )
    )


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
    repository_commit_sha: str = ""
    command: tuple[str, ...] | None = None
    returncode: int | None = None
    stderr: str = ""
    raw_stdout: str = ""
    estimated_cost_usd: str = ""
    cost_basis: str = ""
    mode: str = "assistant"
    collaborator_username: str = ""
    collaborator_role: str = ""
    material_project_evidence: bool = False
    workspace_review_recommended: bool = False
    review_explanation: str = ""


class CodexExecError(RuntimeError):
    """Raised when the `codex exec` project-understanding call cannot complete."""


def resolve_repository_commit_sha(repository_path: str | Path) -> str:
    """Capture the trusted checkout commit without relying on model output."""
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(repository_path),
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    sha = (completed.stdout or "").strip()
    return sha if completed.returncode == 0 and re.fullmatch(r"[0-9a-f]{40}", sha) else ""


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


def build_project_manager_prompt(
    user_message: str,
    *,
    collaborator_username: str,
    collaborator_role: str,
    prompt_version: str = PROJECT_MANAGER_PROMPT_VERSION,
) -> str:
    """Build the repository-mediated Project Manager prompt."""
    message = (user_message or "").strip()
    username = (collaborator_username or "").strip()
    role = (collaborator_role or "").strip()
    if not message:
        raise ValueError("user_message must not be empty")
    if not username or not role:
        raise ValueError("collaborator identity and role must not be empty")
    return f"""You are acting as the established C-LARA-2 AI project manager.

Prompt version: {prompt_version}

First read and follow `AGENTS.md`. Then inspect `docs/global_workspace/README.md`,
`docs/global_workspace/project-intentions.md`, and the live `docs/global_workspace/current_state.*`.
Inspect relevant roadmaps, canonical issue JSON, code, tests, commits, or other repository evidence
when useful. Follow: orient globally -> handle this interaction -> reflect globally.

Authenticated collaborator: {username}
Project role: {role}
Authority: this collaborator may provide attributed project evidence and contextual information but
does not, through this interaction, authorize canonical repository or global-workspace mutation.

Respond conversationally as an informed project collaborator. Distinguish direct human observation,
second-hand reports, project-manager inference, uncertainty, and decisions requiring Manny or another
authorized human. Do not treat every report as established fact. Do not mutate repository state.
Do not require or manufacture affective language. Cite repository paths when they help.

End the response with exactly one machine-readable line in this form:
{PROJECT_MANAGER_CLASSIFICATION_MARKER}: {{"material_project_evidence": true_or_false,
"workspace_review_recommended": true_or_false, "explanation": "short explanation"}}
The classification must reflect whether the message contains material new evidence that could change
the global project assessment. The line is audit metadata and will not be shown as conversational text.

Collaborator message:
{message}
"""


def parse_project_manager_answer(answer: str) -> tuple[str, bool, bool, str]:
    """Separate the conversational answer from its final evidence classification."""
    lines = (answer or "").rstrip().splitlines()
    prefix = f"{PROJECT_MANAGER_CLASSIFICATION_MARKER}:"
    if not lines or not lines[-1].startswith(prefix):
        return (answer or "").strip(), False, True, "Classification missing from Codex response; manual review is recommended."
    try:
        payload = json.loads(lines[-1][len(prefix):].strip())
    except json.JSONDecodeError:
        return (answer or "").strip(), False, True, "Classification was not valid JSON; manual review is recommended."
    conversational = "\n".join(lines[:-1]).strip()
    return (
        conversational,
        bool(payload.get("material_project_evidence")),
        bool(payload.get("workspace_review_recommended")),
        str(payload.get("explanation") or "").strip()[:1000],
    )


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
    sandbox_failure_reviewer: Callable[..., tuple[bool, str]] | None = None,
    sandbox_failure_review_model: str = DEFAULT_SANDBOX_FAILURE_REVIEW_MODEL,
    mode: str = "assistant",
    collaborator_username: str = "",
    collaborator_role: str = "",
    commit_sha_resolver: Callable[[str | Path], str] = resolve_repository_commit_sha,
) -> ProjectUnderstandingAnswer:
    """Answer a project-understanding question by safely wrapping `codex exec`.

    The prompt is passed on stdin rather than interpolated into a shell command.
    The returned answer includes the formatted final response, token usage when
    present in the Codex transcript, and elapsed wall-clock time.
    """

    question = (user_request or "").strip()
    if not question:
        raise ValueError("user_request must not be empty")

    if mode == "project_manager":
        prompt = build_project_manager_prompt(
            question,
            collaborator_username=collaborator_username,
            collaborator_role=collaborator_role,
        )
        prompt_version = PROJECT_MANAGER_PROMPT_VERSION
    elif mode == "assistant":
        prompt = build_project_understanding_prompt(question)
        prompt_version = PROJECT_UNDERSTANDING_PROMPT_VERSION
    else:
        raise ValueError(f"unknown project-understanding mode: {mode}")
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
    repository_commit_sha = commit_sha_resolver(repository_path)
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
    sandbox_failure_detail = detect_codex_sandbox_access_failure(stderr)
    sandbox_failure_stream = "stderr"
    if not sandbox_failure_detail:
        sandbox_failure_detail = detect_codex_sandbox_access_failure(stdout)
        sandbox_failure_stream = "stdout"
    if sandbox_failure_detail:
        reviewer_note = "reviewer not run"
        reviewer_confirms_error = True
        reviewer = sandbox_failure_reviewer or review_codex_sandbox_failure_with_ai
        if openai_api_key or sandbox_failure_reviewer is not None:
            try:
                reviewer_confirms_error, reviewer_note = reviewer(
                    question=question,
                    stdout=stdout,
                    stderr=stderr,
                    detected_detail=sandbox_failure_detail,
                    openai_api_key=openai_api_key,
                    model=sandbox_failure_review_model,
                )
            except Exception as exc:
                reviewer_note = f"reviewer failed: {exc.__class__.__name__}: {exc}"
                reviewer_confirms_error = True
        if reviewer_confirms_error:
            raise CodexExecError(
                "codex exec completed, but Codex reported that it could not inspect the repository because "
                "the Linux sandbox/command execution layer failed. Check bubblewrap/user-namespace/systemd "
                "restrictions for the Unix user running the Assistant worker. "
                f"Detected in Codex {sandbox_failure_stream}. Detail: {sandbox_failure_detail}. {reviewer_note}"
            )
    if completed.returncode != 0:
        detail = (stderr or stdout).strip()
        if len(detail) > 500:
            detail = f"{detail[:500]}..."
        raise CodexExecError(f"codex exec failed with exit status {completed.returncode}: {detail}")

    answer = extract_codex_formatted_answer(stdout)
    material_project_evidence = False
    workspace_review_recommended = False
    review_explanation = ""
    if mode == "project_manager":
        answer, material_project_evidence, workspace_review_recommended, review_explanation = (
            parse_project_manager_answer(answer)
        )
    return ProjectUnderstandingAnswer(
        question=question,
        prompt=prompt,
        answer=answer,
        model=model,
        prompt_version=prompt_version,
        requested_at=requested_at,
        tokens_used=extract_codex_tokens_used("\n".join([stdout, stderr])),
        elapsed_seconds=elapsed,
        invocation_route="codex-exec",
        repository_path=str(Path(repository_path)),
        repository_commit_sha=repository_commit_sha,
        command=tuple(command),
        returncode=completed.returncode,
        stderr=stderr,
        raw_stdout=stdout,
        mode=mode,
        collaborator_username=collaborator_username,
        collaborator_role=collaborator_role,
        material_project_evidence=material_project_evidence,
        workspace_review_recommended=workspace_review_recommended,
        review_explanation=review_explanation,
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
