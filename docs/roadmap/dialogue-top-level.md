# Roadmap: freeform dialogue-based top level

This roadmap proposes an optional **AI dialogue layer** that sits on top of the existing C-LARA-2 UX.

## Goal

Reduce onboarding friction for nontechnical users by allowing them to use the platform through a conversational interface, while still preserving full access to the standard UI.

## Core idea

- Add a two-pane conversational surface:
  - **User input box** for freeform requests/questions.
  - **Platform response box** for explanations, options, and next steps.
- The dialogue agent maps user intents to existing C-LARA-2 features and workflows.
- The system can expose the underlying UI controls and explain them in plain language.

The dialogue layer should **augment** the current UX, not replace it.

## Example interaction

- User: “What can I do?”
- Platform: “You can create and view multimodal learner texts with audio, translations, annotations, and images. I can help you find content or create a new project.”
- User: “Show me a French text.”
- Platform: “Here is an intermediate French text. We currently have multiple French texts; tell me if you want beginner/advanced, different genres, or specific topics.”

## Product requirements

### 1) Intent handling and action planning

- Support broad intents:
  - discover content,
  - start a new project,
  - run annotation/compile steps,
  - manage images,
  - publish/share,
  - ask for explanations/help.
- Convert each intent into explicit action plans using existing backend/view functions.
- Before destructive or expensive actions, require explicit user confirmation.

### 2) Transparent decision-making

For each nontrivial action, the platform should state:

- what it inferred from the user request,
- what defaults/assumptions it selected,
- what alternatives are available,
- how to backtrack or undo.

### 3) Guided UI reveal

- Offer a “show me where this is in the UI” command.
- Highlight corresponding pages/forms and explain field meanings.
- Let users switch between guided dialogue and direct form editing at any step.

### 4) Backtracking and safety

- Keep a dialogue-visible action history.
- Provide one-click rollback for reversible operations.
- Maintain idempotent action wrappers where possible.

### 5) Feedback loop

- Capture explicit feedback signals (“helpful”, “not what I meant”).
- Log intent failures and correction patterns.
- Use this data to tune prompting, policies, and defaults.

### 6) Session memory and lightweight personalization

- Store compact summaries of prior user sessions (with explicit user consent and clear controls).
- Reuse these summaries as context in later sessions to improve relevance and reduce repeated clarification.
- Support per-user memory controls:
  - view/edit/delete stored summaries,
  - disable personalization,
  - reset assistant memory.
- Keep memory payloads concise to control token cost and avoid stale context drift.

## Architecture sketch

### Dialogue orchestrator

- Receives utterances, tracks conversation state, and emits structured intents.
- Calls an action layer that wraps existing platform endpoints/services.

### Action layer

- Thin adapters around current project/content/pipeline/image operations.
- Returns structured status and user-facing summaries.

### Explanation layer

- Translates internal actions into concise, learner-friendly explanations.
- Produces “what happened / what next / alternatives” summaries.

## Initial scope (MVP)

Focus on high-frequency tasks where guidance is most valuable:

1. “What can I do?” onboarding answers.
2. Content discovery and filtering (language, level, genre).
3. New-project creation wizard via dialogue.
4. Compile/publish status checks and next-step guidance.
5. “Show me the UI for this” handoff.

## Current implementation status (April 2026)

The first part of **Phase A (Discovery assistant)** is now implemented in the Django platform:

- Published content discovery supports a **natural-language request** (`nl_query`) plus explicit structured filters.
- The system stores and uses discovery metadata on projects:
  - summary,
  - original-language keywords,
  - English keyword variants for cross-lingual matching,
  - estimated level,
  - word count.
- Search ranking now uses both original and English keywords, which improves cross-lingual queries (for example, searching in English for content whose source text is French/German/Italian).
- The parser now avoids generic title hints (e.g. `"story"`) and prevents broad over-acceptance by excluding zero-score results when semantic constraints are present.
- Dialogue language is user-configurable via profile (`dialogue_language`) and used when interpreting natural-language requests.

This is still read-only discovery behavior (no autonomous write actions), aligned with the intended risk profile of Phase A.

## Phase B progress summary (early personalization + memory)

Initial Phase B capabilities are now in place:

- Per-user profile controls now include:
  - dialogue language selection,
  - a personalization-memory enable/disable toggle,
  - an explicit action to clear stored dialogue memory.
- The system stores a compact cross-session memory payload for discovery conversations
  (for example, recent NL query and interpreted filter plan) when memory is enabled.
- The discovery flow can reuse that compact memory as prior-turn context to improve
  continuity while keeping payload size bounded.

Current limitations (intentional for this first version):

- Memory scope is narrow and discovery-oriented (not full workflow memory yet).
- Adaptive behavior is conservative and transparent-first; no autonomous write operations.
- Memory inspection is basic and should evolve toward richer user-facing controls.

## Sketch plan for Phase C (guided project construction + modification)

