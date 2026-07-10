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
MWE_GOLD_DIR ?= $(abspath $(GENERATED_DIR))/mwe_gold/$(MWE_LANGUAGE)-$(SPLIT)
MWE_GOLD_RECORDS ?= $(MWE_GOLD_DIR)/selected_segments.jsonl
MWE_GOLD_SUMMARY ?= $(MWE_GOLD_DIR)/summary.json
MWE_GOLD_REVIEW ?= $(MWE_GOLD_DIR)/review.md
MWE_RUN_RECORDS ?= $(MWE_GOLD_RECORDS)
MWE_CYCLE_RECORDS ?= $(MWE_GOLD_RECORDS)
GENERATED_DIR := generated
MWE_PROMPT_CYCLE_NUMBER ?= 1
MWE_CYCLE_RUN_LABEL ?= run
MWE_PROMPT_CYCLE_ROOT_DIR ?= $(abspath $(GENERATED_DIR))/mwe_prompt_cycles/$(MWE_LANGUAGE)-$(SPLIT)
MWE_PROMPT_CYCLE_SERIES ?=
MWE_PROMPT_CYCLE_BASE_DIR := $(if $(strip $(MWE_PROMPT_CYCLE_SERIES)),$(MWE_PROMPT_CYCLE_ROOT_DIR)/$(MWE_PROMPT_CYCLE_SERIES),$(MWE_PROMPT_CYCLE_ROOT_DIR))
MWE_PROMPT_CYCLE_DIR := $(MWE_PROMPT_CYCLE_BASE_DIR)/cycle_$(MWE_PROMPT_CYCLE_NUMBER)
MWE_CYCLE_TEMPLATE := $(MWE_PROMPT_CYCLE_DIR)/template.txt
MWE_BASE_TEMPLATE ?= $(ROOT_DIR)/prompts/mwe/$(MWE_LANGUAGE)/template.txt
MWE_DEFAULT_TEMPLATE ?= $(ROOT_DIR)/prompts/mwe/default/template.txt
MWE_CYCLE_INITIAL_TEMPLATE ?=
MWE_CYCLE_OUTPUTS_JSONL := $(MWE_PROMPT_CYCLE_DIR)/$(MWE_CYCLE_RUN_LABEL)/outputs.jsonl
MWE_CYCLE_OUTPUTS_MARKDOWN := $(MWE_PROMPT_CYCLE_DIR)/$(MWE_CYCLE_RUN_LABEL)/outputs.md
MWE_CYCLE_SCORE_DIR := $(MWE_PROMPT_CYCLE_DIR)/score
MWE_CYCLE_IMPROVEMENT_DIR := $(MWE_PROMPT_CYCLE_DIR)/improvement
MWE_CYCLE_REVISION := $(MWE_CYCLE_IMPROVEMENT_DIR)/template_revision.txt
MWE_CYCLE_REVISION_JSON := $(MWE_CYCLE_IMPROVEMENT_DIR)/template_revision.json
MWE_CYCLE_COMPARISON_JSON := $(MWE_PROMPT_CYCLE_BASE_DIR)/cycle_comparison.json
MWE_CYCLE_COMPARISON_MD := $(MWE_PROMPT_CYCLE_BASE_DIR)/cycle_comparison.md
MWE_REVISION_MODEL ?= gpt-5.5
MWE_USE_TRANSLATION_CONTEXT ?= 0
MWE_RECONCILE_ANALYSIS_TEMPLATE_DIR ?= config/translation_context_reconcile_v1/analysis
MWE_RECONCILE_TEMPLATE ?= config/translation_context_reconcile_v1/reconcile.txt
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
PY_MWE_GOLD_RECORDS := $(call python_path,$(MWE_GOLD_RECORDS))
PY_MWE_GOLD_SUMMARY := $(call python_path,$(MWE_GOLD_SUMMARY))
PY_MWE_GOLD_REVIEW := $(call python_path,$(MWE_GOLD_REVIEW))
PY_MWE_RUN_RECORDS := $(call python_path,$(MWE_RUN_RECORDS))
PY_MWE_CYCLE_RECORDS := $(call python_path,$(MWE_CYCLE_RECORDS))
PY_MWE_PROMPT_CYCLE_BASE_DIR := $(call python_path,$(MWE_PROMPT_CYCLE_BASE_DIR))
PY_MWE_PROMPT_CYCLE_DIR := $(call python_path,$(MWE_PROMPT_CYCLE_DIR))
PY_MWE_CYCLE_TEMPLATE := $(call python_path,$(MWE_CYCLE_TEMPLATE))
PY_MWE_CYCLE_OUTPUTS_JSONL := $(call python_path,$(MWE_CYCLE_OUTPUTS_JSONL))
PY_MWE_CYCLE_OUTPUTS_MARKDOWN := $(call python_path,$(MWE_CYCLE_OUTPUTS_MARKDOWN))
PY_MWE_CYCLE_SCORE_DIR := $(call python_path,$(MWE_CYCLE_SCORE_DIR))
PY_MWE_CYCLE_IMPROVEMENT_DIR := $(call python_path,$(MWE_CYCLE_IMPROVEMENT_DIR))
PY_MWE_CYCLE_REVISION := $(call python_path,$(MWE_CYCLE_REVISION))
PY_MWE_CYCLE_REVISION_JSON := $(call python_path,$(MWE_CYCLE_REVISION_JSON))
PY_MWE_CYCLE_COMPARISON_JSON := $(call python_path,$(MWE_CYCLE_COMPARISON_JSON))
PY_MWE_CYCLE_COMPARISON_MD := $(call python_path,$(MWE_CYCLE_COMPARISON_MD))
PY_MWE_RECONCILE_ANALYSIS_TEMPLATE_DIR := $(call python_path,$(abspath $(MWE_RECONCILE_ANALYSIS_TEMPLATE_DIR)))
PY_MWE_RECONCILE_TEMPLATE := $(call python_path,$(abspath $(MWE_RECONCILE_TEMPLATE)))
FAIL_FAST_ARG := $(if $(filter 1,$(FAIL_FAST)),--fail-fast,)
MWE_TRANSLATION_CONTEXT_ARG := $(if $(filter 1,$(MWE_USE_TRANSLATION_CONTEXT)),--use-translation-context,)

