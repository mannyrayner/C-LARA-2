.PHONY: count-lines run-platform run-platform-with-q run-platform-with-real-q merge-project-migrations

# Launch the Django dev server (runs migrations first). We clear PYTHONPATH
# to avoid host-level contamination (e.g., Windows user profiles with custom
# search paths) and default to python3 unless the caller overrides PYTHON.
PYTHON ?= python3

count-lines:
	@docs_lines=$$(find docs -type f -print0 2>/dev/null | xargs -0 cat 2>/dev/null | wc -l); \
	py_lines=$$(find platform_server/projects -maxdepth 1 -name '*.py' -print0 2>/dev/null | xargs -0 cat 2>/dev/null | wc -l); \
	template_lines=$$(find platform_server/projects/templates -type f -print0 2>/dev/null | xargs -0 cat 2>/dev/null | wc -l); \
	status_lines=$$(find platform_server/projects/status -type f -print0 2>/dev/null | xargs -0 cat 2>/dev/null | wc -l); \
	total_lines=$$((docs_lines + py_lines + template_lines + status_lines)); \
	echo "docs: $$docs_lines"; \
	echo "platform_server/projects/*.py: $$py_lines"; \
	echo "platform_server/projects/templates: $$template_lines"; \
	echo "platform_server/projects/status: $$status_lines"; \
	echo "total: $$total_lines"

run-platform:
	cd platform_server && \
		PYTHONPATH= DJANGO_SETTINGS_MODULE=platform_server.settings $(PYTHON) manage.py makemigrations --merge --noinput projects || true && \
		PYTHONPATH= DJANGO_SETTINGS_MODULE=platform_server.settings $(PYTHON) manage.py migrate && \
		PYTHONPATH= DJANGO_SETTINGS_MODULE=platform_server.settings $(PYTHON) manage.py runserver

# Run Django with the bundled/local qcluster command.
run-platform-with-q:
	cd platform_server && \
		PYTHONPATH= DJANGO_SETTINGS_MODULE=platform_server.settings $(PYTHON) manage.py makemigrations --merge --noinput projects || true && \
		PYTHONPATH= DJANGO_SETTINGS_MODULE=platform_server.settings $(PYTHON) manage.py migrate && \
		(PYTHONPATH= DJANGO_SETTINGS_MODULE=platform_server.settings $(PYTHON) manage.py qcluster & ) && \
		PYTHONPATH= DJANGO_SETTINGS_MODULE=platform_server.settings $(PYTHON) manage.py runserver

# Run Django with a real django-q install (if present) by setting DJANGO_Q_USE_REAL.
run-platform-with-real-q:
	cd platform_server && \
		PYTHONPATH= DJANGO_Q_USE_REAL=1 DJANGO_SETTINGS_MODULE=platform_server.settings $(PYTHON) manage.py makemigrations --merge --noinput projects || true && \
		PYTHONPATH= DJANGO_Q_USE_REAL=1 DJANGO_SETTINGS_MODULE=platform_server.settings $(PYTHON) manage.py migrate && \
		(PYTHONPATH= DJANGO_Q_USE_REAL=1 DJANGO_SETTINGS_MODULE=platform_server.settings $(PYTHON) manage.py qcluster & ) && \
		PYTHONPATH= DJANGO_Q_USE_REAL=1 DJANGO_SETTINGS_MODULE=platform_server.settings $(PYTHON) manage.py runserver

# Resolve conflicting leaf migrations in the projects app when branch histories diverge.
merge-project-migrations:
	cd platform_server && \
		PYTHONPATH= DJANGO_SETTINGS_MODULE=platform_server.settings $(PYTHON) manage.py makemigrations --merge projects
