SHELL := /usr/bin/env bash

ROOT_DIR := $(abspath ../../../..)
PLATFORM_DIR := $(ROOT_DIR)/platform_server
PYTHON ?= python3
RUN ?= 0

OPERATION := segmentation_phase_2
LANGUAGE := fr
MECHANISM := boundary_first
TARGET_SET := clitic_compound_v2
PHENOMENA := clitic,compound
COUNT ?= 80
BATCH_SIZE ?= 5
MAX_CONCURRENCY ?= 4
MODEL ?= gpt-4o
TEMPLATE_VERSIONS ?= 3
REVIEW_PASSES ?= 3
TIMEOUT_S ?= 600
REQUEST_ID ?=
AUDIT_LIMIT ?= 0
CORPUS_USER ?= mannyrayner
CORPUS_LANGUAGE ?= fr
CORPUS_LANGUAGE_MATCH ?= exact
SPLIT_SEED ?= fr-boundary-first-clitic-compound-v2
DEV_PROJECT_FRACTION ?= 0.25
MAX_DEVELOPMENT_SEGMENTS ?= 250
MAX_TEST_SEGMENTS ?= 500
SPLIT ?= development
FEWSHOT_COUNT ?= small
RUN_LABEL ?= fr-boundary-first-clitic-compound-v2

DEFAULT_PARAMS := configs/default_stage_parameters.json
CANDIDATE_PARAMS := configs/candidate_stage_parameters.json
EVALUATOR_CONFIG := configs/evaluator_config.json
INPUT_RECORDS := fixtures/input_records.jsonl
GENERATED_DIR := generated
TMP_DIR := tmp
CORPUS_SUMMARY_DIR := $(abspath $(GENERATED_DIR))/corpus_summary
CORPUS_SPLIT_DIR := $(abspath $(GENERATED_DIR))/corpus_splits
SPLIT_RECORDS := $(CORPUS_SPLIT_DIR)/$(SPLIT).jsonl
DERIVED_ASSETS_DIR := $(abspath $(GENERATED_DIR))/derived_assets
PROMPT_VARIANT_DIR := $(ROOT_DIR)/prompts/$(OPERATION)/variants/$(TARGET_SET)
CURATION_ROOT := $(abspath $(GENERATED_DIR))/few_shot_curation

PY_OS := $(shell $(PYTHON) -c 'import os; print(os.name)' 2>/dev/null || echo posix)
python_path = $(shell if [ "$(PY_OS)" = "nt" ] && command -v cygpath >/dev/null 2>&1; then cygpath -am "$(1)"; else printf '%s' "$(1)"; fi)
PY_ROOT_DIR := $(call python_path,$(ROOT_DIR))
PY_CURATION_ROOT := $(call python_path,$(CURATION_ROOT))
PY_CORPUS_SUMMARY_DIR := $(call python_path,$(CORPUS_SUMMARY_DIR))
PY_CORPUS_SPLIT_DIR := $(call python_path,$(CORPUS_SPLIT_DIR))
PY_SPLIT_RECORDS := $(call python_path,$(SPLIT_RECORDS))
PY_DERIVED_ASSETS_DIR := $(call python_path,$(DERIVED_ASSETS_DIR))
PY_PROMPT_VARIANT_DIR := $(call python_path,$(PROMPT_VARIANT_DIR))
PY_DEFAULT_PARAMS := $(call python_path,$(abspath $(DEFAULT_PARAMS)))
PY_CANDIDATE_PARAMS := $(call python_path,$(abspath $(CANDIDATE_PARAMS)))
PY_DEFAULT_OUTPUT_DIR := $(call python_path,$(abspath $(GENERATED_DIR))/default)
PY_CANDIDATE_OUTPUT_DIR := $(call python_path,$(abspath $(GENERATED_DIR))/candidate)

MANAGE = cd "$(PLATFORM_DIR)" && PYTHONPATH= DJANGO_SETTINGS_MODULE=platform_server.settings $(PYTHON) manage.py

.PHONY: help plan validate validate-config prepare summarize-corpus split-corpus curate review audit-reviews derive-processing-examples derive-evaluator-examples run-default run-candidate evaluate compare report clean

help:
	@sed -n '1,220p' README.md
	@echo
	@echo "Common targets: plan validate-config summarize-corpus split-corpus curate review audit-reviews derive-processing-examples derive-evaluator-examples run-default run-candidate evaluate compare report"
	@echo "Targets that call management commands default to dry-run. Set RUN=1 to execute."