MANAGE := cd $(PLATFORM_DIR) && PYTHONPATH= DJANGO_SETTINGS_MODULE=platform_server.settings $(PYTHON) manage.py

.PHONY: help prepare declare-mwe-gold check-mwe-gold check-mwe-translation-context mwe-prompt-cycle mwe-reconcile-prompt-cycle recover-mwe-prompt-cycle-after-run show-mwe-prompt-cycle-results compare-mwe-prompt-cycles prepare-mwe-prompt-cycle run-mwe-prompt-cycle run-mwe-reconcile-prompt-cycle resume-mwe-prompt-cycle format-mwe-prompt-cycle-output score-mwe-prompt-cycle propose-mwe-prompt-cycle-improvement revise-mwe-prompt-cycle-template extract-split-corpus snapshot-gold-projects snapshot-gold-projects-dry-run run-current-mwe score-current-mwe propose-mwe-prompt-improvement refresh-project-metadata refresh-annotations refresh-annotations-dry-run refresh-upstream refresh-upstream-dry-run validate-config clean

help:
	@echo "Focused MWE experiments (multilingual)"
	@echo
	@echo "Targets:"
	@echo "  extract-split-corpus  Extract segment records and create project-separated dev/validation/test splits"
	@echo "  snapshot-gold-projects  Save project snapshots marking MWE, gloss, and lemma as gold standard"
	@echo "  run-current-mwe    Run current MWE prompt over extracted segment records"
	@echo "  score-current-mwe  Score current MWE prompt output against gold MWEs"
	@echo "  propose-mwe-prompt-improvement  Write conservative prompt-improvement guidance from score errors"
	@echo "  declare-mwe-gold  Snapshot selected projects and export explicit gold records"
	@echo "  check-mwe-gold    Re-export selected gold records and fail if no gold MWEs are found"
	@echo "  check-mwe-translation-context  Count records with exported translation_context"
	@echo "  mwe-prompt-cycle  Run prepare/run/score/propose for the selected cycle"
	@echo "  mwe-reconcile-prompt-cycle  Run three analysis prompts plus reconciliation, then format/score/propose"
	@echo "  recover-mwe-prompt-cycle-after-run  Rebuild formatted output, score, and improvement artifacts from an existing cycle run"
	@echo "  show-mwe-prompt-cycle-results  Print cycle summary and per-segment score path"
	@echo "  compare-mwe-prompt-cycles  Collect score/prompt-size trends across completed cycles"
	@echo "  prepare-mwe-prompt-cycle  Create/reuse a cycle-specific MWE prompt template"
	@echo "  run-mwe-prompt-cycle      Run a cycle-specific MWE prompt template"
	@echo "  run-mwe-reconcile-prompt-cycle  Run three MWE analyses plus reconciliation for a cycle"
	@echo "  resume-mwe-prompt-cycle   Run missing records for a cycle with an existing run/outputs.jsonl"
	@echo "  format-mwe-prompt-cycle-output  Render cycle outputs.jsonl as readable Markdown"
	@echo "  score-mwe-prompt-cycle    Score a cycle-specific MWE prompt run"
	@echo "  propose-mwe-prompt-cycle-improvement  Write cycle-specific improvement guidance"
	@echo "  revise-mwe-prompt-cycle-template  Use AI to write the next-cycle prompt draft"
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
	@echo "  MWE_GOLD_RECORDS=$(MWE_GOLD_RECORDS)"
	@echo "  MWE_RUN_RECORDS=$(MWE_RUN_RECORDS)"
	@echo "  MWE_PROMPT_CYCLE_NUMBER=$(MWE_PROMPT_CYCLE_NUMBER)"
	@echo "  MWE_PROMPT_CYCLE_ROOT_DIR=$(MWE_PROMPT_CYCLE_ROOT_DIR)"
	@echo "  MWE_PROMPT_CYCLE_SERIES=$(MWE_PROMPT_CYCLE_SERIES)"
	@echo "  MWE_PROMPT_CYCLE_DIR=$(MWE_PROMPT_CYCLE_DIR)"
	@echo "  MWE_REVISION_MODEL=$(MWE_REVISION_MODEL)"
	@echo "  MWE_CYCLE_INITIAL_TEMPLATE=$(MWE_CYCLE_INITIAL_TEMPLATE)"
	@echo "  MWE_CYCLE_COMPARISON_MD=$(MWE_CYCLE_COMPARISON_MD)"
	@echo "  MWE_USE_TRANSLATION_CONTEXT=$(MWE_USE_TRANSLATION_CONTEXT)"

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

