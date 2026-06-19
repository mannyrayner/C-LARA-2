# Roadmap: evaluation of processing quality using a panel of AI judges

This roadmap proposes a structured, repeatable evaluation framework where outputs from C-LARA-2 processing stages are reviewed by AI evaluators, eventually including a **panel of independent AI judges**.

The immediate report-driven priority is a smaller first version for **ISSUE-0004**: use the already-implemented pipeline runner to evaluate phase outputs for segmentation phase 1, segmentation phase 2, and MWE detection. The sharper goal is not only to score outputs, but to show that AI-based judging can tell whether a candidate processing change is an improvement, so that the system can move toward systematic self-improvement. This gives the First Progress Report a concrete autonomy/self-checking example rather than only a future-work promise.


## Initial experiment plan at a glance

The first progress-report experiment should be intentionally small and concrete:

1. **Curate examples.** Use `curate_fewshots` and `review_fewshots` to create a high-confidence set, starting with French `segmentation_phase_2` / `boundary_first` clitic and compound examples.
2. **Post-process for two uses.** Derive compact prompt-facing examples for stage processing, and derive checking examples/rubrics for evaluation. The underlying curated record should stay the source of truth; algorithmic post-processing only changes the wrapper/template around the same accepted example.
3. **Run pipeline variants.** Use a versioned `experiments/.../<experiment>/Makefile` plus a new `manage.py run_linguistic_pipeline_experiment` command to run the same project or fixture from selected start/end stages with either default parameters or curated-set parameters.
4. **Evaluate outputs.** Apply a boundary-quality evaluator that can submit the same checking operation to one model repeatedly, to multiple models, or to a reconciler after voting.
5. **Use realistic inputs.** Draw initial diagnostic inputs from hand-picked fixtures and the now-substantial imported legacy corpus: about 30 legacy pieces are already available, including the largest/challenging cases, so ISSUE-0010 is becoming a source of evaluation material rather than a blocker.
6. **Report cautiously.** Human spot-check retained examples and key wins/losses before making any claim that a curated set improves processing.

Detailed design sections below spell out the judge protocol, artifact contract, CLI controls, aggregation strategies, and report-oriented success criteria.

## Why this matters

Human expert evaluation is the gold standard but is expensive and hard to schedule at the cadence needed for prompt and pipeline iteration. A panel-of-AIs approach can provide:

- fast comparative feedback,
- broad language coverage,
- consistent repeated scoring across experiments,
- richer diagnostics than pass/fail test outcomes,
- concrete evidence for the First Progress Report that C-LARA-2 can begin to inspect its own linguistic-processing quality,
- evidence that AI judging can guide productive changes by comparing default and candidate processing mechanisms on the same inputs.

The goal is not to replace human evaluation, but to create a practical intermediate layer that helps decide what should be sent to human review. For the first implementation, a single strong judge with a versioned rubric is acceptable; the full multi-model panel is the scaling path once the runner/evaluator interface and artifacts are stable.

## Core concept

For each candidate output item (e.g., MWE detection, gloss, translation segment, exercise distractor set), request ratings from up to five strong models (example set: GPT, Claude, Gemini, Grok, DeepSeek), each returning:

1. a score on a 1–5 scale,
2. a short justification,
3. optional error tags (e.g., grammar, semantic mismatch, pedagogical weakness, formatting).

Then aggregate judge outputs into an overall score and diagnostics bundle.

## Methodological stance

- We acknowledge the risk that AI systems may be biased when judging outputs from similar model families.
- Therefore, this roadmap emphasizes **cross-model diversity**, **disagreement tracking**, and **human spot-audits**.
- Panel judgments are treated as decision support, not ground truth.

## Evaluation targets

Initial phases to score:

- **segmentation phase 1 quality** (page/segment boundaries, especially genre-sensitive granularity; directly supports ISSUE-0005),
- **segmentation phase 2 quality** (token boundaries and token-span sanity, especially over-extended lexical tokens; directly supports ISSUE-0006),
- **MWE identification quality** (candidate expression spans, usefulness, and downstream annotation compatibility),
- translation adequacy/fluency,
- lemma/gloss usefulness,
- exercise quality (especially distractor plausibility and pedagogical fit),
- optional romanization quality.

