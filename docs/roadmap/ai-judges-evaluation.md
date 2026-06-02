# Roadmap: evaluation of processing quality using a panel of AI judges

This roadmap proposes a structured, repeatable evaluation framework where outputs from C-LARA-2 processing stages are reviewed by AI evaluators, eventually including a **panel of independent AI judges**.

The immediate report-driven priority is a smaller first version for **ISSUE-0004**: use the already-implemented pipeline runner to evaluate phase outputs for segmentation phase 1, segmentation phase 2, and MWE detection. The sharper goal is not only to score outputs, but to show that AI-based judging can tell whether a candidate processing change is an improvement, so that the system can move toward systematic self-improvement. This gives the First Progress Report a concrete autonomy/self-checking example rather than only a future-work promise.

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

Once ISSUE-0010 legacy imports provide more coverage, selected legacy C-LARA projects can become a larger regression corpus, but they are not required for the first evaluator.

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