declare-mwe-gold: prepare
	@echo "+ snapshot selected projects and export explicit MWE gold records to $(PY_MWE_GOLD_RECORDS)"
	@if [ "$(RUN)" = "1" ]; then \
		$(MANAGE) snapshot_mwe_experiment_projects --project-ids "$(PROJECT_IDS)" --split-manifest "$(PY_SPLIT_MANIFEST)" --splits "$(SPLIT)" --snapshot-name-prefix "$(SNAPSHOT_NAME_PREFIX)"; \
		$(MANAGE) export_mwe_gold_subset --project-ids "$(PROJECT_IDS)" --language "$(MWE_LANGUAGE)" --split "$(SPLIT)" --output-jsonl "$(PY_MWE_GOLD_RECORDS)" --summary-json "$(PY_MWE_GOLD_SUMMARY)" --review-markdown "$(PY_MWE_GOLD_REVIEW)" --overwrite; \
	else \
		echo "dry-run only; set RUN=1 to snapshot selected projects and export gold records"; \
	fi

check-mwe-gold: prepare
	@echo "+ $(MANAGE) export_mwe_gold_subset --project-ids $(PROJECT_IDS) --language $(MWE_LANGUAGE) --split $(SPLIT) --output-jsonl $(PY_MWE_GOLD_RECORDS) --summary-json $(PY_MWE_GOLD_SUMMARY) --review-markdown $(PY_MWE_GOLD_REVIEW) --require-gold --overwrite"
	@if [ "$(RUN)" = "1" ]; then \
		$(MANAGE) export_mwe_gold_subset --project-ids "$(PROJECT_IDS)" --language "$(MWE_LANGUAGE)" --split "$(SPLIT)" --output-jsonl "$(PY_MWE_GOLD_RECORDS)" --summary-json "$(PY_MWE_GOLD_SUMMARY)" --review-markdown "$(PY_MWE_GOLD_REVIEW)" --require-gold --overwrite; \
	else \
		echo "dry-run only; set RUN=1 to verify selected gold records contain at least one gold MWE"; \
	fi