## Judge protocol design

### Input package per item

- source context (segment/page/project metadata),
- operation type and target schema,
- candidate output,
- any available references/constraints,
- explicit scoring rubric.

### Rubric dimensions

- correctness,
- usefulness for learners,
- consistency/format validity,
- level appropriateness,
- safety/undesirable content checks (where relevant).

### Output schema (example)

```json
{
  "overall_score_1_to_5": 4,
  "dimension_scores": {
    "correctness": 4,
    "pedagogical_value": 5,
    "consistency": 4
  },
  "error_tags": ["minor_word_choice"],
  "justification": "Mostly accurate and learner-friendly; one lexical choice is slightly awkward.",
  "confidence": "medium"
}
```

## Aggregation strategies

### Baseline

- simple arithmetic mean of overall scores,
- per-dimension means,
- disagreement indicators (variance/spread).

### Advanced

- weighted averages by model reliability profile,
- robust aggregation (trimmed mean / median) to reduce outlier effect,
- optional **AI foreman** pass that summarizes panel rationale and recommends action.

Foreman mode should never hide raw judge outputs.

## Human-in-the-loop calibration

To maintain validity:

- perform periodic human audits on sampled items,
- compare panel rankings vs human rankings,
- track drift over time and across languages,
- recalibrate prompts/rubrics when alignment degrades.

## Dependencies and current unblockers

- **ISSUE-0003 pipeline runner dependency:** the original ISSUE-0004 blocker is substantially reduced because `run_full_pipeline` can now run from and to selected stages, allowing evaluation to consume reproducible per-phase outputs without stepping through the UI.
- **Prior C-LARA experience:** AI-based evaluation was already tried in C-LARA, so the first C-LARA-2 version should reuse the proven idea rather than wait for an elaborate new framework.
- **ISSUE-0005 and ISSUE-0006 linkage:** the first evaluator should make segmentation prompt/debug work measurable by scoring phase-1 granularity and phase-2 token-span quality.
- **MWE linkage:** MWE detection is a high-value early target because it is linguistically meaningful, downstream-visible in lemma/gloss/audio/HTML behavior, and relatively easy for an AI judge to explain.

## Experimental workflows supported

1. **Prompt/mechanism A/B evaluation**
   - Run candidate prompts, few-shot sets, or whole processing mechanisms over the same dataset.
   - Use judge scores to estimate win rates and confidence, with paired before/after comparisons rather than only absolute scores.
2. **Regression monitoring**
   - Keep benchmark sets for each processing phase.
   - Re-score after major model/pipeline changes.
   - Include a UI-regression track that snapshots key controls/content in major views and flags unexpected diffs for maintainer review.
3. **Error discovery**
   - Cluster low-score items by error tags.
   - Feed clusters into targeted prompt/pipeline fixes.

## Artifact and storage plan

Suggested layout:

```text
evaluation/
  judges/
    config.json
    rubrics/
      mwe.json
      gloss.json
      distractors.json
    runs/
      <run_id>/
        input_items.jsonl
        judge_outputs.jsonl
        aggregate_scores.json
        disagreement_report.json
        foreman_summary.json
```

Each run should store provenance:

- judge model/version,
- prompt versions,
- dataset snapshot/hash,
- timestamp,
- aggregation method.



## Parameterized processing variants for systematic improvement

The first evaluator should be paired with a lightweight parameterization layer. Otherwise the project can score outputs, but cannot easily answer the report-relevant question: *did this processing change make the system better?*

### Stage-level parameters

Each evaluated phase should expose a default mechanism plus named alternatives. A phase invocation should be reproducible from an explicit parameter bundle, for example:

```json
{
  "segmentation_phase_1": {
    "prompt_version": "default"
  },
  "segmentation_phase_2": {
    "mechanism": "json_direct",
    "prompt_version": "default"
  },
  "mwe": {
    "prompt_version": "default",
    "fewshot_set": "default"
  }
}
```

The immediate implementation does not need a complex experiment-management system. It only needs a way for the runner to pass a small parameter dictionary to each stage, record the resolved settings, and write those settings into evaluation artifacts.

