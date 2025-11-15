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

Contract: Every in-flight API op emits heartbeat events at ~5s cadence:

# src/clara2/core/telemetry.py

```python
class Telemetry:
	def heartbeat(self, op_id: str, elapsed_s: float, note: str = "") -> None: ...
	def event(self, op_id: str, level: str, msg: str, data: dict | None = None) -> None: ...
```

```openai_client.py``` wraps the OpenAI SDK:

```python
await chat_json(prompt, *, model, temperature, tools=None, response_format=None, telemetry, op_id)
```

Handles retries (exponential backoff), httpx errors, and budget-friendly timeouts.

Ensures response_format="json_object" (or tool-calling) for structured outputs.

---

## 2) Data model (stable JSON)

We keep formats uniform across annotation layers.

```python
from dataclasses import dataclass, field
from typing import List, Dict, Optional

@dataclass
class Token:
    surface: str
    annotations: Dict[str, str] = field(default_factory=dict)  # later: lemma, gloss, pos
    # mwe_id, etc. added later

@dataclass
class Segment:
    tokens: List[Token]
    annotations: Dict[str, str] = field(default_factory=dict)  # later: translated, mwe list

@dataclass
class Page:
    segments: List[Segment]
    annotations: Dict[str, str] = field(default_factory=dict)  # page metadata (img hooks later)

@dataclass
class Text:
    l2: str
    l1: Optional[str] = None
    title: Optional[str] = None
    pages: List[Page] = field(default_factory=list)
    annotations: Dict[str, str] = field(default_factory=dict)
```
	
Serialization: ```storage.py``` exposes ```save_text(text, path)``` / ```load_text(path)```.

---

## 3) Generic processing flow for annotation operations

This processing flow is used for all the annotation operations except segmentation. 

Input is a ```Text``` object and a specification of the type of annotations to be added.
Output is a ```Text``` object which includes the extra annotations.

The generic processing flow is as follows:
- Recursively descend from ```Text``` to ```Page``` to ```Segment``` and process each ```Segment``` in parallel (fan-out).
- For each ```Segment```: 
	- Construct an appropriate prompt. The input to the prompt construction process will include 
		- the ```Segment```
		- a prompt template specific to the operation and source language
		- (optionally) a list of few-shot examples specific to the operation and source language
  - pass the prompt to the AI
- When processing of all the ```Segment```s has completed, combine them to create the new ```Text``` object (fan-in)

The segmentation operation is special because it is the first one. 
- The input is plain text, and the output is a ```Text``` object.
- The operation is divided into two parts. 
- The first part converts the input plain text into a ```Text``` object where the ```Segment``` objects only contain plain text content. 
- The second part uses the generic processing flow to convert the output of the first part into a ```Text``` object where each ```Segment``` object includes a list of ```Token``` objects.

---

## 4) Directory layout (initial)

- src/clara2/
  - core/
    - types.py				# dataclasses: Text, Page, Segment, Token, etc.
    - storage.py				# local JSON read/write helpers
    - config.py				# model names, timeouts, concurrency, retry policy
	- ai_api.py				# call gpt5 and other AIs
    - telemetry.py			# heartbeat/event sink interface
  - pipeline/
    - text_gen.py				# create text from spec
    - segmentation.py			# phase-1 + phase-2 orchestration
	- generic_annotation.py		# generic annotation for operations other than segmentation and segmentation phase-2
	- annotation_prompts.py		# Create prompts for use in generic annotation
  - cli/
    - seg.py					# CLI entry points for MVP (argparse/typer)
  - prompts/
	- segmentation_phase_1/	# Information specific to segmention phase 1 
		- fr/					# Information specific to segmention phase 1 and French				 
			- template.txt	
			- fewshots/
		- [similarly for other languages]
    - segmentation_phase_2/	# Information specific to segmention phase 2 
		- fr/					# Information specific to segmention phase 2 and French				 
			- template.txt	
			- fewshots/
		- [similarly for other languages]
	- [similarly for other annotation operations]