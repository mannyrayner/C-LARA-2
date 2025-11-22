PATHSEP := $(shell python -c "import os; print(os.pathsep)")

ROOT := $(abspath $(CURDIR)/..)
PYTHONPATH := $(ROOT)$(PATHSEP)$(ROOT)/src

.PHONY: test

test:
	PYTHONPATH="$(PYTHONPATH)" python -m unittest
