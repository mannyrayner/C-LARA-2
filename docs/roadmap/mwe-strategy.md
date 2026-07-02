# Roadmap: multi-word expression (MWE) strategy

This roadmap consolidates MWE-related design and implementation issues across C-LARA-2.

## Why a dedicated roadmap

MWE handling affects multiple stages and surfaces:
- annotation prompts and postprocessing,
- lemma/gloss consistency,
- compile-time HTML interaction behavior,
- regression testing and migration compatibility.

Keeping this in one document makes it easier to track cross-stage decisions.

## Core requirements

1. **Stable MWE IDs with correct scope**
   - IDs must be unique within a page (minimum) so downstream hover/highlight logic does not cross-link unrelated MWEs.
   - ID normalization must be deterministic and rerun-safe.

2. **Token ↔ MWE alignment integrity**
   - Every token-level `annotations.mwe_id` should map to an entry in `segment.annotations.mwes`.
   - Invalid/single-token MWEs should be filtered or repaired according to policy.

3. **Cross-stage consistency**
   - Lemma stage must preserve MWE grouping and assign MWE-level lemmas consistently.
   - Gloss stage should treat MWE members consistently when glossing whole expressions.

4. **Compile/UX correctness**
   - Hover and click behavior in HTML must only highlight tokens belonging to the same logical MWE.
   - Concordance and token metadata should remain consistent after any ID normalization.

## Implementation strategy

### Phase A: normalization and guardrails
- Centralize MWE ID normalization utility and apply it at MWE stage output.
- Re-apply normalization defensively at compile boundary to protect against stale historical artifacts.
- Keep manual-MWE save behavior aligned with pipeline behavior by normalizing edited IDs on write (including page-scoped remapping), so accidental non-unique reviewer IDs are repaired deterministically.
- Add regression tests for page-level ID uniqueness and HTML data-attribute correctness.

### Phase B: repair policy for partially tagged MWEs
- Define explicit policy when model returns inconsistent tagging (e.g., MWE entry has 2 tokens but only one token marked with `mwe_id`).
- Implement conservative repair heuristics and diagnostics.

### Phase C: observability and review support
- Add telemetry counters for dropped/repaired MWEs.
- Add reviewer-facing cues in the manual annotation editor (e.g., visual highlighting for non-empty `mwe_id` cells) plus optional integrity warnings.

### Phase D: focused MWE workbench and prompt-improvement loop

After the current `segmentation_phase_2` chunk-decomposition round, the next
quality-improvement target should be MWE detection. The task is harder than
token splitting because it combines lexicalization, syntax, discontinuity, and
language-specific false-positive traps, but it can reuse the same experiment
discipline:

1. **Build comparable corpora for English, French, and German.**
   - Extract imported projects for `en`, `fr`, and `de` into manifest-backed
     development/validation/test splits, analogous to the
     `segmentation_phase_2` corpus split flow.
   - Preserve project/page/segment/token IDs so gold MWE corrections can be
     traced back to the manual annotation editor and to runner outputs.
   - Stratify by project/segment size where practical, and keep held-out test
     data untouched until the prompt cycle and evaluator rule are frozen.
2. **Refresh upstream annotations before collecting MWE gold.**
   - Add a runner target that can reprocess the selected texts through
     `segmentation_phase_2`, `translation`, and `mwe` so the MWE workbench is
     judging current upstream output rather than stale imported artifacts.
   - Keep stage artifacts for all three stages, since MWE errors may be caused
     by tokenization or translation context rather than by the MWE prompt alone.
3. **Use the manual annotation editor as the gold-standard correction surface.**
   - The existing editor is the right place for human correction because it is
     ergonomic and already understands project artifacts.
   - The workbench should therefore export/import MWE gold in a format that
     round-trips cleanly through the editor, rather than creating a parallel
     correction UI.
   - Gold exports should include enough context to compare model decisions,
     editor corrections, and later prompt-cycle predictions.
4. **Decompose MWE identification into focused concurrent decisions.**
   - Instead of asking one API call to find all MWEs in a segment, fan out
     token-start candidates: pass the full segment plus a focused subsegment
     beginning at token `i`, and ask whether an MWE starts at that token.
   - The model response should be constrained to a small schema: no MWE here,
     or an MWE beginning at this token with token indices/surfaces, expression
     type, confidence/rationale, and whether the span is continuous or
     discontinuous.
   - Run token-start decisions concurrently, then fan them back in with a
     deterministic resolver that removes duplicates, rejects overlaps according
     to policy, normalizes IDs, and records trace metadata.
