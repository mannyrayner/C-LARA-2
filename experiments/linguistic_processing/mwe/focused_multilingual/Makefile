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
SPLIT ?= development
RUN_LABEL_PREFIX ?= mwe_annotation_refresh_v1
PROJECT_IDS ?=
SPLIT_MANIFEST ?= $(CORPUS_SPLIT_DIR)/multilingual_split_manifest.json
STAGE_PARAMETERS ?= config/stage_parameters.json
RESUME_FROM_PROJECT_ID ?= 0
MAX_PROJECT_RETRIES ?= 2
FAILED_REFRESHES ?= $(abspath $(GENERATED_DIR))/refresh_failures.jsonl
FAIL_FAST ?= 0
SNAPSHOT_NAME_PREFIX ?= MWE gold checkpoint
MWE_RUN_LABEL ?= mwe-current-prompt-$(SPLIT)
MWE_LANGUAGE ?= en
MWE_SPLIT_RECORDS ?= $(CORPUS_SPLIT_DIR)/$(MWE_LANGUAGE)/$(SPLIT)_segments.jsonl
MWE_RUN_OUTPUT_DIR ?= $(abspath $(GENERATED_DIR))/mwe_prompt_runs
MWE_SCORE_DIR ?= $(abspath $(GENERATED_DIR))/mwe_prompt_scores/$(MWE_RUN_LABEL)
MWE_PROMPT_IMPROVEMENT_DIR ?= $(abspath $(GENERATED_DIR))/mwe_prompt_improvements/$(MWE_RUN_LABEL)
MWE_LIMIT ?= 0

GENERATED_DIR := generated
CORPUS_SPLIT_DIR := $(abspath $(GENERATED_DIR))/corpus_splits
PY_OS := $(shell $(PYTHON) -c 'import os; print(os.name)' 2>/dev/null || echo posix)
python_path = $(shell if [ "$(PY_OS)" = "nt" ] && command -v cygpath >/dev/null 2>&1; then cygpath -am "$(1)"; else printf '%s' "$(1)"; fi)
PY_CORPUS_SPLIT_DIR := $(call python_path,$(CORPUS_SPLIT_DIR))
PY_SPLIT_MANIFEST := $(call python_path,$(abspath $(SPLIT_MANIFEST)))
PY_STAGE_PARAMETERS := $(call python_path,$(abspath $(STAGE_PARAMETERS)))
PY_FAILED_REFRESHES := $(call python_path,$(FAILED_REFRESHES))
PY_MWE_SPLIT_RECORDS := $(call python_path,$(MWE_SPLIT_RECORDS))
PY_MWE_RUN_OUTPUT_DIR := $(call python_path,$(MWE_RUN_OUTPUT_DIR))
PY_MWE_SCORE_DIR := $(call python_path,$(MWE_SCORE_DIR))
PY_MWE_PROMPT_IMPROVEMENT_DIR := $(call python_path,$(MWE_PROMPT_IMPROVEMENT_DIR))
FAIL_FAST_ARG := $(if $(filter 1,$(FAIL_FAST)),--fail-fast,)

MANAGE := cd $(PLATFORM_DIR) && PYTHONPATH= DJANGO_SETTINGS_MODULE=platform_server.settings $(PYTHON) manage.py

.PHONY: help prepare extract-split-corpus snapshot-gold-projects snapshot-gold-projects-dry-run run-current-mwe score-current-mwe propose-mwe-prompt-improvement refresh-project-metadata refresh-annotations refresh-annotations-dry-run refresh-upstream refresh-upstream-dry-run validate-config clean

help:
	@echo "Focused MWE experiments (multilingual)"
	@echo
	@echo "Targets:"
	@echo "  extract-split-corpus  Extract segment records and create project-separated dev/validation/test splits"
	@echo "  snapshot-gold-projects  Save project snapshots marking MWE, gloss, and lemma as gold standard"
	@echo "  run-current-mwe    Run current MWE prompt over extracted segment records"
	@echo "  score-current-mwe  Score current MWE prompt output against gold MWEs"
	@echo "  propose-mwe-prompt-improvement  Write conservative prompt-improvement guidance from score errors"
	@echo "  refresh-annotations   Rerun selected projects through segmentation_phase_2 -> translation -> mwe -> lemma -> gloss"
	@echo "  refresh-project-metadata  Keep existing splits/projects but refresh mwe_count from latest saved artifacts"
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
	@echo "  RESUME_FROM_PROJECT_ID=$(RESUME_FROM_PROJECT_ID)"
	@echo "  MAX_PROJECT_RETRIES=$(MAX_PROJECT_RETRIES)"
	@echo "  FAILED_REFRESHES=$(FAILED_REFRESHES)"
	@echo "  FAIL_FAST=$(FAIL_FAST)"
	@echo "  MWE_LANGUAGE=$(MWE_LANGUAGE)"
	@echo "  MWE_SPLIT_RECORDS=$(MWE_SPLIT_RECORDS)"
	@echo "  MWE_RUN_LABEL=$(MWE_RUN_LABEL)"

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

