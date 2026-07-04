#!/usr/bin/env python3
"""Render human-readable Markdown companions for docs/issues issue JSON files."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ISSUES_DIR = ROOT / "docs" / "issues" / "issues"


def load_issue(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def wrap_notes(notes: str) -> str:
    paragraphs = []
    for paragraph in notes.strip().split("\n\n"):
        paragraph = paragraph.strip()
        if paragraph:
            paragraphs.append(
                textwrap.fill(
                    paragraph,
                    width=100,
                    break_long_words=False,
                    break_on_hyphens=False,
                )
            )
    return "\n\n".join(paragraphs) if paragraphs else "_No notes._"


def render_issue(path: Path) -> str:
    issue = load_issue(path)
    dependencies = issue.get("dependencies") or []
    dependency_text = ", ".join(f"[{dep}]({dep}.md)" for dep in dependencies) if dependencies else "None"
    deadline = issue.get("deadline") or "None"

    return f"""# {issue['issue_id']}: {issue['title']}

- **Status:** {issue['state']}
- **Priority:** {issue['priority']}
- **Created:** {issue['created_at']}
- **Updated:** {issue['updated_at']}
- **Origin:** {issue['origin']}
- **Deadline:** {deadline}
- **Dependencies:** {dependency_text}
- **Canonical JSON:** [{path.name}]({path.name})

## Notes

{wrap_notes(issue.get('notes') or '')}
"""


def main() -> int:
    for issue_path in sorted(ISSUES_DIR.glob("ISSUE-*.json")):
        issue_path.with_suffix(".md").write_text(render_issue(issue_path), encoding="utf-8")
    print("Rendered issue Markdown companions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