5. **Start with a minimal, general prompt.**
   - The initial prompt should emphasize lexicalized/fixed expressions,
     language-learning usefulness, conservative false-positive avoidance, and
     surface/index preservation.
   - Language-specific guidance should be small but explicit: separable verbs
     for German, clitic/verb or fixed prepositional patterns where relevant for
     French, and phrasal verbs/light-verb constructions for English.
6. **Score focused predictions against gold and iterate.**
   - Because gold MWE annotations are available after manual correction, score
     each token-start decision as true positive, false positive, false negative,
     boundary/type mismatch, or overlap-resolution error.
   - Generate per-language diagnostic briefs showing high-frequency false
     positives, missed MWE types, discontinuous cases, and examples where
     upstream tokenization likely caused the error.
   - Use those briefs to produce the next prompt cycle, then rerun on the
     development split. Validation should decide whether a prompt cycle
     generalizes; test should remain frozen until the cycle and decision rule
     are fixed.
7. **Keep the design cross-stage and publication-ready.**
   - Separable verbs and similar phenomena should not be patched only in
     segmentation. The MWE output should provide the structure that later lemma
     tagging can use to assign shared lemmas to separated and non-separated
     forms.
   - Store traces, gold corrections, prompt cycles, score summaries, and
     disagreement examples as auditable artifacts. If successful, this becomes
     a strong publication example: a harder linguistic task improved by a
     repeatable AI/human prompt-workbench loop.

### Lemma-stage efficiency follow-up

The current MWE refresh path has exposed lemma tagging as a likely throughput
bottleneck. This is surprising: once segmentation, translation, and MWE grouping
are fixed, lemma/POS tagging should usually be a small lexical or
morphological decision rather than a hard generative task. The current API
request is heavier than that intuition suggests:

1. `annotate_lemmas` uses the generic per-segment annotation harness, so it
   sends one API request per segment. There is no lemma-specific concurrency
   limit or de-duplication layer in this call path.
2. Each request contains the full segment JSON, including token surfaces and any
   existing annotations from earlier stages, followed by the generic output
   instructions. The prompt asks the model to return a full segment-shaped JSON
   object, preserve surface/tokens, and add `annotations.lemma` plus
   `annotations.pos` on every token.
3. The prompt also includes the operation template plus few-shot examples. The
   default/English few-shots are currently phrasal-verb examples such as
   `put up with` and `look after`; useful for MWE consistency, but they add a
   sizable constant prompt prefix to every segment, including trivial segments.
4. After the model returns, postprocessing already overwrites MWE-token lemmas
   with the detected MWE surface when possible, which means some expensive model
   decisions are currently discarded or can be made deterministic.

A representative request therefore has the following shape, repeated for every
segment:

```text
You are a linguist adding lemmas and coarse POS tags to a tokenized segment.
Work only with the provided JSON; do not alter token surfaces.

Segment JSON to annotate with lemmas and POS:
{
  "surface": "They looked after the children.",
  "tokens": [
    {"surface": "They"},
    {"surface": " "},
    {"surface": "looked", "annotations": {"mwe_id": "m1"}},
    ...
  ],
  "annotations": {"mwes": [{"id": "m1", "tokens": ["looked", "after"]}]}
}

Few-shot examples:
... full input/output segment JSON examples ...

Return a JSON object representing the segment.
Preserve the original surface and tokens.
For each token, add annotations.lemma and annotations.pos.
Tokens that share annotations.mwe_id should share the same lemma.
```

Potential efficiency improvements, in roughly increasing implementation depth:

1. **Adopt a simplified lemma prompt format, analogous to gloss.** Strip
   irrelevant prior annotations before the call and ask for a compact list of
   `{token_index, lemma, pos}` records, then merge those annotations back into
   the original segment deterministically. Keep only `surface`, token index,
   existing `mwe_id`, and segment-level `mwes`/translation hints if helpful.
