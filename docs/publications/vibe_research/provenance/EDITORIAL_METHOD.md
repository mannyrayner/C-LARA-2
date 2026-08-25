# Editorial method for the Vibe Research provenance edition

## Purpose

The uploaded ChatGPT session was valuable but not directly navigable. It mixed long text responses, short voice-mode backchannels, timestamps, informal attachment placeholders, a duplicated Sunday prompt, a speaker-label variant, a malformed final marker, and 372 empty terminal speaker blocks. This edition turns that export into a searchable research record without treating editorial metadata as primary evidence.

## Evidence layers

1. [`raw/session_transcript_original.txt`](raw/session_transcript_original.txt) is the exact uploaded byte sequence. It is never generated or edited.
2. [`exchanges/exchanges.jsonl`](exchanges/exchanges.jsonl) is the canonical structural normalization. Each retained turn has its original wording and source-line range.
3. [`exchanges/transcript_normalized.md`](exchanges/transcript_normalized.md) is a readable rendering with stable exchange and turn labels.
4. [`chunks/`](chunks/) is a curated reading edition. The full utterances are repeated under semantically chosen boundaries and preceded by editorial summaries and topics.
5. [`metadata/`](metadata/) and [`indexes/`](indexes/) are discovery aids. They direct a reader to evidence; they are not substitutes for it.

## Multipass procedure

### Pass 1: preservation and inventory

The original transcript was copied before any reorganization. The current manuscript, bibliography, intermediate drafts, and bibliography snapshots were separated by function. Every known artifact was hashed.

### Pass 2: deterministic structural parsing

The builder recognizes day/time headings and `MANNY:`, `MR:`, and `AI:` blocks. It normalizes `MR` to Manny while retaining the original label, drops empty blocks from derived output, and assigns permanent identifiers. A turn is one retained speaker block; an exchange is a Manny turn followed by an AI turn.

One editorial deduplication is declared in code and in `normalization_report.json`: source lines 1027–1028 repeat the opening sentence of the fuller `MR:` turn beginning at line 1032. The shorter copy is excluded. The full version is retained. The builder also records, rather than conceals, the correction of `[Version 13)` to the artifact key `Version 13`.

No spelling, punctuation, disfluency, or wording inside retained utterances is corrected. The normalized edition is therefore not a polished transcript; it is a structurally repaired one.

### Pass 3: semantic segmentation

Chunk boundaries were selected after reading the whole trace. They respect time headings, topic changes, draft-production events, and utterance size. Counts deliberately vary from one to fourteen exchanges: the fourteen-exchange chunk consists mainly of short spoken fragments, while several very long research exchanges stand alone. An exchange is never split.

### Pass 4: editorial enrichment

Each chunk receives a title, concise summary, and reviewed topic terms. These descriptions were produced during the Codex reorganization and encoded as data in `build_provenance.py`. They are interpretive navigation aids. Claims should be verified against the linked exchanges and artifacts.

### Pass 5: artifact linking and indexes

Informal markers such as `[Version 4]` and `[References 1]` are mapped to stable artifact IDs and repository paths. The script generates chronological, topic, keyword, and artifact indexes. A separate reviewed decision index identifies consequential changes in the paper and links them to the relevant exchanges.

### Pass 6: validation

`validate_provenance.py` checks the immutable source hash, turn/exchange counts, source spans, speaker order, chunk coverage, artifact existence and hashes, links, and index references. Regenerating the derived edition with `build_provenance.py` is deterministic.

## Known limitations

- Timestamps are session headings from the exported interface, not timestamps for each exchange.
- The trace does not explicitly mark Version 8, although `drafts/version_8.tex` exists.
- The trace describes work performed with Codex between sessions; it is not a complete record of that separate work.
- Chunk summaries and topic assignments reflect editorial judgement and could reasonably be revised without changing the evidence.
- The original Casey Newton article upload was not retained in the public tree. It was replaced by an original summary; its canonical URL still requires human verification.

## Reuse

The method is intentionally general: preserve raw input, normalize structure deterministically, apply reviewed semantic segmentation, generate discovery metadata, and validate every route back to evidence. Other long human–AI research sessions could use the same evidence-layer separation even if their parsers and semantic categories differ.
