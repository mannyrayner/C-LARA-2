# Linguistic annotation pipeline (full stack)

This document expands Step 3 of the roadmap into a concrete plan for delivering the end-to-end linguistic pipeline, starting from plain text and producing compiled HTML with audio hooks. It builds on the segmentation pipeline (see `docs/roadmap/segmentation-pipeline.md`) and reuses the same annotated text JSON representation (Text → Page → Segment → Token with `annotations` dictionaries).

## Goals

- Reuse the generic per-segment annotation harness (`pipeline/generic_annotation.py`) to deliver all downstream linguistic operations.
- Keep prompts and few-shots organized per operation and language so that new languages can be added by copying the structure.
- Provide test hooks (unit + integration) that can run without OpenAI access by using fakes, while enabling live calls when credentials are present.
- Produce HTML-ready annotated JSON that can be consumed by the compiler step with MWE-aware JavaScript and audio placeholders.

## Data model (recap)

- **Text**: `{ "l2": "en", "surface": "...", "pages": [...], "annotations": { ... } }`
- **Page**: `{ "surface": "...", "segments": [...], "annotations": { ... } }`
- **Segment**: `{ "surface": "...", "tokens": [...?], "annotations": { ... } }`
- **Token**: `{ "surface": "...", "annotations": { ... } }`

New operations enrich `annotations` at the segment or token level, but never mutate `surface` text. The segmentation phases already fill `pages`, `segments`, and `tokens`.

## Operations and outputs

Each operation is defined by a prompt template plus few-shot examples under `prompts/<operation>/<lang>/`. The generic annotator fans out one request per segment (unless noted) and merges results back into the text object.

- **translation** (`prompts/translation/<lang>/`)
  - Input: segment JSON (with tokens when available).
  - Output annotations: `segment.annotations.translation` = target-language string.
- **lemma** (`prompts/lemma/<lang>/`)
  - Input: tokens with surface forms.
  - Output annotations per token: `token.annotations.lemma` = canonical lemma.
- **gloss** (`prompts/gloss/<lang>/`)
  - Input: tokens + optional lemmas.
  - Output annotations per token: `token.annotations.gloss` = short gloss/definition.
- **mwe** (`prompts/mwe/<lang>/`)
  - Input: segment surfaces + tokens.
  - Output: list of MWEs with token spans; annotate tokens with `token.annotations.mwe_id` and attach `segment.annotations.mwes` metadata.
- **pinyin** (`prompts/pinyin/zh/`)
  - Input: Chinese tokens.
  - Output annotations per token: `token.annotations.pinyin` = pinyin with tone numbers.
- **audio_stub** (`prompts/audio_stub/<lang>/`)
  - Input: segment surfaces (and optionally translations).
  - Output: `segment.annotations.audio_hint` holding a TTS-ready script or SSML; later replaced by real audio generation.

## Directory layout

```
src/
  core/
    ai_api.py              # heartbeat-aware OpenAI wrapper (sync via executor)
    config.py              # defaults for model, timeout, etc.
    telemetry.py           # stdout/null telemetry
  pipeline/
    generic_annotation.py  # fan-out/fan-in helper
    annotation_prompts.py  # prompt/template loader utilities
    segmentation.py        # phase 1 + phase 2 + full segmentation
    text_gen.py            # description → generated text
    translation.py         # segment-level translation (new)
    lemma.py               # token-level lemmatization (new)
    gloss.py               # token-level glossing (new)
    mwe.py                 # multi-word expression detection (new)
    pinyin.py              # Chinese romanization (new)
    audio_stub.py          # prepare text for later audio synthesis (new)
    compile_html.py        # HTML assembly with MWE-aware JS hooks (new)
prompts/
  translation/<lang>/template.txt, fewshots/*.json
  lemma/<lang>/template.txt, fewshots/*.json
  gloss/<lang>/template.txt, fewshots/*.json
  mwe/<lang>/template.txt, fewshots/*.json
  pinyin/zh/template.txt, fewshots/*.json
  audio_stub/<lang>/template.txt, fewshots/*.json
```

## Pipeline sequencing

1. **text_gen** → generated plain text.
2. **segmentation_phase_1** → pages/segments filled (already implemented).
3. **segmentation_phase_2** → tokenization + token surfaces (already implemented).
4. **translation** (segment-level, can be parallelized).
5. **lemma** (token-level).
6. **gloss** (token-level, may use lemmas if available).
7. **mwe** (segment-level; must run after tokens/lemmas so spans align).
8. **pinyin** (Chinese-specific token-level; optional per language).
9. **audio_stub** (segment-level; prepares input for future TTS module).
10. **compile_html** (consumes annotated JSON; emits HTML + JS that highlights MWEs and links audio hints).

Steps 4–9 all use `generic_annotation.annotate_segments`, differing only in prompt folder and output schema validation. Each operation should be idempotent on already-annotated tokens (skip if the target annotation exists unless `force=True`).

## Prompt expectations

- **template.txt**: prompt body with placeholders such as `{{segment_json}}`, `{{language}}`, `{{operation}}`, and optional op-specific hints.
- **fewshots/*.json**: minimal JSON with `input` (segment or token list) and `output` (desired annotation structure). Keep examples short for latency.

## Testing strategy

- **Unit tests**: for each operation module:
  - prompt loading + assembly from `annotation_prompts`.
  - normalization/validation of AI responses into the annotated text object.
  - idempotency checks when annotations already exist.
- **Integration tests** (guarded by `OPENAI_API_KEY` and `OPENAI_TEST_MODEL`):
  - end-to-end per operation on short English (and Chinese for pinyin) segments.
  - full pipeline run (text_gen → segmentation → translation → lemma → gloss → mwe → compile_html) with assertions on shape and required annotations.
- **Offline mode**: default test runs use fake clients and sample outputs; real OpenAI calls are skipped automatically when credentials are missing.

## Telemetry & observability

- All operations accept an optional telemetry sink (stdout/null or future structured logger).
- Heartbeats fire every `heartbeat_s` during OpenAI calls to show progress on fan-out work.
- Record per-operation timings and retry counts for later UI surfacing.

## HTML compilation notes

- `compile_html.py` should accept the fully annotated text JSON and emit HTML with:
  - token spans tagged with IDs for MWEs (`data-mwe-id`), lemmas, and gloss popups.
  - per-segment hooks for audio (`data-audio-hint`), ready for later TTS linking.
  - bundled JS/CSS to highlight MWEs when hovering any member token and to show glosses.

## Deliverables checklist

- [ ] Operation modules under `src/pipeline/` as listed above.
- [ ] Prompt templates + few-shots for English (and Mandarin for pinyin) under `prompts/`.
- [ ] Unit + integration tests covering the new operations and full pipeline.
- [ ] Documentation updates (this doc + README pointer) once modules land.

