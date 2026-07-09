# ISSUE-0036: Systematize creation and evaluation of few-shot examples for linguistic annotation

- **Status:** active
- **Priority:** P1
- **Created:** 2026-06-02T20:39:51Z
- **Updated:** 2026-07-09T04:25:00Z
- **Origin:** human-suggestion
- **Deadline:** None
- **Dependencies:** [ISSUE-0003](ISSUE-0003.md), [ISSUE-0004](ISSUE-0004.md)
- **Canonical JSON:** [ISSUE-0036.json](ISSUE-0036.json)

## Notes

Created from human suggestion #26 (submitted by mannyrayner on 2026-06-02) and escalated to P1 after
maintainer review on 2026-06-02 because current annotation errors are frequent, few-shot quality is
a plausible contributor, and the work can provide strong evidence for the First Progress Report. The
current few-shot examples for linguistic annotation have largely been produced in one-off Codex
passes. Recent segmentation_phase_2 work suggests larger example sets can help, but the examples
themselves may contain linguistic mistakes, uneven language coverage, and unclear ordering/tranche
design. Track a principled generate -> adversarial review -> repair -> gold acceptance workflow for
generating, validating, versioning, and evaluating few-shot examples for linguistic annotation
stages (segmentation, MWE detection, lemma/gloss support where appropriate). The architecture should
generate many candidate examples per operation/language, validate them against explicit schemas
before linguistic judgement, ask critic models to find defects and classify severity, repair
plausible defects before discarding examples, score candidates by schema pass, linguistic
confidence, critic agreement, and severity penalties, and store auditable records containing
original generated examples, operation/language metadata, validation results, critic comments,
repairs, final accepted versions, acceptance rationale, and model/prompt versions. The issue should
coordinate with ISSUE-0003 and ISSUE-0004 so example-set changes can be measured systematically
rather than eyeballed, and with ISSUE-0005/ISSUE-0006 for segmentation-specific evidence. Initial
roadmap: docs/roadmap/few-shot-example-curation.md. Follow-up maintainer review on 2026-06-02
clarified the intended operating model: curation should be incremental, with management-command and
admin-UI invocation paths, durable curation requests, batch statuses, separate auditable records
under a docs/few_shot_curation-style tree, compact derived prompt assets under prompts/, and review
surfaces for accepting, repairing, rejecting, or promoting examples. A minimal first implementation
now provides a curate_fewshots management command plus core storage/validation helpers for
segmentation_phase_2 candidate generation, deterministic schema validation, auditable
docs/few_shot_curation records, and optional prompt-variant export for valid candidates. Follow-up
command work added visible trace output and fan-out/fan-in generation shards controlled by
batch-size and max-concurrency settings so larger requests do not appear stalled and can complete
more efficiently. A minimal second-step review implementation now provides a review_fewshots
management command: it creates multiple language-specific hostile-review template drafts when no
template exists, reconciles them with an AI call, stores the final template, and runs concurrent AI
reviews that classify candidate defects by severity. Follow-up prompt revision reframed review as a
plain language-specific word/unit-boundary task over input plus boundary_marked strings, because
deterministic validation has already checked preservation and the critic should judge whether the
markers define appropriate word-like or meaningful units rather than reason about C-LARA-2
internals. A further review-prompt revision avoids the word token in generated templates, gives
explicit French clitic guidance (productive clitics/elisions should often be separated; lexicalized
apostrophe forms should remain intact), checks request IDs before expensive template generation, and
exposes longer API timeouts for review runs. A later review-prompt revision adds explicit
positive/negative examples (e.g. split the clitic in the boy¦'s, split transparent bubble¦gum,
reject false bar¦becue, keep lexicalized aujourd'hui), removes the word token from draft
instructions, and replaces accidental {boundary_marker} placeholders during review prompt rendering.
Follow-up on 2026-06-04: the first French segmentation_phase_2/boundary_first clitic_compound_v2
smoke test is encouraging. From a 40-candidate generated set, deterministic validation plus AI
hostile review retained eight examples; maintainer review found all eight retained examples correct.
The process may be somewhat overstrict, pruning a few acceptable examples, but this is preferable
for few-shot promotion. The run also exposed that validation-failed candidates with missing
interword spaces were still being sent to AI review; review_candidate_batch now re-runs
deterministic validation, skips invalid records, and records skipped validation failures in the
summary.

Follow-up on 2026-06-19: the first imported French evaluation corpus has been sized through the
experiment Makefile target `make summarize-corpus RUN=1`. The maintainer-reported laptop run for
user `mannyrayner`, language `fr`, exact match found 53 projects, all with segmentation_phase_2
artifacts, 1600 segments, 17344 current segmentation tokens, 10566 non-whitespace tokens, 6778
whitespace-only tokens, and 60 empty-token segments. This is sufficient for a report-quality first
experiment if split conservatively. Next implementation should create deterministic development/test
manifests from the corpus summary, keep held-out test data isolated from prompt/evaluator tuning,
derive processing/evaluator assets from audited accepted examples, then run default-vs-candidate
comparisons over the fixed splits.

Implementation follow-up on 2026-06-19: added the deterministic split step proposed by the roadmap.
The experiment now has a `make split-corpus` target backed by `split_french_evaluation_corpus`,
which reads `generated/corpus_summary/corpus_summary.json` and writes
`generated/corpus_splits/development.jsonl`, `generated/corpus_splits/test.jsonl`, and
`generated/corpus_splits/split_manifest.json`. The split is project-separated, size-stratified,
seed-stable, and segment-capped. The manifest records the explicit hypotheses and the required human
audit gates: pre-tuning split audit, development-set evaluator audit during tuning, and final
held-out test audit before report claims.

Implementation follow-up later on 2026-06-19: added the next derivation step. The experiment now has
`derive-processing-examples` and `derive-evaluator-examples` Make targets backed by
`derive_fewshot_assets`, which reads reviewed and human-audited curation items, derives compact
prompt-facing examples for `prompts/segmentation_phase_2/variants/clitic_compound_v2/fewshots/`,
writes evaluator examples under `generated/derived_assets/evaluator_examples.jsonl`, and records
shared provenance in a derivation manifest. This preserves the audit chain from generated candidate
through AI review and human audit into both processing and evaluator assets. The roadmap also
records this thread as process evidence for the report's AI-autonomy theme: the AI assistant
proposed and implemented the experiment design, leakage controls, hypotheses, audit gates, Make
targets, tests, and documentation under human supervision.

Implementation follow-up on 2026-06-20: added the first runnable processing-experiment slice. The
`run_linguistic_pipeline_experiment` management command now supports `segmentation_phase_2` over
JSONL split manifests, writing per-record outputs, per-record stage artifacts, and a run manifest.
The experiment Makefile's `run-default` and `run-candidate` targets now call this command over
`SPLIT=development` or `SPLIT=test` with the default and `clitic_compound_v2` candidate parameter
bundles. This completes the processing side of the default-vs-candidate setup; the next remaining
step is evaluator/comparison/report generation.

Follow-up on 2026-06-20: candidate processing runs now expose the few-shot tranche as an experiment
parameter. `run_linguistic_pipeline_experiment` accepts repeated `--set-stage-parameter
stage.key=value` overrides, and the French experiment Makefile's `run-candidate` target passes
`FEWSHOT_COUNT` through to `segmentation_phase_2.fewshot_count`. This lets development runs compare
small, medium, all, or numeric accepted-example counts before locking the held-out test setting,
addressing the risk that more few-shot examples may top out or become counterproductive.

Follow-up on 2026-07-04: the next concrete slice for this issue is an English MWE prompt-improvement
pilot built from seven hand-annotated development projects in the focused multilingual MWE
workbench. After page-oriented manual annotation and metadata refresh, the sample contains 336
segments, 5,104 tokens, and 140 manually corrected MWEs across projects 239, 245, 254, 255, 257,
261, and 263. Treat this as development data only: use it for baseline scoring, error analysis, and
prompt/few-shot iteration; keep validation/test projects untouched until the comparison procedure is
fixed. This is also useful report evidence for AI autonomy because the AI proposed the experiment
structure, implemented metadata refresh tooling, and maintained the issue/roadmap/report trail,
while the human supplied domain judgement, manual gold corrections, and go/no-go decisions.

Implementation follow-up on 2026-07-07: extended the focused multilingual MWE workbench with the
first snapshot-backed prompt-scoring loop. Added a snapshot_mwe_experiment_projects management
command and Make target to save snapshots for selected split projects, marking MWE annotations,
gloss annotations, and lemma annotations as gold-standard components. Added Make targets and
management commands to run current MWE prompts over extracted MWE segment records, score predicted
MWE spans against extracted gold spans, and write conservative prompt-improvement guidance from
false-positive/false-negative examples. The improvement proposal is intentionally general and does
not edit production prompts automatically; it is meant to support human review and avoid overfitting
to development examples.

MWE experiment progress follow-up on 2026-07-07: maintainer testing showed run-current-mwe looked
idle while processing API calls. The run_mwe_prompt_experiment command now prints per-record
running/finished/error messages, writes progress.jsonl incrementally, and appends outputs.jsonl one
record at a time so long runs expose current position and partial results before completion.
Follow-up on 2026-07-07: the first 600-record MWE run showed that the development segment file can
contain projects outside the seven-project hand-curated subset if PROJECT_IDS is not applied to the
run/score stages. The focused MWE Make targets and commands now pass and honor --project-ids for
run-current-mwe and score-current-mwe, so existing broad outputs can be rescored for only the
selected projects and new prompt runs can avoid processing out-of-scope records. Follow-up on
2026-07-08: maintainer testing found one remaining subset leak because
propose-mwe-prompt-improvement read the existing score directory without honoring PROJECT_IDS. The
proposal command and Make target now accept --project-ids, filter per-record score examples before
building prompt_improvement.md, recompute the displayed score summary for the selected subset, and
print trace counts showing total scored records versus records used after filtering. Follow-up on
2026-07-08: added the first MWE iterative prompt-cycle machinery. The focused MWE workbench now
supports cycle-specific generated prompt templates, a --template-file path for
run_mwe_prompt_experiment, Make targets to prepare/run/score/propose per-cycle prompts, and README
instructions for the seven-project sanity-check cycle before scaling to larger annotated
English/French/German data. Follow-up on 2026-07-08: clarified and implemented explicit MWE gold
declaration for the seven-project sanity-check workflow. Added export_mwe_gold_subset to write all
selected-project segment records directly from latest MWE artifacts, with summary/review files and a
require-gold check; added Make targets declare-mwe-gold and check-mwe-gold, made cycle runs consume
the explicit gold JSONL, and added a high-level mwe-prompt-cycle target plus results display so
progress is visible through gold scores and per-segment score records. Follow-up later on
2026-07-08: fixed a workflow inconsistency found during maintainer testing. The current-prompt
sanity-check target run-current-mwe now reads MWE_RUN_RECORDS, defaulting to the explicit
selected-project MWE_GOLD_RECORDS produced by declare-mwe-gold, instead of the older capped corpus
split JSONL. README guidance now states this directly so gold_mwes from selected_segments.jsonl are
preserved in current-prompt outputs. Follow-up on 2026-07-08: added an AI-assisted MWE
prompt-revision command and Make target revise-mwe-prompt-cycle-template, which reads the current
cycle prompt plus prompt_improvement.md/candidate_prompt_guidance.txt and writes an auditable
next-cycle template_revision.txt plus template_revision.json while instructing the model to keep
changes simple, general, and non-memorised. Follow-up later on 2026-07-08: changed the MWE
prompt-revision default model to gpt-5.5 because this is the highest-leverage once-per-cycle step,
while keeping MWE_REVISION_MODEL overridable for cheaper smoke tests. Follow-up later on 2026-07-08:
removed the explicit temperature=0 override from MWE prompt revision calls so gpt-5.5 can use its
supported default temperature. Follow-up on 2026-07-09: after five MWE prompt cycles, added
summarize_mwe_prompt_cycles and a compare-mwe-prompt-cycles Make target to collect per-cycle
precision/recall/F1, exact-match, TP/FP/FN, prompt length, revision length, and artifact paths in
one report. README now records the next hypothesis to test: whether supplying whole-segment
translation context improves MWE recall, starting with the gloss-language translation as a
controlled cycle variant. Follow-up later on 2026-07-09: implemented the first translation-context
MWE variant. Gold export now carries a translation_context list from the latest translation stage
when available, run_mwe_prompt_experiment can pass it via --use-translation-context, pipeline.mwe
includes the context only under an explicit mwe_translation_context annotation, and prompt revision
now asks for concise translation-aware revisions rather than longer over-elaborate prompts.
Follow-up later on 2026-07-09: added MWE_PROMPT_CYCLE_SERIES so translation-context prompt cycles
can start from cycle_1 in a separate subdirectory instead of continuing the prompt-only series;
README now gives cut-and-paste commands for the translation_context series and explains comparing
its cycle_comparison.md with the prompt-only report. Follow-up later on 2026-07-09: README now
includes cut-and-paste translation-context commands beginning with declare-mwe-gold, a Python sanity
check for translation_context records, mwe-prompt-cycle, revise-mwe-prompt-cycle-template, and
compare-mwe-prompt-cycles; run_mwe_prompt_experiment now prints and records
translation_context_record_count when translation context is enabled. Follow-up later on 2026-07-09:
replaced the inline README Python translation_context sanity check with a
check-mwe-translation-context Make target so the translation-context workflow remains consistently
Make-driven. Follow-up later on 2026-07-09: fixed check-mwe-translation-context to use the
Python-normalized MWE gold path, matching other Make targets on Windows/Cygwin; no
SNAPSHOT_NAME_PREFIX is required for the check target. Follow-up later on 2026-07-09: documented
translation-context sanity-check findings in the focused MWE README. The initial translation-context
series underperformed the prompt-only series, so next proposed variants are explicit translation-use
guidance plus a two-step analysis-before-selection prompt, and a prompt-only analysis variant to
separate reasoning-structure effects from translation-context effects. Follow-up later on
2026-07-09: prepared the translation_context_analysis_v1 controlled MWE cycle series. Added a
concise analysis-before-selection seed prompt, a Makefile MWE_CYCLE_INITIAL_TEMPLATE override for
cycle 1 seeding, and README cut-and-paste commands to run the fresh translation-aware series with
explicit translation-use guidance while keeping prior prompt-only and translation_context series
comparable. Follow-up later on 2026-07-09: extended translation_context_analysis_v1 outputs to
preserve the model candidate analysis as mwe_analysis alongside selected MWEs. Scoring and
prompt-improvement reports now carry that analysis forward, giving revise-mwe-prompt-cycle-template
richer evidence about why false positives and false negatives occurred. Follow-up later on
2026-07-09: added a format_mwe_prompt_outputs command and format-mwe-prompt-cycle-output Make target
so cycle outputs.jsonl can be rendered as readable Markdown with segment text, gold/predicted MWEs,
model analysis, and translation context. Follow-up later on 2026-07-09: hardened the MWE output
formatter after maintainer testing found that some model analysis fields can be structured values
rather than strings; formatter text fields now coerce lists/dicts safely when building Markdown.
