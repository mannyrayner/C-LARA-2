import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "src"

# Ensure project packages are importable when running pytest directly
sys.path[:0] = [str(SRC), str(ROOT)]
