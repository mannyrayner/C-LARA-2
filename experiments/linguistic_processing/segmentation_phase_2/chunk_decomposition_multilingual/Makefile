SHELL := /usr/bin/env bash

ROOT_DIR := $(abspath ../../../..)
PLATFORM_DIR := $(ROOT_DIR)/platform_server
PYTHON ?= python3
RUN ?= 0

CORPUS_USER ?= mannyrayner
LANGUAGES ?= fr,de,en
LANGUAGE_MATCH ?= exact
SPLIT_SEED ?= chunk-decomposition-multilingual-v1
DEVELOPMENT_PROJECT_FRACTION ?= 0.50
VALIDATION_PROJECT_FRACTION ?= 0.25
MAX_DEVELOPMENT_CHUNKS ?= 800
MAX_VALIDATION_CHUNKS ?= 400
MAX_TEST_CHUNKS ?= 800

GENERATED_DIR := generated
CORPUS_SPLIT_DIR := $(abspath $(GENERATED_DIR))/corpus_splits

PY_OS := $(shell $(PYTHON) -c 'import os; print(os.name)' 2>/dev/null || echo posix)
python_path = $(shell if [ "$(PY_OS)" = "nt" ] && command -v cygpath >/dev/null 2>&1; then cygpath -am "$(1)"; else printf '%s' "$(1)"; fi)
PY_CORPUS_SPLIT_DIR := $(call python_path,$(CORPUS_SPLIT_DIR))

MANAGE := cd $(PLATFORM_DIR) && PYTHONPATH= DJANGO_SETTINGS_MODULE=platform_server.settings $(PYTHON) manage.py

.PHONY: help prepare extract-split-corpus clean

help:
	@echo "Chunk-decomposition segmentation experiments (multilingual)"
	@echo
	@echo "Targets:"
	@echo "  extract-split-corpus  Extract whitespace chunk records and create dev/validation/test splits"
	@echo "  clean                 Remove generated experiment artifacts"
	@echo
	@echo "Important variables:"
	@echo "  RUN=$(RUN)"
	@echo "  CORPUS_USER=$(CORPUS_USER)"
	@echo "  LANGUAGES=$(LANGUAGES)"
	@echo "  DEVELOPMENT_PROJECT_FRACTION=$(DEVELOPMENT_PROJECT_FRACTION)"
	@echo "  VALIDATION_PROJECT_FRACTION=$(VALIDATION_PROJECT_FRACTION)"
	@echo "  MAX_DEVELOPMENT_CHUNKS=$(MAX_DEVELOPMENT_CHUNKS)"
	@echo "  MAX_VALIDATION_CHUNKS=$(MAX_VALIDATION_CHUNKS)"
	@echo "  MAX_TEST_CHUNKS=$(MAX_TEST_CHUNKS)"
	@echo
	@echo "Generated corpus splits: $(CORPUS_SPLIT_DIR)"

prepare:
	@mkdir -p "$(GENERATED_DIR)" "$(CORPUS_SPLIT_DIR)"

extract-split-corpus: prepare
	@echo "+ $(MANAGE) extract_chunk_segmentation_corpus --username $(CORPUS_USER) --languages $(LANGUAGES) --language-match $(LANGUAGE_MATCH) --output-dir $(PY_CORPUS_SPLIT_DIR) --seed $(SPLIT_SEED) --development-project-fraction $(DEVELOPMENT_PROJECT_FRACTION) --validation-project-fraction $(VALIDATION_PROJECT_FRACTION) --max-development-chunks $(MAX_DEVELOPMENT_CHUNKS) --max-validation-chunks $(MAX_VALIDATION_CHUNKS) --max-test-chunks $(MAX_TEST_CHUNKS) --overwrite"
	@if [ "$(RUN)" = "1" ]; then \
		$(MANAGE) extract_chunk_segmentation_corpus --username "$(CORPUS_USER)" --languages "$(LANGUAGES)" --language-match "$(LANGUAGE_MATCH)" --output-dir "$(PY_CORPUS_SPLIT_DIR)" --seed "$(SPLIT_SEED)" --development-project-fraction "$(DEVELOPMENT_PROJECT_FRACTION)" --validation-project-fraction "$(VALIDATION_PROJECT_FRACTION)" --max-development-chunks "$(MAX_DEVELOPMENT_CHUNKS)" --max-validation-chunks "$(MAX_VALIDATION_CHUNKS)" --max-test-chunks "$(MAX_TEST_CHUNKS)" --overwrite; \
	else \
		echo "dry-run only; set RUN=1 to extract chunk records and write multilingual splits"; \
	fi

clean:
	rm -rf "$(GENERATED_DIR)"