### Concrete variant examples

1. **Segmentation phase 1 prompt/few-shot variants**
   - Keep the current prompt/few-shot set as `default`.
   - Add at least one candidate prompt/few-shot version that directly targets ISSUE-0005: prose should normally produce sentence-like segments; poetry should usually preserve line-like segments; dialogue/children's material should avoid pathological over-fragmentation.
   - Evaluate default versus candidate outputs on the same source texts.

2. **Segmentation phase 2 mechanism variants**
   - Keep the current text-to-JSON tokenization route as `json_direct`.
   - Add the ISSUE-0006 candidate route as `boundary_first`: first ask the model to insert token/segment boundaries into the original string while preserving text, validate preservation, then convert the validated boundary-marked string into JSON tokens.
   - Evaluate both mechanisms on examples likely to show over-extended tokens or boundary failures.

3. **MWE prompt/few-shot variants**
   - Keep the current MWE prompt/few-shot set as `default`.
   - Add one or more candidate prompt/few-shot sets that make the desired MWE granularity explicit and include both positive examples and non-MWE distractors.
   - Evaluate whether candidates reduce spurious MWEs while preserving obvious useful expressions.

### Pipeline-level parameter passing

Extend the pipeline runner so a run can specify per-stage settings in one obvious structure and pass each sub-dictionary to the relevant stage. The runner should record:

- stage name, mechanism, prompt version, and few-shot set;
- model settings used for processing;
- input dataset identifier/hash;
- output artifact paths;
- evaluator rubric/version and judge model.

This makes a complete experiment reproducible: input dataset + processing parameter bundle + evaluator parameter bundle.

### Variant-comparison judging workflow

For the report, the most persuasive result would be a paired comparison:

1. Select a small diagnostic dataset for phase 1, phase 2, and MWE.
2. Run the default processing bundle and one candidate bundle on the same inputs.
3. Judge each output independently using the phase-specific evaluator.
4. Optionally ask a comparison judge to see both outputs side by side and choose `default_better`, `candidate_better`, `tie`, or `unclear`, with reasons.
5. Aggregate by task: win/loss/tie counts, mean score deltas, recurrent error tags, and representative examples.
6. Use human spot-checking on the most important wins/losses before claiming that a candidate is genuinely better.

This is the shortest path from AI evaluation to useful autonomy: the AI does not merely detect poor outputs, but helps identify which prompt/mechanism changes are productive.



## Repository experiment workspace

The initial experiments should live under a new top-level `experiments/` workspace. This keeps experiment orchestration close to the repository while keeping bulky generated data out of version control. The intended pattern is:

```text
experiments/
  linguistic_processing/
    segmentation_phase_2/
      fr_boundary_first_clitic_compound_v2/
        Makefile
        README.md
        configs/
          default_stage_parameters.json
          candidate_stage_parameters.json
          evaluator_config.json
        fixtures/
          input_records.jsonl
        generated/        # ignored; command outputs, reviews, reports
        tmp/              # ignored; scratch/intermediate files
```

The repo should contain the lightweight, reviewable orchestration files: `Makefile`, `README.md`, small config JSON files, and small hand-authored fixtures where appropriate. The generated folders (`generated/`, `tmp/`, and any large run-output directories) should be ignored by Git, because they may contain large model outputs, repeated run artifacts, or machine/local paths. If a run becomes report evidence, promote only a compact, curated summary or selected artifact into an explicitly versioned evidence location.

Each specific experiment directory should own a small `Makefile` that documents and runs the intended sequence. For the first French `segmentation_phase_2` experiment, targets should mirror the plan above:

- `make summarize-corpus` — inspect the imported project corpus and write JSON/CSV/Markdown size and anomaly summaries;
- `make split-corpus` — create deterministic development/test manifests from the summarized corpus before any evaluator tuning; this now maps to `split_french_evaluation_corpus` and writes `development.jsonl`, `test.jsonl`, and `split_manifest.json`;
- `make curate` — call `python manage.py curate_fewshots ...` or document the existing curation request used as input;
- `make review` — call `python manage.py review_fewshots ...`;
- `make derive-processing-examples` — post-process accepted curation records into prompt-facing few-shot files or a staged candidate variant; this now maps to `derive_fewshot_assets`;
- `make derive-evaluator-examples` — derive checking/rubric examples from the same accepted records; this is currently produced by the same shared derivation command so processing and evaluator assets keep matching provenance;
- `make run-default` — run `run_linguistic_pipeline_experiment` with default stage parameters;
- `make run-candidate` — run the same inputs with curated-set stage parameters;
- `make evaluate` — run the evaluator/repeated judges/panel over default and candidate outputs;
- `make compare` — aggregate default-vs-candidate results into win/loss/tie counts and flagged examples;
- `make report` — build a concise Markdown summary suitable for human review and possible progress-report evidence.

As of 2026-06-19, the first laptop corpus summary for `mannyrayner`/`fr` reported 53 projects, 1600 segments, and 17344 current segmentation tokens, so the first experiment can move from tiny fixtures to a held-out sample of real imported legacy projects. The next design decision has been made concrete as a deterministic development/test split target: development data is for prompt, few-shot, and evaluator iteration; test data is reserved for the reportable default-vs-candidate comparison.

The top-level `experiments/` directory can later contain other tracks, for example `experiments/linguistic_processing/mwe/...` or `experiments/ui_regression/...`, but the first concrete path should stay narrow: French `segmentation_phase_2`, `boundary_first`, and the `clitic_compound_v2` curated set. This gives maintainers one obvious place to run and inspect the experiment while the underlying infrastructure is still being filled in.

## Manage.py experiment runner for processing + evaluation

The near-term evaluator needs a CLI entry point that can run linguistic processing with explicit parameters and optionally apply evaluation methods to the resulting artifacts. This should be a management command rather than an admin-only UI feature at first, because report experiments need repeatable command lines, visible logs, and durable artifacts.

Provisional command:

```bash
python manage.py run_linguistic_pipeline_experiment \
  --project <project-id-or-slug> \
  --start-stage segmentation_phase_1 \
  --end-stage segmentation_phase_2 \
  --stage-parameters-file experiments/fr_boundary_first_candidate.json \
  --evaluator segmentation_phase_2_boundary_v1 \
  --judge-model gpt-5 \
  --judge-repeats 3 \
  --run-label fr-boundary-first-candidate
```

### Required processing inputs

The command should support two input modes:

1. **Existing project mode:** `--project <id-or-slug>` loads source text and project metadata from the platform database/storage. This is the fastest path for maintainers already using `projects/.../annotation/`.
2. **Standalone fixture mode:** `--source-file`, `--source-json`, or `--input-records-jsonl` runs over a small diagnostic dataset without requiring a database project. This is the right mode for report experiments and regression fixtures.

### Required processing controls

The first version should expose:

- `--start-stage` and `--end-stage`, matching the existing pipeline stage names;
- `--stage-parameters-json` and `--stage-parameters-file`, using the same JSON structure as the power-user pipeline controls in `projects/.../annotation/`;
- `--variant-label` or `--run-label` for human-readable artifact names;
- `--persist-intermediates` defaulting to true;
- `--dry-run`, which resolves stages, prompt/few-shot files, model settings, and output paths without calling models;
- `--output-root`, defaulting to a docs or media experiment-artifact directory depending on whether the run is intended for version-controlled evidence.

For few-shot curation experiments, a candidate parameter bundle might look like:

```json
{
  "segmentation_phase_2": {
    "mechanism": "boundary_first",
    "variant": "clitic_compound_v2",
    "fewshot_count": "small"
  }
}
```

The command must record both requested and resolved parameters: if `variant=clitic_compound_v2` resolves to specific template and few-shot files, those file paths and hashes should be written into the experiment manifest.

### Optional evaluator controls

Evaluation should be optional, because sometimes maintainers only need processing artifacts. When evaluation is requested, the command should support:

- `--evaluator <rubric-name>` for a single evaluator, repeatable for multiple evaluators;
- `--evaluator-config <json-file>` for complex judge/model/rubric settings;
- `--judge-model <model>` and `--judge-repeats <n>` for same-model repeated judging;
- `--judge-panel <json-file>` for multi-model panels;
- `--aggregation voting|mean|median|reconcile` to combine repeated or panel judgements;
- `--compare-with <run-id-or-dir>` for paired default-vs-candidate comparisons.

