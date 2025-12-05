.PHONY: run-platform

# Launch the Django dev server (runs migrations first). We clear PYTHONPATH
# to avoid host-level contamination (e.g., Windows user profiles with custom
# search paths) and default to python3 unless the caller overrides PYTHON.
PYTHON ?= python3

run-platform:
	cd platform_server && \
		PYTHONPATH= DJANGO_SETTINGS_MODULE=platform_server.settings $(PYTHON) manage.py migrate && \
		PYTHONPATH= DJANGO_SETTINGS_MODULE=platform_server.settings $(PYTHON) manage.py runserver

# Run both the Django dev server and the (stub) Django Q cluster.
run-platform-with-q:
	cd platform_server && \
		PYTHONPATH= DJANGO_SETTINGS_MODULE=platform_server.settings $(PYTHON) manage.py migrate && \
		(PYTHONPATH= DJANGO_SETTINGS_MODULE=platform_server.settings $(PYTHON) manage.py qcluster & ) && \
		PYTHONPATH= DJANGO_SETTINGS_MODULE=platform_server.settings $(PYTHON) manage.py runserver

# Run the Django dev server with a real django-q installation (requires django-q2
# or compatible to be installed in your environment). This uses DJANGO_Q_USE_REAL
# to avoid the local stub so the real qcluster is started.
run-platform-with-real-q:
	cd platform_server && \
		PYTHONPATH= DJANGO_Q_USE_REAL=1 DJANGO_SETTINGS_MODULE=platform_server.settings $(PYTHON) manage.py migrate && \
		(PYTHONPATH= DJANGO_Q_USE_REAL=1 DJANGO_SETTINGS_MODULE=platform_server.settings $(PYTHON) manage.py qcluster & ) && \
		PYTHONPATH= DJANGO_Q_USE_REAL=1 DJANGO_SETTINGS_MODULE=platform_server.settings $(PYTHON) manage.py runserver
