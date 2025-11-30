"""Run the test suite via pytest, logging output to tests/test_results.log."""
from __future__ import annotations

import os
import pathlib
import shutil
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
    artifacts_root = root / "tests" / "artifacts"

    # Start from a clean slate so fresh audio/HTML artifacts are generated on
    # each run. This avoids confusing leftovers from previous executions when
    # reviewing outputs.
    if artifacts_root.exists():
        shutil.rmtree(artifacts_root)

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
        with log_path.open("w", encoding="utf-8") as log_file:
            proc = subprocess.Popen(
                cmd,
                cwd=root,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            assert proc.stdout
            for line in proc.stdout:
                sys.stdout.write(line)
                log_file.write(line)
            proc.wait()
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
