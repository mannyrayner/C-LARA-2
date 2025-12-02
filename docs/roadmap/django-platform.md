# Django platform specification (C-LARA-2)

This document sketches the Django layer that will host users, projects, and compiled content. It is a peer to `linguistic-pipeline.md` and focuses on the web app that orchestrates pipeline runs, manual edits, sharing, and publishing.

## Current status (initial implementation)

- A minimal Django project lives under `platform_server/` with registration/login/logout, project creation, compile-to-HTML, publish toggle, and gated viewing of compiled artifacts. It uses the existing pipeline to run segmentation→HTML and stores outputs under `media/projects/<user>/<project>/run_<timestamp>/`.
- The UI is currently the “advanced” workspace aimed at technical users; the minimal guided UI (chat-first create/edit/access) will layer on top without breaking the existing flows.
- Next iterations: collaborator roles, background job handling for long pipelines, published content browsing, rating/commenting, and cost/credit tracking hooks.
- How to run it locally: see [howto/run-django-platform.md](../howto/run-django-platform.md) for a one-line dev server command and manual steps.

## Goals

- Provide an authenticated multi-user platform for creating, editing, and publishing annotated texts.
- Keep projects aligned with the pipeline outputs while allowing manual edits and versioning.
- Offer clear artifacts for auditing: source uploads, intermediate JSON, compiled HTML/audio, logs.
- Make permissions explicit so projects can be shared, published, or kept private.

## Core concepts

### Users
- Standard Django user model plus profile (display name, affiliation, avatar, preferred languages).
- Roles/flags: admin, staff/moderator, regular user. Use Django permissions for fine-grained access (e.g., can_review_projects, can_publish_public).
- Activity log per user: project actions, publishes, comments/ratings given.

### Projects
- Owned by a single user; can invite collaborators with role-based permissions (owner/editor/viewer).
- Stores:
  - **Source inputs**: raw text uploads (UTF-8), optional project description, optional seeded segmentation/annotation JSON.
  - **Pipeline outputs**: JSON per stage (segmentation, translation, MWE, lemma, gloss, pinyin, audio metadata), compiled HTML bundles, audio/image assets, logs.
  - **Manual edits**: captured as patches/diffs against the latest pipeline JSON for reproducibility.
  - **Metadata**: languages (L1/L2), title, summary, tags, last pipeline run info, access level, publish status.
- Versions: immutable checkpoints per pipeline run or manual edit session. Each version records: created_by, created_at, input refs, stage range, artifacts paths, and a human-readable note.

### Content visibility and sharing
- Access levels: private (owner/collaborators), shared (invitees), organization/group, public.
- Publication: selecting a version to publish creates a public artifact set (HTML/audio) under a stable URL; metadata (title, tags, description) is exposed for discovery.
- Ratings/comments: tied to published versions; moderation flags and abuse reports feed into staff workflows.

## Data model sketch (Django models)
- `Project`: owner FK, title, summary, l1, l2, tags, visibility enum, status, timestamps.
- `ProjectCollaborator`: user FK, project FK, role enum (editor/viewer), invitation + acceptance timestamps.
- `ProjectVersion`: project FK, created_by FK, stage_start, stage_end, note, artifact_root, publish_state, created_at.
- `PipelineArtifact`: version FK, stage enum, path (relative to project storage), checksum/size, created_at.
- `ManualEdit`: version FK, stage enum, diff blob (JSON patch), created_by, created_at.
- `PublishedEntry`: project FK, version FK, slug, is_public, published_at, last_view_count, rating_summary.
- `Comment`/`Rating`: user FK, published FK, body/score, timestamps, moderation flags.
- `AuditLog`: user FK, project FK, action enum, payload (JSON), created_at.

## Storage layout
```
media/
  users/<user_id>/projects/<project_slug>/
    source/                 # uploaded texts, descriptions
    runs/<timestamp>/       # per-pipeline-run artifacts
      input/                # normalized input JSON for the run
      stage_<name>/         # JSON outputs per stage
      audio/                # TTS assets (token/segment/page) copied per run
      html/                 # compiled multi-page HTML + static assets (page_*.html + concordance_*.html + static/)
      logs/                 # telemetry + pipeline logs
    manual_edits/           # patches keyed by version
    published/<version_id>/ # frozen artifacts for public serving
```
- Media backed by Django `FileField` storage; default to local filesystem in dev, S3/GCS/Azure in production.
- Checksums recorded per artifact to detect drift and support caching.
- Paths exposed in the UI should be **POSIX-style relative to `runs/<timestamp>/`** so HTML/audio links remain valid when served
  from Django or opened directly from disk during reviews. When copying audio into a run, the compiler rewrites `data-audio`
  attributes to `audio/<hash>.wav` to avoid leaking absolute paths.

