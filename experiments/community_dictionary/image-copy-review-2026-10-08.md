# Image-copy selection and pending-image descriptions — 8 October 2026

## Report

Manny reports the unified Type/Speak/AI feature works, then finds that image-only
copying includes only accepted/shared pictures and leaves them accepted. He wants
Accepted/Awaiting review/Both selection (default Both) and all copies awaiting
review, to rework an existing Swedish dictionary and Cathy's new images.

Inspection confirms the accepted-only copy query and status assignment. However,
Accepted itself did not block AI descriptions: the old capture policy required an
accepted source and an enabled Picture descriptions setting. This follow-up changes
the copy behaviour and adds explicit editor approval during description, rather
than making pending copies unusable. AI settings continue to be inherited, with a
notice when the source has Picture descriptions off.

## Implementation and checks

- Status selection, deduplication, exclusion of unavailable material, pending copies
  and landing on Awaiting review; original source review states remain unchanged.
- Owner/editor-only pending-image description, common three-mode preview, atomic
  picture approval plus sentence publication, role-aware next-picture navigation.
- Failed/discarded previews leave pictures pending. Checks before/after provider
  calls and at confirmation block rejected sources, role loss and withdrawal.
- Existing attribution and withdrawal/restore chains preserved across dictionaries;
  copying itself never sends data to AI.
- 376 Django app tests pass, including 11 focused copy/review regressions. Existing
  copy/visibility assertions updated for the deliberately changed pending status.
- `manage.py check` has no issues; `makemigrations --check --dry-run` finds no changes.
- Mocked-provider Chromium rehearsal at 390/1280px: Both default and per-status
  counts; two pending copied images; AI preview leaves both pending; confirmation
  saves one sentence and accepts its copy; Next picture offers the other pending
  image; the original dictionary retains one accepted and one pending image.
  No horizontal overflow or JavaScript errors observed.

No real provider calls, new human listening evidence, physical-phone trial or AWS
deployment was performed by the assistant. Source content was synthetic and the
browser used an isolated SQLite database. The prior AI-description update has
human acceptance; this follow-up awaits Manny's experiment. WordPress/email reset
and broader MWE work remain deferred.

See [workflow](../../docs/howto/community-image-copy-review.md) and
[installation](../../docs/howto/community-image-copy-review-install.md).
