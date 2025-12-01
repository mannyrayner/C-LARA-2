.PHONY: run-platform

# Launch the Django dev server (runs migrations first). We clear PYTHONPATH
# to avoid host-level contamination (e.g., Windows user profiles with custom
# search paths) and default to python3 unless the caller overrides PYTHON.
PYTHON ?= python3

run-platform:
	cd platform_server && PYTHONPATH= $(PYTHON) manage.py migrate && PYTHONPATH= $(PYTHON) manage.py runserver
