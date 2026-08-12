from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_global_workspace_layout_and_root_instructions() -> None:
    workspace = ROOT / "docs" / "global_workspace"

    assert (ROOT / "AGENTS.md").is_file()
    assert (workspace / "README.md").is_file()
    assert (workspace / "project-intentions.md").is_file()
    assert not (ROOT / "docs" / "workplan").exists()

    agents_text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "orient globally → perform local task → reflect globally" in agents_text
    assert "do not silently edit approved global-workspace state" in agents_text

    intentions = (workspace / "project-intentions.md").read_text(encoding="utf-8")
    for goal_number in range(1, 6):
        assert f"GOAL-{goal_number}:" in intentions