2. **Reduce or condition few-shots.** Use zero-shot or one compact few-shot for
   simple segments; include MWE-specific examples only when the segment actually
   contains `mwe_id` or `segment.annotations.mwes`. This should cut constant
   prompt cost on the many non-MWE segments.
3. **Handle deterministic cases before the API call.** Skip whitespace and
   punctuation; copy lemma/POS for tokens already carrying trusted manual
   annotations; assign shared MWE lemmas from `segment.annotations.mwes` where
   the MWE surface is already explicit; possibly handle numerals, proper-name
   capitalization, and closed-class punctuation-like tokens by rules.
4. **Cache lexical decisions.** Many projects repeat the same surface forms and
   the same MWE expressions. Cache `(language, lowercased surface, local POS/MWE
   context)` to lemma/POS decisions within a run, and later persist a reviewed
   cache for common high-confidence items. Be conservative for homographs: cache
   keys should include enough context or POS to avoid collapsing cases like noun
   vs verb readings.
5. **Batch unique lexical items instead of whole segments.** After deterministic
   preprocessing, collect unresolved unique token/MWE candidates and ask the
   model for lemma/POS decisions in batches. Then project the results back to
   all occurrences. This turns repeated segment-level calls into a smaller
   dictionary-style task, which is closer to the true problem.
6. **Add targeted timeout/retry controls.** Even before call-level caching lands,
   expose lemma-specific `max_concurrency`, timeout, and retry settings so the
   refresh target can throttle the slowest stage without slowing the whole
   pipeline. Combined with phase-level retry, this should make large project
   refreshes much less fragile.
7. **Evaluate lightweight linguistic backends.** For languages where reliable
   lemmatizers or morphological analyzers are available, use them as first-pass
   suggestions or fallback for obvious tokens, reserving LLM calls for MWEs,
   ambiguous forms, and low-resource languages.

The first concrete implementation slice should be the simplified request/merge
format plus conditional few-shots, because it is low risk and mirrors the
already-documented gloss-stage optimization. The second slice should add
run-local caching of identical token/MWE decisions, measured on the MWE
experiment corpus before considering persistent caches.

## Open policy questions

- Should ID uniqueness be **page-level** or **global text-level** by default?
- For inconsistent model output, should we repair automatically or require reviewer confirmation?
- How much normalization should happen in upstream stages vs compile-time safety net?

## Success criteria

- No cross-segment false highlighting caused by reused IDs.
- MWE IDs are deterministic and scoped according to chosen policy.
- MWE integrity issues are detectable, test-covered, and observable in logs/telemetry.

## Language-specific prompting guidance (cross-lingual policy)

To improve annotation quality, MWE templates/few-shots should include a small language-specific section whenever the language has recurrent structural traps.

### General policy for set phrases vs open combinations

- Prefer MWEs that are lexicalized/fixed in usage, not merely frequent compositional spans.
- Include explicit boundary examples where over-tagging is likely.
- Canonical example pattern:
  - mark fixed quantifier/adverbial phrases (e.g., "ein wenig"),
  - do **not** mark open compositional combinations derived from them (e.g., "wenig nervös").

### German priorities

German templates and few-shots should explicitly cover:

1. **Separable verbs**
   - Treat verb stem + separated particle as one MWE when lexically established (e.g., `steht ... auf`, `ruft ... an`).
2. **Reflexive verb constructions**
   - Capture fixed reflexive constructions (e.g., `sich freuen`, `sich erinnern`) where reflexive marking is part of lexical behavior.
3. **Set-phrase boundaries**
   - Provide positive/negative contrasts such as `ein wenig` (MWE) vs `wenig nervös` (not an MWE by default).
4. **False-positive blockers for German**
   - Explicitly reject ordinary quantifier+noun phrases (e.g., `etwas Obst`) and accidental long-distance pairings (e.g., `beginnt ... reist`, `im ... auf`).

German discontinuous MWEs are predominantly separable verbs and fixed reflexive verb constructions; other discontinuous types should be treated as rare and require strong lexical evidence before annotation.

### Reuse in other languages

When adding a new language-specific MWE prompt set, include:
- 1 example focused on language-typical discontinuous or morphosyntactic MWE behavior,
- 1 example focused on a common false-positive boundary,
- concise rules in template text describing both.
