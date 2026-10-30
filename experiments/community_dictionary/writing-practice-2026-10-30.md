# Writing-practice increment, 30 October 2026

Manny reports a concrete learner request: privately write a target-language
description of a saved picture, receive corrections with explanations, approve
the wording, then delegate the remaining resource generation. The agreed design
preserves learner intention, separates necessary corrections from optional style,
keeps feedback private, and uses a personal dictionary preference. A second
learner's beginner Icelandic needs remain a parallel design question, not an
evaluated outcome of this change.

Implementation: `writing_ai.py` supplies bounded structured feedback;
`writing.py`/`writing_views.py` implement private drafts, approval and background
continuation using existing PictureCapture storage. The existing capture
publisher, word linking, TTS and billing are reused. Published provenance omits
the private original and explanations and does not claim vocabulary was reviewed.
English, French and Slovak UI text is included. No database migration or new
dependency is needed. The preference is per dictionary and current login.

Validation: 749 Community Dictionaries tests pass on the local Linux/SQLite
checkout, including 21 writing-practice tests. A 68-test focused run covering
writing, settings, discovery and allowances also passed. The first full run
exposed one old test expecting all member Settings access to be denied; it now
checks the personal page and continued denial of owner configuration changes.
After tightening rollback privacy (the common description field contains only approved text),
the 21 writing tests passed again. A missing-photo AJAX error is also covered.
Django system checks and migration-drift checks pass. French/Slovak catalogs
compile with msgfmt checks; the new JavaScript passes node syntax checking.
The global-workspace renderer and code-only deployment path check pass.

No live provider requests or dictionary changes are part of the automated tests.
Phone/browser interaction has not been rehearsed in this environment: Playwright
is installed but its browser executable is unavailable. Server-rendered pages and
routing are covered by the Django client tests; physical-phone testing is pending.
Learner judgments, physical-phone usability and live feedback quality remain
pending until Manny and the learner test the increment.

## Earlier deployment milestone now accepted

The Tools release `48ad6c3866ba7e633a3f91da3a44a85c1c3cc50f` completed both
supervised workflows using control commit
`8ccb2e1306444c5aa080d7a2981dd537dda92adc`:

- Laptop run `41034724689`: 17 successful controller steps; Manny accepted Tools.
- AWS run `41035557064`: 21 successful steps, exact same app commit, prior commit
  `db1557ce1ae4f19245624a48a04d7aafb8c857cb`; receipt references laptop run
  `41034724689` and SSM command `17550189-1093-43d1-a41f-c271c6993b2d`.
- Manny subsequently refreshed AWS and confirmed the new version was present.

This is evidence for one changed-release deployment with human acceptance, not
for autonomous functional testing, AWS staging or long-run maintenance.
The application CI job passed; a separate Windows controller CI checkout failed
on an existing overlong archive path before executing tests. That CI issue and
safe provider-error reporting in the cloud controller remain separate follow-ups.
