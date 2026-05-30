# Roadmap: platform self-knowledge assistant

Tracked by [ISSUE-0034](../issues/issues/ISSUE-0034.json).

## Goal

Add a read-only conversational assistant that lets users ask C-LARA-2 about its own functionality, workflows, issue registry, roadmap documents, and implementation status.

The intended first version is a support and orientation tool: it should answer questions such as “How do I create a picture dictionary?”, “What is the status of legacy C-LARA migration?”, or “Which issue tracks community audio recording?” using repository and platform documentation context.

## Why this matters

C-LARA-2 is intentionally developed with extensive repository-native documentation so AI tools can understand and help maintain the platform. Exposing a carefully bounded version of that capability inside the platform could:

- reduce onboarding friction for teachers, organisers, and developers;
- make roadmap/issue knowledge easier to discover than browsing Markdown and JSON files manually;
- help users connect UI features to documentation, known issues, and recommended workflows;
- provide a practical test of whether the documentation is sufficiently coherent for AI-mediated explanation.

## Relationship to existing dialogue work

This roadmap is related to, but narrower than, [the freeform dialogue-based top-level roadmap](dialogue-top-level.md).

- The dialogue top level is about operating C-LARA-2 workflows through conversation.
- The self-knowledge assistant is initially about answering questions about C-LARA-2 itself.
- The first implementation should be read-only and should not trigger project mutations, expensive AI runs, admin actions, or repository changes.

A later phase can decide whether the two surfaces should merge or share a common dialogue/orchestration layer.

## Initial design sketch

### Context source

The assistant should ground answers in controlled C-LARA-2 context, for example:

- `docs/roadmap/` roadmap documents;
- `docs/issues/overview.md` and `docs/issues/issues/*.json`;
- selected user-facing help or how-to pages once available;
- small, curated code references for feature-location questions where needed.

The implementation should prefer explicit source citation or source links in answers so users can inspect the underlying documentation.

### Model/API route

The human suggestion proposes wrapping user input in a platform-specific prompt and sending it to a Codex-class model connected to the C-LARA-2 repo. Before implementation, confirm the supported API route for repo-aware model context and whether the production platform can safely provide repository context through:

1. a retrieval/indexing layer over checked-in documentation;
2. a prebuilt repository documentation bundle;
3. a hosted assistant/vector-store style setup;
4. a direct repo-aware tool integration, if available and appropriate.

The first prototype should be conservative: use a bounded documentation/context bundle rather than granting broad repository or shell access from the web application.

### User interface

Possible MVP surface:

- authenticated page linked from Help/Admin or the main dashboard;
- single question box and conversational answer area;
- optional category hints such as “using the platform”, “roadmap/issues”, “developer documentation”; 
- answer footer listing source documents consulted;
- feedback buttons for “helpful”, “not enough detail”, and “incorrect/outdated”.

### Safety and governance

The assistant must not expose secrets, private user data, server paths, credentials, or raw logs. It should not run code or mutate repository/platform state from user prompts.

Required controls before broad rollout:

- strict allowlist for documentation/context files;
- prompt-injection guidance for quoted documentation and user inputs;
- rate limiting and cost accounting through the existing credits/billing framework where appropriate;
- clear disclaimers when answers are based on stale checked-in documentation;
- admin-visible logs for failed/low-confidence answers, excluding sensitive user content where possible.

## Phased plan

### Phase A: planning and context inventory

- Decide which documentation files are safe and useful in the initial context set.
- Define the answer style, citation format, and confidence/fallback behavior.
- Confirm current OpenAI/Codex API capabilities for repo-aware or retrieval-backed answering.
- Identify whether this belongs in a new help view, the admin issue browser, or a shared dialogue shell.

### Phase B: read-only prototype

- Build a minimal authenticated question-answering view.
- Ground answers in `docs/roadmap/` and `docs/issues/` only.
- Return source links with each answer.
- Log token/cost data and user feedback.

### Phase C: platform help integration

- Add links from relevant UI pages to ask context-specific questions.
- Include curated how-to/help documents as they are created.
- Add regression tests for access control, prompt construction, and source allowlisting.

### Phase D: possible convergence with dialogue top level

- Evaluate whether self-knowledge answers should become one intent of the broader dialogue top level.
- Consider limited action suggestions, still requiring explicit user confirmation and never bypassing existing permission checks.

## Open questions

- Which current OpenAI API surface is the best fit for repo-grounded answers from a production Django app?
- How often should documentation context be refreshed after deployment?
- Should non-admin users be able to ask about issue/roadmap status, or should some answers be limited to staff?
- How should incorrect answers be reported back into the human suggestion loop?
