# Few-shot example curation and evaluation roadmap

## Why this exists

Recent work on `segmentation_phase_2` variants, especially the `boundary_first` mechanism, suggests that prompt and few-shot choices can materially affect annotation quality. The current examples are useful for experimentation, but they were mostly created in one-off AI-assisted passes. That makes it hard to know whether an example is linguistically correct, whether it covers the right phenomena, and whether adding more examples is actually improving the pipeline.

This is now a P1 roadmap item because maintainers are seeing many annotation errors, and because a disciplined few-shot curation/evaluation workflow could become strong evidence for the First Progress Report: C-LARA-2 should show that AI-assisted evaluation is guiding real annotation improvements rather than merely producing plausible-looking prompt edits.

Related issue: [ISSUE-0036](../issues/issues/ISSUE-0036.json).

## Core architecture: generate → adversarial review → repair → gold acceptance

The target architecture is a pipeline for few-shot examples themselves:

1. **Generate candidates generously.** For each operation/language/mechanism, generate more examples than will be used in prompts. Candidate batches should deliberately cover edge cases such as punctuation, clitics, compounds, named entities, idioms, discontinuous MWEs, ambiguous glosses, and examples where the correct action is to leave default boundaries unchanged.
2. **Validate against an explicit schema.** Before asking for linguistic judgement, run deterministic checks: valid JSON/XML or boundary-marked text, token surfaces line up with source text, MWE spans refer to existing tokens, gloss counts match token/MWE units, no duplicated or missing items, and no empty units unless explicitly allowed.
3. **Use critic models as adversarial reviewers.** Prompt critic models to find the strongest reason an example should *not* be used as a few-shot example. Require severity labels such as `fatal`, `serious`, `minor`, or `none` rather than a rubber-stamp yes/no judgement.
4. **Repair before discard.** If critics find plausible defects, ask a stronger repair model to preserve the pedagogical intent while producing a corrected example. Re-run schema validation and adversarial criticism on repaired candidates.
5. **Use consensus scoring, not unanimity.** Score each candidate using schema pass/fail, linguistic confidence, critic agreement, and severity penalties. For core/high-cost examples, require a final arbiter call that sees the original example, critiques, and repairs.
6. **Accept into an auditable gold library.** Accepted examples should carry provenance: original generated example, operation/language/mechanism, validation results, critic comments, repairs, final accepted version, acceptance rationale, model/prompt versions, and timestamps.

## Scope

In scope:

- Few-shot examples for linguistic annotation prompts, starting with:
  - `segmentation_phase_1` segment-boundary selection,
  - `segmentation_phase_2` tokenization/boundary repair,
  - MWE detection.
- Ordered example sets and tranche sizes (`minimal`, `small`, `medium`, `all`) that can be selected through stage parameters.
- AI-assisted generation, adversarial criticism, repair, and acceptance of candidate examples.
- Evaluation of example-set variants using the pipeline runner and AI-based judges.
- Versioned, auditable example records in addition to compact prompt assets.

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
- prompts and examples drifting apart as mechanisms such as `boundary_first` evolve;
- lack of traceability when annotation failures may be caused or reinforced by bad few-shot examples.

## Proposed workflow

### 1. Define operation/language phenomenon matrices

For each stage and mechanism, define a compact phenomenon list before generating examples. For `segmentation_phase_2`, the first list should include:

- apostrophe clitics where default punctuation splitting is too fine;
- bound clitic strings that need new internal boundaries;
- transparent compounds that should be split;
- cases where default boundaries should be left alone;
- cases where provisional markers should be deleted.

For MWE detection, the first list should include:

- continuous idioms;
- phrasal verbs and light-verb constructions;
- named entities that should not be misclassified as MWEs;
- discontinuous or interrupted expressions where supported by the representation;
- ambiguous cases where the expected decision should be explicit.

### 2. Generate candidate pools

Generate candidate examples in batches larger than the target prompt tranche size. Store raw candidates separately from prompt assets so rejected and repaired examples remain inspectable.

Candidate metadata should include operation, language, mechanism/variant, intended phenomenon, generator model, generator prompt version, and generation timestamp.

### 3. Run deterministic validation

Before linguistic criticism, validate each candidate against stage-specific rules. Initial validators should check:

- JSON/XML parseability or boundary-marker format;
- source-text preservation modulo permitted markers;
- token/MWE/gloss span consistency;
- no missing, duplicated, or empty annotation units unless explicitly allowed;
- stable sorting/tranche metadata;
- compatibility with the prompt template that would consume the example.

