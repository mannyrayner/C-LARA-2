# Cross-platform test entrypoint that avoids inheriting a host PYTHONPATH.
# We compute the repo root and src path in Python so Windows/Cygwin and POSIX
# behave the same.
.ONESHELL:
.PHONY: test

PY_SCRIPT=import pathlib,sys,unittest; \
  ROOT=pathlib.Path.cwd().parent; \
  SRC=ROOT / 'src'; \
  sys.path[:0]=[str(SRC), str(ROOT)]; \
  unittest.main(module=None)

test:
	PYTHONPATH= python -c "$(PY_SCRIPT)"