prepare:
	@mkdir -p "$(GENERATED_DIR)" "$(TMP_DIR)"

plan: prepare
	@echo "Experiment: $(RUN_LABEL)"
	@echo "Root:       $(ROOT_DIR)"
	@echo "Platform:   $(PLATFORM_DIR)"
	@echo "Operation:  $(OPERATION)"
	@echo "Language:   $(LANGUAGE)"
	@echo "Mechanism:  $(MECHANISM)"
	@echo "Target set: $(TARGET_SET)"
	@echo
	@echo "Tracked configs:"
	@echo "  default:   $(DEFAULT_PARAMS)"
	@echo "  candidate: $(CANDIDATE_PARAMS)"
	@echo "  evaluator: $(EVALUATOR_CONFIG)"
	@echo "  fixtures:  $(INPUT_RECORDS)"
	@echo "  split:     $(SPLIT_RECORDS)"
	@echo "  candidate few-shot count: $(FEWSHOT_COUNT)"
	@echo
	@echo "Generated data will be written under $(GENERATED_DIR)/ and $(TMP_DIR)/ (ignored by Git)."
	@echo "Curation:  $(CURATION_ROOT)"
	@echo "Corpus summary: $(CORPUS_SUMMARY_DIR)"
	@echo "Corpus splits:  $(CORPUS_SPLIT_DIR)"
	@echo "Derived assets: $(DERIVED_ASSETS_DIR)"
	@echo "Prompt variant: $(PROMPT_VARIANT_DIR)"

validate: validate-config

validate-config:
	@$(PYTHON) -m json.tool "$(DEFAULT_PARAMS)" >/dev/null
	@$(PYTHON) -m json.tool "$(CANDIDATE_PARAMS)" >/dev/null
	@$(PYTHON) -m json.tool "$(EVALUATOR_CONFIG)" >/dev/null
	@$(PYTHON) -c 'import json; from pathlib import Path; path=Path("$(INPUT_RECORDS)"); records=[json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]; [(_ for _ in ()).throw(SystemExit(f"{path}: record {idx} missing required keys")) for idx, payload in enumerate(records, start=1) if not {"record_id", "language", "input"}.issubset(payload)]; print(f"validated configs and {path} ({len(records)} records)")'

summarize-corpus: prepare
	@echo "+ $(MANAGE) summarize_french_evaluation_corpus --username $(CORPUS_USER) --language $(CORPUS_LANGUAGE) --language-match $(CORPUS_LANGUAGE_MATCH) --output-dir $(PY_CORPUS_SUMMARY_DIR) --json corpus_summary.json --csv corpus_summary.csv --markdown corpus_summary.md"
	@if [ "$(RUN)" = "1" ]; then \
		$(MANAGE) summarize_french_evaluation_corpus --username "$(CORPUS_USER)" --language "$(CORPUS_LANGUAGE)" --language-match "$(CORPUS_LANGUAGE_MATCH)" --output-dir "$(PY_CORPUS_SUMMARY_DIR)" --json corpus_summary.json --csv corpus_summary.csv --markdown corpus_summary.md; \
	else \
		echo "dry-run only; set RUN=1 to inspect imported projects and write corpus summaries"; \
	fi

split-corpus: prepare
	@echo "+ $(MANAGE) split_french_evaluation_corpus --corpus-summary-json $(PY_CORPUS_SUMMARY_DIR)/corpus_summary.json --output-dir $(PY_CORPUS_SPLIT_DIR) --seed $(SPLIT_SEED) --dev-project-fraction $(DEV_PROJECT_FRACTION) --max-development-segments $(MAX_DEVELOPMENT_SEGMENTS) --max-test-segments $(MAX_TEST_SEGMENTS)"
	@if [ "$(RUN)" = "1" ]; then \
		$(MANAGE) split_french_evaluation_corpus --corpus-summary-json "$(PY_CORPUS_SUMMARY_DIR)/corpus_summary.json" --output-dir "$(PY_CORPUS_SPLIT_DIR)" --seed "$(SPLIT_SEED)" --dev-project-fraction "$(DEV_PROJECT_FRACTION)" --max-development-segments "$(MAX_DEVELOPMENT_SEGMENTS)" --max-test-segments "$(MAX_TEST_SEGMENTS)"; \
	else \
		echo "dry-run only; set RUN=1 after summarize-corpus has written corpus_summary.json"; \
	fi