Phase C should move from read-only discovery into **guided, confirmation-first project actions**.
The goal is to keep dialogue natural while safely mapping user intent onto existing project UX.

### Proposed interaction sequence

1. **Start new project / return to existing project**
   - Detect intent: create vs continue.
   - If creating, collect and confirm required parameters:
     - project title,
     - text language + annotation language,
     - text source mode:
       - user-supplied source text, or
       - AI-generated text from user description.
   - If resuming, identify the target project explicitly and confirm context.

2. **Invoke AI annotation pipeline**
   - Ask for confirmation before potentially expensive multi-step operations.
   - Explain pipeline stages in plain language when needed.
   - Provide progress/status summaries and expected next actions.

3. **Invoke AI image generation**
   - Confirm intent and scope (whole project vs selected pages/elements).
   - Explain relevant style/options in non-technical language with defaults shown.
   - Surface costs/credits expectations before execution where possible.

4. **Render/compile to HTML and handoff**
   - Run compile/render flow.
   - Explain where output is available (links, project resources, downloadable artifacts).
   - Offer optional “show me where this is in the UI” guidance.

5. **Assist with annotation correction**
   - Dual mode support:
     - guided explanation of manual annotation editor, and/or
     - interpretation of NL editing commands mapped to concrete editor actions.
   - When references are ambiguous, ask targeted clarification questions (page/span/token).

### UX style principles for Phase C

- **Confirmation before action** for expensive/destructive steps.
- **Clarify ambiguity early** with focused follow-up questions.
- **Always show assumptions** and provide easy correction paths.
- **Ground references in project resources** (pages, segments, links, artifacts).

Illustrative prompts:

- Confirmation:
  - “Okay, you want to create a text in English with glosses in French, and I’ll
    generate the text for you based on a short description you give me. Correct?”
- Clarification:
  - “You said the gloss for ‘go away’ is wrong. Could you check the text pane and
    tell me which page this is on?”

### Why this is harder (and worth it)

Compared with content discovery, Phase C requires stronger intent disambiguation,
state tracking, and safe action orchestration across multiple project subsystems.
But it should deliver significantly higher user value by reducing friction in core
create/annotate/image/compile workflows for non-expert users.

## Detailed proposal: Phase C step 2 (“Invoke AI annotation pipeline”)

This section refines the Phase C plan for a user-friendly annotation experience,
with explicit safeguards against confusion and overload.

### Design goals

1. **Avoid dead ends**: users should always see clear next options.
2. **Avoid overload**: default to short, plain-language choices and only expand detail on request.
3. **Keep control visible**: assistant proposes; user approves before meaningful state changes.

### Dialogue strategy (progressive disclosure)

- Start with a brief state summary:
  - “You currently have X, but not Y.”
- Offer 1–2 common next actions (recommended first), not the full pipeline menu.
- Include a simple “show advanced options” escape hatch for power users.
- For each proposed action:
  - state what will happen,
  - state expected output artifact,
  - ask for explicit approval.

### State-aware suggestion matrix (first implementation)

#### Case A — No compiled output yet, no generated plain text

- Suggested default:
  - “Create draft plain text from your initial description.”
- Confirmation prompt:
  - “I can generate a first plain-text draft and show it to you before we continue. Proceed?”
- Alternative:
  - “Skip generation for now and show project setup options.”

#### Case B — Plain text exists, but no segmented/pages representation

- Suggested options:
  1. Segment into pages/segments (recommended),
  2. Render directly to HTML first (faster preview path).
- Confirmation prompt:
  - “Would you like me to split this into pages and segments first, or render a quick HTML preview now?”

#### Case C — Plain text + segmented text exist

- Suggested options:
  1. Continue with page image generation (if user wants visual output),
  2. Render to HTML now (if user wants text-first review).
- Confirmation prompt:
  - “Next step could be creating page images, or rendering HTML immediately. Which do you prefer?”

#### Case D — HTML already exists

- Suggested default:
  - Show/open HTML and switch to revision loop.
- Confirmation prompt:
  - “I can open the latest HTML now. After you review it, I can help apply corrections. Open it?”

### UX copy guidelines for unsophisticated users

- Avoid stage names unless user asks (“segmentation_phase_1”, etc.).
- Prefer plain labels:
  - “split into pages” instead of “segmentation pipeline”,
  - “make web version” instead of “compile HTML”.
- Keep prompts short and concrete:
  - one recommendation,
  - one alternative,
  - one question.

### Safety + confidence policy

- Require confirmation for:
  - AI generation calls,
  - long-running multi-stage operations,
  - operations with likely credit/cost impact.
- If user intent is ambiguous:
  - ask one focused clarification question,
  - do not ask multiple abstract questions at once.

### Proposed first rollout scope

Phase C step 2 can be rolled out in three small increments:

1. **State detection + recommended next step only**  
   (no automatic execution; just guidance + confirmation prompts).
2. **Confirmed execution wrappers for 2–3 common actions**  
   (text generation, segmentation, HTML render).
