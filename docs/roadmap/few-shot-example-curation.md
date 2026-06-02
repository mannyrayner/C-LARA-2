# Few-shot example curation and evaluation roadmap

## Why this exists

Recent work on `segmentation_phase_2` variants, especially the `boundary_first` mechanism, suggests that prompt and few-shot choices can materially affect annotation quality. The current examples are useful for experimentation, but they were mostly created in one-off AI-assisted passes. That makes it hard to know whether an example is linguistically correct, whether it covers the right phenomena, and whether adding more examples is actually improving the pipeline.

This roadmap tracks a principled workflow for creating, checking, versioning, and evaluating few-shot examples used by linguistic annotation stages.

Related issue: [ISSUE-0036](../issues/issues/ISSUE-0036.json).

## Scope

In scope:

- Few-shot examples for linguistic annotation prompts, starting with:
  - `segmentation_phase_1` segment-boundary selection,
  - `segmentation_phase_2` tokenization/boundary repair,
  - MWE detection.
- Ordered example sets and tranche sizes (`minimal`, `small`, `medium`, `all`) that can be selected through stage parameters.
- AI-assisted generation and review of candidate examples, with explicit checks for text preservation, expected annotation format, and plausible linguistic analysis.
- Evaluation of example-set variants using the pipeline runner and AI-based judges.

Out of scope for the first pass:

- Full expert linguistic validation for every language.
- A large multilingual gold corpus before the evaluator workflow exists.
- Replacing human review where expert judgement is available; the goal is to make review targeted and evidence-based.

## Initial problem statement

Few-shot examples are currently easy to add but hard to trust. Known risks include:

- linguistically wrong examples being amplified by prompts;
- examples that overfit to one language or phenomenon;
- example ordering that makes `fewshot_count` tranches arbitrary;
- example sets that appear better by anecdote but are not measured against default processing;
- prompts and examples drifting apart as mechanisms such as `boundary_first` evolve.

## Proposed workflow

### 1. Create candidate examples in structured batches

For each stage and mechanism, define a short phenomenon list before generating examples. For `segmentation_phase_2`, the first list should include:

- apostrophe clitics where default punctuation splitting is too fine;
- bound clitic strings that need new internal boundaries;
- transparent compounds that should be split;
- cases where default boundaries should be left alone;
- cases where provisional markers should be deleted.

Candidate examples should be stored as normal prompt assets under `prompts/<stage>/...` so they remain versioned and selectable.

### 2. Run automatic sanity checks

Before an example is admitted to a prompt set, check at least:

- input/output text preservation modulo boundary markers or JSON token grouping;
- output schema compatibility with the stage;
- no empty tokens unless explicitly allowed;
- deterministic ordering by filename/tranche.

### 3. Use AI review as a first-pass linguistic judge

For each candidate batch, ask an AI reviewer to flag likely linguistic mistakes and to explain the intended phenomenon. Store review summaries separately from prompt assets so prompt files stay compact.

This is not a substitute for expert review, but it can filter obvious mistakes and identify examples worth human attention.

### 4. Evaluate variants systematically

Use the pipeline runner and ISSUE-0004 evaluator work to compare:

- default prompt/few-shots vs candidate prompt/few-shots;
- `json_direct` vs `boundary_first` mechanisms;
- tranche sizes (`minimal`, `small`, `medium`, `all`);
- language- or phenomenon-specific variants.

The expected output is not only a pass/fail judgement, but evidence about which changes improve phase outputs and why.

## Near-term implementation steps

1. Add validation utilities for few-shot files used by segmentation and MWE prompts.
2. Define small curated test sets for `segmentation_phase_2` clitics/compounds and MWE detection.
3. Add evaluator prompts that compare outputs from two few-shot variants on the same input.
4. Persist evaluation records with prompt/few-shot variant metadata so report claims can cite concrete runs.
5. Decide whether successful example sets should be promoted to default prompts or remain named variants.

## Relationship to other roadmap items

- [AI judges evaluation](ai-judges-evaluation.md): provides the evaluator architecture and comparison workflow.
- [Segmentation pipeline](segmentation-pipeline.md): owns the segmentation stages where the first experiments are happening.
- [MWE strategy](mwe-strategy.md): should receive the same curation/evaluation treatment once segmentation experiments are stable.
- [Reports and papers](reports-and-papers.md): can use this work as evidence that C-LARA-2 improvements are being guided by AI-assisted evaluation rather than ad hoc prompt editing.

## Success criteria

- Few-shot example sets are versioned, selectable, and documented by stage/mechanism.
- Tranche choices are meaningful and ordered from simplest/highest-confidence examples to broader coverage.
- Automated checks catch preservation/schema mistakes before examples are used in runs.
- AI-based evaluators can show whether a prompt/few-shot change improves outputs on representative cases.
- The First Progress Report can cite at least one concrete example where evaluation of few-shot variants led to a better processing choice.