### 4. Run adversarial critic review

Critic prompts should ask for defects, not approval. A useful review shape is:

- strongest reason not to use this as a few-shot example;
- severity: `fatal`, `serious`, `minor`, or `none`;
- affected annotation units/spans;
- suggested repair, if possible;
- confidence and brief rationale.

Multiple critic models or prompt variants can be used when the example is central to a default prompt set.

### 5. Repair and re-review

If a defect is plausible and repairable, run a repair step that preserves the intended phenomenon and pedagogical purpose. The repaired candidate then returns to deterministic validation and critic review. Fatal unrepaired examples stay in the audit trail but are not promoted.

### 6. Score and accept gold examples

Maintain a score such as:

```text
schema_pass + linguistic_confidence + critic_agreement - severity_penalties
```

Use thresholds to decide whether a candidate is rejected, repaired again, accepted into an experimental set, or accepted into a gold/default set. For high-impact examples, add an arbiter model call that sees the original, validation results, critiques, and repairs before final acceptance.

### 7. Promote prompt assets deliberately

Accepted gold examples can be copied into compact prompt-facing few-shot files under `prompts/<stage>/...`. Experimental examples should remain named variants until evaluator evidence supports promotion to defaults.

## Auditable example records

Prompt-facing files should stay small, but the project should also be able to store richer records for accepted and rejected candidates. A future record could include:

- `example_id`;
- operation, language, mechanism, variant, and intended phenomenon;
- original generated example;
- deterministic validation results;
- critic model/prompt versions and comments;
- repair attempts;
- final accepted version;
- acceptance score and rationale;
- generator/critic/repair/arbiter model versions;
- links to pipeline/evaluator runs that used the example.

These records matter because later annotation failures should be traceable back to the few-shot examples that may have influenced them.


## Invocation, storage, use, and review model

In practice, curation should be incremental rather than a single large generation run. We should be able to ask for "more French `segmentation_phase_2/boundary_first` clitic examples" or "a first MWE idiom batch for Drehu" without disturbing existing accepted examples.

### Invocation surfaces

Start with two complementary invocation paths:

1. **Management command for repeatable generation experiments.** The first minimal command is `python manage.py curate_fewshots --operation segmentation_phase_2 --language fr --mechanism boundary_first --phenomena clitic,compound --count 40 --target-set clitic_compound_v2`. It generates candidate JSON examples with trace output and fan-out/fan-in shards (`--batch-size`, `--max-concurrency`), validates them deterministically, stores auditable records, and can optionally write valid examples into a prompt variant. This is the right surface for bulk generation, laptop/server runs, scripted reruns, and reproducible report evidence.
2. **Management command for AI review.** The initial second-step command is `python manage.py review_fewshots --operation segmentation_phase_2 --language fr --mechanism boundary_first --target-set clitic_compound_v2 --request-id <request-id>`. If no language-specific review template exists, it first creates several AI-drafted templates, reconciles them with another AI call, stores the final template under the curation tree, then reviews candidates concurrently and writes `reviews/*.review.json` plus a summary. It accepts `--timeout-s` for slower models. The review prompt is deliberately framed as a plain word/unit-boundary task: deterministic validation has already checked preservation, so the AI reviewer sees an `input` and `boundary_marked` string and judges whether the material between boundary markers should count as word-like or meaningful units, with language-specific guidance and concrete positive/negative examples such as clitic splitting, transparent compound splitting, false compound rejection, and cases where default boundaries should remain unchanged.
3. **Admin UI for small requests and review.** Add an admin-only page where a maintainer can create a curation request, inspect generated candidates, run critic/repair passes, and promote accepted examples. The UI should be able to request additional examples for an existing operation/language/set and should show existing coverage by phenomenon and tranche.

Both paths should create a durable curation request record before calling models. A request should include operation, language, mechanism, target set, requested phenomena, requested count, generator/critic/repair model choices, prompt versions, submitter, timestamp, and notes.

### Incremental batches

A few-shot set should be built from many batches. Each batch should have a stable ID and status, for example:

- `requested`;
- `generated`;
- `schema_validated`;
- `critic_reviewed`;
- `repair_pending`;
- `repaired`;
- `accepted_experimental`;
- `accepted_gold`;
- `rejected`;
- `promoted_to_prompt_assets`.

