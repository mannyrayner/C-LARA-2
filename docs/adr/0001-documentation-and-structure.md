# ADR-0001: Documentation & Structure

**Status**: Accepted  
**Date**: 2025-11-14

## Context
We want docs that are:
- Easy to edit in GitHub (web UI or local editor)
- Cross-linkable with relative links
- Ready to grow into MkDocs later

## Decision
- Use a simple `docs/` tree with subfolders:
  - `howto/` – task-oriented guides
  - `adr/` – architecture decisions (ADR-0001, ADR-0002, …)
  - `_generated/` – AI-generated notes/summaries (clearly labeled)
- Use **relative links** exclusively so navigation works in GitHub and MkDocs.

## Consequences
- Low friction: anyone can edit a page online.
- Easy to expand to MkDocs (optional) without breaking links.

---

- Back to [Docs Home](../README.md)
- See [Quickstart](../howto/quickstart.md)