# Linguistic annotation pipeline (full stack)

This document expands Step 3 of the roadmap into a concrete plan for delivering the end-to-end linguistic pipeline, starting from plain text and producing compiled HTML with audio hooks. It builds on the segmentation pipeline (see `docs/roadmap/segmentation-pipeline.md`) and reuses the same annotated text JSON representation (Text → Page → Segment → Token with `annotations` dictionaries).

## Goals

- Reuse the generic per-segment annotation harness (`pipeline/generic_annotation.py`) to deliver all downstream linguistic operations.
- Keep prompts and few-shots organized per operation and language so that new languages can be added by copying the structure.
- Provide test hooks (unit + integration) that can run without OpenAI access by using fakes, while enabling live calls when credentials are present.
- Produce HTML-ready annotated JSON that can be consumed by the compiler step with MWE-aware JavaScript and audio placeholders.
The HTML compiler (`compile_html.py`) and end-to-end runner (`run_full_pipeline`) are now implemented; the runner can start and end at any stage of the pipeline, which lets tests or downstream tools compose partial flows (e.g., start at segmentation outputs and finish at HTML).

## Data model (recap)

- **Text**: `{ "l2": "en", "surface": "...", "pages": [...], "annotations": { ... } }`
- **Page**: `{ "surface": "...", "segments": [...], "annotations": { ... } }`
- **Segment**: `{ "surface": "...", "tokens": [...?], "annotations": { ... } }`
- **Token**: `{ "surface": "...", "annotations": { ... } }`

New operations enrich `annotations` at the segment or token level, but never mutate `surface` text. Each step must preserve any annotations produced by earlier steps (including token arrays) and only add new annotation keys or values. The segmentation phases already fill `pages`, `segments`, and `tokens`.

## Operations and outputs

Each operation is defined by a prompt template plus few-shot examples under `prompts/<operation>/<lang>/`. The generic annotator fans out one request per segment (unless noted) and merges results back into the text object. Implemented so far: translation (EN→FR), MWE detection, lemma tagging, glossing, pinyin (via `pypinyin`), audio annotation (stub/OpenAI TTS), HTML compilation, and the stitched full-pipeline helper.

All steps must be additive: keep surfaces/tokens as-is, preserve annotations from earlier stages, and only layer on the new fields for that operation. Use downstream hints (e.g., translation, lemma, MWE IDs) without overwriting prior metadata.

- **translation** (`prompts/translation/<lang>/`)
  - Input: segment JSON (with tokens when available).
  - Output annotations: `segment.annotations.translation` = target-language string.
  - Current prompts cover English → French; add new language pairs by copying the same structure under `prompts/translation/<l2>/`.
- **mwe** (`prompts/mwe/<lang>/`)
  - Input: tokenized segments produced by segmentation (phase 2). Existing tokens/annotations must be preserved; this step only layers MWE metadata onto them.
  - Output: list of MWEs with token spans; annotate tokens with `token.annotations.mwe_id` and attach `segment.annotations.mwes` metadata. Must precede lemma/gloss so downstream steps can treat MWE tokens as a unit.
- **lemma** (`prompts/lemma/<lang>/`)
  - Input: tokens with surface forms and optional `mwe_id`s.
  - Output annotations per token: `token.annotations.lemma` = canonical lemma (MWE-linked tokens should share the same lemma).
- **gloss** (`prompts/gloss/<lang>/`)
  - Input: tokenized segments with `mwe_id`s, ideally after translation so `segment.annotations.translation` is available as a hint.
  - Output annotations per token: `token.annotations.gloss` = short L1 gloss/definition for each L2 token. If a token belongs to an MWE, the gloss applies to the whole MWE and all member tokens share the same value. Treat translations as guidance, not strict literals.
- **pinyin** (library-backed via `pypinyin`)
  - Input: Chinese tokens.
  - Output annotations per token: `token.annotations.pinyin` = pinyin with tone numbers.
- **audio** (TTS-backed with caching, extensible for human/phonetic paths)
  - Input: tokenized segments with prior annotations preserved.
