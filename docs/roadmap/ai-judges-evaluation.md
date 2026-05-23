# Roadmap: evaluation of processing quality using a panel of AI judges

This roadmap proposes a structured, repeatable evaluation framework where outputs from C-LARA-2 processing stages are reviewed by a **panel of independent AI judges**.

## Why this matters

Human expert evaluation is the gold standard but is expensive and hard to schedule at the cadence needed for prompt and pipeline iteration. A panel-of-AIs approach can provide:

- fast comparative feedback,
- broad language coverage,
- consistent repeated scoring across experiments,
- richer diagnostics than pass/fail test outcomes.

The goal is not to replace human evaluation, but to create a practical intermediate layer that helps decide what should be sent to human review.

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

- segmentation quality (readability/usefulness of boundaries),
- translation adequacy/fluency,
- MWE identification quality,
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

## Experimental workflows supported

1. **Prompt A/B evaluation**
   - Run candidate prompts over the same dataset.
   - Use panel scores to estimate win rates and confidence.
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

## Governance and risk controls

- Require disclosure in reports that scores are AI-judged.
- Preserve full audit trail of prompts and outputs.
- Add privacy filters for user content before external evaluation calls.
- Set budget/latency caps and fallback policies when judge models are unavailable.

## Delivery phases

### Phase A — Minimal evaluator

- Single-task evaluator (e.g., gloss or MWE) with 2–3 judges.
- 1–5 scale + short justification + mean score.

### Phase B — Multi-phase panel + disagreement metrics

- Extend to multiple processing tasks.
- Add per-dimension scoring and disagreement reports.

### Phase C — Calibration and benchmarking

- Human audit sampling and correlation analysis.
- Establish stable benchmark suites and acceptance thresholds.

### Phase D — Foreman summarization and decision support

- Add optional foreman summarizer for panel synthesis.
- Integrate with release/prompt-change review workflow.

## Success criteria

- Team can compare candidate prompts/pipeline variants quickly and reproducibly.
- Panel scores correlate usefully with human spot-judgments on key tasks.
- Evaluation artifacts support root-cause analysis, not only leaderboard numbers.
- The process reduces time-to-decision for iterative quality improvements.

## Relationship to other roadmaps

- Directly supports `docs/roadmap/linguistic-pipeline.md`, `docs/roadmap/exercises.md`, and `docs/roadmap/alignment.md`.
- Complements `docs/roadmap/dialogue-top-level.md` by enabling quality evaluation of assistant decisions and generated guidance.
- Can be exposed in platform monitoring/reporting views in future Django roadmap work.
