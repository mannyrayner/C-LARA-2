# Vibe Research paper and provenance record

This directory contains the current *Vibe Research* manuscript and a curated, auditable record of the interactive ChatGPT-5.6 session through which it developed. The organization is designed both for human readers and for repository-grounded assistants investigating the provenance of arguments and revisions.

## Start here

- [`paper/main.tex`](paper/main.tex) — current canonical manuscript.
- [`paper/references.bib`](paper/references.bib) — current consolidated bibliography.
- [`provenance/indexes/chronological.md`](provenance/indexes/chronological.md) — chronological guide to the research session.
- [`provenance/indexes/topics.md`](provenance/indexes/topics.md) — topic-to-chunk index.
- [`provenance/indexes/decisions.md`](provenance/indexes/decisions.md) — consequential paper decisions with exchange evidence.
- [`provenance/indexes/artifacts.md`](provenance/indexes/artifacts.md) — intermediate drafts and bibliography snapshots.
- [`provenance/EDITORIAL_METHOD.md`](provenance/EDITORIAL_METHOD.md) — how the uploaded trace was preserved, normalized, segmented, enriched, and checked.

## Directory layout

- `paper/` contains the current manuscript and bibliography.
- `drafts/` contains Versions 1–9 and 12–13, plus the partial Version 10 introduction and Version 11 replacement passages.
- `bibliography_snapshots/` contains bibliography additions supplied at different stages of the session.
- `provenance/raw/` contains the exact uploaded session trace.
- `provenance/exchanges/` contains stable turn/exchange records and a readable normalized transcript.
- `provenance/chunks/` contains nineteen semantically selected reading chunks. Chunk length varies with topic and utterance length.
- `provenance/metadata/` contains machine-readable normalization, chunk, artifact, and decision records.
- `provenance/indexes/` contains generated and reviewed discovery indexes.
- `sources/` contains a summary and metadata for the Casey Newton article; the uploaded full text was removed for copyright reasons.
- `scripts/` contains the deterministic builder and validator.

## Evidence and discovery metadata

The exact trace and manuscript artifacts are evidence. Chunk titles, summaries, topics, and the decision index are editorial discovery metadata produced during the Codex reorganization. They help locate material but should not be quoted as if they were original utterances. Answers should follow metadata links to stable exchange IDs and, where relevant, to the actual draft.

The raw trace has SHA-256 `7ec2eced0e1c7f7263d4bbfb788022ad4dda151794e6e0403537ea058a556b56`. It includes all original irregularities and empty headings. Derived records remove 372 empty speaker blocks, exclude one truncated duplicate prompt, normalize the `MR` label to Manny, and map informal attachment markers to repository files. Substantive retained utterances are not copy-edited.

## Regeneration and validation

From the repository root:

```bash
python docs/publications/vibe_research/scripts/build_provenance.py
python docs/publications/vibe_research/scripts/validate_provenance.py
```

The builder uses only the Python standard library. Structural processing and output rendering are deterministic. Semantic chunk boundaries, summaries, and topics are reviewed editorial constants in the builder, so regeneration does not call an external model or silently reinterpret the record.

## Suggested Assistant questions

The record supports questions such as:

- Who first proposed framing the paper around an asymmetry between software and research?
- Why did provenance become more central than the question of deserving authorship?
- Why was the ACL argument made more cautious?
- What role did the Casey Newton article play, and what was it not considered evidence for?
- When and why were mathematical examples added?
- Which versions are complete manuscripts and which are partial replacement text?
- What did Manny change in Version 12, and what issues did the AI identify afterward?

A grounded answer should cite exchange IDs and artifact paths, and should distinguish the original conversation from later editorial summaries.
