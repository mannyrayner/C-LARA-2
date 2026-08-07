# Preliminary GPT-5.6 prompt-learning results

**Team update — 7 August 2026**

## Executive summary

We have been discussing a possible ALTA 2026 paper about **learning linguistic
annotation prompts from data**: run an annotation prompt, compare its output with
human-reviewed data, audit the disagreements, and use the resulting error
evidence to produce a better prompt. Belinda has indicated that she can present
the paper in Melbourne if it is accepted.

Our initial experiments were not very successful. Following the recent release
of GPT-5.6, however, both the initial annotations and the learned prompt revisions
have improved markedly. This is a practical observation rather than a controlled
5.5-versus-5.6 comparison; the research objective is to establish whether the
stronger model enables a reliable human-supervised prompt-learning method.

The current evidence is still preliminary. It covers only seven short,
manually reviewed English development texts, only token-level
`segmentation_phase_2` and multi-word expression (MWE) annotation, and no unseen
data. Even with those limitations, the figures are promising. For segmentation,
the initial credible GPT-5.6 prompt scored 98.81% exact match over 4,370 chunks;
one recursive prompt-improvement cycle reached 99.75%, and manual audit showed
that the remaining 11 disagreements were inconsistent gold annotations. After
correction, the learned prompt scored 100% on this development set. For MWE, the
latest cycle-1 run over 336 segments obtained 83.9% exact segment match,
precision 0.817, recall 0.882, and F1 0.848.

The MWE result is good enough that the immediate obstacle is now conceptual,
not simply model accuracy. Many nominal failures have defensible model analyses
and expose inconsistent or underspecified decisions about what counts as an MWE
for C-LARA. We need a clearer annotation policy before further optimisation;
otherwise prompt learning may reproduce annotation accidents rather than learn a
well-defined linguistic task.

The rest of this update describes the experimental workflow and integrity fixes,
the segmentation and MWE results in more detail, the unresolved MWE policy
questions, and a possible ALTA study using project-separated unseen data. English,
French, and German currently appear to be the realistic language scope, subject
to corpus inventory and reviewer capacity.

## What has been done

We restarted the earlier experiments rather than trying to salvage annotations
whose downstream MWE, lemma, and gloss corrections had been made over imperfect
segmentation. For seven English projects (`239,245,254,255,257,261,263`) we:

1. regenerated `segmentation_phase_2` with GPT-5.6;
2. archived the untouched model output;
3. manually corrected segmentation in the page-oriented editor;
4. generated translation, MWE, lemma, and gloss annotations without overwriting
   corrected segmentation;
5. manually reviewed the MWE annotations;
6. froze explicit development gold and retained run manifests and prompt-cycle
   artifacts;
7. ran prompt predictions against that gold, generated error briefs, asked
   GPT-5.6 for revised prompts, and manually audited the remaining disagreements.

During this process we fixed two experimental-integrity problems. First, the
chunk runner initially exposed gold decomposition fields to the model, producing
a meaningless 100% score; the model-facing schema is now an allowlist containing
only the chunk surface. Second, GPT-5.6 rejects an explicit `temperature=0`, so
the runners now leave temperature unset. The credible results below were obtained
after both fixes.

## Segmentation result

The evaluated task is decomposition of one whitespace-delimited English chunk
into the token units required by C-LARA. The initial prompt was generally strong
but handled apostrophes inconsistently. Typical errors included:

- `Emma|'|s` instead of `Emma|'s`;
- `don|'|t` or unsplit `don't` instead of `do|n't`;
- failure to separate quotation marks from a contraction;
- occasional failure to separate hyphens.

The development results were:

| Prompt | Correct / total | Exact-match accuracy | Apparent errors |
|---|---:|---:|---:|
| Initial GPT-5.6 prompt | 4,318 / 4,370 | 98.81% | 52 |
| Learned cycle-2 prompt, before gold audit | 4,359 / 4,370 | 99.75% | 11 |
| Learned cycle-2 prompt, after gold audit | 4,370 / 4,370 | 100% | 0 |

The revised prompt added compact general rules for possessive and contracted
`'s`, other English clitics (`'m`, `'re`, `'ve`, `'ll`, `'d`), negative `n't`,
surrounding punctuation, and hyphens. It did not enumerate the project strings.
The remaining cycle-2 differences revealed inconsistent gold conventions—for
example splitting apostrophe and `s` in some possessives but not others, or
leaving `didn't` and some hyphenated compounds unsplit. Human audit corrected
these inconsistencies.

The 100% figure is still a development result. The prompt was derived from errors
on these seven texts, and the corrected gold was inspected after predictions
were available. The important claim at this stage is not “segmentation is
solved,” but that the recursive procedure learned a concise rule set that fits
the development evidence extremely well. Its value depends on performance on
previously unseen projects.

## MWE result and the definition problem

The MWE cycle-1 result is:

