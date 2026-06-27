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
DIVERGENCE_REVIEW_LIMIT ?= 0
PROMPT_KIND ?= segmentation
PROMPT_SUBDIR := $(if $(filter rating,$(PROMPT_KIND)),chunk_rating,chunk_segmentation)
CURRENT_PROMPT ?= prompts/$(PROMPT_SUBDIR)/$(JUDGE_LANGUAGE).md
PROMPT_IMPROVEMENT_CYCLE_NUMBER ?= 1
RESET_CYCLE_PROMPT ?= 0
MODEL ?= gpt-4o
PROMPT_LIMIT ?= 0
MAX_CONCURRENCY ?= 4
PROGRESS_EVERY ?= 25
GENERATE_REVISED_PROMPT ?= 1
REVISION_MODEL ?= $(MODEL)

GENERATED_DIR := generated
CORPUS_SPLIT_DIR := $(abspath $(GENERATED_DIR))/corpus_splits
GOLD_DIR := $(abspath $(GENERATED_DIR))/gold
PREDICTIONS_DIR := $(abspath $(GENERATED_DIR))/predictions
PROMPT_IMPROVEMENT_BASE_DIR := $(abspath $(GENERATED_DIR))/prompt_improvement/$(JUDGE_LANGUAGE)-$(PROMPT_KIND)-$(SPLIT)
PROMPT_IMPROVEMENT_DIR := $(PROMPT_IMPROVEMENT_BASE_DIR)/cycle_$(PROMPT_IMPROVEMENT_CYCLE_NUMBER)
CYCLE_PROMPT := $(PROMPT_IMPROVEMENT_DIR)/prompt.md
PROMPT_IMPROVEMENT_SUMMARY_JSON := $(PROMPT_IMPROVEMENT_BASE_DIR)/cycles_summary.json
PROMPT_IMPROVEMENT_SUMMARY_MD := $(PROMPT_IMPROVEMENT_BASE_DIR)/cycles_summary.md
DIVERGENCE_REVIEW_RECORDS := $(PROMPT_IMPROVEMENT_DIR)/gold_divergence_review.jsonl
CHUNK_RECORDS := $(CORPUS_SPLIT_DIR)/$(JUDGE_LANGUAGE)/$(SPLIT).jsonl
GOLD_RECORDS := $(GOLD_DIR)/$(JUDGE_LANGUAGE)-$(SPLIT).jsonl
PREDICTION_RECORDS ?= $(PROMPT_IMPROVEMENT_DIR)/predictions.jsonl
CURRENT_PROMPT_PATH := $(abspath $(CURRENT_PROMPT))
CYCLE_PROMPT_PATH := $(abspath $(CYCLE_PROMPT))
PREDICTION_RECORDS_PATH := $(abspath $(PREDICTION_RECORDS))

PY_OS := $(shell $(PYTHON) -c 'import os; print(os.name)' 2>/dev/null || echo posix)
python_path = $(shell if [ "$(PY_OS)" = "nt" ] && command -v cygpath >/dev/null 2>&1; then cygpath -am "$(1)"; else printf '%s' "$(1)"; fi)
PY_CORPUS_SPLIT_DIR := $(call python_path,$(CORPUS_SPLIT_DIR))
PY_CHUNK_RECORDS := $(call python_path,$(CHUNK_RECORDS))
PY_GOLD_RECORDS := $(call python_path,$(GOLD_RECORDS))
PY_PREDICTION_RECORDS := $(call python_path,$(PREDICTION_RECORDS_PATH))
PY_PROMPT_IMPROVEMENT_DIR := $(call python_path,$(PROMPT_IMPROVEMENT_DIR))
PY_CURRENT_PROMPT := $(call python_path,$(CURRENT_PROMPT_PATH))
PY_CYCLE_PROMPT := $(call python_path,$(CYCLE_PROMPT_PATH))
PY_PROMPT_IMPROVEMENT_SUMMARY_JSON := $(call python_path,$(PROMPT_IMPROVEMENT_SUMMARY_JSON))
PY_PROMPT_IMPROVEMENT_SUMMARY_MD := $(call python_path,$(PROMPT_IMPROVEMENT_SUMMARY_MD))
PY_DIVERGENCE_REVIEW_RECORDS := $(call python_path,$(DIVERGENCE_REVIEW_RECORDS))
CURRENT_PROMPT_ARG := --current-prompt $(PY_CYCLE_PROMPT)

MANAGE := cd $(PLATFORM_DIR) && PYTHONPATH= DJANGO_SETTINGS_MODULE=platform_server.settings $(PYTHON) manage.py