check-mwe-translation-context: prepare
	@MWE_GOLD_RECORDS="$(PY_MWE_GOLD_RECORDS)" $(PYTHON) -c 'import json, os; from pathlib import Path; path = Path(os.environ["MWE_GOLD_RECORDS"]); records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]; with_translation = [record for record in records if record.get("translation_context")]; print(f"records={len(records)} records_with_translation_context={len(with_translation)}"); print(with_translation[0]["record_id"], with_translation[0]["translation_context"][0]) if with_translation else None'

mwe-prompt-cycle: run-mwe-prompt-cycle format-mwe-prompt-cycle-output score-mwe-prompt-cycle propose-mwe-prompt-cycle-improvement
	@echo "MWE prompt cycle $(MWE_PROMPT_CYCLE_NUMBER) complete."
	@echo "Readable outputs: $(MWE_CYCLE_OUTPUTS_MARKDOWN)"
	@echo "Summary: $(MWE_CYCLE_SCORE_DIR)/summary.md"
	@echo "Per-segment scores: $(MWE_CYCLE_SCORE_DIR)/per_record_scores.jsonl"
	@echo "Improvement report: $(MWE_CYCLE_IMPROVEMENT_DIR)/prompt_improvement.md"

mwe-reconcile-prompt-cycle: run-mwe-reconcile-prompt-cycle format-mwe-prompt-cycle-output score-mwe-prompt-cycle propose-mwe-prompt-cycle-improvement
	@echo "MWE reconcile prompt cycle $(MWE_PROMPT_CYCLE_NUMBER) complete."
	@echo "Readable outputs: $(MWE_CYCLE_OUTPUTS_MARKDOWN)"
	@echo "Summary: $(MWE_CYCLE_SCORE_DIR)/summary.md"
	@echo "Per-segment scores: $(MWE_CYCLE_SCORE_DIR)/per_record_scores.jsonl"
	@echo "Improvement report: $(MWE_CYCLE_IMPROVEMENT_DIR)/prompt_improvement.md"

recover-mwe-prompt-cycle-after-run: resume-mwe-prompt-cycle format-mwe-prompt-cycle-output score-mwe-prompt-cycle propose-mwe-prompt-cycle-improvement
	@echo "Recovered MWE prompt cycle $(MWE_PROMPT_CYCLE_NUMBER) artifacts from existing run output."
	@echo "Readable outputs: $(MWE_CYCLE_OUTPUTS_MARKDOWN)"
	@echo "Summary: $(MWE_CYCLE_SCORE_DIR)/summary.md"
	@echo "Per-segment scores: $(MWE_CYCLE_SCORE_DIR)/per_record_scores.jsonl"
	@echo "Improvement report: $(MWE_CYCLE_IMPROVEMENT_DIR)/prompt_improvement.md"

show-mwe-prompt-cycle-results: prepare
	@if [ -f "$(MWE_CYCLE_SCORE_DIR)/summary.md" ]; then cat "$(MWE_CYCLE_SCORE_DIR)/summary.md"; else echo "Missing $(MWE_CYCLE_SCORE_DIR)/summary.md" >&2; exit 1; fi
	@echo
	@echo "Per-segment scores: $(MWE_CYCLE_SCORE_DIR)/per_record_scores.jsonl"
	@echo "Improvement report: $(MWE_CYCLE_IMPROVEMENT_DIR)/prompt_improvement.md"