This lets us top up an existing language or operation without rerunning the whole pipeline. If a language later shows a new failure mode, we add a targeted batch for that phenomenon and evaluate whether it improves outputs.

### Storage layout

Prompt-facing few-shot files should remain compact under `prompts/<operation>/...`, but curation records should be stored separately so rejected and repaired examples remain auditable. A proposed repository layout is:

```text
docs/few_shot_curation/
  segmentation_phase_2/
    fr/
      boundary_first/
        clitic_compound_v2/
          requests/20260602-001.json
          candidates/EXAMPLE-0001.json
          reviews/EXAMPLE-0001.critic-gpt-5.3.json
          repairs/EXAMPLE-0001.repair-gpt-5.5.json
          accepted/EXAMPLE-0001.json
          manifest.json
```

The `manifest.json` should list accepted examples, their ordering/tranche membership, validation status, scores, and the prompt-asset files they were copied into. Generated and reviewed examples can be large; compact prompt assets should be derived outputs, not the only source of truth.

### Using curated examples

Accepted examples should become usable in two ways:

1. **Experimental variants.** Copy selected accepted examples into a named prompt/few-shot variant under `prompts/<operation>/variants/<variant>/fewshots/`, then use existing stage parameters such as `{"segmentation_phase_2": {"mechanism": "boundary_first", "variant": "clitic_compound_v2", "fewshot_count": "small"}}`.
2. **Default promotion.** After evaluator evidence shows that a set improves outputs, promote a selected tranche to the operation/language default few-shot directory, preserving links back to curation record IDs.

The evaluator should record operation, language, mechanism, prompt variant, few-shot set, tranche size, candidate record IDs, and score deltas so a report claim can identify exactly what changed.

### Review workflow

Review should not require a maintainer to read every raw model output. The admin/review surface should prioritize:

- candidates with fatal/serious critic findings;
- candidates selected for `minimal` or `small` tranches;
- examples proposed for default promotion;
- examples associated with a known annotation failure mode;
- disagreements between critics and repair/arbiter outcomes.

A human reviewer can then accept, reject, request more repair, or mark an example as experimental-only. The review decision and rationale should be stored in the same curation record.

## Near-term implementation steps

1. **Done in minimal form:** add validation utilities for `segmentation_phase_2` few-shot candidates. Extend these validators to MWE and later lemma/gloss examples.
2. **Done in minimal form:** implement a traced, fan-out/fan-in candidate-generation command for `segmentation_phase_2`, initially useful for French `boundary_first` experiments.
3. **Done in minimal form:** implement a second-step AI review command that creates/reconciles language-specific word/unit-boundary review templates when needed, then runs hostile-review calls over generated candidates. The prompt avoids project-internal terms and focuses on whether proposed boundary markers define appropriate word-like or meaningful units.
4. Define a small phenomenon matrix for `segmentation_phase_2` clitics/compounds and MWE detection.
5. Add repair prompts and re-review loops for candidates with fatal/serious/minor findings.
6. Expand persisted records from candidate/request/accepted/manifest files to include repair, arbiter, and human-review records.
7. Add evaluator prompts that compare outputs from two few-shot variants on the same input.
8. Run a first documented experiment comparing tranche sizes and variant sets.
9. Decide whether successful example sets should be promoted to default prompts or remain named variants.

## Relationship to other roadmap items

- [AI judges evaluation](ai-judges-evaluation.md): provides the evaluator architecture and comparison workflow.
- [Segmentation pipeline](segmentation-pipeline.md): owns the segmentation stages where the first experiments are happening.
- [MWE strategy](mwe-strategy.md): should receive the same curation/evaluation treatment once segmentation experiments are stable.
- [Reports and papers](reports-and-papers.md): can use this work as evidence that C-LARA-2 improvements are being guided by AI-assisted evaluation rather than ad hoc prompt editing.

## Success criteria

- Few-shot example sets are versioned, selectable, and documented by stage/mechanism.
- Tranche choices are meaningful and ordered from simplest/highest-confidence examples to broader coverage.
- Automated checks catch preservation/schema mistakes before examples are used in runs.
- Adversarial critics and repair steps improve the accepted library rather than just rejecting many examples.
- AI-based evaluators can show whether a prompt/few-shot change improves outputs on representative cases.
- The First Progress Report can cite at least one concrete example where evaluation of few-shot variants led to a better processing choice.
