# Roadmap: alignment in C-LARA-2

This roadmap covers the **second alignment stream** requested for C-LARA-2, based on successful LARA work and extended with AI-assisted methods.

We define two complementary alignment tracks:

- **2a. Phonetic alignment**: decompose words into phonetic units and support compilation of a phonetic-view document.
- **2b. Triple alignment**: align source text, high-quality source-language audio, and high-quality translation.

---

## Why this matters

Alignment supports two high-value learner experiences:

1. **Better reading/listening synchronisation** for long literary texts.
2. **Richer pronunciation support** through phonetic decomposition and phonetic-mode rendering.

LARA experiments (2022) suggest strong quality is feasible even on difficult texts, with low text/audio and audio/translation error rates after light post-editing.

---

## 2a. Phonetic alignment roadmap

### Target functionality

- For each token (or MWE component), generate a **phonetic decomposition** into units appropriate for the language.
- Persist decompositions in a **cache/artifact store** so results are reusable.
- Provide a compile mode that can output a **phonetic version** of the text where display units are phonetic units rather than orthographic tokens.

### Processing strategy

Use a layered strategy, highest confidence first:

1. **Lexicon-driven decomposition**
   - Extract character-sequence → phoneme mappings from language resources.
   - Apply deterministic longest-match decomposition where possible.
2. **Rule/transducer fallback** (language-specific when available)
   - Use grapheme-to-phoneme rules or finite-state mappings.
3. **AI fallback decomposition**
   - Ask the model to return structured decomposition with schema constraints.
   - Validate output against language/script constraints before accepting.

### Storage model

Suggested artifact layout:

```text
alignment/
  phonetic/
    config.json
    units_table.json
    token_decompositions.json
    cache_index.json
```

Each cached decomposition should keep provenance:

- token surface + lemma + language,
- method used (`lexicon`, `rules`, `ai`),
- model/version where relevant,
- validation status and timestamp.

### Compile integration

Add compile option variants:

- `normal` (existing behavior),
- `phonetic` (phonetic units as renderable segments),
- optional `hybrid` (orthography + phonetic hints).

Phonetic compile should remain compatible with:

- audio playback controls,
- concordance/click interactions,
- existing segment/page boundaries.

### Quality controls

- Structural validator for decomposition format.
- Language-aware checks (allowed symbol inventory, stress/tone conventions where applicable).
- Spot-check workflow for uncertain items.

---

## 2b. Text/audio/translation triple alignment roadmap

### Goal

Produce a segmented source text where each segment is linked to:

- a high-quality source-language audio span,
- a matching high-quality translation span.

### Baseline method (from LARA)

Retain the proven backbone:

1. translation alignment on source/target text,
2. split audio on silences,
3. ASR over audio chunks,
4. beam alignment of ASR output to source text,
5. reconciliation/postprocessing of translation and audio boundaries,
6. joint segmentation at agreed boundaries,
7. segment-level aggregation of audio + translation.

### C-LARA-2 AI-augmented improvements

- **ASR normalization with AI assistance** for punctuation/casing/noisy recognitions before beam matching.
- **Boundary repair proposals** from AI constrained by deterministic checks.
- **Translation alignment rescoring** using embedding similarity + lexical constraints.
- **Adaptive segmentation policy** (sentence-length targets per language/genre).

### Metrics and acceptance

Track at least these metrics per corpus:

- audio/source-text WER,
- audio/translation WER,
- segmentation quality (boundary similarity / segeval-compatible score),
- mean segment length and variance.

Recommended quality gates for broad publishability (initial targets):

- text/audio WER near or below ~1%,
- audio/translation WER around ~1–2%,
- segmentation quality sufficient to avoid routinely overlong segments.

(Exact thresholds should be refined by language and genre.)

### Artifact outputs

Suggested layout:

```text
alignment/
  triple/
    translation_alignment.json
    audio_chunks.json
    asr_results.json
    double_aligned.txt
    reconciled_alignment.txt
    joint_alignment.json
    metrics.json
```

### Post-editing and human review

Provide a review UI prioritizing uncertain segments:

- boundary conflicts,
- high local WER,
- low translation-match confidence.

Support quick operations:

- merge/split segments,
- move boundary left/right,
- reattach translation/audio spans.

---

## Integration points with current C-LARA-2

1. **Pipeline spec**
   - Extend `FullPipelineSpec`/orchestrator options to include alignment modes and thresholds.
2. **Compile pipeline**
   - Consume alignment artifacts for synchronized player behavior and optional phonetic rendering.
3. **Platform UI**
   - Add alignment job management pages (status, diagnostics, review queue).
4. **Publishing**
   - Publish aligned artifacts with provenance metadata.

---

## Incremental implementation plan

### Phase A: Foundations

- Define schemas for phonetic and triple-alignment artifacts.
- Implement deterministic cache/provenance layer.
- Add CLI/dev entrypoints for standalone alignment runs.

### Phase B: Phonetic alignment MVP (2a)

- Lexicon-driven decomposition + cache.
- AI fallback with strict schema validation.
- Phonetic compile mode prototype.

### Phase C: Triple-alignment MVP (2b)

- Implement LARA-style baseline pipeline end-to-end.
- Produce metrics and confidence diagnostics.
- Add manual review tool for boundary fixes.

### Phase D: AI-assisted quality improvements

- Boundary repair rescoring.
- Translation alignment rescoring.
- Segment policy tuning by language/genre.

### Phase E: Scale-out and benchmarking

- Evaluate on short, medium, and very long literary texts.
- Compare against LARA-style baseline and prior results.
- Establish recommended defaults per language profile.

---

## Open questions

- Best phonetic unit granularity per script/language family (phoneme vs syllable vs mixed).
- How to harmonize phonetic decomposition with MWE behavior in UI interactions.
- Whether one global segmentation policy can work, or if per-language profiles are required.
- How far AI can reduce segmentation errors without increasing hallucination risk.