curate: prepare
	@echo "+ $(MANAGE) curate_fewshots --operation $(OPERATION) --language $(LANGUAGE) --mechanism $(MECHANISM) --phenomena $(PHENOMENA) --count $(COUNT) --batch-size $(BATCH_SIZE) --max-concurrency $(MAX_CONCURRENCY) --target-set $(TARGET_SET) --model $(MODEL) --repo-root $(PY_ROOT_DIR) --curation-root $(PY_CURATION_ROOT)"
	@if [ "$(RUN)" = "1" ]; then \
		$(MANAGE) curate_fewshots --operation "$(OPERATION)" --language "$(LANGUAGE)" --mechanism "$(MECHANISM)" --phenomena "$(PHENOMENA)" --count "$(COUNT)" --batch-size "$(BATCH_SIZE)" --max-concurrency "$(MAX_CONCURRENCY)" --target-set "$(TARGET_SET)" --model "$(MODEL)" --repo-root "$(PY_ROOT_DIR)" --curation-root "$(PY_CURATION_ROOT)"; \
	else \
		echo "dry-run only; set RUN=1 to execute"; \
	fi

review: prepare
	@if [ "$(RUN)" = "1" ] && [ -z "$(REQUEST_ID)" ]; then echo "Set REQUEST_ID=<curation-request-id>" >&2; exit 2; fi
	@echo "+ $(MANAGE) review_fewshots --operation $(OPERATION) --language $(LANGUAGE) --mechanism $(MECHANISM) --target-set $(TARGET_SET) --request-id $${REQUEST_ID:-<request-id>} --model $(MODEL) --template-versions $(TEMPLATE_VERSIONS) --review-passes $(REVIEW_PASSES) --max-concurrency $(MAX_CONCURRENCY) --timeout-s $(TIMEOUT_S) --repo-root $(PY_ROOT_DIR) --curation-root $(PY_CURATION_ROOT)"
	@if [ "$(RUN)" = "1" ]; then \
		$(MANAGE) review_fewshots --operation "$(OPERATION)" --language "$(LANGUAGE)" --mechanism "$(MECHANISM)" --target-set "$(TARGET_SET)" --request-id "$(REQUEST_ID)" --model "$(MODEL)" --template-versions "$(TEMPLATE_VERSIONS)" --review-passes "$(REVIEW_PASSES)" --max-concurrency "$(MAX_CONCURRENCY)" --timeout-s "$(TIMEOUT_S)" --repo-root "$(PY_ROOT_DIR)" --curation-root "$(PY_CURATION_ROOT)"; \
	else \
		echo "dry-run only; set RUN=1 REQUEST_ID=<id> to execute"; \
	fi

audit-reviews: prepare
	@if [ "$(RUN)" = "1" ] && [ -z "$(REQUEST_ID)" ]; then echo "Set REQUEST_ID=<curation-request-id>" >&2; exit 2; fi
	@echo "+ $(MANAGE) audit_fewshot_reviews --operation $(OPERATION) --language $(LANGUAGE) --mechanism $(MECHANISM) --target-set $(TARGET_SET) --request-id $${REQUEST_ID:-<request-id>} --limit $(AUDIT_LIMIT) --repo-root $(PY_ROOT_DIR) --curation-root $(PY_CURATION_ROOT)"
	@if [ "$(RUN)" = "1" ]; then \
		$(MANAGE) audit_fewshot_reviews --operation "$(OPERATION)" --language "$(LANGUAGE)" --mechanism "$(MECHANISM)" --target-set "$(TARGET_SET)" --request-id "$(REQUEST_ID)" --limit "$(AUDIT_LIMIT)" --repo-root "$(PY_ROOT_DIR)" --curation-root "$(PY_CURATION_ROOT)"; \
	else \
		echo "dry-run only; set RUN=1 REQUEST_ID=<id> to audit interactively"; \
	fi

