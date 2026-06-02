# Roadmap: evaluation of processing quality using a panel of AI judges

This roadmap proposes a structured, repeatable evaluation framework where outputs from C-LARA-2 processing stages are reviewed by AI evaluators, eventually including a **panel of independent AI judges**.

The immediate report-driven priority is a smaller first version for **ISSUE-0004**: use the already-implemented pipeline runner to evaluate phase outputs for segmentation phase 1, segmentation phase 2, and MWE detection. This gives the First Progress Report a concrete autonomy/self-checking example rather than only a future-work promise.

## Why this matters

Human expert evaluation is the gold standard but is expensive and hard to schedule at the cadence needed for prompt and pipeline iteration. A panel-of-AIs approach can provide:

- fast comparative feedback,
- broad language coverage,
- consistent repeated scoring across experiments,
- richer diagnostics than pass/fail test outcomes,
- concrete evidence for the First Progress Report that C-LARA-2 can begin to inspect its own linguistic-processing quality.

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
- Store raw phase output, evaluator prompt version, judge model, response JSON, and aggregate summary in a run artifact.
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
  input_records.jsonl
  judge_outputs.jsonl
  aggregate_scores.json
  flagged_items.md
```

`flagged_items.md` should be readable enough for a human maintainer to inspect quickly and should group findings by issue target: phase-1 segmentation, phase-2 tokenization, and MWE detection.

### Success criteria for the First Progress Report

- The evaluator can run over a fixed sample without UI interaction.
- It produces stable, inspectable artifacts with prompt/model/version metadata.
- It catches at least synthetic or known examples of bad phase-1 granularity, over-extended phase-2 tokens, and bad MWE spans.
- Human review of a small sample finds the AI judgments useful enough to guide debugging, even if not authoritative.
- The report can honestly say that C-LARA-2 has a first operational AI self-checking mechanism for linguistic phase outputs, while still noting that calibration and broader benchmarks remain future work.

### Non-goals for the first version

- Do not require five independent judge models before shipping v1.
- Do not block normal pipeline execution on judge scores yet.
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

### Phase A — Report-driven phase-output evaluator

- Use the existing pipeline runner to produce reproducible phase outputs.
- Implement single-judge, strict-JSON evaluators for segmentation phase 1, segmentation phase 2, and MWE detection.
- Store versioned evaluator artifacts and a concise flagged-items report.
- Use this as the First Progress Report example of operational AI self-checking/autonomy.

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

- Team can run an initial segmentation/MWE phase-output evaluator over fixed samples before the First Progress Report.
- Team can compare candidate prompts/pipeline variants quickly and reproducibly.
- Panel scores correlate usefully with human spot-judgments on key tasks.
- Evaluation artifacts support root-cause analysis, not only leaderboard numbers.
- The process reduces time-to-decision for iterative quality improvements.

## Relationship to other roadmaps

- Directly supports `docs/roadmap/linguistic-pipeline.md`, especially the implemented `run_full_pipeline` runner that can start and end at selected stages.
- Directly supports ISSUE-0004 and gives measurable feedback for ISSUE-0005, ISSUE-0006, and MWE prompt quality.
- Also supports `docs/roadmap/exercises.md` and `docs/roadmap/alignment.md` as later evaluation targets.
- Complements `docs/roadmap/dialogue-top-level.md` by enabling quality evaluation of assistant decisions and generated guidance.
- Can be exposed in platform monitoring/reporting views in future Django roadmap work.