## Pipeline orchestration (Django layer)
- A `PipelineService` (Django service module) wraps `run_full_pipeline` with:
  - Stage range selection (start/end) to support partial reruns (e.g., redo glosses only).
  - Idempotent logging: store input spec, outputs, and telemetry per run.
  - Background execution via Celery/RQ for long-running jobs; progress updates push to WebSocket/SSE for UI.
  - Error handling: mark run as failed with traceback and partial artifacts for debugging.
  - Progress visibility: emit ordered start/done events per stage (with timestamps) and optionally persist `stages/<name>.json`
    snapshots so the UI can show “in progress” updates and links as soon as a stage finishes.
  - Start-stage selection: the UI passes an explicit `start_stage` (description → text_gen vs. provided source → segmentation
    phase 1); intermediate artifacts from later stages are cleared when rerunning from an earlier stage.
- Manual edit flow: users can open the latest JSON at a stage, apply edits via UI, save as a new `ProjectVersion` with a `ManualEdit` entry, and re-run downstream stages.
- Import/export: allow uploading existing C-LARA projects (ZIP containing JSON/HTML/audio) into a project; export any version as ZIP for offline review.

## UI flows (high level)
- **Minimal, guided UI (non-technical users)**:
  - Landing dialog to **create a project** with AI-guided questions (title, L1/L2, short description). Defaults select a safe pipeline preset and storage layout; advanced fields stay hidden until expanded.
  - **Modify existing project** via an AI-backed chat that can launch common actions (rerun pipeline, regenerate audio, toggle visibility, trigger publish) and offers links to manual forms for overrides.
  - **Access posted content** from a simple library view listing published projects; respects permissions and opens the compiled HTML viewer. Non-essential controls remain tucked behind an “Options” menu.
  - The minimal UI coexists with the full workspace; users can switch to the advanced view without losing state.
- **Dashboard**: list projects with status badges (draft, running, failed, published), quick actions (resume/edit/publish/view), and search/filter by tag/language.
  - **Project workspace**:
    - Source tab: upload/edit raw text and metadata; start pipeline runs with stage selection and target languages.
    - Compile tab: choose start stage (description → text_gen or supplied source → segmentation_phase_1 by default), kick off the
      pipeline, and show live status messages for each stage. Intermediate artifacts and compiled HTML links appear as soon as
      they are written.
    - Versions tab: chronological list of versions with stage coverage, notes, artifacts links, and diff view between versions.
    - Annotations tab: read-only view of JSON per stage with download buttons.
    - Manual edit tab: UI to edit JSON (segmentation or later stages) with validation and change previews.
    - Publish tab: select a version to publish, set visibility, manage slug, view published URL, and preview compiled HTML.
- **Viewer**: public-facing page to read compiled HTML, play audio, and see concordance; shows translation toggles, gloss popups, MWE highlights; includes rating/comment widgets if enabled.
- **Admin/moderation**: manage users, handle abuse reports, remove content, view audit logs.

## Permissions and safety
- Enforce per-project permissions across views and APIs; download endpoints honor visibility.
- Rate limiting for pipeline runs and TTS to avoid quota exhaustion; per-user quotas configurable.
- Sanitization: escape user-generated content in comments/titles; validate uploaded text encoding; restrict HTML in manual edits.

## Testing strategy
- Unit tests for models, services, and permission checks.
- Integration tests for pipeline orchestration (mocking Celery) to ensure artifacts are stored and versions recorded.
- End-to-end tests for publishing flow: create project → run partial pipeline → manual edit → publish → fetch public page.
- Fixture projects for regression testing (small EN/FR; small ZH with pinyin/audio; MWE-heavy sample).

## Open questions / TODO
- Decide on rich-text versus plain-text editor for manual annotation edits.
- Determine default quotas (runs/day, max text size, max audio minutes) and where to surface warnings.
- Select search technology for public content (e.g., Postgres full-text vs. external search service).
- Define notification strategy (email/WebSocket) for run completion, comments, and collaborator invites.
