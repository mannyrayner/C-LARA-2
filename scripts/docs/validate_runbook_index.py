#!/usr/bin/env python3
from pathlib import Path
import re
root = Path(__file__).resolve().parents[2]
howto = root / "docs/howto"
files = {}
for path in howto.glob("[0-9][0-9]_*.md"):
    step = int(path.name[:2]); files.setdefault(step, []).append(path.name)
duplicates = {step: names for step, names in files.items() if len(names) != 1}
if duplicates: raise SystemExit(f"duplicate runbook steps: {duplicates}")
index = (howto / "README.md").read_text(encoding="utf-8")
links = re.findall(r"\((\d\d_[^)]+\.md)\)", index)
if sorted(links) != sorted(name for names in files.values() for name in names):
    raise SystemExit("README runbook links do not exactly match numbered runbook files")
print(f"validated {len(files)} numbered runbook(s)")
