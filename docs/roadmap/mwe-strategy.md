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
- Add regression tests for page-level ID uniqueness and HTML data-attribute correctness.

### Phase B: repair policy for partially tagged MWEs
- Define explicit policy when model returns inconsistent tagging (e.g., MWE entry has 2 tokens but only one token marked with `mwe_id`).
- Implement conservative repair heuristics and diagnostics.

### Phase C: observability and review support
- Add telemetry counters for dropped/repaired MWEs.
- Add optional review diagnostics in manual annotation editor for MWE integrity warnings.

## Open policy questions

- Should ID uniqueness be **page-level** or **global text-level** by default?
- For inconsistent model output, should we repair automatically or require reviewer confirmation?
- How much normalization should happen in upstream stages vs compile-time safety net?

## Success criteria

- No cross-segment false highlighting caused by reused IDs.
- MWE IDs are deterministic and scoped according to chosen policy.
- MWE integrity issues are detectable, test-covered, and observable in logs/telemetry.