- Output: `token.annotations.audio` for lexical tokens, `segment.annotations.audio` for every segment, and `page.annotations.audio` built by concatenating segment audio. Each audio annotation is a JSON object carrying the WAV path plus metadata (`surface`, `engine`, `voice`, `language`, `level`) so audits can trace provenance. Default implementation synthesizes short WAV files (offline-friendly stub) and caches per-language/voice+surface to avoid recomputation. If `OPENAI_API_KEY`/`OPENAI_TTS_MODEL` (e.g., `gpt-4o-mini-tts`) are set, the pipeline prefers OpenAI TTS. Google Cloud TTS is opt-in (set `ENABLE_GOOGLE_TTS=1` alongside `GOOGLE_APPLICATION_CREDENTIALS`/`GOOGLE_CREDENTIALS_JSON`) because platform stability varies; when enabled and available, it takes precedence over the stub. Token-level cache keys may incorporate lemmas/POS when present to disambiguate homographs (e.g., "tear" noun vs. verb). Future enhancements will add human-recorded audio ingestion (e.g., Audacity-sliced clips) and phonetic-text pipelines that swap in specialised TTS engines.

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
    audio.py               # token/segment audio synthesis with caching (new)
    compile_html.py        # HTML assembly with MWE-aware JS hooks (new)
