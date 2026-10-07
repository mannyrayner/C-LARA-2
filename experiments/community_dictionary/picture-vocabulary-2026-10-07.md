# Picture-description vocabulary follow-up — 7 October 2026

## Human evidence

Manny reports nearly everything working on the laptop, a much faster/more intuitive
workflow and a more useful dictionary. His concrete counterexample is “Katten
sträcker ut sig på soffan”: the first cut suggests sträcka and ut separately. He
requests MWE reuse, editable vocabulary and an image-only test-copy utility before
larger AWS trials. This is positive human evidence with a specific linguistic defect;
it is not acceptance of this follow-up or new AWS/phone evidence.

## Implemented

- Adapt C-LARA's language-specific/default MWE templates and up to four compact
  examples into the existing image/description request. No separate MWE API call;
  no claim of running the full segmented-text annotation pipeline. Require lexical
  expressions as units; support ordered discontinuous surface spans with ellipsis.
- Allow editing/removing/adding suggested vocabulary before confirmation (up to 12).
  Preserve original proposals and confirmed vocabulary in provenance. Reuse by local
  lemma/sense, never a browser-supplied entry ID. Whole-expression links/audio;
  validation errors preserve the form, and retries do not republish. Spoken feedback
  cannot reload away edits. Unsaved edits get the browser's navigation warning.
- Owner-only Settings image copy: shared accepted images only, no text/audio/member
  copies; duplicates along the same original-image lineage are collapsed. Original
  author/custodian/source links retained. Shared file references stay private. Same
  lock order as withdrawal; no provider calls; idempotent receipt and atomic rollback
  if a file is missing. Source withdrawal/restoration follows through copied images
  and subsequently derived sentences.
- No migration or dependency addition. Static asset versions bumped.

## Local verification

- Django 5.2.17 / Python 3.12 Linux: **324 app tests pass** (310 previous +14 new).
- `manage.py check`: clean; `makemigrations --check --dry-run`: no changes.
- New tests exercise contiguous/discontinuous expression alignment, whole-expression
  speech requests, edit/add/remove/all-remove, validation, 12-item audio completion,
  no-JavaScript add, local reuse/foreign-ID rejection, copy permissions/CSRF/receipts,
  omission of archived/pending content, missing-file rollback and withdrawal/restore
  through copied images into newly derived sentences.
- Real Django + Chromium, simulated providers, 390px and 1280px: expand vocabulary,
  edit expression and meaning, add/reuse/remove rows, preserve edits when delayed
  voice feedback arrives, publish/playable audio controls, Settings copy and new
  image-only dictionary. No JS errors or horizontal overflow. Screenshots inspected.
- A repeat browser-fixture seed encountered a transient SQLite read-only error in
  the disposable local rehearsal database; rerunning the isolated rehearsal passed.
  It was not a user database or application migration failure.

No paid provider requests, AWS deployment, physical-phone checks or independent
MWE/translation/TTS quality measurement were performed. Next: Manny's fresh Finley
capture and vocabulary/copy trial, then combined release and larger AWS trial.

## Subsequent laptop acceptance and release decision

On 7 October, Manny reports: “It all works on the small Swedish laptop dictionary”.
He requests check-in and AWS redeployment for a more thorough, larger-image trial.
He expects further MWE work but explicitly defers it until after assessing the new
Community Dictionaries functionality. This updates laptop acceptance; it does not
supply a linguistic accuracy measure, enumerated per-action assertions, an AWS
release SHA or physical-phone results for this increment.

A documentation-only release patch adds the
[combined check-in/AWS runbook](../../docs/howto/community-picture-descriptions-aws.md).
Runtime code and the previously reported 324-test result are unchanged. AWS is
expected to move from 0014 to 0015; the vocabulary follow-up needs no later migration.
The runbook retains PostgreSQL 18 tools, restricted backup permissions only inside
a subshell, scoped database/private-media backup, static collection and web/Q restart.
