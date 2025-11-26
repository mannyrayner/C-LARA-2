"""Run the test suite via pytest, logging output to tests/test_results.log."""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys


def _pytest_available() -> bool:
    try:
        import pytest  # noqa: F401
    except Exception:  # pragma: no cover - exercised in user envs
        return False
    return True


def main() -> int:
    root = pathlib.Path(__file__).resolve().parent.parent
    log_path = root / "tests" / "test_results.log"
    env = os.environ.copy()
    env_paths = [str(root / "src"), str(root), env.get("PYTHONPATH", "")]
    env["PYTHONPATH"] = os.pathsep.join(p for p in env_paths if p)

    if _pytest_available():
        asyncio_args: list[str] = []
        try:
            import pytest_asyncio  # noqa: F401
        except Exception:  # pragma: no cover - optional dependency
            asyncio_args = []
        else:
            asyncio_args = ["--asyncio-mode=auto"]

        cmd = [sys.executable, "-m", "pytest", "-s", *asyncio_args]
        proc = subprocess.run(cmd, cwd=root, env=env, capture_output=True, text=True)
        log_path.write_text(proc.stdout)
        sys.stdout.write(proc.stdout)
        if proc.stderr:
            sys.stderr.write(proc.stderr)
        return proc.returncode

    # Defensive fallback if pytest is missing: run the unittest suite directly.
    import unittest

    sys.path[:0] = [str(root / "src"), str(root)]
    suite = unittest.defaultTestLoader.discover(start_dir=str(root / "tests"))
    with log_path.open("w", encoding="utf-8") as log_file:
        runner = unittest.TextTestRunner(stream=log_file, verbosity=2)
        result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
