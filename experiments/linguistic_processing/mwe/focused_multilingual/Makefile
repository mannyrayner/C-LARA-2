# Focused MWE multilingual workbench.
# Targets are dry-run by default where they would make API calls. Use RUN=1 to execute.

MANAGE ?= python manage.py
USERNAME ?= mannyrayner
LANGUAGES ?= en,fr,de
LANGUAGE_MATCH ?= exact
SEED ?= mwe-focused-v1
RUN_LABEL_PREFIX ?= mwe_refresh_v1
WORKBENCH_DIR := $(CURDIR)
ARTIFACT_ROOT ?= $(WORKBENCH_DIR)/artifacts
CORPUS_DIR ?= $(ARTIFACT_ROOT)/corpus
STAGE_PARAMETERS ?= $(WORKBENCH_DIR)/config/stage_parameters.json
SPLITS ?= development,validation,test
RUN ?= 0

.PHONY: plan validate-config extract-corpus refresh-upstream refresh-upstream-dry-run clean

plan:
	@echo "Focused MWE multilingual workbench"
	@echo "  USERNAME=$(USERNAME)"
	@echo "  LANGUAGES=$(LANGUAGES)"
	@echo "  CORPUS_DIR=$(CORPUS_DIR)"
	@echo "  STAGE_PARAMETERS=$(STAGE_PARAMETERS)"
	@echo "  RUN_LABEL_PREFIX=$(RUN_LABEL_PREFIX)"
	@echo ""
	@echo "Typical setup:"
	@echo "  1. make refresh-upstream RUN=1    # rerun segmentation_phase_2 -> translation -> mwe"
	@echo "  2. make extract-corpus            # create project-level splits for manual MWE judging"

validate-config:
	@test -f "$(STAGE_PARAMETERS)" || (echo "Missing $(STAGE_PARAMETERS)" && exit 1)
	@python -m json.tool "$(STAGE_PARAMETERS)" >/dev/null
	@echo "Config OK: $(STAGE_PARAMETERS)"

refresh-upstream: validate-config
ifeq ($(RUN),1)
	$(MANAGE) refresh_mwe_experiment_projects \
		--project-ids "$(PROJECT_IDS)" \
		--split-manifest "$(SPLIT_MANIFEST)" \
		--splits "$(SPLITS)" \
		--run-label-prefix "$(RUN_LABEL_PREFIX)" \
		--stage-parameters-file "$(STAGE_PARAMETERS)" \
		--overwrite
else
	$(MAKE) refresh-upstream-dry-run
endif

refresh-upstream-dry-run: validate-config
	$(MANAGE) refresh_mwe_experiment_projects \
		--project-ids "$(PROJECT_IDS)" \
		--split-manifest "$(SPLIT_MANIFEST)" \
		--splits "$(SPLITS)" \
		--run-label-prefix "$(RUN_LABEL_PREFIX)" \
		--stage-parameters-file "$(STAGE_PARAMETERS)" \
		--dry-run

extract-corpus:
	$(MANAGE) extract_mwe_corpus \
		--username "$(USERNAME)" \
		--languages "$(LANGUAGES)" \
		--language-match "$(LANGUAGE_MATCH)" \
		--output-dir "$(CORPUS_DIR)" \
		--seed "$(SEED)" \
		--overwrite

clean:
	rm -rf "$(ARTIFACT_ROOT)"