derive-processing-examples: prepare
	@if [ "$(RUN)" = "1" ] && [ -z "$(REQUEST_ID)" ]; then echo "Set REQUEST_ID=<audited-curation-request-id>" >&2; exit 2; fi
	@echo "+ $(MANAGE) derive_fewshot_assets --operation $(OPERATION) --language $(LANGUAGE) --mechanism $(MECHANISM) --target-set $(TARGET_SET) --request-id $${REQUEST_ID:-<request-id>} --repo-root $(PY_ROOT_DIR) --curation-root $(PY_CURATION_ROOT) --processing-output-dir $(PY_PROMPT_VARIANT_DIR)/fewshots --evaluator-output-jsonl $(PY_DERIVED_ASSETS_DIR)/evaluator_examples.jsonl --manifest-json $(PY_DERIVED_ASSETS_DIR)/derived_assets_manifest.json --overwrite"
	@if [ "$(RUN)" = "1" ]; then \
		$(MANAGE) derive_fewshot_assets --operation "$(OPERATION)" --language "$(LANGUAGE)" --mechanism "$(MECHANISM)" --target-set "$(TARGET_SET)" --request-id "$(REQUEST_ID)" --repo-root "$(PY_ROOT_DIR)" --curation-root "$(PY_CURATION_ROOT)" --processing-output-dir "$(PY_PROMPT_VARIANT_DIR)/fewshots" --evaluator-output-jsonl "$(PY_DERIVED_ASSETS_DIR)/evaluator_examples.jsonl" --manifest-json "$(PY_DERIVED_ASSETS_DIR)/derived_assets_manifest.json" --overwrite; \
	else \
		echo "dry-run only; set RUN=1 REQUEST_ID=<audited-curation-request-id> to derive assets"; \
	fi

derive-evaluator-examples: derive-processing-examples
	@echo "Evaluator examples are derived together with processing examples into $(DERIVED_ASSETS_DIR)/evaluator_examples.jsonl."

run-default: prepare validate-config
	@echo "+ $(MANAGE) run_linguistic_pipeline_experiment --input-records-jsonl $(PY_SPLIT_RECORDS) --start-stage segmentation_phase_2 --end-stage segmentation_phase_2 --stage-parameters-file $(PY_DEFAULT_PARAMS) --run-label $(RUN_LABEL)-$(SPLIT)-default --output-root $(PY_DEFAULT_OUTPUT_DIR) --language $(LANGUAGE) --overwrite"
	@if [ "$(RUN)" = "1" ]; then \
		$(MANAGE) run_linguistic_pipeline_experiment --input-records-jsonl "$(PY_SPLIT_RECORDS)" --start-stage segmentation_phase_2 --end-stage segmentation_phase_2 --stage-parameters-file "$(PY_DEFAULT_PARAMS)" --run-label "$(RUN_LABEL)-$(SPLIT)-default" --output-root "$(PY_DEFAULT_OUTPUT_DIR)" --language "$(LANGUAGE)" --overwrite; \
	else \
		echo "dry-run only; set RUN=1 after split-corpus has written $(SPLIT_RECORDS)"; \
	fi

run-candidate: prepare validate-config
	@echo "+ $(MANAGE) run_linguistic_pipeline_experiment --input-records-jsonl $(PY_SPLIT_RECORDS) --start-stage segmentation_phase_2 --end-stage segmentation_phase_2 --stage-parameters-file $(PY_CANDIDATE_PARAMS) --set-stage-parameter segmentation_phase_2.fewshot_count=$(FEWSHOT_COUNT) --run-label $(RUN_LABEL)-$(SPLIT)-candidate-fewshots-$(FEWSHOT_COUNT) --output-root $(PY_CANDIDATE_OUTPUT_DIR) --language $(LANGUAGE) --overwrite"
	@if [ "$(RUN)" = "1" ]; then \
		$(MANAGE) run_linguistic_pipeline_experiment --input-records-jsonl "$(PY_SPLIT_RECORDS)" --start-stage segmentation_phase_2 --end-stage segmentation_phase_2 --stage-parameters-file "$(PY_CANDIDATE_PARAMS)" --set-stage-parameter "segmentation_phase_2.fewshot_count=$(FEWSHOT_COUNT)" --run-label "$(RUN_LABEL)-$(SPLIT)-candidate-fewshots-$(FEWSHOT_COUNT)" --output-root "$(PY_CANDIDATE_OUTPUT_DIR)" --language "$(LANGUAGE)" --overwrite; \
	else \
		echo "dry-run only; set RUN=1 FEWSHOT_COUNT=<small|medium|all|N> after split-corpus and derive-processing-examples are ready"; \
	fi

evaluate: prepare validate-config
	@echo "TODO: run evaluator $(EVALUATOR_CONFIG) over generated/default and generated/candidate outputs."
	@echo "Expected future command: $(MANAGE) run_linguistic_pipeline_experiment --evaluator-config $(abspath $(EVALUATOR_CONFIG)) --compare-with ..."

compare: prepare
	@echo "TODO: aggregate default-vs-candidate evaluator outputs into win/loss/tie counts and flagged examples."

report: prepare
	@echo "TODO: build $(GENERATED_DIR)/report.md from comparison outputs."

clean:
	@rm -rf "$(GENERATED_DIR)" "$(TMP_DIR)"
