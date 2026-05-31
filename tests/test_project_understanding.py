from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.project_understanding import (
    DEFAULT_PROJECT_UNDERSTANDING_MODEL,
    PROJECT_UNDERSTANDING_PROMPT_VERSION,
    ProjectUnderstandingAnswer,
    answer_project_understanding_question,
    build_project_understanding_prompt,
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
        self.assertIn("## Prompt sent to model", rendered)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = write_project_understanding_record(result, output_dir=tmpdir)
            self.assertEqual(Path(tmpdir) / "project-understanding-20260531T100000Z.md", path)
            self.assertIn("An answer with citations.", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