3. **Revision handoff loop from rendered HTML**  
   (open output + guided correction entry to manual editor paths).

## Explicit operation inventory for dialogue support (first version)

This section lists the underlying C-LARA-2 operations the dialogue layer should
explicitly support in the first implementation pass, with notes on expected UX behavior.

### 1) Create project

- Core operation:
  - Create a new project record.
- Required user inputs:
  - project title,
  - text language,
  - annotation/gloss language,
  - input mode:
    - AI-generated text from user description, or
    - user-supplied source text.
- First-version dialogue behavior:
  - Prompt for missing required fields.
  - Confirm interpreted settings before creation.
  - If AI-generated mode is selected, ask for concise generation brief.
  - If source-text mode is selected, ask user to paste/provide source text.

### 2) Find and open existing project

- Core operation:
  - Search user-visible projects, disambiguate, open target project context.
- First-version dialogue behavior:
  - Resolve references like “my French project from yesterday”.
  - If ambiguous, present top candidates and ask user to choose.
  - Confirm current active project after selection.

### 3) Perform AI-based annotation (AI-supported text languages)

- Core operation:
  - Invoke linguistic annotation pipeline stages for supported languages.
- Dependencies:
  - language support availability and required models.
- First-version dialogue behavior:
  - Explain pipeline in simple terms.
  - Confirm execution before running potentially costly steps.
  - Provide progress updates and post-run summary.

### 4) Perform manual annotation (non-AI-supported text languages)

- Core operation:
  - Route user to manual annotation workflows when AI annotation is unavailable.
- First-version dialogue behavior:
  - Detect unsupported AI language path and switch strategy automatically.
  - Explain why manual path is needed.
  - Offer “show me where in UI” handoff with step-by-step guidance.

### 5) Perform AI-based image generation (image pipeline)

- Core operation:
  - Run image pipeline stages (style/elements/pages generation) per project.
- Reference:
  - `docs/roadmap/linguistic-pipeline.md`.
- First-version dialogue behavior:
  - Confirm scope (full project vs targeted pages/elements).
  - Explain defaults and optional style controls.
  - Surface cost/credit implications before execution where feasible.

### 6) Render to HTML form

- Core operation:
  - Compile/render project outputs to browsable HTML artifacts.
- Reference:
  - `docs/roadmap/linguistic-pipeline.md`.
- First-version dialogue behavior:
  - Trigger render step and summarize status/result.
  - Provide direct guidance on where to open rendered output.

### 7) Manual revision of annotations from user-reported errors

- Core operation:
  - Support correction workflows via manual annotation editor.
- Reference:
  - `docs/roadmap/manual-annotation-editor.md`.
- First-version dialogue behavior:
  - Interpret error reports in natural language and ask clarifying questions
    (page, segment, token, gloss/lemma/POS dimension).
  - Either:
    - guide user through manual UI edits, or
    - translate NL correction intent into explicit editor actions (confirmation-first).

### 8) Community image reviewing (members + organisers)

- Core operation:
  - Support community review workflows for images.
- Reference:
  - `docs/roadmap/low-resource-languages.md`.
- First-version dialogue behavior:
  - Check role/permissions (member vs organiser).
  - Explain available review actions and constraints.
  - Route user to the correct community review UI and summarize outcomes.

### Notes on first-version exposure model

- Keep operation set explicit and bounded (the list above), with unsupported actions
  acknowledged clearly by the assistant.
- Prefer confirmation-first execution for any costly, state-changing, or destructive step.
- Keep transparent mapping from NL request to concrete C-LARA-2 operation names so users
  can correct misunderstandings quickly.
- Treat this inventory as versioned: expand/refine after observing real usage patterns.

## Delivery phases

### Phase A — Discovery assistant

- Read-only conversational help + content discovery.
- No write actions, low risk.

### Phase B — Early personalization and memory

- Introduce compact per-user session summaries to carry context across sessions.
- Add user controls for memory visibility, correction, reset, and opt-out.
- Start lightweight adaptive guidance from observed preferences.

### Phase C — Guided project actions

- Create project and configure core options.
- Confirmed execution of safe operations.
- Use stored preferences to preselect defaults, while always showing assumptions.

### Phase D — Full workflow assistant + iterative tuning

- Support annotation/image/publish operations end-to-end.
- Backtracking controls and richer failure recovery.
- Continue policy/prompt tuning from explicit and implicit feedback.

## Success criteria

- New users can complete first meaningful task with fewer steps and less help from experts.
- Users can understand why the system took an action and how to change it.
- Task completion and satisfaction improve for nontechnical users without reducing expert productivity.
- Users receive increasingly relevant suggestions over time, with transparent and controllable personalization.

## Relationship to other roadmaps

- Complements `docs/roadmap/django-platform.md` as a higher-level interaction layer.
- Supports `docs/roadmap/manual-annotation-editor.md` by making advanced editing workflows discoverable.
- Reinforces low-resource and community goals by lowering entry barriers for broader contributor groups.
