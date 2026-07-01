SHELL := /usr/bin/env bash

ROOT_DIR := $(abspath ../../../..)
PLATFORM_DIR := $(ROOT_DIR)/platform_server
PYTHON ?= python3
RUN ?= 0

CORPUS_USER ?= mannyrayner
LANGUAGES ?= en,fr,de
LANGUAGE_MATCH ?= exact
SPLIT_SEED ?= mwe-focused-multilingual-v1
DEVELOPMENT_PROJECT_FRACTION ?= 0.50
VALIDATION_PROJECT_FRACTION ?= 0.25
MAX_DEVELOPMENT_SEGMENTS ?= 600
MAX_VALIDATION_SEGMENTS ?= 300
MAX_TEST_SEGMENTS ?= 600
SPLITS ?= development,validation,test
RUN_LABEL_PREFIX ?= mwe_annotation_refresh_v1
PROJECT_IDS ?=
SPLIT_MANIFEST ?= $(CORPUS_SPLIT_DIR)/multilingual_split_manifest.json
STAGE_PARAMETERS ?= config/stage_parameters.json

GENERATED_DIR := generated
CORPUS_SPLIT_DIR := $(abspath $(GENERATED_DIR))/corpus_splits
PY_OS := $(shell $(PYTHON) -c 'import os; print(os.name)' 2>/dev/null || echo posix)
python_path = $(shell if [ "$(PY_OS)" = "nt" ] && command -v cygpath >/dev/null 2>&1; then cygpath -am "$(1)"; else printf '%s' "$(1)"; fi)
PY_CORPUS_SPLIT_DIR := $(call python_path,$(CORPUS_SPLIT_DIR))
PY_SPLIT_MANIFEST := $(call python_path,$(abspath $(SPLIT_MANIFEST)))
PY_STAGE_PARAMETERS := $(call python_path,$(abspath $(STAGE_PARAMETERS)))

MANAGE := cd $(PLATFORM_DIR) && PYTHONPATH= DJANGO_SETTINGS_MODULE=platform_server.settings $(PYTHON) manage.py

.PHONY: help prepare extract-split-corpus refresh-annotations refresh-annotations-dry-run refresh-upstream refresh-upstream-dry-run validate-config clean

help:
	@echo "Focused MWE experiments (multilingual)"
	@echo
	@echo "Targets:"
	@echo "  extract-split-corpus  Extract segment records and create project-separated dev/validation/test splits"
	@echo "  refresh-annotations   Rerun selected projects through segmentation_phase_2 -> translation -> mwe -> lemma -> gloss"
	@echo "  validate-config       Validate stage-parameter JSON used by refresh-annotations"
	@echo "  clean                 Remove generated experiment artifacts"
	@echo
	@echo "Typical setup:"
	@echo "  1. make extract-split-corpus"
	@echo "  2. make refresh-annotations RUN=1"
	@echo "  3. make extract-split-corpus   # export refreshed segment records for judging"
	@echo
	@echo "Important variables:"
	@echo "  RUN=$(RUN)"
	@echo "  CORPUS_USER=$(CORPUS_USER)"
	@echo "  LANGUAGES=$(LANGUAGES)"
	@echo "  SPLIT_SEED=$(SPLIT_SEED)"
	@echo "  CORPUS_SPLIT_DIR=$(CORPUS_SPLIT_DIR)"
	@echo "  SPLIT_MANIFEST=$(SPLIT_MANIFEST)"
	@echo "  PROJECT_IDS=$(PROJECT_IDS)"
	@echo "  RUN_LABEL_PREFIX=$(RUN_LABEL_PREFIX)"
	@echo "  STAGE_PARAMETERS=$(STAGE_PARAMETERS)"

prepare:
	@mkdir -p $(GENERATED_DIR)

validate-config:
	@test -f "$(STAGE_PARAMETERS)" || (echo "Missing $(STAGE_PARAMETERS)" && exit 1)
	@python -m json.tool "$(STAGE_PARAMETERS)" >/dev/null
	@echo "Config OK: $(STAGE_PARAMETERS)"

extract-split-corpus: prepare
	$(MANAGE) extract_mwe_corpus \
		--username "$(CORPUS_USER)" \
		--languages "$(LANGUAGES)" \
		--language-match "$(LANGUAGE_MATCH)" \
		--output-dir "$(PY_CORPUS_SPLIT_DIR)" \
		--seed "$(SPLIT_SEED)" \
		--development-project-fraction "$(DEVELOPMENT_PROJECT_FRACTION)" \
		--validation-project-fraction "$(VALIDATION_PROJECT_FRACTION)" \
		--max-development-segments "$(MAX_DEVELOPMENT_SEGMENTS)" \
		--max-validation-segments "$(MAX_VALIDATION_SEGMENTS)" \
		--max-test-segments "$(MAX_TEST_SEGMENTS)" \
		--overwrite

refresh-annotations: validate-config
ifeq ($(RUN),1)
	$(MANAGE) refresh_mwe_experiment_projects \
		--project-ids "$(PROJECT_IDS)" \
		--split-manifest "$(PY_SPLIT_MANIFEST)" \
		--splits "$(SPLITS)" \
		--run-label-prefix "$(RUN_LABEL_PREFIX)" \
		--stage-parameters-file "$(PY_STAGE_PARAMETERS)" \
		--overwrite
else
	$(MAKE) refresh-annotations-dry-run
endif

refresh-annotations-dry-run: validate-config
	$(MANAGE) refresh_mwe_experiment_projects \
		--project-ids "$(PROJECT_IDS)" \
		--split-manifest "$(PY_SPLIT_MANIFEST)" \
		--splits "$(SPLITS)" \
		--run-label-prefix "$(RUN_LABEL_PREFIX)" \
		--stage-parameters-file "$(PY_STAGE_PARAMETERS)" \
		--dry-run

refresh-upstream: refresh-annotations

refresh-upstream-dry-run: refresh-annotations-dry-run

clean:
	rm -rf "$(GENERATED_DIR)"