| Records | Exact segment match | Precision | Recall | F1 |
|---:|---:|---:|---:|---:|
| 336 | 83.9% (282/336) | 0.817 | 0.882 | 0.848 |

This is promising for a harder and less deterministic task, but the figures are
not yet straightforward to interpret. Review examples expose several unresolved
policy dimensions:

- **Lexicalised versus productive constructions:** should `not just ... but`,
  `as ... as`, or `a little bit of` count, or are they productive grammar?
- **Verb–preposition and adjective–preposition combinations:** the gold and model
  differ on examples such as `filled with`, `pleased with`, `know about`,
  `respond to`, and `refer to`.
- **Named entities and technical terms:** should `International Space Station`,
  `Expedition 58`, `Willow Creek`, or `Dr. Pussy` be MWEs, named entities handled
  elsewhere, or excluded?
- **Hyphenated compounds:** tokenisation can make `high-tech` appear as
  `high|-|tech`; we need to decide whether a lexicalised compound is an MWE when
  segmentation exposes multiple tokens.
- **Span boundaries:** examples include `all over` versus `all over the world`,
  `testament to` versus `a testament to`, and `as ... as` with or without the
  intervening modifier.
- **Discontinuous patterns:** should objects be included in `herald someone as`,
  and how should optional modifiers in `make new friends` or `have a particular
  penchant for` be represented?
- **Pedagogical purpose:** an expression may be compositional to a linguist but
  still useful as a learning unit. We have not stated whether that is sufficient
  for inclusion.

The model analyses are useful because they often give a defensible reason for a
decision that differs from the current gold. We now have an interactive review
tool that records whether gold or prediction is preferred and asks for a reason.
These decisions should be distilled into a short annotation guideline before we
generate another MWE prompt. At minimum, it should state the task purpose,
included and excluded construction classes, treatment of proper names and
hyphenated compounds, preferred span boundaries, and policy for discontinuous
expressions and overlaps.

## Model effect

The practical improvement after moving to GPT-5.6 is large and obvious to the
human reviewer, both in the initial annotations and in the quality of the
suggested segmentation revision. We should nevertheless phrase this carefully.
The current work is designed to obtain good prompt-learning results with 5.6,
not as a controlled 5.5-versus-5.6 comparison. Earlier artifacts provide useful
historical context, but the durable research question is whether a stronger
model plus a disciplined human/AI learning loop can produce reliable linguistic
annotation prompts.

## Proposed ALTA 2026 scope

The submission deadline is 11 September, so scope must be fixed soon. A realistic
core experiment would contain:

1. **Tasks:** `segmentation_phase_2` and MWE annotation.
2. **Languages:** English, French, and German, subject to confirming enough
   manually reviewable material in each language. Other languages should not be
   promised unless corpus and reviewer capacity are verified immediately.
3. **Data split:** project-separated development, validation, and test sets.
   Development supports prompt revision and annotation-guideline formation;
   validation selects a frozen prompt; test is run once and remains unseen until
   the method and selection rule are fixed.
4. **Baselines and candidates:** the initial GPT-5.6 prompt versus the selected
   learned GPT-5.6 prompt. A fresh 5.5 comparison is lower priority and should not
   displace unseen evaluation or multilingual coverage.
5. **Measures:** exact-match and boundary measures for segmentation; precision,
   recall, F1, segment exact match, and construction-level error analysis for
   MWE. Report results by language as well as pooled totals.
6. **Human audit:** preserve correction logs and report how often apparent model
   errors were actually gold problems. For MWE, report agreement before and after
   the annotation guideline is clarified.

The number of texts should be chosen from a corpus inventory and reviewer-time
budget rather than set arbitrarily. A smaller genuinely unseen project-level test
set with complete human review is preferable to a large weakly checked set.

## Immediate next actions

1. Complete the interactive review of English MWE cycle-1 disagreements and
   extract a concise MWE annotation guideline from the recorded rationales.
2. Correct the experimental gold, rescore the preserved predictions, and only
   then generate and assess the next MWE prompt.
3. Inventory unused English, French, and German projects and estimate annotation
   volume and reviewer time for development/validation/test splits.
4. Freeze English segmentation cycle 2 and evaluate it on unseen English texts.
5. Create small French and German development gold samples using the same
   archive → annotate → audit → learn protocol.
6. Fix the paper's research questions, experiment table, and minimum viable scope
   early enough to reserve time for unseen evaluation, analysis, and writing.

## Current conclusion

The preliminary evidence is strong enough to justify pursuing an ALTA 2026
submission. Segmentation shows that one human-supervised recursive prompt cycle
can remove a systematic error class on development data. MWE shows both the
potential of GPT-5.6 and the importance of defining the target annotation task
before treating disagreement counts as model errors. The next milestone is not
another headline development score: it is a stable MWE guideline and credible
performance on unseen, project-separated English data, followed by French and
German if annotation capacity permits.
