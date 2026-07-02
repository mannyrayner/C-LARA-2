.PHONY: run-platform run-platform-with-q run-platform-with-real-q count-lines list-successfully-converted-legacy-projects

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

# Count tracked lines under key repository folders and print a grand total.
# Using git ls-files keeps local generated experiment artifacts out of the count
# even if a run leaves extra files outside the standard generated/tmp folders.
count-lines:
	@folders="docs experiments platform_server prompts src tests"; total=0; \
	for dir in $$folders; do \
		if [ -d $$dir ]; then \
			count=$$(git ls-files -z -- $$dir | \
				perl -0ne 'print unless m#(^|/)(generated|tmp|media|artifacts)(/|$$)# || m#^docs/few_shot_curation(/|$$)# || m#\.sqlite3$$#' | \
				xargs -0 -r wc -l | awk 'END {print $$1 + 0}'); \
			printf "%-16s %s\n" $$dir $$count; \
			total=$$((total + count)); \
		else \
			printf "%-16s %s\n" $$dir "[missing]"; \
		fi; \
	done; \
	printf "%-16s %s\n" total $$total

# List legacy projects whose first-stage conversion has produced both metadata.json
# and source.zip. Override CLARA if the legacy workspace is outside this repo.
CLARA ?= $(CURDIR)
LEGACY_CONVERTED_PROJECTS_DIR ?= $(CLARA)/CLARADownloadedProjectsFromServer_v3_JSON
LEGACY_CONVERTED_PROJECTS_LIST ?= $(CLARA)/successfully_converted_legacy_projects.tsv

list-successfully-converted-legacy-projects:
	$(PYTHON) scripts/list_converted_legacy_projects.py \
		--input-dir "$(LEGACY_CONVERTED_PROJECTS_DIR)" \
		--output "$(LEGACY_CONVERTED_PROJECTS_LIST)"
