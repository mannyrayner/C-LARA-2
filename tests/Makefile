# Cross-platform test entrypoint that avoids inheriting a host PYTHONPATH.
# We compute the repo root and src path in Python so Windows/Cygwin and POSIX
# behave the same.
.ONESHELL:
.PHONY: test

PYTHON ?= python3

# Use a dedicated helper script so we can log results to test_results.log.
test:
	$(PYTHON) run_tests.py
