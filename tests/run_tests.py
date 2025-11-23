"""Test runner that logs results to tests/test_results.log."""
from __future__ import annotations

import pathlib
import sys
import unittest


class Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, data: str) -> None:
        for stream in self.streams:
            stream.write(data)

    def flush(self) -> None:
        for stream in self.streams:
            stream.flush()


def main() -> int:
    root = pathlib.Path(__file__).resolve().parent.parent
    src = root / "src"
    sys.path[:0] = [str(src), str(root)]

    log_path = root / "tests" / "test_results.log"
    suite = unittest.defaultTestLoader.discover(start_dir=str(root / "tests"))

    with log_path.open("w", encoding="utf-8") as log_file:
        runner = unittest.TextTestRunner(stream=Tee(sys.stdout, log_file), verbosity=2)
        result = runner.run(suite)

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