prompts/
  translation/<lang>/template.txt, fewshots/*.json
  lemma/<lang>/template.txt, fewshots/*.json
  gloss/<lang>/template.txt, fewshots/*.json
  mwe/<lang>/template.txt, fewshots/*.json
  pinyin/zh/template.txt, fewshots/*.json
  # audio uses a library-backed synthesizer and cache; no prompts required
```

## Pipeline sequencing

1. **text_gen** → generated plain text.
2. **segmentation_phase_1** → pages/segments filled (already implemented).
3. **segmentation_phase_2** → tokenization + token surfaces (already implemented).
4. **translation** (segment-level, can be parallelized).
5. **mwe** (segment-level; establishes shared IDs before token-level work).
6. **lemma** (token-level; respects shared `mwe_id` lemma).
7. **gloss** (token-level; respects shared `mwe_id` gloss).
8. **pinyin** (Chinese-specific token-level; optional per language; uses `pypinyin` instead of AI prompts).
9. **audio** (token + segment level; generates/caches audio files with a pluggable TTS backend and prepares for human/phonetic inputs later).
10. **compile_html** (consumes annotated JSON; emits HTML + JS that highlights MWEs and links audio). **Implemented.**

Steps 4–9 all use `generic_annotation.annotate_segments`, differing only in prompt folder and output schema validation. Each operation should be idempotent on already-annotated tokens (skip if the target annotation exists unless `force=True`).

## Prompt expectations

- **template.txt**: prompt body with placeholders such as `{{segment_json}}`, `{{language}}`, `{{operation}}`, and optional op-specific hints.
- **fewshots/*.json**: minimal JSON with `input` (segment or token list) and `output` (desired annotation structure). Keep examples short for latency.

## Example progression (with MWE)

The table below shows a short segment containing an MWE ("put up with") as it moves through the operations. Each step adds annotations but keeps `surface` unchanged.

| Step | Annotated view |
| --- | --- |
| Segmentation phase 1 | `surface`: "She put up with the noise." → pages/segments created. |
| Segmentation phase 2 | Tokens: `She` ` ` `put` ` ` `up` ` ` `with` ` ` `the` ` ` `noise` `.` |
| MWE | `segment.annotations.mwes`: `[{"id": "m1", "tokens": ["put","up","with"], "label": "phrasal verb"}]`; tokens `put/up/with` carry `token.annotations.mwe_id="m1"`. |
| Lemma | `token.annotations.lemma`: `she`, `put` (m1), `put` (m1), `put` (m1), `the`, `noise`; MWE members share the same lemma. |
| Gloss | `token.annotations.gloss`: `she`, `tolerate` (m1 across three tokens), `the`, `noise`; MWE members share the same gloss. |
| Translation | `segment.annotations.translation`: "Elle a supporté le bruit." |
| Audio | `segment.annotations.audio`: cached audio file path for the segment; `token.annotations.audio` attached only to word tokens (e.g., `put`, `noise`). Audio metadata includes path, engine, voice, language, and level; files are validated for minimal duration and fall back to the stub engine if an upstream TTS responds with empty audio. |
| Compile HTML | Tokens rendered with `data-mwe-id="m1"`, lemmas/gloss popups, and audio hooks. |

## Testing strategy

- **Unit tests**: for each operation module:
  - prompt loading + assembly from `annotation_prompts`.
  - normalization/validation of AI responses into the annotated text object.
  - idempotency checks when annotations already exist.
- **Integration tests** (guarded by `OPENAI_API_KEY` and `OPENAI_TEST_MODEL`):
  - end-to-end per operation on short English (and Chinese for pinyin) segments.
  - full pipeline run (text_gen → segmentation → translation → mwe → lemma → gloss → audio → compile_html) with assertions on shape and required annotations.
- **Offline mode**: default test runs use fake clients and sample outputs; real OpenAI calls are skipped automatically when credentials are missing.

## Telemetry & observability

- All operations accept an optional telemetry sink (stdout/null or future structured logger).
- Heartbeats fire every `heartbeat_s` during OpenAI calls to show progress on fan-out work.
- Record per-operation timings and retry counts for later UI surfacing.

## HTML compilation notes

`compile_html.py` is the final presentation step. It consumes the fully annotated JSON and emits a static bundle (HTML + JS + CSS + audio links) that mirrors the C-LARA UX. The compiler must **never mutate existing annotations**; it only adds presentational data.

### Inputs

- Fully annotated text JSON (segments contain translations, MWEs, lemmas, glosses, pinyin when present, and audio metadata at token/segment/page levels).
- Audio files referenced by annotation metadata (token/segment/page) in a predictable relative path (e.g., `audio/<hash>.wav`).

### Concordance construction

1. Build an in-memory concordance keyed by **lemma**. Each entry keeps the lemma string, optional POS, and the list of segment references where the lemma appears.
2. When a token belongs to an MWE, its concordance entry references the **shared MWE lemma** so the concordance treats the whole expression consistently.
3. Persist the concordance alongside the HTML (as embedded JSON in the page) so client-side JS can render and filter without server calls.

### Layout

- Split the page into two panes (CSS grid/flex):
  - **Text pane (left)**: paginated text with per-page and per-segment controls (play page audio, play segment audio, toggle translations). Tokens are wrapped in spans with:
    - `data-lemma`, `data-gloss`, and `data-mwe-id` for hover/highlight behavior.
    - `data-token-id` and `data-audio` (if available) for click-to-play.
  - **Concordance pane (right)**: interactive list keyed by lemma. Selecting a lemma shows the segments containing it, reusing the same token markup so hover/click behavior is identical.

### Interactions

- **Click a token or concordance item**: opens the lemma’s concordance view in the right pane and plays token audio if present. If the token is part of an MWE, all member tokens highlight together.
- **Hover a token**: shows a popup with gloss (and pinyin when available) and highlights all tokens in the same MWE. Hovering in either pane uses the same JS handlers.
- **Segment controls**: buttons for translation reveal and segment audio playback, wired to the segment-level audio annotation.
- **Page controls**: button for page-level audio playback that streams the concatenated audio file if available.
- All interactions should degrade gracefully when audio/gloss/pinyin are missing (no errors, just no-op or textual fallback).
- **Chinese pinyin rendering**: when `token.annotations.pinyin` is present, wrap L2 surfaces in `<ruby><rb>…</rb><rt>pinyin</rt></ruby>` so users see inline pinyin above characters. The same markup should be used in both panes and in concordance entries.

### Assets and output

- Emit the compiled HTML, a small JS bundle, and CSS into `artifacts/html/` (created if absent) so humans can open results directly from disk during reviews. The current implementation writes to `artifacts/html/run_<id>/index.html` with inline JS/CSS and embedded concordance JSON for quick inspection.
- JS helpers should stay generic and live alongside the HTML output (e.g., `artifacts/html/static/`). Minimal dependencies: vanilla JS for DOM events plus optional lightweight utility (no heavy frameworks).
- Keep audio references relative to the HTML output root to avoid CORS/file URL issues when opened locally.

### Testing & auditing hooks

- Unit tests for `compile_html` should write artifacts into a temporary `artifacts/html/test_run_<uuid>/` folder and log the absolute path to make manual inspection easy. Current tests log both the annotated segment JSON and the rendered HTML path for reviewers.
- Include sample concordance snippets in the test log to confirm MWEs map to shared lemmas and that gloss/pinyin show up in popups.
- Consider a lint step that validates `data-*` attributes are present for tokens with lemmas/MWEs and that audio metadata points to existing files when a TTS engine is configured.

## Deliverables checklist

- [x] Operation modules under `src/pipeline/` as listed above.
- [x] Prompt templates + few-shots for English-backed AI operations under `prompts/`; pinyin is library-based and does not need prompts.
- [x] Unit + integration tests covering the new operations and full pipeline.
- [x] Documentation updates (this doc + README pointer) once modules land.

