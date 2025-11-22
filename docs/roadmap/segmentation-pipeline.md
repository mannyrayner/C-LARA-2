# Segmentation MVP: Plan & Interfaces

**Goal (MVP)**  
Implement the *create text → segment pages/segments → token-level split* pipeline with clean interfaces, prompts, and tests — ready to extend to translation/MWE/lemma/gloss/pinyin later.

---

## 0) Scope (what’s in / out)

**In (MVP):**
- Generate a fresh L2 text from a simple spec (title, genre, length, level, style hints).
- Page/segment partitioning (phase 1).
- Per-segment tokenization/splitting (phase 2) using language-specific prompt templates and optional few-shot examples.
- Async OpenAI calls with a periodic heartbeat (every ~5s) surfaced to the caller.
- Deterministic JSON outputs that the later annotation operations (translation, MWE, lemma, gloss, pinyin) can consume.

**Out (for now):**
- Rendering to HTML/mobile views.
- Translation/MWE/Lemma/Gloss/Pinyin (will layer on same patterns).
- Auth/roles/UI — we’ll CLI/test-drive first.

---

## 1) Heartbeat + async calls

Contract: Every in-flight API op emits heartbeat events at ~5s cadence. The core pieces live under `src/core/` (sibling to `docs/`) so they are easy to import from the CLI and future Django app.

# src/core/telemetry.py

```python
class Telemetry:
        def heartbeat(self, op_id: str, elapsed_s: float, note: str = "") -> None: ...
        def event(self, op_id: str, level: str, msg: str, data: dict | None = None) -> None: ...

class NullTelemetry(Telemetry):
        ... # no-op default for tests/CLI

class StdoutTelemetry(Telemetry):
        ... # quick feedback while bootstrapping
```

# src/core/ai_api.py

```python
await OpenAIClient(config).chat_json(
        prompt,
        *,
        model=None,
        temperature=None,
        tools=None,
        response_format=None,
        telemetry=None,
        op_id=None,
)
```

- Wraps the async OpenAI SDK so every request has: heartbeat every ~5s, exponential backoff on `RateLimit`/`APIError`/timeouts, and deterministic JSON parsing of the first message choice.
- `config.py` holds defaults for model/temperature/timeout/backoff/heartbeat cadence, picks up `OPENAI_API_KEY` from the environment, and can be overridden per-call.
- The default model is `gpt5`, matching the quality bar we need from the C-LARA experiments.
- `OpenAIClient` passes the configured `api_key` directly into `AsyncOpenAI`; by default this comes from `OPENAI_API_KEY`, but callers can construct `OpenAIConfig(api_key="...")` to override.
- A generated `op_id` is attached to all telemetry events when the caller does not provide one.

---

## 2) Text generation (text_gen operation)

**Purpose:** First pipeline step: generate a raw L2 text from a short description.

**Flow:**
- Input: a JSON object describing the desired text (e.g., title, genre, level, length/word-count, style hints, target reader).
- Build a prompt by injecting the description into an operation-specific template (per language/genre, stored under `prompts/text_gen/`).
- Call the AI once (no fan-out) and return a `Text` JSON object with the generated `surface`, `title`, and metadata filled in. Downstream segmentation operates directly on this output.
- Telemetry is optional but should log a single operation ID; heartbeat timing matches the generic OpenAI wrapper defaults.

**Notes:**
- Keep the prompt template explicit about constraints (length, register, avoid formatting) so segmentation isn’t complicated by Markdown or bullets.
- Few-shot examples can live alongside the template in `prompts/text_gen/<lang>/fewshots/`.

---

## 3) Data model (stable JSON)

We keep formats uniform across annotation layers and represent them as JSON objects so they can be passed directly between the CLI, pipeline steps, and the AI.

```jsonc
// Token
{
  "surface": "The",
  "annotations": {} // later: lemma, gloss, pos, mwe_id, etc.
}

// Segment
{
  "surface": "The boy's name was Will.",
  "tokens": [
    { "surface": "The", "annotations": {} }
  ],
  "annotations": {} // later: translated text, MWE list
}

// Page
{
  "surface": "A full page worth of text…",
  "segments": [ /* Segment[] */ ],
  "annotations": {} // page metadata (img hooks later)
}

// Text
{
  "l2": "en", // source language code
  "l1": "fr", // optional target language code
  "title": "My Story", // optional
  "surface": "Full raw text…",
  "pages": [ /* Page[] */ ],
  "annotations": {}
}
```

In code we can still expose light dataclasses in ```types.py``` for developer ergonomics, but the persisted/on-wire format is JSON with these fields. ```storage.py``` should serialize/deserialize the plain JSON structures (`save_text(path, text_json)` / `load_text(path) -> dict`).

---

## 4) Generic processing flow for annotation operations

