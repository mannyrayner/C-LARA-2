# Cross-platform test entrypoint that avoids inheriting a host PYTHONPATH.
# We compute the repo root and src path in Python so Windows/Cygwin and POSIX
# behave the same.
.ONESHELL:
.PHONY: test

PYTHON ?= python3

# Use a heredoc to keep quoting simple across shells.
test:
	$(PYTHON) - <<-'PY'
	import pathlib, sys, unittest

	ROOT = pathlib.Path(__file__).resolve().parent.parent
	SRC = ROOT / 'src'
	sys.path[:0] = [str(SRC), str(ROOT)]
	unittest.main(module=None)
	PY
