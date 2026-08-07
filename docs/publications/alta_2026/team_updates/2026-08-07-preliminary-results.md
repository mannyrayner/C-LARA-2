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

**The immediate critical task is now to define what an MWE should mean in
C-LARA-2.** The definition may not be identical to the one a linguist would use
for a general-purpose MWE corpus. C-LARA-2 identifies MWEs primarily so that a
learner can receive a helpful gloss for a meaningful unit spanning several
tokens. Many nominal failures have defensible model analyses and expose
inconsistent or underspecified decisions about this task-specific concept. We
need a clearer annotation policy before further optimisation; otherwise prompt
learning may reproduce annotation accidents rather than learn a well-defined and
pedagogically useful task.

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

## Initial MWE results

The MWE cycle-1 result is:

| Records | Exact segment match | Precision | Recall | F1 |
|---:|---:|---:|---:|---:|
| 336 | 83.9% (282/336) | 0.817 | 0.882 | 0.848 |

This is promising for a harder and less deterministic task. It is not yet a
clean estimate of model quality, however, because disagreement review shows that
the target annotation policy is underspecified. Some apparent false positives
and false negatives may instead be reasonable alternative analyses.

## What is an MWE in C-LARA-2?

The definition should begin with the role of MWE annotation in the application.
Its most important purpose is to let C-LARA-2 **gloss a unit consisting of more
than one token as a whole**, where doing so gives the learner a more useful
interpretation than separate token-by-token glosses. This functional goal may
justify a task-specific definition rather than direct adoption of a linguistic
corpus standard. Lexical fixedness remains relevant, but it may not be the only
criterion: pedagogical usefulness, reliable glossing, and the behaviour of later
lemma/gloss stages also matter.

This goal may mean there is not always one uniquely correct MWE tagging. Two
different spans can sometimes support equally helpful learner glosses, and an
annotator may reasonably include or omit a borderline but useful unit. Evaluation
must not silently count every such alternative as a model error. We should decide
whether the guideline can make most cases unique, whether some records need
multiple accepted analyses, or whether the reported results should distinguish
clear errors from acceptable alternatives. This choice could materially change
the measured precision, recall, and exact-match rate.

We also need to decide whether MWE tags should be independent of the glossing
language. Independence is highly desirable: the same source-language MWE analysis
could then be reused when a project is glossed into French, German, English, or
another language. But source expressions do not always map onto target-language
units in the same way, so complete independence may be difficult. The current
experiments suggest that seeing a translation of the whole segment is useful when
deciding whether a multi-token source unit should receive a joint gloss. We should
therefore test translation context explicitly while keeping source-language MWE
structure separate from any particular target-language gloss wherever possible.

Against that general background, the reviewed examples expose several concrete
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
- **Pedagogical usefulness versus lexicalisation:** an expression may be
  compositional to a linguist but still benefit from a joint learner gloss. We
  have not stated when that is sufficient for inclusion.

The model analyses are useful because they often give a defensible reason for a
decision that differs from the current gold. We now have an interactive review
tool that records whether gold or prediction is preferred and asks for a reason.
These decisions should be distilled into a short annotation guideline before we
generate another MWE prompt. At minimum, it should state the task purpose,
included and excluded construction classes, treatment of proper names and
hyphenated compounds, preferred span boundaries, and policy for discontinuous
expressions and overlaps. It should also state whether alternative taggings are
allowed, how translation context may be used, and what—if anything—may depend on
the glossing language.

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
   the annotation guideline is clarified, and distinguish clear errors from any
   explicitly permitted alternative analyses.

The number of texts should be chosen from a corpus inventory and reviewer-time
budget rather than set arbitrarily. A smaller genuinely unseen project-level test
set with complete human review is preferable to a large weakly checked set.

## Immediate next actions

1. Complete the interactive review of English MWE cycle-1 disagreements and
   extract a concise, C-LARA-specific MWE annotation guideline from the recorded
   rationales, starting from the goal of producing helpful multi-token glosses.
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