run-current-mwe: prepare
	@echo "+ $(MANAGE) run_mwe_prompt_experiment --input-records-jsonl $(PY_MWE_RUN_RECORDS) --output-dir $(PY_MWE_RUN_OUTPUT_DIR) --run-label $(MWE_RUN_LABEL) --limit $(MWE_LIMIT) --project-ids $(PROJECT_IDS) $(MWE_TRANSLATION_CONTEXT_ARG) --overwrite"
	@if [ "$(RUN)" = "1" ]; then \
		$(MANAGE) run_mwe_prompt_experiment --input-records-jsonl "$(PY_MWE_RUN_RECORDS)" --output-dir "$(PY_MWE_RUN_OUTPUT_DIR)" --run-label "$(MWE_RUN_LABEL)" --limit "$(MWE_LIMIT)" --project-ids "$(PROJECT_IDS)" $(MWE_TRANSLATION_CONTEXT_ARG) --overwrite; \
	else \
		echo "dry-run only; set RUN=1 after declare-mwe-gold has written $(MWE_RUN_RECORDS)"; \
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

compare-mwe-prompt-cycles: prepare
	@echo "+ $(MANAGE) summarize_mwe_prompt_cycles --cycle-base-dir $(PY_MWE_PROMPT_CYCLE_BASE_DIR) --output-json $(PY_MWE_CYCLE_COMPARISON_JSON) --output-markdown $(PY_MWE_CYCLE_COMPARISON_MD) --overwrite"
	@if [ "$(RUN)" = "1" ]; then \
		$(MANAGE) summarize_mwe_prompt_cycles --cycle-base-dir "$(PY_MWE_PROMPT_CYCLE_BASE_DIR)" --output-json "$(PY_MWE_CYCLE_COMPARISON_JSON)" --output-markdown "$(PY_MWE_CYCLE_COMPARISON_MD)" --overwrite; \
	else \
		echo "dry-run only; set RUN=1 after at least one cycle has produced score/summary.json"; \
	fi

prepare-mwe-prompt-cycle: prepare
	@if [ "$(RUN)" != "1" ]; then \
		echo "dry-run only; cycle $(MWE_PROMPT_CYCLE_NUMBER) prompt would be prepared at $(MWE_CYCLE_TEMPLATE)"; \
		exit 0; \
	fi; \
	if [ "$(MWE_PROMPT_CYCLE_NUMBER)" -lt 1 ]; then \
		echo "MWE_PROMPT_CYCLE_NUMBER must be >= 1" >&2; \
		exit 1; \
	fi; \
	mkdir -p "$(MWE_PROMPT_CYCLE_DIR)"; \
	if [ "$(MWE_PROMPT_CYCLE_NUMBER)" = "1" ]; then \
		if [ -n "$(MWE_CYCLE_INITIAL_TEMPLATE)" ]; then source_prompt="$(MWE_CYCLE_INITIAL_TEMPLATE)"; elif [ -f "$(MWE_BASE_TEMPLATE)" ]; then source_prompt="$(MWE_BASE_TEMPLATE)"; else source_prompt="$(MWE_DEFAULT_TEMPLATE)"; fi; \
	else \
		previous_cycle=$$(( $(MWE_PROMPT_CYCLE_NUMBER) - 1 )); \
		source_prompt="$(MWE_PROMPT_CYCLE_BASE_DIR)/cycle_$${previous_cycle}/improvement/template_revision.txt"; \
	fi; \
	if [ ! -f "$$source_prompt" ]; then \
		echo "source prompt not found: $$source_prompt" >&2; \
		echo "For cycle >1, copy/edit the previous cycle template into its improvement/template_revision.txt before preparing the next cycle." >&2; \
		exit 1; \
	fi; \
	if [ ! -f "$(MWE_CYCLE_TEMPLATE)" ]; then \
		cp "$$source_prompt" "$(MWE_CYCLE_TEMPLATE)"; \
		echo "Prepared MWE cycle prompt: $(MWE_CYCLE_TEMPLATE)"; \
	else \
		echo "Using existing MWE cycle prompt: $(MWE_CYCLE_TEMPLATE)"; \
	fi

