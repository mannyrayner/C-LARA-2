# Social-network functionality roadmap

This document defines the next roadmap slice for social/community features in C-LARA-2.

## Current baseline (already implemented)

The platform now has a first, usable social layer:

1. **Publishing**: project owners can publish a project.
2. **Content browsing**: authenticated users can open the **Content** tab and search published content.
3. **Content home page**: each published item has a metadata page including access count and link to compiled page 1.

These features provide the base for community interaction and moderation.

## Goals for next iterations

- Enable meaningful user interaction around published content (comments/ratings).
- Enable multi-user project collaboration with explicit roles.
- Enable language-centered communities and organizer workflows.
- Connect social feedback loops to image quality control and regeneration.
- Improve published-content access/presentation controls, including anonymous access policy and context-aware navigation (ISSUE-0031).

---

## 1) Comments and ratings on published content

### Scope
- Add comments to published content pages.
- Add simple ratings (initially thumbs-up/thumbs-down; optional text comment attached).
- Show aggregate rating summary on content pages and listing pages.

### Data model sketch
- `ContentComment`:
  - `published_project` FK,
  - `author` FK,
  - `body`,
  - timestamps,
  - moderation flags (hidden/removed/reported).
- `ContentRating`:
  - `published_project` FK,
  - `author` FK,
  - `value` enum (`up`, `down`),
  - optional short comment,
  - timestamps.
- Unique constraint on `(published_project, author)` for ratings to prevent duplicates; allow updates.

### UX sketch
- On content page:
  - rating controls,
  - comment composer,
  - comment thread (paged).
- On content list:
  - show rating summary and comment count.

### Moderation
- Report comment/rating.
- Organizer/admin moderation queue.
- Soft-delete strategy for auditability.

---

## 1b) Published-content access controls and navigation context (ISSUE-0031)

### Problem statement

Current compiled-page presentation and access behavior is oriented toward the project workspace context. Two gaps called out in ISSUE-0031:

1. Navigation labels/links can be misleading when the same compiled artifact is opened from content discovery views rather than from a project page (for example, showing “Back to project” in a public/content-browsing context).
2. Access policy needs to support publisher-managed visibility levels, including optional anonymous/public access, with a safe way to change/reset policy after publication.

### Proposed access policy model

Use explicit publication visibility states on the published artifact entry (not only project ownership):

- `private`: owner/collaborators only.
- `community`: limited to members of assigned community.
- `platform_users`: any authenticated C-LARA-2 user.
- `public_anonymous`: accessible without login.

Notes:
- Keep project editing permissions separate from published-reading permissions.
- Require explicit publisher confirmation when switching to `public_anonymous`.
- Record every visibility change in audit history (who, when, from, to, optional reason).

### Context-aware navigation strategy

Treat compiled pages as reusable artifacts with a lightweight “entry context”:

- `from_project`
- `from_content`
- `direct_public` (no authenticated context)

For each context, render different top navigation affordances:

- `from_project` → “Back to project”.
- `from_content` → “Back to content”.
- `direct_public` → neutral home/discovery links without project-internal affordances.

Implementation options (can be combined):
- signed query parameter carrying entry context,
- session-based last-entry marker,
- dedicated route wrappers per context (cleanest for templates/permissions).

### Security and safety requirements

- Never trust client-only context flags for authorization decisions.
- Evaluate visibility permissions server-side before rendering content.
- Ensure direct URL access checks visibility policy and user/session identity consistently.
- Add explicit tests for permission transitions (private → public, public → private, community → public, etc.).

### UX and governance requirements

- Publisher-facing control panel on content metadata page:
  - current visibility,
  - change visibility action,
  - warning copy for anonymous/public mode,
  - “last changed by/at” audit metadata.
- Optional cool-down or second confirmation before making high-visibility transitions.
- Clear viewer-facing indicators of visibility level and ownership/moderation policy.

### Suggested delivery plan for ISSUE-0031

1. Add visibility state model + server-side enforcement + tests.
2. Add publisher controls and audit log for visibility transitions.
3. Add context-aware navigation labels/routes for compiled pages.
4. Add regression tests covering:
   - navigation label correctness by entry context,
   - anonymous vs authenticated access boundaries,
   - visibility change correctness and rollback behavior.

---

## 2) Multi-user project association and roles

### Role model
- `OWNER`: full control (same as original owner).
- `ANNOTATOR`: run annotation operations and edit annotation content.
- `VIEWER`: read-only access to project artifacts and metadata.

### Collaboration model
- Project has one canonical creator, but may have multiple `OWNER` users.
- Creator/owner can invite users and assign role.
- Role changes are audited.

### Permission matrix (first cut)
- Pipeline runs:
  - OWNER ✅
  - ANNOTATOR ✅
  - VIEWER ❌
- Project settings (publish/delete/share):
  - OWNER ✅
  - ANNOTATOR ❌
  - VIEWER ❌
- View artifacts and compiled output:
  - OWNER ✅
  - ANNOTATOR ✅
  - VIEWER ✅

---

## 3) Language-centered communities

### Concept
- Admin can grant **community organizer** status.
- Organizer can assign **community member** status to users.
- Organizer who is also a project owner can assign project to a community.

### Community entities
- `Community` (language-centric):
  - name,
  - focus language(s),
  - description,
  - organizer set.
- `CommunityMembership`:
  - user,
  - community,
  - status/role.
- `ProjectCommunityAssignment`:
  - project,
  - community,
  - assigned_by,
  - assigned_at.

### UX
- Community pages for browsing assigned projects and recent activity.
- Community filter in content browsing.

---

## 4) Community rating loop for generated images

### Problem
Generated images vary in quality. Community feedback can improve project outputs over time.

### Proposed flow
1. Allow generation of multiple variants for selected project images.
2. Provide a community review page with variant sets.
3. Members provide thumbs-up/down (+ optional comment).
4. Organizer/owner reviews low-rated variants and triggers regeneration.
5. Regeneration can use either:
   - automatic prompt adaptation from comments, or
   - manually written summary feedback.

### Data model sketch
- `ImageVariantBatch` (project/page/element scoped).
- `ImageVariant` (image path + prompt metadata).
- `ImageVariantRating` (member vote + optional comment).
- `ImageRegenerationAction` (who regenerated, why, strategy).

### Governance
- Eligibility to vote: community members only.
- Optional confidence threshold before replacement decisions.

---

## Incremental delivery plan

1. Comments + thumbs ratings on content pages.
2. Collaboration roles for projects (OWNER/ANNOTATOR/VIEWER).
3. Community entities and assignment flow.
4. Image-variant community rating + regeneration loop.

Each step should include:
- migrations,
- permissions tests,
- end-to-end UI tests,
- audit logging hooks.
