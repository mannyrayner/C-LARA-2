# First larger AWS picture-description trial and focused fixes

## Human evidence

On 7 October Manny reported a successful AWS redeployment and three initial examples
in an image-only Swedish dictionary copy. Two described examples produced correct
Swedish sentences, word pages and links: *Två flaskor vin.* (två/flaska/vin) and
*En katt tittar på ett schackparti på teve.* (including *tittar på* as an MWE).
Both left an extra unlabelled image card, one named Entry 391. The second sentence's
audio failed after about a minute of page refreshing. These are human reports,
not an instrumented accuracy sample or a new physical-phone acceptance claim.
GitHub main was observed at `06747ea28008a6303b6f0587490f55217186eeea`;
AWS HEAD and the actual provider exception were not independently observed.

## Diagnosis and bounded revision

The apparent duplicate is the retained original image-only Entry, alongside the new
sentence Entry. A dictionary-scoped, before-pagination query now omits a redundant
source from Pictures/Accepted, preserving the original and its provenance/backlink.
Independent contributions, manual word tags, pending requests and undescribed extra
images retain the original card. All/review views remain available. Source visibility
returns if the accepted description disappears. Existing records require no migration.

The reported cat/chess text has 42 characters, below the app's 255-character bound.
Local risk detection matches Swedish `En` as an English spelling and previously
sent the entire sentence through a dictionary-definition/IPA coaching call. This is
an inappropriate sentence path, but it is **not a proven cause of the AWS failure**.
Sentences/feedback now use explicit sentence instructions (native instructions for
French/German/Swedish/Italian, named-language instructions otherwise). Word and MWE
coaching remains unchanged. Sentence requests use a 60-second client timeout;
silence checks and the single completed-silent retry still apply. Manual sentence
audio retries use the same corrected path. No live provider quality claim is made.

The repeated refresh was polling progress, not repeated paid requests. Saved pages
now merge updated audio/status fragments without top-level navigation, preserving
unchanged players, open translations and preview edits. Polling uses authenticated
GETs, stops on error or after three minutes, and does not start synthesis. One-time
navigation from initial interpretation to its preview remains intentional.

New failed capture/manual TTS attempts persist only a bounded error category and
stage, not provider exception messages or private text. Logs include attempt ID,
exception class, stage and category. Existing failed previews still offer explicit
retry without retrospectively inventing their cause. Retry is not automatic billing.

## Verification

- **334 Community Dictionary tests passed** on Linux/Python 3.12/Django 5.2.17,
  including ten new regressions for old source visibility/reappearance, independent
  material, sentence/word/feedback routing, 252-character speech input, quiet retry,
  bounded timeout diagnostics and idempotent manual retry. Providers were mocked;
  no paid API requests or real community data were used.
- Chromium at 390- and 1280-pixel widths: spoken confirmation preserved vocabulary
  edits; saved audio arrived without navigation; an existing looping player remained
  the same DOM element and playing while other clips completed; its translation
  stayed open; new Listen controls worked; a simulated timeout showed its reason
  and retry link; the picture grid omitted the described blank source. No JS errors
  or horizontal overflow. Synthetic fixture images and audio only.
- `makemigrations --check --dry-run`: no changes. Code/document whitespace checks passed (verbatim archived input is excluded).
- No laptop/Windows, AWS or physical-phone acceptance of this fix yet. The first
  browser run reached all audio assertions but had a wrong card CSS selector in
  the rehearsal script; correcting that selector yielded a complete passing run.

Use [the fix runbook](../../docs/howto/community-picture-capture-aws-fixes.md).
The next evidence needed is live sentence listening and continued varied-image use.
Do not reopen broader MWE research on the basis of this bounded repair.