The IDs for the annotation operations are the following: 
- ```segmentation``` # Add segmentation information 
- ```segmentation_phase_1``` # First part of ```segmentation``` operation
- ```segmentation_phase_2``` # Second part of ```segmentation``` operation
- ```translation``` # Add a translation to each ```Segment``` 
- ```mwe``` # Add MWE (multi word expression) information to each ```Segment``` 
- ```lemma``` # Add lemma and POS information to each ```Token``` 
- ```gloss``` # Add gloss information to each ```Token``` 
- ```pinyin``` # Add pinyin information to each ```Token``` (only relevant for Chinese)

The generic processing flow is used for all the annotation operations except ```segmentation``` and ```segmentation_phase_1```. 

The generic processing flow is as follows:
- Input is a ```Text``` JSON object and a specification of the type of annotations to be added.
- Output is a ```Text``` JSON object which includes the extra annotations.
- Recursively descend from ```Text``` to ```Page``` to ```Segment``` and process each ```Segment``` in parallel (fan-out).
- For each ```Segment```: 
	- Construct an appropriate prompt. The input to the prompt construction process will include 
		- the ```Segment```
		- a prompt template specific to the operation and source language
		- (optionally) a list of few-shot examples specific to the operation and source language
  - pass the prompt to the AI
- When processing of all the ```Segment```s has completed, combine them to create the new ```Text``` object (fan-in)

The ```segmentation``` operation is special because it is the first one.
- The input is plain text, and the output is a ```Text``` JSON object.
- The ```segmentation``` operation is divided into two parts, ```segmentation_phase_1``` and ```segmentation_phase_2```.
- ```segmentation_phase_1``` converts the input plain text into a ```Text``` JSON object where the ```Segment``` objects only contain plain text content in the form of a ```surface``` field.
- ```segmentation_phase_2``` uses the generic processing flow to convert the output of the first part into a ```Text``` JSON object where each ```Segment``` object includes a list of ```Token``` objects.

---

## 5) Example inputs and outputs for segmentation operation

Here is a minimal example of inputs and outputs for the ```segmentation``` operation.

The input plain text string is the following:

```
A boy once lived with his mother in a house by the sea. The boy's name was Will. His mother's name was Emma.

One day, walking on the beach, Will noticed a curious object. It looked like a very large egg.
```

A plausible output of the ```segmentation_phase_1``` operation could be the following ```Text``` JSON object:

```json
{
  "l2": "en",
  "surface": """A boy once lived with his mother in a house by the sea. The boy's name was Will. His mother's name was Emma.

One day, walking on the beach, Will noticed a curious object.  It looked like a very large egg.""",
  "pages": [
    {
      "surface": "A boy once lived with his mother in a house by the sea. The boy's name was Will. His mother's name was Emma.",
      "segments": [
        { "surface": "A boy once lived with his mother in a house by the sea." },
        { "surface": " The boy's name was Will." },
        { "surface": " His mother's name was Emma." }
      ]
    },
    {
      "surface": "One day, walking on the beach, Will noticed a curious object. It looked like a very large egg.",
      "segments": [
        { "surface": "One day, walking on the beach, Will noticed a curious object." },
        { "surface": " It looked like a very large egg." }
      ]
    }
  ]
}
```

This ```Text``` JSON object will be the input to the ```segmentation_phase_2```. The output will be the same as the input, except that each ```Segment``` object will be further annotated with a ```tokens``` array. For example, the ```Segment``` object

```json
{ "surface": " The boy's name was Will." }
```

will be transformed into

```json
{
  "surface": " The boy's name was Will.",
  "tokens": [
    { "surface": " " },
    { "surface": "The" },
    { "surface": " " },
    { "surface": "boy" },
    { "surface": "'s" },
    { "surface": " " },
    { "surface": "name" },
    { "surface": " " },
    { "surface": "was" },
    { "surface": " " },
    { "surface": "Will" },
    { "surface": "." }
  ]
}
```

---

## 6) Directory layout (initial)

- src/
  - core/                           # import root for shared infra (sibling of `docs/`)
    - ai_api.py                     # AsyncOpenAI wrapper with heartbeats + retries
    - config.py                     # model names, timeouts, retry policy, heartbeat cadence
    - telemetry.py                  # heartbeat/event sink interface (NullTelemetry, StdoutTelemetry)
    - types.py                      # dataclasses: Text, Page, Segment, Token, etc. (JSON-on-wire)
    - storage.py                    # local JSON read/write helpers
  - pipeline/                       # pipeline steps sit next to core under src/
    - text_gen.py                   # create text from spec
    - segmentation.py               # phase-1 + phase-2 orchestration
    - generic_annotation.py         # generic annotation for operations other than segmentation-phase-1
    - annotation_prompts.py         # create prompts for use in generic annotation
  - cli/
    - seg.py                        # CLI entry points for MVP (argparse/typer)
- prompts/
  - text_gen/                       # per-language templates + fewshots for text generation
    - fr/
      - template.txt
      - fewshots/
    - [similarly for other languages]
  - segmentation_phase_1/           # per-language templates + fewshots
    - fr/
      - template.txt
      - fewshots/
    - [similarly for other languages]
  - segmentation_phase_2/
    - fr/
      - template.txt
      - fewshots/
    - [similarly for other languages]
  - [similarly for other annotation operations]
