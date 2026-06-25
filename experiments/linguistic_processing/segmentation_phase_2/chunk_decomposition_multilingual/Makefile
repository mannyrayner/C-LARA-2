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
JUDGE_LANGUAGE ?= fr
SPLIT ?= development
JUDGE_LIMIT ?= 0

GENERATED_DIR := generated
CORPUS_SPLIT_DIR := $(abspath $(GENERATED_DIR))/corpus_splits
GOLD_DIR := $(abspath $(GENERATED_DIR))/gold
CHUNK_RECORDS := $(CORPUS_SPLIT_DIR)/$(JUDGE_LANGUAGE)/$(SPLIT).jsonl
GOLD_RECORDS := $(GOLD_DIR)/$(JUDGE_LANGUAGE)-$(SPLIT).jsonl

PY_OS := $(shell $(PYTHON) -c 'import os; print(os.name)' 2>/dev/null || echo posix)
python_path = $(shell if [ "$(PY_OS)" = "nt" ] && command -v cygpath >/dev/null 2>&1; then cygpath -am "$(1)"; else printf '%s' "$(1)"; fi)
PY_CORPUS_SPLIT_DIR := $(call python_path,$(CORPUS_SPLIT_DIR))
PY_CHUNK_RECORDS := $(call python_path,$(CHUNK_RECORDS))
PY_GOLD_RECORDS := $(call python_path,$(GOLD_RECORDS))

MANAGE := cd $(PLATFORM_DIR) && PYTHONPATH= DJANGO_SETTINGS_MODULE=platform_server.settings $(PYTHON) manage.py

.PHONY: help prepare extract-split-corpus judge-corpus clean

help:
	@echo "Chunk-decomposition segmentation experiments (multilingual)"
	@echo
	@echo "Targets:"
	@echo "  extract-split-corpus  Extract whitespace chunk records and create dev/validation/test splits"
	@echo "  judge-corpus          Accept/correct one language+split into a human gold JSONL"
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
	@echo "  JUDGE_LANGUAGE=$(JUDGE_LANGUAGE)"
	@echo "  SPLIT=$(SPLIT)"
	@echo "  JUDGE_LIMIT=$(JUDGE_LIMIT)"
	@echo
	@echo "Generated corpus splits: $(CORPUS_SPLIT_DIR)"
	@echo "Gold judgements: $(GOLD_DIR)"

prepare:
	@mkdir -p "$(GENERATED_DIR)" "$(CORPUS_SPLIT_DIR)" "$(GOLD_DIR)"

extract-split-corpus: prepare
	@echo "+ $(MANAGE) extract_chunk_segmentation_corpus --username $(CORPUS_USER) --languages $(LANGUAGES) --language-match $(LANGUAGE_MATCH) --output-dir $(PY_CORPUS_SPLIT_DIR) --seed $(SPLIT_SEED) --development-project-fraction $(DEVELOPMENT_PROJECT_FRACTION) --validation-project-fraction $(VALIDATION_PROJECT_FRACTION) --max-development-chunks $(MAX_DEVELOPMENT_CHUNKS) --max-validation-chunks $(MAX_VALIDATION_CHUNKS) --max-test-chunks $(MAX_TEST_CHUNKS) --overwrite"
	@if [ "$(RUN)" = "1" ]; then \
		$(MANAGE) extract_chunk_segmentation_corpus --username "$(CORPUS_USER)" --languages "$(LANGUAGES)" --language-match "$(LANGUAGE_MATCH)" --output-dir "$(PY_CORPUS_SPLIT_DIR)" --seed "$(SPLIT_SEED)" --development-project-fraction "$(DEVELOPMENT_PROJECT_FRACTION)" --validation-project-fraction "$(VALIDATION_PROJECT_FRACTION)" --max-development-chunks "$(MAX_DEVELOPMENT_CHUNKS)" --max-validation-chunks "$(MAX_VALIDATION_CHUNKS)" --max-test-chunks "$(MAX_TEST_CHUNKS)" --overwrite; \
	else \
		echo "dry-run only; set RUN=1 to extract chunk records and write multilingual splits"; \
	fi

judge-corpus: prepare
	@echo "+ $(MANAGE) judge_chunk_segmentation_corpus --input-jsonl $(PY_CHUNK_RECORDS) --output-jsonl $(PY_GOLD_RECORDS) --limit $(JUDGE_LIMIT)"
	@if [ "$(RUN)" = "1" ]; then \
		$(MANAGE) judge_chunk_segmentation_corpus --input-jsonl "$(PY_CHUNK_RECORDS)" --output-jsonl "$(PY_GOLD_RECORDS)" --limit "$(JUDGE_LIMIT)"; \
	else \
		echo "dry-run only; set RUN=1 to judge $(JUDGE_LANGUAGE) $(SPLIT) chunks into $(GOLD_RECORDS)"; \
	fi

clean:
	rm -rf "$(GENERATED_DIR)"
