from pathlib import Path
import subprocess


def test_issues_registry_validator_passes() -> None:
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        ["python", "scripts/validate_issues_registry.py"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