.PHONY: help prepare prepare-cycle extract-split-corpus judge-corpus run-prompt prepare-prompt-improvement review-prompt-divergences summarize-prompt-improvement-cycles clean

help:
	@echo "Chunk-decomposition segmentation experiments (multilingual)"
	@echo
	@echo "Targets:"
	@echo "  extract-split-corpus  Extract whitespace chunk records and create dev/validation/test splits"
	@echo "  judge-corpus          Accept/correct one language+split into a human gold JSONL"
	@echo "  run-prompt            Run this cycle's segmentation/rating prompt to create prediction JSONL"
	@echo "  prepare-prompt-improvement  Summarize cycle performance into an anti-overfitting prompt revision brief"
	@echo "  review-prompt-divergences  Review prediction/gold divergences and optionally correct gold"
	@echo "  summarize-prompt-improvement-cycles  Summarize all completed prompt-improvement cycles"
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
	@echo "  DIVERGENCE_REVIEW_LIMIT=$(DIVERGENCE_REVIEW_LIMIT)"
	@echo "  PROMPT_KIND=$(PROMPT_KIND)"
	@echo "  CURRENT_PROMPT=$(CURRENT_PROMPT)"
	@echo "  PROMPT_IMPROVEMENT_CYCLE_NUMBER=$(PROMPT_IMPROVEMENT_CYCLE_NUMBER)"
	@echo "  RESET_CYCLE_PROMPT=$(RESET_CYCLE_PROMPT)"
	@echo "  CYCLE_PROMPT=$(CYCLE_PROMPT)"
	@echo "  PREDICTION_RECORDS=$(PREDICTION_RECORDS)"
	@echo "  MAX_CONCURRENCY=$(MAX_CONCURRENCY)"
	@echo "  PROGRESS_EVERY=$(PROGRESS_EVERY)"
	@echo "  GENERATE_REVISED_PROMPT=$(GENERATE_REVISED_PROMPT)"
	@echo "  REVISION_MODEL=$(REVISION_MODEL)"
	@echo
	@echo "Generated corpus splits: $(CORPUS_SPLIT_DIR)"
	@echo "Gold judgements: $(GOLD_DIR)"
	@echo "Prompt improvement base: $(PROMPT_IMPROVEMENT_BASE_DIR)"
	@echo "Prompt improvement cycle: $(PROMPT_IMPROVEMENT_DIR)"

prepare:
	@mkdir -p "$(GENERATED_DIR)" "$(CORPUS_SPLIT_DIR)" "$(GOLD_DIR)" "$(PREDICTIONS_DIR)" "$(PROMPT_IMPROVEMENT_BASE_DIR)"

prepare-cycle: prepare
	@if [ "$(RUN)" != "1" ]; then \
		echo "dry-run only; cycle $(PROMPT_IMPROVEMENT_CYCLE_NUMBER) prompt would be prepared at $(CYCLE_PROMPT)"; \
		exit 0; \
	fi; \
	if [ "$(PROMPT_IMPROVEMENT_CYCLE_NUMBER)" -lt 1 ]; then \
		echo "PROMPT_IMPROVEMENT_CYCLE_NUMBER must be >= 1" >&2; \
		exit 1; \
	fi; \
	mkdir -p "$(PROMPT_IMPROVEMENT_DIR)"; \
	if [ "$(PROMPT_IMPROVEMENT_CYCLE_NUMBER)" = "1" ]; then \
		source_prompt="$(CURRENT_PROMPT_PATH)"; \
	else \
		previous_cycle=$$(( $(PROMPT_IMPROVEMENT_CYCLE_NUMBER) - 1 )); \
		source_prompt="$(PROMPT_IMPROVEMENT_BASE_DIR)/cycle_$${previous_cycle}/prompt_revision.md"; \
	fi; \
	if [ ! -f "$$source_prompt" ]; then \
		echo "source prompt not found: $$source_prompt" >&2; \
		exit 1; \
	fi; \
	if [ ! -f "$(CYCLE_PROMPT)" ] || [ "$(RESET_CYCLE_PROMPT)" = "1" ]; then \
		cp "$$source_prompt" "$(CYCLE_PROMPT)"; \
		echo "Prepared cycle prompt: $(CYCLE_PROMPT)"; \
	else \
		echo "Using existing cycle prompt: $(CYCLE_PROMPT)"; \
	fi

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

