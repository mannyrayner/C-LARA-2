# Community judging autosave roadmap

## Purpose

Capture a low-risk implementation plan for autosave-on-change in the community judging page so we can schedule delivery after the June 1 Kok Kaper visit.

Related issue: **[ISSUE-0029](../issues/issues/ISSUE-0029.json)**.

## Current behavior and risk

- Community members currently enter judgements on `communities/<community_id>/member/projects/<project_id>/judge/` and then click **Save judgements**.
- If users navigate away before pressing Save, entered values can be lost.
- This is a direct workflow risk for community review sessions, especially when users are moving quickly across many variants.

## Existing implementation baseline

The current server-side view already has a robust persistence path:

- `community_member_judge_project` reads `vote_<variant_id>` and `note_<variant_id>` values and writes via `update_or_create`.
- `CommunityImageVote` uniqueness (`user`, `variant`) supports safe repeated updates for incremental autosaves.
- The template already uses stable per-variant input naming that can be targeted by JavaScript event listeners.

This means autosave can be implemented as an extension rather than a rewrite.

## Recommended implementation shape (post-visit)

### Phase 1: Minimal safe autosave

1. Add a dedicated autosave endpoint for the judging page (member-auth protected).
2. Save one variant at a time using existing `update_or_create` semantics.
3. Add frontend listeners:
   - immediate save on vote (thumbs up/down) change,
   - debounced save on note edits (e.g. 400–800ms).
4. Show clear per-variant status: `Saving…`, `Saved`, `Failed`.
5. Keep existing **Save judgements** submit flow as fallback.

### Phase 2: UX hardening

- Optional unload guard only when pending unsaved requests exist.
- Retry logic for transient network/server errors.
- Lightweight telemetry/logging for autosave failures.

## Open decisions

- Clearing behavior: if vote is cleared, should we delete the row or keep last explicit vote?
- Conflict policy: if two tabs edit the same variant, should latest write silently win (default) or show conflict hint?
- Feedback granularity: per-row status only, or global “all changes saved” indicator too?

## Testing plan

- View tests for autosave endpoint:
  - create vote,
  - update vote,
  - update note,
  - permission checks.
- Template/JS behavior checks for status transitions and debounce behavior.
- Keep legacy form submit tests in place as compatibility/fallback coverage.

## Scheduling note

Given proximity to Sophie’s June 1 Kok Kaper visit, defer implementation until after the visit and use this document as the execution checklist when work starts.

Cross-link back from issue registry: **ISSUE-0029 notes should reference this roadmap document.**
