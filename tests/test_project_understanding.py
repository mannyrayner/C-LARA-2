from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.project_understanding import (
    DEFAULT_PROJECT_UNDERSTANDING_MODEL,
    PROJECT_UNDERSTANDING_PROMPT_VERSION,
    CodexExecError,
    ProjectUnderstandingAnswer,
    answer_project_understanding_question,
    answer_project_understanding_question_with_codex_exec,
    build_codex_exec_command,
    build_codex_exec_environment,
    build_project_understanding_prompt,
    detect_codex_sandbox_access_failure,
    extract_codex_formatted_answer,
    extract_codex_tokens_used,
    resolve_codex_executable,
    render_project_understanding_record,
    write_project_understanding_record,
)


class FakeProjectUnderstandingClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.closed = False

    async def responses_text(self, prompt: str, **kwargs: object) -> str:
        self.calls.append({"prompt": prompt, **kwargs})
        return "C-LARA-2 supports repository-grounded project answers in this test."

    async def aclose(self) -> None:
        self.closed = True


class FakeCodexExecRunner:
    def __init__(self, stdout: str, returncode: int = 0, stderr: str = "") -> None:
        self.stdout = stdout
        self.returncode = returncode
        self.stderr = stderr
        self.calls: list[dict[str, object]] = []

    def __call__(self, command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        self.calls.append({"command": command, **kwargs})
        return subprocess.CompletedProcess(
            args=command,
            returncode=self.returncode,
            stdout=self.stdout,
            stderr=self.stderr,
        )


class FakeClock:
    def __init__(self) -> None:
        self.values = iter([10.0, 12.75])

    def __call__(self) -> float:
        return next(self.values)


class ProjectUnderstandingTests(unittest.IsolatedAsyncioTestCase):
    def test_build_prompt_wraps_question_with_safety_and_evidence_rules(self) -> None:
        prompt = build_project_understanding_prompt("What is ISSUE-0034?")

        self.assertIn("Prompt version: project-understanding-v1", prompt)
        self.assertIn("User question:\nWhat is ISSUE-0034?", prompt)
        self.assertIn("docs/roadmap/", prompt)
        self.assertIn("docs/issues/", prompt)
        self.assertIn("Distinguish implemented functionality", prompt)
        self.assertIn("Cite supporting repository file paths", prompt)
        self.assertIn("Do not expose secrets", prompt)

    def test_build_prompt_rejects_empty_question(self) -> None:
        with self.assertRaises(ValueError):
            build_project_understanding_prompt("   ")

    def test_build_codex_exec_command_uses_argument_vector(self) -> None:
        command = build_codex_exec_command(
            repository_path="/srv/C-LARA-2",
            codex_executable="/usr/local/bin/codex",
            model="gpt-5.3-codex",
        )

        self.assertEqual(
            [
                "/usr/local/bin/codex",
                "exec",
                "--cd",
                "/srv/C-LARA-2",
                "--sandbox",
                "read-only",
                "--ephemeral",
                "--model",
                "gpt-5.3-codex",
                "-",
            ],
            command,
        )

    def test_build_codex_exec_environment_preserves_runtime_auth_inputs(self) -> None:
        env = build_codex_exec_environment(
            openai_api_key="test-key",
            base_environment={"PATH": "/bin", "CODEX_HOME": "/srv/codex-home", "SECRET": "do-not-copy"},
        )

        self.assertEqual("test-key", env["OPENAI_API_KEY"])
        self.assertEqual("/bin", env["PATH"])
        self.assertEqual("/srv/codex-home", env["CODEX_HOME"])
        self.assertNotIn("SECRET", env)

    def test_build_codex_exec_environment_allows_cached_codex_login_without_api_key(self) -> None:
        env = build_codex_exec_environment(
            base_environment={"PATH": "/bin", "CODEX_HOME": "/srv/codex-home"},
        )

        self.assertEqual("/srv/codex-home", env["CODEX_HOME"])
        self.assertNotIn("OPENAI_API_KEY", env)

    def test_resolve_codex_executable_checks_windows_npm_bin(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            npm_dir = Path(tmpdir) / "npm"
            npm_dir.mkdir()
            codex_cmd = npm_dir / "codex.cmd"
            codex_cmd.write_text("@echo off\n", encoding="utf-8")

            self.assertEqual(
                str(codex_cmd),
                resolve_codex_executable(
                    "codex",
                    environment={"PATH": "", "APPDATA": tmpdir, "OPENAI_API_KEY": "test-key"},
                ),
            )

    def test_resolve_codex_executable_checks_unix_service_locations(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            local_bin = Path(tmpdir) / ".local" / "bin"
            local_bin.mkdir(parents=True)
            codex_bin = local_bin / "codex"
            codex_bin.write_text("#!/bin/sh\n", encoding="utf-8")

            self.assertEqual(
                str(codex_bin),
                resolve_codex_executable(
                    "codex",
                    environment={"PATH": "", "HOME": tmpdir},
                ),
            )

    def test_resolve_codex_executable_expands_configured_absolute_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            bin_dir = Path(tmpdir) / "bin"
            bin_dir.mkdir()
            codex_bin = bin_dir / "codex"
            codex_bin.write_text("#!/bin/sh\n", encoding="utf-8")

            self.assertEqual(
                str(codex_bin),
                resolve_codex_executable(
                    "$CODEX_TEST_BIN/codex",
                    environment={"PATH": "", "CODEX_TEST_BIN": str(bin_dir)},
                ),
            )

    def test_resolve_codex_executable_does_not_crash_on_permission_denied_probe(self) -> None:
        with patch.object(Path, "exists", side_effect=PermissionError("permission denied")):
            self.assertEqual(
                "/home/ubuntu/.local/bin/codex",
                resolve_codex_executable(
                    "/home/ubuntu/.local/bin/codex",
                    environment={"PATH": ""},
                ),
            )

    def test_codex_exec_missing_executable_raises_friendly_error(self) -> None:
        def missing_runner(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
            raise FileNotFoundError("no such file")

        with self.assertRaisesRegex(CodexExecError, "Codex CLI executable was not found"):
            answer_project_understanding_question_with_codex_exec(
                "Summarise the project.",
                repository_path="/srv/C-LARA-2",
                codex_executable="missing-codex",
                openai_api_key="test-key",
                base_environment={"PATH": ""},
                runner=missing_runner,
            )

    def test_detect_codex_sandbox_access_failure_identifies_bwrap_namespace_block(self) -> None:
        detail = detect_codex_sandbox_access_failure(
            "codex\n"
            "I cannot summarize because local file access is currently blocked "
            "(bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted)."
        )

        self.assertIn("local file access is currently blocked", detail)

    def test_detect_codex_sandbox_access_failure_prefers_specific_symptom_line(self) -> None:
        detail = detect_codex_sandbox_access_failure(
            "warning: Codex's Linux sandbox uses bubblewrap and needs access to create user namespaces.\n"
            "I cannot summarize because local file access is currently blocked "
            "(`bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted`)."
        )

        self.assertIn("local file access is currently blocked", detail)
        self.assertNotIn("needs access to create user namespaces", detail)

    def test_detect_codex_sandbox_access_failure_flags_blocked_shell_transcript(self) -> None:
        detail = detect_codex_sandbox_access_failure(
            "I can't access the repository contents in this session "
            "(shell commands are blocked by the current sandbox)."
        )

        self.assertIn("shell commands are blocked", detail)

    def test_codex_exec_successful_process_with_sandbox_failure_raises_error(self) -> None:
        runner = FakeCodexExecRunner(
            """OpenAI Codex v0.137.0
--------
codex
I cannot reliably summarize this repository because local file access is currently blocked (`bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted`).
tokens used
7,263
""",
            returncode=0,
        )

        with self.assertRaisesRegex(CodexExecError, "could not inspect the repository"):
            answer_project_understanding_question_with_codex_exec(
                "Summarise the project.",
                repository_path="/srv/C-LARA-2",
                openai_api_key="test-key",
                base_environment={"PATH": "/bin"},
                runner=runner,
            )

    def test_extract_codex_transcript_answer_and_tokens(self) -> None:
        transcript = """OpenAI Codex v0.135.0
--------
codex
I am checking files.
exec
rg README.md
 succeeded in 100ms:
3:C-LARA-2 is ...

codex
- C-LARA-2 is a platform.
- It cites files.
tokens used
41,940
"""

        self.assertEqual(41940, extract_codex_tokens_used(transcript))
        self.assertEqual(
            "- C-LARA-2 is a platform.\n- It cites files.",
            extract_codex_formatted_answer(transcript),
        )

    def test_answer_project_understanding_question_with_codex_exec(self) -> None:
        runner = FakeCodexExecRunner(
            """OpenAI Codex v0.135.0
--------
codex
- Repository-grounded answer with citations.
""",
            stderr="tokens used\n1,234\n",
        )

        result = answer_project_understanding_question_with_codex_exec(
            "Summarise the project.",
            repository_path="/srv/C-LARA-2",
            openai_api_key="test-key",
            base_environment={"PATH": "/bin"},
            runner=runner,
            monotonic=FakeClock(),
        )

        self.assertEqual("Summarise the project.", result.question)
        self.assertEqual("- Repository-grounded answer with citations.", result.answer)
        self.assertEqual(1234, result.tokens_used)
        self.assertEqual(2.75, result.elapsed_seconds)
        self.assertEqual("codex-exec", result.invocation_route)
        self.assertEqual("/srv/C-LARA-2", result.repository_path)
        self.assertEqual(0, result.returncode)
        self.assertEqual(1, len(runner.calls))
        call = runner.calls[0]
        self.assertEqual(
            [
                "codex",
                "exec",
                "--cd",
                "/srv/C-LARA-2",
                "--sandbox",
                "read-only",
                "--ephemeral",
                "--model",
                DEFAULT_PROJECT_UNDERSTANDING_MODEL,
                "-",
            ],
            call["command"],
        )
        self.assertIn("Summarise the project.", call["input"])
        self.assertFalse(call.get("check"))
        self.assertEqual("utf-8", call["encoding"])
        self.assertEqual("replace", call["errors"])
        self.assertEqual({"PATH": "/bin", "OPENAI_API_KEY": "test-key"}, call["env"])

    async def test_answer_project_understanding_question_calls_responses_model(self) -> None:
        client = FakeProjectUnderstandingClient()

        result = await answer_project_understanding_question(
            "Summarize the issue registry.",
            client=client,  # type: ignore[arg-type]
            op_id="understanding-test",
        )

        self.assertEqual("Summarize the issue registry.", result.question)
        self.assertEqual(DEFAULT_PROJECT_UNDERSTANDING_MODEL, result.model)
        self.assertEqual(PROJECT_UNDERSTANDING_PROMPT_VERSION, result.prompt_version)
        self.assertEqual("C-LARA-2 supports repository-grounded project answers in this test.", result.answer)
        self.assertFalse(client.closed)
        self.assertEqual(1, len(client.calls))
        call = client.calls[0]
        self.assertEqual(DEFAULT_PROJECT_UNDERSTANDING_MODEL, call["model"])
        self.assertEqual("medium", call["reasoning_effort"])
        self.assertIn("Summarize the issue registry.", call["prompt"])

    def test_render_and_write_project_understanding_record(self) -> None:
        result = ProjectUnderstandingAnswer(
            question="What is implemented?",
            prompt="Wrapped prompt",
            answer="An answer with citations.",
            model="gpt-5.3-codex",
            prompt_version="project-understanding-v1",
            requested_at="2026-05-31T10:00:00Z",
        )

        rendered = render_project_understanding_record(result)
        self.assertIn("Human assessment: `unreviewed`", rendered)
        self.assertIn("Invocation route: `responses-api`", rendered)
        self.assertIn("## Prompt sent to model", rendered)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = write_project_understanding_record(result, output_dir=tmpdir)
            self.assertEqual(Path(tmpdir) / "project-understanding-20260531T100000Z.md", path)
            self.assertIn("An answer with citations.", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
