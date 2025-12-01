.PHONY: run-platform

# Launch the Django dev server (runs migrations first). We clear PYTHONPATH
# to avoid host-level contamination (e.g., Windows user profiles with custom
# search paths) and default to python3 unless the caller overrides PYTHON.
PYTHON ?= python3

run-platform:
	cd platform_server && \
		PYTHONPATH= DJANGO_SETTINGS_MODULE=platform_server.settings $(PYTHON) manage.py migrate && \
		PYTHONPATH= DJANGO_SETTINGS_MODULE=platform_server.settings $(PYTHON) manage.py runserver