snapshot-gold-projects: prepare
ifeq ($(RUN),1)
	$(MANAGE) snapshot_mwe_experiment_projects \
		--project-ids "$(PROJECT_IDS)" \
		--split-manifest "$(PY_SPLIT_MANIFEST)" \
		--splits "$(SPLITS)" \
		--snapshot-name-prefix "$(SNAPSHOT_NAME_PREFIX)"
else
	$(MAKE) snapshot-gold-projects-dry-run
endif

snapshot-gold-projects-dry-run: prepare
	$(MANAGE) snapshot_mwe_experiment_projects \
		--project-ids "$(PROJECT_IDS)" \
		--split-manifest "$(PY_SPLIT_MANIFEST)" \
		--splits "$(SPLITS)" \
		--snapshot-name-prefix "$(SNAPSHOT_NAME_PREFIX)" \
		--dry-run

run-current-mwe: prepare
	@echo "+ $(MANAGE) run_mwe_prompt_experiment --input-records-jsonl $(PY_MWE_SPLIT_RECORDS) --output-dir $(PY_MWE_RUN_OUTPUT_DIR) --run-label $(MWE_RUN_LABEL) --limit $(MWE_LIMIT) --project-ids $(PROJECT_IDS) --overwrite"
	@if [ "$(RUN)" = "1" ]; then \
		$(MANAGE) run_mwe_prompt_experiment --input-records-jsonl "$(PY_MWE_SPLIT_RECORDS)" --output-dir "$(PY_MWE_RUN_OUTPUT_DIR)" --run-label "$(MWE_RUN_LABEL)" --limit "$(MWE_LIMIT)" --project-ids "$(PROJECT_IDS)" --overwrite; \
	else \
		echo "dry-run only; set RUN=1 after extract-split-corpus has written $(MWE_SPLIT_RECORDS)"; \
	fi

score-current-mwe: prepare
	@echo "+ $(MANAGE) score_mwe_prompt_outputs --outputs-jsonl $(PY_MWE_RUN_OUTPUT_DIR)/$(MWE_RUN_LABEL)/outputs.jsonl --output-dir $(PY_MWE_SCORE_DIR) --split $(SPLIT) --project-ids $(PROJECT_IDS) --overwrite"
	@if [ "$(RUN)" = "1" ]; then \
		$(MANAGE) score_mwe_prompt_outputs --outputs-jsonl "$(PY_MWE_RUN_OUTPUT_DIR)/$(MWE_RUN_LABEL)/outputs.jsonl" --output-dir "$(PY_MWE_SCORE_DIR)" --split "$(SPLIT)" --project-ids "$(PROJECT_IDS)" --overwrite; \
	else \
		echo "dry-run only; set RUN=1 after run-current-mwe has produced outputs.jsonl"; \
	fi

propose-mwe-prompt-improvement: prepare
	@echo "+ $(MANAGE) propose_mwe_prompt_improvement --score-dir $(PY_MWE_SCORE_DIR) --output-dir $(PY_MWE_PROMPT_IMPROVEMENT_DIR) --project-ids $(PROJECT_IDS) --overwrite"
	@if [ "$(RUN)" = "1" ]; then \
		$(MANAGE) propose_mwe_prompt_improvement --score-dir "$(PY_MWE_SCORE_DIR)" --output-dir "$(PY_MWE_PROMPT_IMPROVEMENT_DIR)" --project-ids "$(PROJECT_IDS)" --overwrite; \
	else \
		echo "dry-run only; set RUN=1 after score-current-mwe has produced a score directory"; \
	fi

refresh-project-metadata: prepare
	$(MANAGE) refresh_mwe_corpus_metadata \
		--corpus-split-dir "$(PY_CORPUS_SPLIT_DIR)" \
		--languages "$(LANGUAGES)" \
		--splits "$(SPLITS)"

refresh-annotations: validate-config
ifeq ($(RUN),1)
	$(MANAGE) refresh_mwe_experiment_projects \
		--project-ids "$(PROJECT_IDS)" \
		--split-manifest "$(PY_SPLIT_MANIFEST)" \
		--splits "$(SPLITS)" \
		--run-label-prefix "$(RUN_LABEL_PREFIX)" \
		--stage-parameters-file "$(PY_STAGE_PARAMETERS)" \
		--resume-from-project-id "$(RESUME_FROM_PROJECT_ID)" \
		--max-project-retries "$(MAX_PROJECT_RETRIES)" \
		--failed-projects-jsonl "$(PY_FAILED_REFRESHES)" \
		$(FAIL_FAST_ARG) \
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
		--resume-from-project-id "$(RESUME_FROM_PROJECT_ID)" \
		--dry-run

refresh-upstream: refresh-annotations

refresh-upstream-dry-run: refresh-annotations-dry-run

clean:
	rm -rf "$(GENERATED_DIR)"