run-mwe-prompt-cycle: prepare-mwe-prompt-cycle
	@echo "+ $(MANAGE) run_mwe_prompt_experiment --input-records-jsonl $(PY_MWE_CYCLE_RECORDS) --output-dir $(PY_MWE_PROMPT_CYCLE_DIR) --run-label $(MWE_CYCLE_RUN_LABEL) --limit $(MWE_LIMIT) --project-ids $(PROJECT_IDS) --template-file $(PY_MWE_CYCLE_TEMPLATE) $(MWE_TRANSLATION_CONTEXT_ARG) --overwrite"
	@if [ "$(RUN)" = "1" ]; then \
		$(MANAGE) run_mwe_prompt_experiment --input-records-jsonl "$(PY_MWE_CYCLE_RECORDS)" --output-dir "$(PY_MWE_PROMPT_CYCLE_DIR)" --run-label "$(MWE_CYCLE_RUN_LABEL)" --limit "$(MWE_LIMIT)" --project-ids "$(PROJECT_IDS)" --template-file "$(PY_MWE_CYCLE_TEMPLATE)" $(MWE_TRANSLATION_CONTEXT_ARG) --overwrite; \
	else \
		echo "dry-run only; set RUN=1 after declare-mwe-gold has written $(MWE_CYCLE_RECORDS), then run $(MWE_CYCLE_TEMPLATE)"; \
	fi

run-mwe-reconcile-prompt-cycle: prepare
	@echo "+ $(MANAGE) run_mwe_reconcile_prompt_experiment --input-records-jsonl $(PY_MWE_CYCLE_RECORDS) --output-dir $(PY_MWE_PROMPT_CYCLE_DIR) --run-label $(MWE_CYCLE_RUN_LABEL) --limit $(MWE_LIMIT) --project-ids $(PROJECT_IDS) --analysis-template-dir $(PY_MWE_RECONCILE_ANALYSIS_TEMPLATE_DIR) --reconcile-template $(PY_MWE_RECONCILE_TEMPLATE) --overwrite"
	@if [ "$(RUN)" = "1" ]; then \
		$(MANAGE) run_mwe_reconcile_prompt_experiment --input-records-jsonl "$(PY_MWE_CYCLE_RECORDS)" --output-dir "$(PY_MWE_PROMPT_CYCLE_DIR)" --run-label "$(MWE_CYCLE_RUN_LABEL)" --limit "$(MWE_LIMIT)" --project-ids "$(PROJECT_IDS)" --analysis-template-dir "$(PY_MWE_RECONCILE_ANALYSIS_TEMPLATE_DIR)" --reconcile-template "$(PY_MWE_RECONCILE_TEMPLATE)" --overwrite; \
	else \
		echo "dry-run only; set RUN=1 after declare-mwe-gold has written $(MWE_CYCLE_RECORDS)"; \
	fi

resume-mwe-prompt-cycle: prepare-mwe-prompt-cycle
	@echo "+ $(MANAGE) run_mwe_prompt_experiment --input-records-jsonl $(PY_MWE_CYCLE_RECORDS) --output-dir $(PY_MWE_PROMPT_CYCLE_DIR) --run-label $(MWE_CYCLE_RUN_LABEL) --limit $(MWE_LIMIT) --project-ids $(PROJECT_IDS) --template-file $(PY_MWE_CYCLE_TEMPLATE) $(MWE_TRANSLATION_CONTEXT_ARG) --resume"
	@if [ "$(RUN)" = "1" ]; then \
		$(MANAGE) run_mwe_prompt_experiment --input-records-jsonl "$(PY_MWE_CYCLE_RECORDS)" --output-dir "$(PY_MWE_PROMPT_CYCLE_DIR)" --run-label "$(MWE_CYCLE_RUN_LABEL)" --limit "$(MWE_LIMIT)" --project-ids "$(PROJECT_IDS)" --template-file "$(PY_MWE_CYCLE_TEMPLATE)" $(MWE_TRANSLATION_CONTEXT_ARG) --resume; \
	else \
		echo "dry-run only; set RUN=1 to append missing records to $(MWE_CYCLE_OUTPUTS_JSONL)"; \
	fi