Curated few-shot examples should be usable both for stage processing and as evaluator exemplars. For processing, an accepted curation record can be algorithmically post-processed into the compact prompt-facing shape expected by the stage, for example by keeping the `input` and converting accepted boundary units into the `output.tokens` representation consumed by `segmentation_phase_2`. For evaluation, the same accepted record can be wrapped in a checking template that asks the model to *check* an output rather than *produce* one. For example, the same French boundary examples that teach `segmentation_phase_2` where to place boundaries can be transformed into a judge prompt that asks whether a proposed output has similarly appropriate word-like or meaningful units.

### Evaluation aggregation modes

The initial implementation can support three increasingly strong modes:

1. **Repeated single-model voting:** run the same evaluator prompt against the same item `n` times and combine labels by majority vote, keeping all raw responses.
2. **Panel voting:** run the same item through several configured judge models and aggregate labels/scores with disagreement statistics.
3. **Reconciliation:** after repeated or panel judgements, ask a final reconciler model to read the raw judgements and produce a final decision with rationale. Reconciliation must preserve links to the raw judge outputs rather than replacing them.

### Artifact contract

A run should produce a directory such as:

```text
evaluation/phase_outputs/runs/<run_id>/
  config.json
  requested_stage_parameters.json
  resolved_stage_parameters.json
  input_records.jsonl
  stage_outputs/
  evaluator_config.json
  judge_outputs.jsonl
  aggregation.json
  comparison_judgments.jsonl
  flagged_items.md
  manifest.json
```

`manifest.json` should include the input dataset identifier/hash, start/end stages, requested and resolved processing parameters, prompt/few-shot file hashes, model settings, evaluator prompt versions, judge models/repeats, aggregation method, and links to any curation request IDs or accepted example IDs used by either processing or evaluation.

### Report-oriented experiment shape

For the First Progress Report, the target demonstration is:

1. Create one or more curated few-shot sets, starting with French `segmentation_phase_2` / `boundary_first`.
2. Summarize the imported French project corpus and create deterministic development/test manifests, keeping the test split held out from prompt/evaluator iteration.
3. Run a default processing bundle and a curated-set candidate bundle over the same split inputs with `run_linguistic_pipeline_experiment`.
4. Evaluate both outputs with a boundary-quality evaluator that can use curated examples as checking exemplars.
5. Combine repeated or panel judgements by voting or reconciliation.
6. Human spot-check the retained examples and the most important evaluator wins/losses.
7. Report a cautious result: whether the curated set appears to improve boundary quality on the diagnostic sample, with artifacts and caveats.

## Report-driven first implementation: phase-output AI evaluator (ISSUE-0004)

This is the near-term implementation target for strengthening the autonomy theme in the First Progress Report. It should be delivered before the full panel architecture if time is limited.

### Scope

Start with three evaluator tasks:

1. **Segmentation phase 1 evaluator**
   - Input: source text plus generated pages/segments.
   - Score whether boundaries are pedagogically useful and genre-appropriate.
   - Default expectations: prose should usually segment at sentence-like units; poetry can preserve line-like units; dialogue and very short learner texts should avoid over-fragmentation.
   - Output tags should include `too_short`, `too_long`, `bad_page_break`, `lost_text`, `genre_mismatch`, and `looks_good`.

2. **Segmentation phase 2 evaluator**
   - Input: phase-1 segment surface plus token list from phase 2.
   - Score token boundary correctness and text preservation.
   - Explicitly flag the ISSUE-0006 failure mode where a lexical token covers an entire segment or an implausibly large span.
   - Output tags should include `overextended_token`, `missing_token`, `extra_token`, `boundary_error`, `text_not_preserved`, and `looks_good`.

3. **MWE evaluator**
   - Input: tokenized segment plus candidate MWE spans/labels.
   - Score whether detected MWEs are plausible, useful for learners, and compatible with downstream lemma/gloss/audio treatment.
   - Output tags should include `missed_obvious_mwe`, `spurious_mwe`, `bad_span`, `bad_label`, `downstream_risk`, and `looks_good`.