run-prompt: prepare-cycle
	@echo "+ $(MANAGE) run_chunk_prompt_on_corpus --input-jsonl $(PY_GOLD_RECORDS) --prompt-file $(PY_CYCLE_PROMPT) --output-jsonl $(PY_PREDICTION_RECORDS) --prompt-kind $(PROMPT_KIND) --model $(MODEL) --limit $(PROMPT_LIMIT) --max-concurrency $(MAX_CONCURRENCY) --progress-every $(PROGRESS_EVERY) --overwrite"
	@if [ "$(RUN)" = "1" ]; then \
		$(MANAGE) run_chunk_prompt_on_corpus --input-jsonl "$(PY_GOLD_RECORDS)" --prompt-file "$(PY_CYCLE_PROMPT)" --output-jsonl "$(PY_PREDICTION_RECORDS)" --prompt-kind "$(PROMPT_KIND)" --model "$(MODEL)" --limit "$(PROMPT_LIMIT)" --max-concurrency "$(MAX_CONCURRENCY)" --progress-every "$(PROGRESS_EVERY)" --overwrite; \
	else \
		echo "dry-run only; set RUN=1 to run $(CYCLE_PROMPT) over $(GOLD_RECORDS)"; \
	fi

prepare-prompt-improvement: prepare-cycle
	@revision_arg=""; if [ "$(GENERATE_REVISED_PROMPT)" = "1" ]; then revision_arg="--generate-revised-prompt --revision-model $(REVISION_MODEL)"; fi; echo "+ $(MANAGE) prepare_chunk_prompt_improvement --gold-jsonl $(PY_GOLD_RECORDS) --predictions-jsonl $(PY_PREDICTION_RECORDS) --language $(JUDGE_LANGUAGE) --prompt-kind $(PROMPT_KIND) $(CURRENT_PROMPT_ARG) --output-dir $(PY_PROMPT_IMPROVEMENT_DIR) $$revision_arg --overwrite"
	@if [ "$(RUN)" = "1" ]; then \
		revision_arg=""; \
		if [ "$(GENERATE_REVISED_PROMPT)" = "1" ]; then revision_arg="--generate-revised-prompt --revision-model $(REVISION_MODEL)"; fi; \
		$(MANAGE) prepare_chunk_prompt_improvement --gold-jsonl "$(PY_GOLD_RECORDS)" --predictions-jsonl "$(PY_PREDICTION_RECORDS)" --language "$(JUDGE_LANGUAGE)" --prompt-kind "$(PROMPT_KIND)" $(CURRENT_PROMPT_ARG) --output-dir "$(PY_PROMPT_IMPROVEMENT_DIR)" $$revision_arg --overwrite; \
	else \
		echo "dry-run only; set RUN=1 after writing predictions to $(PREDICTION_RECORDS)"; \
	fi


review-prompt-divergences: prepare-cycle
	@echo "+ $(MANAGE) review_chunk_prompt_divergences --gold-jsonl $(PY_GOLD_RECORDS) --predictions-jsonl $(PY_PREDICTION_RECORDS) --review-jsonl $(PY_DIVERGENCE_REVIEW_RECORDS) --limit $(DIVERGENCE_REVIEW_LIMIT)"
	@if [ "$(RUN)" = "1" ]; then \
		$(MANAGE) review_chunk_prompt_divergences --gold-jsonl "$(PY_GOLD_RECORDS)" --predictions-jsonl "$(PY_PREDICTION_RECORDS)" --review-jsonl "$(PY_DIVERGENCE_REVIEW_RECORDS)" --limit "$(DIVERGENCE_REVIEW_LIMIT)"; \
	else \
		echo "dry-run only; set RUN=1 to review $(PREDICTION_RECORDS) divergences against $(GOLD_RECORDS)"; \
	fi

summarize-prompt-improvement-cycles: prepare
	@echo "+ $(MANAGE) summarize_chunk_prompt_improvement_cycles --cycles-dir $(call python_path,$(PROMPT_IMPROVEMENT_BASE_DIR)) --output-json $(PY_PROMPT_IMPROVEMENT_SUMMARY_JSON) --output-markdown $(PY_PROMPT_IMPROVEMENT_SUMMARY_MD) --overwrite"
	@if [ "$(RUN)" = "1" ]; then \
		$(MANAGE) summarize_chunk_prompt_improvement_cycles --cycles-dir "$(call python_path,$(PROMPT_IMPROVEMENT_BASE_DIR))" --output-json "$(PY_PROMPT_IMPROVEMENT_SUMMARY_JSON)" --output-markdown "$(PY_PROMPT_IMPROVEMENT_SUMMARY_MD)" --overwrite; \
	else \
		echo "dry-run only; set RUN=1 to summarize prompt-improvement cycles under $(PROMPT_IMPROVEMENT_BASE_DIR)"; \
	fi

clean:
	rm -rf "$(GENERATED_DIR)"