format-mwe-prompt-cycle-output: prepare
	@echo "+ $(MANAGE) format_mwe_prompt_outputs --outputs-jsonl $(PY_MWE_CYCLE_OUTPUTS_JSONL) --output-markdown $(PY_MWE_CYCLE_OUTPUTS_MARKDOWN) --overwrite"
	@if [ "$(RUN)" = "1" ]; then \
		$(MANAGE) format_mwe_prompt_outputs --outputs-jsonl "$(PY_MWE_CYCLE_OUTPUTS_JSONL)" --output-markdown "$(PY_MWE_CYCLE_OUTPUTS_MARKDOWN)" --overwrite; \
	else \
		echo "dry-run only; set RUN=1 after run-mwe-prompt-cycle has produced $(MWE_CYCLE_OUTPUTS_JSONL)"; \
	fi

score-mwe-prompt-cycle: prepare
	@echo "+ $(MANAGE) score_mwe_prompt_outputs --outputs-jsonl $(PY_MWE_CYCLE_OUTPUTS_JSONL) --output-dir $(PY_MWE_CYCLE_SCORE_DIR) --split $(SPLIT) --project-ids $(PROJECT_IDS) --overwrite"
	@if [ "$(RUN)" = "1" ]; then \
		$(MANAGE) score_mwe_prompt_outputs --outputs-jsonl "$(PY_MWE_CYCLE_OUTPUTS_JSONL)" --output-dir "$(PY_MWE_CYCLE_SCORE_DIR)" --split "$(SPLIT)" --project-ids "$(PROJECT_IDS)" --overwrite; \
	else \
		echo "dry-run only; set RUN=1 after run-mwe-prompt-cycle has produced $(MWE_CYCLE_OUTPUTS_JSONL)"; \
	fi

propose-mwe-prompt-cycle-improvement: prepare
	@echo "+ $(MANAGE) propose_mwe_prompt_improvement --score-dir $(PY_MWE_CYCLE_SCORE_DIR) --output-dir $(PY_MWE_CYCLE_IMPROVEMENT_DIR) --project-ids $(PROJECT_IDS) --overwrite"
	@if [ "$(RUN)" = "1" ]; then \
		$(MANAGE) propose_mwe_prompt_improvement --score-dir "$(PY_MWE_CYCLE_SCORE_DIR)" --output-dir "$(PY_MWE_CYCLE_IMPROVEMENT_DIR)" --project-ids "$(PROJECT_IDS)" --overwrite; \
		if [ ! -f "$(MWE_CYCLE_REVISION)" ]; then cp "$(MWE_CYCLE_TEMPLATE)" "$(MWE_CYCLE_REVISION)"; fi; \
		echo "Editable next-cycle prompt draft: $(MWE_CYCLE_REVISION)"; \
	else \
		echo "dry-run only; set RUN=1 after score-mwe-prompt-cycle has produced $(MWE_CYCLE_SCORE_DIR)"; \
	fi

revise-mwe-prompt-cycle-template: prepare
	@echo "+ $(MANAGE) revise_mwe_prompt_from_report --current-template $(PY_MWE_CYCLE_TEMPLATE) --improvement-report $(PY_MWE_CYCLE_IMPROVEMENT_DIR)/prompt_improvement.md --candidate-guidance $(PY_MWE_CYCLE_IMPROVEMENT_DIR)/candidate_prompt_guidance.txt --output-template $(PY_MWE_CYCLE_REVISION) --output-json $(PY_MWE_CYCLE_REVISION_JSON) --model $(MWE_REVISION_MODEL) --overwrite"
	@if [ "$(RUN)" = "1" ]; then \
		$(MANAGE) revise_mwe_prompt_from_report --current-template "$(PY_MWE_CYCLE_TEMPLATE)" --improvement-report "$(PY_MWE_CYCLE_IMPROVEMENT_DIR)/prompt_improvement.md" --candidate-guidance "$(PY_MWE_CYCLE_IMPROVEMENT_DIR)/candidate_prompt_guidance.txt" --output-template "$(PY_MWE_CYCLE_REVISION)" --output-json "$(PY_MWE_CYCLE_REVISION_JSON)" --model "$(MWE_REVISION_MODEL)" --overwrite; \
	else \
		echo "dry-run only; set RUN=1 after propose-mwe-prompt-cycle-improvement has produced $(MWE_CYCLE_IMPROVEMENT_DIR)/prompt_improvement.md"; \
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