### Minimal architecture

- Add a small evaluator interface that accepts normalized phase-output records and a rubric name/version.
- Use the existing OpenAI chat wrapper first; leave provider/model diversity for the later panel phase.
- Require strict JSON output with score, tags, justification, and confidence.
- Keep each evaluator prompt short, explicit, and versioned.
- Store raw phase output, processing parameter bundle, evaluator prompt version, judge model, response JSON, paired-comparison result when available, and aggregate summary in a run artifact.
- Make evaluator failure non-destructive: failed/invalid judge responses should be recorded and reported, not silently converted into passing scores.

### Candidate first dataset

Use a deliberately small but diagnostic suite rather than waiting for a large benchmark:

- a short prose text where phase-1 should prefer sentence-like segments;
- a poem or line-structured text where line boundaries matter;
- a dialogue or child-language-learning text where over-fragmentation is tempting;
- at least one known or suspected ISSUE-0006-style phase-2 token-span failure case;
- a few MWE-rich segments with obvious expressions and non-MWE distractors.

ISSUE-0010 now provides enough coverage for realistic first experiments: about 30 legacy pieces have been imported, including the largest and most challenging cases, and more can be imported quickly if a specific diagnostic need appears. Selected imported projects should therefore become a practical regression/evaluation corpus, while hand-picked fixtures remain useful for synthetic edge cases.

### Output format for the first version

A single run should produce a compact report such as:

```text
evaluation/phase_outputs/runs/<run_id>/
  config.json
  processing_variants.json
  input_records.jsonl
  default_outputs.jsonl
  candidate_outputs.jsonl
  judge_outputs.jsonl
  comparison_judgments.jsonl
  aggregate_scores.json
  flagged_items.md
```

`flagged_items.md` should be readable enough for a human maintainer to inspect quickly and should group findings by issue target: phase-1 segmentation, phase-2 tokenization, and MWE detection.

### Success criteria for the First Progress Report

- The evaluator can run over a fixed sample without UI interaction.
- It produces stable, inspectable artifacts with prompt/model/version metadata.
- It catches at least synthetic or known examples of bad phase-1 granularity, over-extended phase-2 tokens, and bad MWE spans.
- It can compare default and candidate processing variants and produce a clear provisional recommendation (`candidate better`, `default better`, `tie`, or `unclear`) for at least one stage.
- Human review of a small sample finds the AI judgments useful enough to guide debugging and choose promising variants, even if not authoritative.
- The report can honestly say that C-LARA-2 has a first operational AI self-checking mechanism for linguistic phase outputs, while still noting that calibration and broader benchmarks remain future work.

### Non-goals for the first version

- Do not require five independent judge models before shipping v1.
- Do not block normal pipeline execution on judge scores yet.
- Do not require a fully general parameter system before trying the first explicit phase-1, phase-2, and MWE variants.
- Do not claim AI evaluation is ground truth.
- Do not attempt to evaluate every annotation phase before the progress report.

## First elaboration: UI-regression monitoring track (ISSUE-0025)

This section provides an initial concrete plan for the UI-regression line item added under regression monitoring.

### Objective

Detect unintentional disappearance or relocation of important UI controls/content early, and force an explicit human acknowledgment for intentional UI changes.

### Scope (phase 1)

Prioritize high-impact pages where recent regressions were reported:

- `/projects/<id>/images/` and child views (`style`, `elements`, `pages`),
- `/content/` (including natural-language search controls),
- top-level project workflow pages where stage actions are triggered.

### Snapshot model

For each monitored page, store a compact JSON snapshot with:

- route identifier + template name,
- key controls (buttons/links/forms/inputs/selects/textareas) with stable selectors,
- key visibility guards/conditions (where known),
- short semantic labels for controls (human-readable names),
- optional rendered text anchors for critical headings/messages.

Snapshots should be deterministic and sorted so diffs are stable.

### Storage convention (initial proposal)

Use timestamped artifacts in-repo for easy review:

```text
docs/ui-regression/
  snapshots/
    ui-snapshot-YYYYMMDD-HHMMSSZ.json
  baselines/
    current-ui-baseline.json
```

`current-ui-baseline.json` is the expected reference; timestamped snapshots provide audit history.

### Comparison + alerting workflow

1. Generate fresh snapshot in CI (or pre-merge validation).
2. Diff against `current-ui-baseline.json`.
3. Classify changes:
   - **expected** (explicitly approved UX change),
   - **needs review** (ambiguous),
   - **unexpected** (potential regression).
4. Post a structured report in CI output and PR checks.
5. Require maintainer acknowledgement for any removed critical control before merge.

### AI-judges integration

The UI track can reuse the panel pattern at low cost:

- ask judges to score change intent alignment (1–5) using page context + before/after control inventories,
- collect rationale tags (`missing_control`, `renamed_control`, `moved_control`, `visibility_guard_change`),
- use disagreement as a signal to escalate to human UI review.

This remains assistive: AI signals never replace maintainer judgment for UI acceptance.

### Immediate implementation steps

1. Define the first monitored control inventory for `/images/` and `/content/`.
2. Add a deterministic extractor script to build snapshots from templates/rendered responses.
3. Add a baseline file and CI diff check with readable Markdown/JSON report output.
4. Add a small test fixture proving the diff check catches a removed control.
5. Document maintainer acknowledgement protocol in `docs/howto/`.

## Governance and risk controls

- Require disclosure in reports that scores are AI-judged.
- Preserve full audit trail of prompts and outputs.
- Add privacy filters for user content before external evaluation calls.
- Set budget/latency caps and fallback policies when judge models are unavailable.

## Delivery phases

### Phase A — Report-driven variant-comparison evaluator

- Add lightweight per-stage processing parameters for segmentation phase 1, segmentation phase 2, and MWE detection.
- Use the existing pipeline runner to produce reproducible default and candidate phase outputs on the same inputs.
- Implement single-judge, strict-JSON evaluators for segmentation phase 1, segmentation phase 2, and MWE detection.
- Add paired comparison summaries that estimate whether candidate prompts/mechanisms improve over defaults.
- Store versioned processing/evaluator artifacts and a concise flagged-items/comparison report.
- Use this as the First Progress Report example of operational AI self-checking/autonomy leading toward systematic improvement.

### Phase B — Minimal panel evaluator

- Add 2–3 judges for one or more of the Phase A tasks.
- Add 1–5 scale aggregation, short justification summaries, and disagreement metrics.

### Phase C — Multi-phase panel + disagreement metrics

- Extend to translation, gloss, exercise distractors, and other processing tasks.
- Add per-dimension scoring and disagreement reports.

### Phase D — Calibration and benchmarking

- Human audit sampling and correlation analysis.
- Establish stable benchmark suites and acceptance thresholds.

### Phase E — Foreman summarization and decision support

- Add optional foreman summarizer for panel synthesis.
- Integrate with release/prompt-change review workflow.

## Success criteria

- Team can run an initial segmentation/MWE variant-comparison evaluator over fixed samples before the First Progress Report.
- Team can show at least one concrete before/after comparison where AI judging gives a useful provisional recommendation about whether a candidate processing change is an improvement.
- Team can compare candidate prompts/pipeline variants quickly and reproducibly.
- Panel scores correlate usefully with human spot-judgments on key tasks.
- Evaluation artifacts support root-cause analysis, not only leaderboard numbers.
- The process reduces time-to-decision for iterative quality improvements.

## Relationship to other roadmaps

- Directly supports `docs/roadmap/linguistic-pipeline.md`, especially the implemented `run_full_pipeline` runner that can start and end at selected stages.
- Directly supports ISSUE-0004 and gives measurable before/after feedback for ISSUE-0005, ISSUE-0006, and MWE prompt/mechanism quality.
- Also supports `docs/roadmap/exercises.md` and `docs/roadmap/alignment.md` as later evaluation targets.
- Complements `docs/roadmap/dialogue-top-level.md` by enabling quality evaluation of assistant decisions and generated guidance.
- Can be exposed in platform monitoring/reporting views in future Django roadmap work.
